import pytest

from greensense.composicion import crear_aplicacion
from greensense.config import Config
from greensense.dominio.usuarios import Rol
from tests.api.conftest import cliente_como, cliente_para, entrar
from tests.fabricas import crear_lectura

pytestmark = pytest.mark.anyio

SUSCRIPCION = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/abc",
    "keys": {"p256dh": "k", "auth": "a"},
}


def _config(**cambios) -> Config:
    return Config(
        _env_file=None, almacenamiento="memoria", mqtt_habilitado=False, hash_rapido=True, **cambios
    )


@pytest.fixture
async def app():
    app = crear_aplicacion(_config(vapid_privada="privada", vapid_publica="publica"))
    c = app.state.contenedor
    await c.registrar_invernadero.ejecutar("inv1", "Invernadero")
    await c.registrar_nodo.ejecutar("inv1", "nodo1", "Nodo", sensor_suelo=True)
    return app


@pytest.fixture
async def cliente(app):
    async with cliente_como(app, Rol.OPERADOR) as cliente:
        yield cliente


async def test_alerta_aparece_en_la_api_y_en_el_estado_actual(app, cliente):
    from datetime import UTC, datetime

    ahora = datetime.now(UTC).replace(microsecond=0)
    await app.state.contenedor.registrar_lectura.ejecutar(
        "inv1", crear_lectura(ts=ahora, temperatura=27.0)
    )

    (alerta,) = (await cliente.get("/api/v1/alertas", params={"activas": True})).json()
    assert alerta["severidad"] == "advertencia"
    assert alerta["variable"] == "temperatura"
    assert alerta["activa"] is True

    (estado,) = (await cliente.get("/api/v1/lecturas/ultimas")).json()
    assert [a["id"] for a in estado["alertas"]] == [alerta["id"]]

    atendida = (await cliente.post(f"/api/v1/alertas/{alerta['id']}/atender")).json()
    assert atendida["atendida_en"] is not None
    assert atendida["atendida_por_nombre"] == "Usuario operador"


async def test_filtros_del_historial_de_alertas(app, cliente):
    from datetime import UTC, datetime, timedelta

    ahora = datetime.now(UTC).replace(microsecond=0)
    await app.state.contenedor.registrar_lectura.ejecutar(
        "inv1", crear_lectura(ts=ahora, temperatura=27.0)
    )

    async def cuantas(**parametros):
        respuesta = await cliente.get("/api/v1/alertas", params=parametros)
        assert respuesta.status_code == 200
        return len(respuesta.json())

    assert await cuantas(severidad="advertencia", variable="temperatura") == 1
    assert await cuantas(severidad="critica") == 0
    assert await cuantas(variable="humedad_aire") == 0
    manana = (ahora + timedelta(days=1)).isoformat()
    assert await cuantas(hasta=ahora.isoformat()) == 0
    assert await cuantas(desde=ahora.isoformat(), hasta=manana) == 1
    assert await cuantas(desde=manana) == 0

    # Valores inválidos y rango al revés.
    assert (await cliente.get("/api/v1/alertas", params={"severidad": "x"})).status_code == 422
    invertido = {"desde": manana, "hasta": ahora.isoformat()}
    assert (await cliente.get("/api/v1/alertas", params=invertido)).status_code == 422


async def test_atender_alerta_inexistente(cliente):
    assert (await cliente.post("/api/v1/alertas/999/atender")).status_code == 404


async def test_clave_publica_no_necesita_sesion(app):
    async with cliente_para(app) as cliente:
        respuesta = await cliente.get("/api/v1/push/clave-publica")
    assert respuesta.json() == {
        "habilitado": True,
        "clave": "publica",
    }


async def test_suscribir_y_desuscribir(cliente):
    respuesta = await cliente.post("/api/v1/push/suscripciones", json=SUSCRIPCION)
    assert respuesta.status_code == 201

    borrar = await cliente.delete(
        "/api/v1/push/suscripciones", params={"endpoint": SUSCRIPCION["endpoint"]}
    )
    assert borrar.status_code == 204
    otra_vez = await cliente.delete(
        "/api/v1/push/suscripciones", params={"endpoint": SUSCRIPCION["endpoint"]}
    )
    assert otra_vez.status_code == 404


@pytest.mark.parametrize(
    "cuerpo",
    [
        {**SUSCRIPCION, "endpoint": "http://inseguro"},
        {**SUSCRIPCION, "keys": {"p256dh": "", "auth": "a"}},
        {"endpoint": SUSCRIPCION["endpoint"]},
    ],
)
async def test_suscripcion_invalida(cliente, cuerpo):
    assert (await cliente.post("/api/v1/push/suscripciones", json=cuerpo)).status_code == 422


async def test_suscripcion_ligada_al_usuario(app, cliente):
    await cliente.post("/api/v1/push/suscripciones", json=SUSCRIPCION)
    (suscripcion,) = await app.state.contenedor.registrar_suscripcion._suscripciones.listar()
    operador = await app.state.contenedor.usuario_del_token.ejecutar(
        await entrar(app, Rol.OPERADOR)
    )
    assert suscripcion.usuario_id == operador.id

    # Otro usuario no puede borrar la suscripción ajena.
    async with cliente_como(app, Rol.TECNICO) as tecnico:
        borrar = await tecnico.delete(
            "/api/v1/push/suscripciones", params={"endpoint": SUSCRIPCION["endpoint"]}
        )
    assert borrar.status_code == 404


async def test_suscribirse_requiere_sesion(app):
    async with cliente_para(app) as anonimo:
        respuesta = await anonimo.post("/api/v1/push/suscripciones", json=SUSCRIPCION)
    assert respuesta.status_code == 401


async def test_sin_vapid_no_acepta_suscripciones():
    async with cliente_como(crear_aplicacion(_config())) as cliente:
        assert (await cliente.get("/api/v1/push/clave-publica")).json()["habilitado"] is False
        respuesta = await cliente.post("/api/v1/push/suscripciones", json=SUSCRIPCION)
        assert respuesta.status_code == 503
