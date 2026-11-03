from dataclasses import replace
from datetime import timedelta

import pytest

from greensense.aplicacion.casos_uso.notificaciones import ProgramarNotificacion
from greensense.aplicacion.casos_uso.revisar_nodos import RevisarNodos
from greensense.dominio.alertas import Severidad, TipoAlerta
from greensense.dominio.modelos import EstadoNodo
from greensense.dominio.notificaciones import SuscripcionPush
from tests.fabricas import AHORA, crear_nodo

pytestmark = pytest.mark.anyio


@pytest.fixture
async def revisar(nodos, alertas, suscripciones, usuarios, envios, despertador, eventos, reloj):
    await suscripciones.guardar(SuscripcionPush("https://push/1", "k", "a", AHORA, 1))
    programar = ProgramarNotificacion(suscripciones, usuarios, envios, despertador, reloj)
    return RevisarNodos(nodos, alertas, programar, eventos, reloj)


async def _nodo_con_ultima_lectura(nodos, hace_min: float, **cambios):
    nodo = crear_nodo(
        estado=EstadoNodo.CONECTADO,
        ultima_lectura_en=AHORA - timedelta(minutes=hace_min),
        **cambios,
    )
    await nodos.guardar(nodo)
    return nodo


async def test_nodo_al_dia_no_genera_alerta(revisar, nodos, alertas):
    await _nodo_con_ultima_lectura(nodos, hace_min=4)

    assert await revisar.ejecutar() == []
    assert (await nodos.obtener("nodo1")).estado is EstadoNodo.CONECTADO


async def test_nodo_sin_lecturas_por_5_min_queda_desconectado(
    revisar, nodos, alertas, envios, eventos
):
    await _nodo_con_ultima_lectura(nodos, hace_min=7)

    (alerta,) = await revisar.ejecutar()

    assert alerta.tipo is TipoAlerta.DESCONEXION
    assert alerta.severidad is Severidad.CRITICA
    assert alerta.mensaje == "El nodo lleva más de 5 min sin enviar lecturas"
    assert alerta.fuera_desde == AHORA - timedelta(minutes=7)
    assert (await nodos.obtener("nodo1")).estado is EstadoNodo.DESCONECTADO
    assert [e.alerta_id for e in envios.todos()] == [alerta.id]
    assert {e.tipo for e in eventos.publicados} == {"nodo", "alerta"}


async def test_no_repite_la_alerta(revisar, nodos, alertas):
    await _nodo_con_ultima_lectura(nodos, hace_min=7)
    await revisar.ejecutar()

    assert await revisar.ejecutar() == []
    assert len(await alertas.listar()) == 1


async def test_periodo_largo_espera_tres_periodos(revisar, nodos):
    await _nodo_con_ultima_lectura(nodos, hace_min=12, periodo_s=300)

    assert await revisar.ejecutar() == []


async def test_nodo_que_nunca_ha_enviado_se_ignora(revisar, nodos):
    await nodos.guardar(crear_nodo())

    assert await revisar.ejecutar() == []


async def test_desconectado_por_ultima_voluntad_igual_genera_alerta(revisar, nodos):
    nodo = await _nodo_con_ultima_lectura(nodos, hace_min=10)
    await nodos.guardar(replace(nodo, estado=EstadoNodo.DESCONECTADO))

    assert len(await revisar.ejecutar()) == 1


async def test_tras_arrancar_el_servidor_el_nodo_tiene_su_plazo_normal(
    nodos, alertas, suscripciones, usuarios, envios, despertador, eventos, reloj
):
    """La computadora estuvo apagada toda la noche: el nodo guardó sus lecturas y las
    manda en cuanto el broker vuelve. No debe saltar una alerta de desconexión."""
    programar = ProgramarNotificacion(suscripciones, usuarios, envios, despertador, reloj)
    revisar = RevisarNodos(
        nodos, alertas, programar, eventos, reloj, escuchando_desde=AHORA - timedelta(minutes=2)
    )
    await _nodo_con_ultima_lectura(nodos, hace_min=8 * 60)

    assert await revisar.ejecutar() == []

    reloj.actual += timedelta(minutes=4)
    (alerta,) = await revisar.ejecutar()
    assert alerta.fuera_desde == AHORA - timedelta(hours=8)
