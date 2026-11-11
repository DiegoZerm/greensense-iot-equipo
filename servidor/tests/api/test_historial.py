from datetime import timedelta

import pytest

from greensense.composicion import crear_aplicacion
from greensense.dominio.usuarios import Rol
from tests.api.conftest import cliente_como
from tests.fabricas import AHORA, crear_lectura

pytestmark = pytest.mark.anyio

RANGO = {
    "nodo": "nodo1",
    "desde": (AHORA - timedelta(hours=2)).isoformat(),
    "hasta": (AHORA + timedelta(hours=1)).isoformat(),
}


@pytest.fixture
async def app(config):
    app = crear_aplicacion(config)
    c = app.state.contenedor
    await c.registrar_invernadero.ejecutar("inv1", "Invernadero")
    await c.registrar_nodo.ejecutar("inv1", "nodo1", "Nodo", sensor_suelo=True)
    repo = c.consultar_lecturas._lecturas
    for minuto in (0, 30, 60):
        await repo.guardar(crear_lectura(seq=minuto, ts=AHORA - timedelta(minutes=minuto)))
    return app


async def test_lecturas_agregadas_y_resumen(app):
    async with cliente_como(app, Rol.OPERADOR) as cliente:
        serie = (await cliente.get("/api/v1/lecturas", params=RANGO)).json()
        horas = (await cliente.get("/api/v1/lecturas/agregadas", params=RANGO)).json()
        resumen = (await cliente.get("/api/v1/reportes/resumen", params=RANGO)).json()

    assert serie["completa"] is True
    assert [lec["ts"] for lec in serie["lecturas"]] == [
        "2026-11-01T15:00:00Z",
        "2026-11-01T15:30:00Z",
        "2026-11-01T16:00:00Z",
    ]
    assert [(h["inicio"], h["lecturas"]) for h in horas] == [
        ("2026-11-01T09:00:00-06:00", 2),
        ("2026-11-01T10:00:00-06:00", 1),
    ]
    assert horas[0]["variables"]["temperatura"] == {
        "minimo": 24.3, "maximo": 24.3, "promedio": 24.3, "n": 2,
    }  # fmt: skip
    assert resumen["lecturas"] == 3
    assert resumen["variables"]["humedad_aire"]["promedio"] == 68.0


async def test_agregados_por_dia(app):
    async with cliente_como(app) as cliente:
        dias = (
            await cliente.get("/api/v1/lecturas/agregadas", params={**RANGO, "periodo": "dia"})
        ).json()
    assert [(d["inicio"], d["lecturas"]) for d in dias] == [("2026-11-01T00:00:00-06:00", 3)]


@pytest.mark.parametrize(
    ("rol", "codigo"),
    [(Rol.OPERADOR, 403), (Rol.TECNICO, 403), (Rol.SUPERVISOR, 200), (Rol.ADMINISTRADOR, 200)],
)
async def test_exportar_solo_con_permiso(app, rol, codigo):
    async with cliente_como(app, rol) as cliente:
        lecturas = await cliente.get("/api/v1/reportes/lecturas.csv", params=RANGO)
        alertas = await cliente.get(
            "/api/v1/reportes/alertas.csv",
            params={"desde": RANGO["desde"], "hasta": RANGO["hasta"]},
        )
    assert (lecturas.status_code, alertas.status_code) == (codigo, codigo)
    if codigo == 200:
        assert lecturas.headers["content-type"] == "text/csv; charset=utf-8"
        assert lecturas.headers["content-disposition"] == (
            'attachment; filename="lecturas_nodo1_2026-11-01_2026-11-01.csv"'
        )
        assert lecturas.text.count("\n") == 4


async def test_la_exportacion_queda_en_la_bitacora(app):
    async with cliente_como(app) as admin:
        await admin.get("/api/v1/reportes/lecturas.csv", params=RANGO)
        (registro, *_) = (await admin.get("/api/v1/bitacora")).json()
    assert (registro["accion"], registro["objeto"]) == ("exportar", "reporte")
    assert registro["detalle"] == "3 lecturas de nodo1"


@pytest.mark.parametrize(
    ("cambios", "codigo"),
    [
        ({"nodo": "nodo9"}, 404),
        ({"desde": "2026-11-01T10:00:00"}, 422),
        ({"hasta": RANGO["desde"]}, 422),
        ({"desde": "ayer"}, 422),
    ],
)
async def test_errores(app, cambios, codigo):
    async with cliente_como(app) as cliente:
        respuesta = await cliente.get("/api/v1/lecturas", params={**RANGO, **cambios})
    assert respuesta.status_code == codigo
