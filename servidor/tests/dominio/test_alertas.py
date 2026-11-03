from datetime import timedelta

from greensense.dominio.alertas import (
    Cambio,
    Condicion,
    EstadoCondicion,
    Severidad,
    TipoAlerta,
    aplicar_condicion,
)
from greensense.dominio.modelos import Variable
from tests.fabricas import AHORA

NORMAL = Condicion(EstadoCondicion.NORMAL)
CERCA = Condicion(EstadoCondicion.CERCA, "cerca", "ventilar", 27.0, 28.0)
FUERA = Condicion(EstadoCondicion.FUERA, "alta", "ventilar", 29.0, 28.0, tiempo_minimo_s=300)


def aplicar(activa, condicion, minutos=0):
    return aplicar_condicion(
        activa,
        condicion,
        "nodo1",
        TipoAlerta.UMBRAL,
        Variable.TEMPERATURA,
        AHORA + timedelta(minutes=minutos),
    )


def test_normal_sin_alerta_no_hace_nada():
    assert aplicar(None, NORMAL) is None


def test_cerca_del_limite_abre_advertencia():
    t = aplicar(None, CERCA)

    assert t.cambio is Cambio.CREADA
    assert t.alerta.severidad is Severidad.ADVERTENCIA
    assert t.alerta.fuera_desde is None
    assert not t.notificar


def test_fuera_de_rango_empieza_como_advertencia():
    t = aplicar(None, FUERA)

    assert t.alerta.severidad is Severidad.ADVERTENCIA
    assert t.alerta.fuera_desde == AHORA
    assert not t.notificar


def test_pasa_a_critica_al_cumplir_el_tiempo_minimo():
    alerta = aplicar(None, FUERA).alerta
    alerta = aplicar(alerta, FUERA, minutos=4).alerta
    assert alerta.severidad is Severidad.ADVERTENCIA

    t = aplicar(alerta, FUERA, minutos=5)

    assert t.cambio is Cambio.ESCALADA
    assert t.alerta.severidad is Severidad.CRITICA
    assert t.alerta.escalada_en == AHORA + timedelta(minutes=5)
    assert t.notificar


def test_una_lectura_aislada_fuera_no_escala():
    alerta = aplicar(None, FUERA).alerta
    alerta = aplicar(alerta, CERCA, minutos=3).alerta
    assert alerta.fuera_desde is None

    t = aplicar(alerta, FUERA, minutos=6)

    assert t.alerta.severidad is Severidad.ADVERTENCIA
    assert t.alerta.fuera_desde == AHORA + timedelta(minutes=6)


def test_sin_tiempo_minimo_es_critica_de_inmediato():
    inmediata = Condicion(EstadoCondicion.FUERA, "x", "y", 1.0, 2.0, tiempo_minimo_s=0)

    t = aplicar(None, inmediata)

    assert t.alerta.severidad is Severidad.CRITICA
    assert t.notificar


def test_critica_no_se_vuelve_a_notificar():
    alerta = aplicar(aplicar(None, FUERA).alerta, FUERA, minutos=5).alerta

    t = aplicar(alerta, FUERA, minutos=6)

    assert t.cambio is Cambio.ACTUALIZADA
    assert not t.notificar


def test_critica_se_mantiene_cerca_del_limite_y_se_resuelve_en_normal():
    critica = aplicar(aplicar(None, FUERA).alerta, FUERA, minutos=5).alerta

    cerca = aplicar(critica, CERCA, minutos=6).alerta
    assert cerca.severidad is Severidad.CRITICA
    assert cerca.activa

    t = aplicar(cerca, NORMAL, minutos=7)
    assert t.cambio is Cambio.RESUELTA
    assert t.alerta.resuelta_en == AHORA + timedelta(minutes=7)
    assert not t.alerta.activa


def test_actualiza_valor_y_mensaje():
    alerta = aplicar(None, CERCA).alerta

    t = aplicar(alerta, FUERA, minutos=1)

    assert (t.alerta.valor, t.alerta.mensaje) == (29.0, "alta")
    assert t.alerta.iniciada_en == AHORA


EN_HOLGURA = Condicion(EstadoCondicion.NORMAL, valor=25.5, en_holgura=True)


def test_en_la_holgura_no_abre_ni_resuelve():
    assert aplicar(None, EN_HOLGURA) is None

    advertencia = aplicar(None, CERCA).alerta
    assert aplicar(advertencia, EN_HOLGURA, minutos=1) is None


def test_ruido_en_el_borde_del_margen_no_abre_una_alerta_por_lectura():
    alerta = aplicar(None, CERCA).alerta
    for minuto in range(1, 30):
        condicion = CERCA if minuto % 2 else EN_HOLGURA
        t = aplicar(alerta, condicion, minutos=minuto)
        alerta = t.alerta if t else alerta
        assert alerta.activa

    assert alerta.iniciada_en == AHORA


def test_en_la_holgura_deja_de_contar_tiempo_fuera():
    alerta = aplicar(None, FUERA).alerta

    t = aplicar(alerta, EN_HOLGURA, minutos=3)
    assert t.cambio is Cambio.ACTUALIZADA
    assert t.alerta.fuera_desde is None

    # Vuelve a salir: el tiempo mínimo se cuenta otra vez desde cero.
    alerta = aplicar(t.alerta, FUERA, minutos=4).alerta
    assert aplicar(alerta, FUERA, minutos=8).alerta.severidad is Severidad.ADVERTENCIA
    assert aplicar(alerta, FUERA, minutos=9).cambio is Cambio.ESCALADA
