"""Fase 4: cada rol solo ve y hace lo de la matriz de permisos."""

import pytest

from greensense.adaptadores.entrada.api.dependencias import usuario_de_eventos
from greensense.composicion import crear_aplicacion
from greensense.dominio.usuarios import Rol
from tests.api.conftest import CONTRASENA, cliente_como, cliente_para, entrar

pytestmark = pytest.mark.anyio

OP, S, T, A = Rol.OPERADOR, Rol.SUPERVISOR, Rol.TECNICO, Rol.ADMINISTRADOR
TODOS = {OP, S, T, A}

CULTIVO = {
    "id": "tomate",
    "nombre": "Jitomate",
    "umbrales": [{"variable": "temperatura", "minimo": 18, "maximo": 30, "margen": 2}],
}

# (método, ruta, cuerpo, roles que pueden)
RUTAS = [
    ("get", "/lecturas/ultimas", None, TODOS),
    ("get", "/alertas", None, TODOS),
    ("get", "/nodos", None, TODOS),
    ("get", "/invernaderos", None, TODOS),
    ("get", "/cultivos", None, TODOS),
    ("get", "/bitacora", None, {S, A}),
    ("get", "/usuarios", None, {A}),
    ("post", "/cultivos", CULTIVO, {A}),
    ("put", "/cultivos/hortalizas-hoja", {"nombre": "Hoja", "umbrales": []}, {A}),
    ("post", "/invernaderos", {"id": "inv2", "nombre": "Dos"}, {A}),
    ("patch", "/invernaderos/inv1", {"nombre": "Uno"}, {A}),
    ("post", "/nodos", {"id": "nodo9", "invernadero_id": "inv1", "nombre": "N"}, {T, A}),
    ("patch", "/nodos/nodo1", {"nombre": "Renombrado"}, {T, A}),
    (
        "post",
        "/usuarios",
        {"nombre": "X", "correo": "x@ejemplo.com", "rol": "operador", "contrasena": CONTRASENA},
        {A},
    ),
]


@pytest.fixture
async def app(config):
    app = crear_aplicacion(config)
    c = app.state.contenedor
    await c.registrar_invernadero.ejecutar("inv1", "Invernadero")
    await c.registrar_nodo.ejecutar("inv1", "nodo1", "Nodo")
    return app


@pytest.mark.parametrize("rol", [OP, S, T, A])
@pytest.mark.parametrize(("metodo", "ruta", "cuerpo", "pueden"), RUTAS)
async def test_matriz_en_la_api(app, rol, metodo, ruta, cuerpo, pueden):
    async with cliente_como(app, rol) as cliente:
        opciones = {"json": cuerpo} if cuerpo is not None else {}
        respuesta = await cliente.request(metodo, f"/api/v1{ruta}", **opciones)

    if rol in pueden:
        assert respuesta.status_code in (200, 201), respuesta.text
    else:
        assert respuesta.status_code == 403, respuesta.text


@pytest.mark.parametrize(("metodo", "ruta", "cuerpo", "pueden"), RUTAS)
async def test_sin_sesion_todo_responde_401(app, metodo, ruta, cuerpo, pueden):
    async with cliente_para(app) as anonimo:
        respuesta = await anonimo.request(metodo, f"/api/v1{ruta}", json=cuerpo)
    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


async def test_login_y_yo(app):
    await entrar(app, Rol.SUPERVISOR)
    async with cliente_para(app) as anonimo:
        malo = await anonimo.post(
            "/api/v1/auth/login", json={"correo": "supervisor@ejemplo.com", "contrasena": "x"}
        )
        bueno = await anonimo.post(
            "/api/v1/auth/login",
            json={"correo": "Supervisor@ejemplo.com", "contrasena": CONTRASENA},
        )
    assert malo.status_code == 401
    sesion = bueno.json()
    assert sesion["usuario"]["rol"] == "supervisor"
    assert "hash_contrasena" not in sesion["usuario"]
    assert sorted(sesion["usuario"]["permisos"]) == [
        "atender_alertas",
        "consultar_bitacora",
        "consultar_historial",
        "exportar_reportes",
        "notificaciones_cultivo",
        "ver_panel",
    ]

    async with cliente_para(app, sesion["token"]) as cliente:
        yo = (await cliente.get("/api/v1/auth/yo")).json()
    assert yo == sesion["usuario"]


