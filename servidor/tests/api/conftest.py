"""Clientes HTTP con sesión iniciada para probar la API."""

import contextlib

import httpx2

from greensense.dominio.usuarios import Rol

CONTRASENA = "contrasena-segura"


async def entrar(app, rol: Rol = Rol.ADMINISTRADOR, correo: str | None = None) -> str:
    """Crea un usuario con ese rol y devuelve el token de su sesión."""
    c = app.state.contenedor
    correo = correo or f"{rol}@ejemplo.com"
    if not any(u.correo == correo for u in await c.listar_usuarios.ejecutar()):
        await c.crear_usuario.ejecutar(None, f"Usuario {rol}", correo, rol, CONTRASENA)
    return (await c.iniciar_sesion.ejecutar(correo, CONTRASENA)).token


@contextlib.asynccontextmanager
async def cliente_para(app, token: str | None = None):
    transporte = httpx2.ASGITransport(app=app)
    encabezados = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx2.AsyncClient(
        transport=transporte, base_url="http://prueba", headers=encabezados
    ) as cliente:
        yield cliente


@contextlib.asynccontextmanager
async def cliente_como(app, rol: Rol = Rol.ADMINISTRADOR):
    async with cliente_para(app, await entrar(app, rol)) as cliente:
        yield cliente
