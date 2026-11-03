"""Alertas generadas al registrar lecturas, de punta a punta con repositorios en memoria."""

from dataclasses import replace
from datetime import timedelta

import pytest

from greensense.aplicacion.casos_uso.evaluar_alertas import EvaluarAlertas
from greensense.aplicacion.casos_uso.notificaciones import ProgramarNotificacion
from greensense.aplicacion.casos_uso.registrar_lectura import RegistrarLectura
from greensense.dominio.alertas import Severidad, TipoAlerta
from greensense.dominio.cultivo import Cultivo, Umbral
from greensense.dominio.modelos import Invernadero, Variable
from greensense.dominio.notificaciones import SuscripcionPush
from tests.fabricas import AHORA, crear_alerta, crear_lectura, crear_nodo

pytestmark = pytest.mark.anyio


@pytest.fixture
async def registrar(
    lecturas, nodos, invernaderos, cultivos, alertas, suscripciones, usuarios, envios, despertador,
    reloj, eventos,
):  # fmt: skip
    await invernaderos.guardar(Invernadero("inv1", "Invernadero"))
    await nodos.guardar(crear_nodo(sensor_suelo=True))
    await suscripciones.guardar(SuscripcionPush("https://push/1", "k", "a", AHORA, 1))
    programar = ProgramarNotificacion(suscripciones, usuarios, envios, despertador, reloj)
    evaluar = EvaluarAlertas(alertas, invernaderos, cultivos, programar, eventos)
    caso = RegistrarLectura(lecturas, nodos, reloj, eventos, evaluar)

    seq = iter(range(1000))

    async def lectura_en(minuto: float, retraso_min: float = 0, **valores):
        """Lectura que llega en `minuto`, tomada `retraso_min` minutos antes."""
        reloj.actual = AHORA + timedelta(minutes=minuto)
        ts = reloj.actual - timedelta(minutes=retraso_min)
        return await caso.ejecutar("inv1", crear_lectura(seq=next(seq), ts=ts, **valores))

    return lectura_en


def _de_temperatura(lista):
    return [a for a in lista if a.tipo is TipoAlerta.UMBRAL and a.variable is Variable.TEMPERATURA]


async def test_lectura_normal_no_genera_alertas(registrar, alertas):
    await registrar(0)

    assert await alertas.activas() == []


async def test_temperatura_alta_sostenida_llega_a_critica_y_se_notifica(
    registrar, alertas, envios, despertador
):
    for minuto in range(6):
        await registrar(minuto, temperatura=30.0)

    (alerta,) = _de_temperatura(await alertas.activas())
    assert alerta.severidad is Severidad.CRITICA
    assert alerta.escalada_en == AHORA + timedelta(minutes=5)
    assert [e.alerta_id for e in envios.todos()] == [alerta.id]
    assert despertador.avisos == 1


async def test_al_volver_a_la_normalidad_se_resuelve(registrar, alertas, eventos):
    await registrar(0, temperatura=30.0)
    await registrar(1, temperatura=23.0)

    assert await alertas.activas() == []
    (alerta,) = await alertas.listar()
    assert alerta.resuelta_en == AHORA + timedelta(minutes=1)
    cambios = [e.datos["alerta"].activa for e in eventos.publicados if e.tipo == "alerta"]
    assert cambios == [True, False]


async def test_una_sola_alerta_mientras_dura_el_problema(registrar, alertas, eventos):
    for minuto in range(3):
        await registrar(minuto, temperatura=27.0)

    assert len(await alertas.listar()) == 1
    assert sum(e.tipo == "alerta" for e in eventos.publicados) == 1


async def test_sensor_que_deja_de_medir_genera_alerta(registrar, alertas):
    await registrar(0, temperatura=None)

    tipos = {(a.tipo, a.variable) for a in await alertas.activas()}
    assert (TipoAlerta.SENSOR, Variable.TEMPERATURA) in tipos


async def test_nodo_sin_sensor_de_suelo_no_alerta_por_sustrato(registrar, nodos, alertas):
    await nodos.guardar(replace(await nodos.obtener("nodo1"), sensor_suelo=False))

    await registrar(0, humedad_sustrato=10.0)

    assert all(a.variable is not Variable.HUMEDAD_SUSTRATO for a in await alertas.activas())


async def test_lectura_reenviada_con_mas_de_10_min_no_genera_alertas(registrar, alertas):
    resultado = await registrar(30, retraso_min=15, temperatura=40.0)

    assert resultado.guardada
    assert await alertas.activas() == []


async def test_lectura_mas_vieja_que_la_ultima_no_genera_alertas(registrar, alertas):
    await registrar(10)

    resultado = await registrar(11, retraso_min=5, temperatura=40.0)

    assert resultado.guardada
    assert await alertas.activas() == []


async def test_lectura_resuelve_la_desconexion(registrar, alertas):
    desconexion = await alertas.guardar(
        crear_alerta(tipo=TipoAlerta.DESCONEXION, variable=None, severidad=Severidad.CRITICA)
    )

    await registrar(0)

    assert not (await alertas.obtener(desconexion.id)).activa


async def test_usa_los_umbrales_del_cultivo_del_invernadero(
    registrar, invernaderos, cultivos, alertas
):
    estricto = Cultivo(
        "estricto",
        "Estricto",
        (Umbral(Variable.TEMPERATURA, 10, 20, 1, timedelta(0), timedelta(0)),),
    )
    await cultivos.guardar(estricto)
    await invernaderos.guardar(Invernadero("inv1", "Invernadero", cultivo_id="estricto"))

    await registrar(0, temperatura=22.0)

    (alerta,) = _de_temperatura(await alertas.activas())
    assert alerta.severidad is Severidad.CRITICA
    assert alerta.limite == 20