async def test_cambiar_mi_contrasena(app):
    async with cliente_como(app, Rol.OPERADOR) as cliente:
        mala = await cliente.put(
            "/api/v1/auth/yo/contrasena", json={"actual": "otra", "nueva": "nueva-contrasena"}
        )
        corta = await cliente.put(
            "/api/v1/auth/yo/contrasena", json={"actual": CONTRASENA, "nueva": "corta"}
        )
        buena = await cliente.put(
            "/api/v1/auth/yo/contrasena", json={"actual": CONTRASENA, "nueva": "nueva-contrasena"}
        )
    assert (mala.status_code, corta.status_code, buena.status_code) == (400, 422, 204)


async def test_usuario_desactivado_pierde_acceso_de_inmediato(app):
    token = await entrar(app, Rol.OPERADOR)
    async with cliente_como(app, Rol.ADMINISTRADOR) as admin:
        (operador,) = [
            u for u in (await admin.get("/api/v1/usuarios")).json() if u["rol"] == "operador"
        ]
        await admin.patch(f"/api/v1/usuarios/{operador['id']}", json={"activo": False})

    async with cliente_para(app, token) as cliente:
        assert (await cliente.get("/api/v1/lecturas/ultimas")).status_code == 401


async def test_errores_de_configuracion(app):
    async with cliente_como(app) as admin:
        repetido = await admin.post("/api/v1/invernaderos", json={"id": "inv1", "nombre": "X"})
        id_malo = await admin.post("/api/v1/invernaderos", json={"id": "Inv 1", "nombre": "X"})
        sin_cultivo = await admin.patch("/api/v1/invernaderos/inv1", json={"cultivo_id": "nada"})
        no_existe = await admin.patch("/api/v1/nodos/nodo9", json={"nombre": "X"})
        umbral_malo = await admin.put(
            "/api/v1/cultivos/hortalizas-hoja",
            json={
                "nombre": "Hoja",
                "umbrales": [{"variable": "temperatura", "minimo": 30, "maximo": 20, "margen": 1}],
            },
        )
        con_nodos = await admin.delete("/api/v1/invernaderos/inv1")
        ultimo_admin = await admin.patch("/api/v1/usuarios/1", json={"rol": "operador"})
    assert repetido.status_code == 409
    assert id_malo.status_code == 422
    assert sin_cultivo.status_code == 404
    assert no_existe.status_code == 404
    assert umbral_malo.status_code == 422
    assert "mínimo" in umbral_malo.json()["detail"]
    assert con_nodos.status_code == 409
    assert ultimo_admin.status_code == 409


async def test_cultivo_de_ida_y_vuelta_y_bitacora(app):
    async with cliente_como(app) as admin:
        creado = (await admin.post("/api/v1/cultivos", json=CULTIVO)).json()
        await admin.patch("/api/v1/invernaderos/inv1", json={"cultivo_id": "tomate"})
        bitacora = (await admin.get("/api/v1/bitacora", params={"limite": 2})).json()

    assert creado == {
        **CULTIVO,
        "umbrales": [{**CULTIVO["umbrales"][0], "tiempo_bajo_s": 300, "tiempo_alto_s": 300}],
        "hongos": {"humedad_minima": 85.0, "temperatura_minima": 20.0, "tiempo_minimo_s": 3600},
    }
    assert [(b["accion"], b["objeto"], b["objeto_id"]) for b in bitacora] == [
        ("modificar", "invernadero", "inv1"),
        ("crear", "cultivo", "tomate"),
    ]
    assert bitacora[0]["usuario_nombre"] == "Usuario administrador"


async def test_eventos_aceptan_el_token_en_la_url(app):
    """EventSource no manda encabezados: el token puede ir en ?token=.

    El flujo abierto no se prueba por HTTP porque el transporte ASGI de httpx espera a
    que la respuesta termine y un SSE nunca termina; se prueba la dependencia.
    """
    token = await entrar(app, Rol.OPERADOR)
    async with cliente_para(app) as anonimo:
        assert (await anonimo.get("/api/v1/eventos")).status_code == 401
        assert (await anonimo.get("/api/v1/eventos", params={"token": "x"})).status_code == 401

    usuario = await usuario_de_eventos(app.state.contenedor, None, token)
    assert usuario.rol is Rol.OPERADOR


async def test_eventos_abren_con_un_comentario_para_que_los_proxys_no_esperen(app):
    """Sin un primer mensaje, `ng serve` y nginx retienen los encabezados del SSE."""
    from greensense.adaptadores.entrada.api.eventos import RECONEXION_MS, eventos

    token = await entrar(app, Rol.OPERADOR)
    usuario = await usuario_de_eventos(app.state.contenedor, None, token)
    flujo = eventos(usuario, app.state.contenedor)
    primero = await anext(flujo)
    await flujo.aclose()

    assert primero.comment == "conectado"
    assert primero.retry == RECONEXION_MS
    assert primero.data is None
