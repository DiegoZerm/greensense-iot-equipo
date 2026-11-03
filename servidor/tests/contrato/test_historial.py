"""Consultas del historial: las mismas pruebas para memoria y PostgreSQL."""

from datetime import UTC, datetime, timedelta

import pytest

from greensense.dominio.historial import ZONA_HORARIA, Estadistica, Periodo
from greensense.dominio.modelos import Variable
from tests.contrato.test_repositorios import (  # noqa: F401 - fixtures
    base_de_pruebas,
    con_nodo,
    repos,
)
from tests.fabricas import crear_alerta, crear_lectura, crear_nodo

pytestmark = pytest.mark.anyio


def local(dia: int, hora: int, minuto: int = 0) -> datetime:
    return datetime(2026, 11, dia, hora, minuto, tzinfo=ZONA_HORARIA)


# Medianoche local del 1 de noviembre son las 06:00 UTC.
LECTURAS = [
    crear_lectura(seq=0, ts=local(1, 23, 30) - timedelta(days=1), temperatura=15.0),
    crear_lectura(seq=1, ts=local(1, 0, 30), temperatura=16.0, humedad_sustrato=None),
    crear_lectura(seq=2, ts=local(1, 10, 0), temperatura=24.0, humedad_aire=60.0),
    crear_lectura(seq=3, ts=local(1, 10, 20), temperatura=26.0, humedad_aire=None),
    crear_lectura(seq=4, ts=local(1, 10, 40), temperatura=None, humedad_aire=70.0),
]


@pytest.fixture
async def con_lecturas(con_nodo):  # noqa: F811
    await con_nodo.nodos.guardar(crear_nodo(id="nodo2"))
    for lectura in LECTURAS:
        await con_nodo.lecturas.guardar(lectura)
    await con_nodo.lecturas.guardar(crear_lectura(nodo_id="nodo2", ts=local(1, 10, 0)))
    return con_nodo


async def test_en_rango_cronologico_con_limite(con_lecturas):
    lecturas = con_lecturas.lecturas

    todas = await lecturas.en_rango("nodo1", local(1, 0), local(2, 0), 100)
    assert [lec.seq for lec in todas] == [1, 2, 3, 4]
    assert todas[3].temperatura is None

    assert [lec.seq for lec in await lecturas.en_rango("nodo1", local(1, 0), local(2, 0), 2)] == [
        1,
        2,
    ]
    # hasta no se incluye
    assert [
        lec.seq for lec in await lecturas.en_rango("nodo1", local(1, 0, 30), local(1, 10, 0), 9)
    ] == [1]


async def test_primera_lectura(con_lecturas):
    assert (await con_lecturas.lecturas.primera("nodo1")).seq == 0
    assert await con_lecturas.lecturas.primera("nodo9") is None


async def test_agregados_por_hora_en_hora_local(con_lecturas):
    agregados = await con_lecturas.lecturas.agregadas(
        "nodo1", local(1, 0), local(2, 0), Periodo.HORA
    )

    assert [(a.inicio, a.lecturas) for a in agregados] == [(local(1, 0), 1), (local(1, 10), 3)]
    diez = agregados[1].variables
    assert diez[Variable.TEMPERATURA] == Estadistica(24.0, 26.0, 25.0, 2)
    assert diez[Variable.HUMEDAD_AIRE] == Estadistica(60.0, 70.0, 65.0, 2)
    assert agregados[0].variables[Variable.HUMEDAD_SUSTRATO] is None
    assert agregados[1].inicio.utcoffset() == timedelta(hours=-6)


async def test_agregados_por_dia_cortan_a_medianoche_local(con_lecturas):
    agregados = await con_lecturas.lecturas.agregadas(
        "nodo1", local(1, 0) - timedelta(days=1), local(2, 0), Periodo.DIA
    )

    assert [(a.inicio, a.lecturas) for a in agregados] == [
        (local(1, 0) - timedelta(days=1), 1),
        (local(1, 0), 4),
    ]
    temperatura = agregados[1].variables[Variable.TEMPERATURA]
    assert (temperatura.minimo, temperatura.maximo, temperatura.n) == (16.0, 26.0, 3)
    assert temperatura.promedio == pytest.approx(22.0)


async def test_estadisticas_del_rango(con_lecturas):
    lecturas, variables = await con_lecturas.lecturas.estadisticas(
        "nodo1", datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 12, 1, tzinfo=UTC)
    )

    assert lecturas == 5
    assert variables[Variable.TEMPERATURA].n == 4
    assert variables[Variable.HUMEDAD_SUSTRATO] == Estadistica(52.0, 52.0, 52.0, 4)

    vacio, sin_datos = await con_lecturas.lecturas.estadisticas("nodo1", local(3, 0), local(4, 0))
    assert vacio == 0
    assert all(e is None for e in sin_datos.values())


async def test_alertas_en_rango(con_lecturas):
    alertas = con_lecturas.alertas
    vieja = await alertas.guardar(crear_alerta(iniciada_en=local(1, 9)))
    nueva = await alertas.guardar(crear_alerta(iniciada_en=local(1, 11), resuelta_en=local(1, 12)))
    await con_lecturas.nodos.guardar(crear_nodo(id="nodo3"))
    otra = await alertas.guardar(crear_alerta(nodo_id="nodo3", iniciada_en=local(1, 10)))

    assert await alertas.en_rango(local(1, 0), local(2, 0)) == [vieja, otra, nueva]
    assert await alertas.en_rango(local(1, 0), local(2, 0), "nodo1") == [vieja, nueva]
    assert await alertas.en_rango(local(1, 10), local(1, 11)) == [otra]
