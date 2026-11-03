from datetime import timedelta

import pytest

from greensense.aplicacion.casos_uso import consultar_historial
from greensense.aplicacion.casos_uso.consultar_historial import (
    ConsultarLecturas,
    ConsultarResumen,
    ExportarAlertas,
    ExportarLecturas,
)
from greensense.aplicacion.errores import NoEncontrado
from greensense.dominio.bitacora import Accion, Objeto
from greensense.dominio.historial import ZONA_HORARIA, RangoInvalido
from greensense.dominio.modelos import Variable
from tests.fabricas import AHORA, crear_alerta, crear_lectura, crear_nodo, crear_usuario

pytestmark = pytest.mark.anyio

ANA = crear_usuario(id=1)


@pytest.fixture
async def nodo_con_datos(nodos, lecturas):
    """10 lecturas, una por minuto, en la última hora; faltan 50."""
    await nodos.guardar(crear_nodo())
    for minuto in range(10):
        await lecturas.guardar(
            crear_lectura(
                seq=minuto, ts=AHORA - timedelta(minutes=60 - minuto), temperatura=20.0 + minuto
            )
        )


async def test_resumen_cuenta_esperadas_desde_la_primera_lectura(
    nodo_con_datos, lecturas, nodos, reloj
):
    resumen = await ConsultarResumen(lecturas, nodos, reloj).ejecutar(
        "nodo1", AHORA - timedelta(days=7), AHORA + timedelta(days=1)
    )

    # De la primera lectura (hace 60 min) a ahora caben 60; el futuro no cuenta.
    assert (resumen.lecturas, resumen.esperadas, resumen.perdidas) == (10, 60, 50)
    assert resumen.porcentaje_perdidas == pytest.approx(83.33)
    temperatura = resumen.variables[Variable.TEMPERATURA]
    assert (temperatura.minimo, temperatura.maximo, temperatura.promedio) == (20.0, 29.0, 24.5)


async def test_resumen_sin_lecturas(nodos, lecturas, reloj):
    await nodos.guardar(crear_nodo())
    resumen = await ConsultarResumen(lecturas, nodos, reloj).ejecutar(
        "nodo1", AHORA - timedelta(days=1), AHORA
    )
    assert (resumen.lecturas, resumen.esperadas, resumen.porcentaje_perdidas) == (0, 0, None)


@pytest.mark.parametrize(
    ("desde", "hasta"),
    [
        (AHORA, AHORA),
        (AHORA, AHORA - timedelta(hours=1)),
        (AHORA - timedelta(days=400), AHORA),
        (AHORA.replace(tzinfo=None), AHORA.replace(tzinfo=None) + timedelta(hours=1)),
    ],
    ids=["vacio", "invertido", "mas-de-un-ano", "sin-zona"],
)
async def test_rango_invalido(nodo_con_datos, lecturas, nodos, desde, hasta):
    with pytest.raises(RangoInvalido):
        await ConsultarLecturas(lecturas, nodos).ejecutar("nodo1", desde, hasta)


async def test_nodo_inexistente(lecturas, nodos):
    with pytest.raises(NoEncontrado):
        await ConsultarLecturas(lecturas, nodos).ejecutar(
            "nodo9", AHORA - timedelta(hours=1), AHORA
        )


async def test_serie_recortada_avisa(nodo_con_datos, lecturas, nodos, monkeypatch):
    monkeypatch.setattr(consultar_historial, "LECTURAS_MAXIMAS", 4)

    serie = await ConsultarLecturas(lecturas, nodos).ejecutar(
        "nodo1", AHORA - timedelta(days=1), AHORA
    )

    assert len(serie.lecturas) == 4
    assert serie.completa is False


async def test_csv_de_lecturas_en_hora_local_y_anotado(
    nodo_con_datos, lecturas, nodos, anotador, bitacora
):
    archivo = await ExportarLecturas(lecturas, nodos, anotador).ejecutar(
        ANA, "nodo1", AHORA - timedelta(days=1), AHORA
    )

    assert archivo.nombre == "lecturas_nodo1_2026-10-31_2026-11-01.csv"
    lineas = archivo.contenido.lstrip("﻿").splitlines()
    assert lineas[0] == (
        "fecha_hora,nodo,arranque,seq,temperatura,humedad_aire,humedad_sustrato,muestras,rssi"
    )
    assert lineas[1] == "2026-11-01T09:00:00-06:00,nodo1,1,0,20,68,52,5,-60"
    assert len(lineas) == 11
    (registro,) = await bitacora.listar()
    assert (registro.accion, registro.objeto, registro.usuario_id) == (
        Accion.EXPORTAR,
        Objeto.REPORTE,
        1,
    )
    assert registro.detalle == "10 lecturas de nodo1"


async def test_csv_de_alertas(nodos, alertas, anotador):
    await nodos.guardar(crear_nodo())
    await alertas.guardar(
        crear_alerta(
            atendida_en=AHORA, atendida_por=1, atendida_por_nombre="Ana", mensaje="Calor, mucho"
        )
    )

    archivo = await ExportarAlertas(alertas, nodos, anotador).ejecutar(
        ANA, AHORA - timedelta(hours=1), AHORA + timedelta(hours=1)
    )

    encabezado, fila = archivo.contenido.lstrip("﻿").splitlines()
    assert encabezado.startswith("id,nodo,tipo,variable,severidad,mensaje")
    # La coma del mensaje queda entre comillas.
    assert fila.startswith('1,nodo1,umbral,temperatura,advertencia,"Calor, mucho",29,28,')
    assert fila.endswith(",2026-11-01T10:00:00-06:00,Ana")


async def test_nombre_del_csv_usa_el_ultimo_dia_incluido(nodo_con_datos, lecturas, nodos, anotador):
    medianoche = AHORA.astimezone(ZONA_HORARIA).replace(hour=0, minute=0) + timedelta(days=1)

    archivo = await ExportarLecturas(lecturas, nodos, anotador).ejecutar(
        ANA, "nodo1", medianoche - timedelta(days=7), medianoche
    )

    assert archivo.nombre == "lecturas_nodo1_2026-10-26_2026-11-01.csv"
