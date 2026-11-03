import pytest

from greensense.adaptadores.entrada.api.esquemas import evento_a_json
from greensense.aplicacion.puertos import Evento
from greensense.composicion import crear_aplicacion
from tests.api.conftest import cliente_como, cliente_para
from tests.fabricas import crear_lectura

pytestmark = pytest.mark.anyio


@pytest.fixture
async def app(config):
    app = crear_aplicacion(config)
    c = app.state.contenedor
    await c.registrar_invernadero.ejecutar("inv1", "Invernadero")
    await c.registrar_nodo.ejecutar("inv1", "nodo1", "Nodo con datos", sensor_suelo=True)
    await c.registrar_nodo.ejecutar("inv1", "nodo2", "Nodo sin datos")
    return app


@pytest.fixture
async def cliente_async(app):
    async with cliente_como(app) as cliente:
        yield cliente


async def test_sin_sesion_no_hay_datos(app):
    async with cliente_para(app) as anonimo:
        assert (await anonimo.get("/api/v1/lecturas/ultimas")).status_code == 401
    async with cliente_para(app, "token-inventado") as falso:
        assert (await falso.get("/api/v1/lecturas/ultimas")).status_code == 401


async def test_nodo_dado_de_baja_no_aparece_en_el_panel(app, cliente_async):
    respuesta = await cliente_async.patch("/api/v1/nodos/nodo2", json={"activo": False})
    assert respuesta.json()["activo"] is False

    ultimas = (await cliente_async.get("/api/v1/lecturas/ultimas")).json()
    assert [e["nodo"]["id"] for e in ultimas] == ["nodo1"]


async def test_ultimas_sin_lecturas(cliente_async):
    respuesta = await cliente_async.get("/api/v1/lecturas/ultimas")

    assert respuesta.status_code == 200
    assert [(e["nodo"]["id"], e["ultima"]) for e in respuesta.json()] == [
        ("nodo1", None),
        ("nodo2", None),
    ]


async def test_ultimas_con_lectura(app, cliente_async):
    await app.state.contenedor.registrar_lectura.ejecutar("inv1", crear_lectura())

    nodo1 = (await cliente_async.get("/api/v1/lecturas/ultimas")).json()[0]

    assert nodo1["nodo"]["estado"] == "conectado"
    assert nodo1["nodo"]["ultima_lectura_en"] == "2026-11-01T16:00:00Z"
    assert nodo1["ultima"] == {
        "ts": "2026-11-01T16:00:00Z",
        "arranque": 1,
        "seq": 0,
        "temperatura": 24.3,
        "humedad_aire": 68.0,
        "humedad_sustrato": 52.0,
        "muestras": 5,
        "rssi": -60,
    }


async def test_evento_usa_el_mismo_formato_que_la_api(app, cliente_async):
    contenedor = app.state.contenedor
    await contenedor.registrar_lectura.ejecutar("inv1", crear_lectura())
    nodo = (await contenedor.consultar_estado_actual.ejecutar())[0].nodo

    datos = evento_a_json(Evento("lectura", {"nodo": nodo, "lectura": crear_lectura()}))

    api = (await cliente_async.get("/api/v1/lecturas/ultimas")).json()[0]
    assert datos == {"nodo": api["nodo"], "lectura": api["ultima"]}
