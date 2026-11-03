"""Dependencias de FastAPI: el contenedor, el usuario de la sesión y los permisos."""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from greensense.aplicacion.puertos import TokenInvalido
from greensense.contenedor import Contenedor
from greensense.dominio.usuarios import Permiso, Usuario


def contenedor(request: Request) -> Contenedor:
    return request.app.state.contenedor


ContenedorDep = Annotated[Contenedor, Depends(contenedor)]

_bearer = HTTPBearer(auto_error=False, description="Token de POST /auth/login")


def _no_autenticado(detalle: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detalle, headers={"WWW-Authenticate": "Bearer"}
    )


async def _usuario(c: Contenedor, token: str | None) -> Usuario:
    if not token:
        raise _no_autenticado("Falta iniciar sesión")
    try:
        return await c.usuario_del_token.ejecutar(token)
    except TokenInvalido as error:
        raise _no_autenticado("La sesión no es válida o ya venció") from error


async def usuario_actual(
    c: ContenedorDep,
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Usuario:
    return await _usuario(c, credenciales.credentials if credenciales else None)


async def usuario_de_eventos(
    c: ContenedorDep,
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    token: Annotated[
        str | None, Query(description="Para EventSource, que no manda encabezados")
    ] = None,
) -> Usuario:
    """EventSource del navegador no permite encabezados: el token puede ir en la URL."""
    return await _usuario(c, credenciales.credentials if credenciales else token)


UsuarioActual = Annotated[Usuario, Depends(usuario_actual)]


def requiere_permiso(permiso: Permiso) -> Callable[..., Awaitable[Usuario]]:
    """Uso: `usuario: Annotated[Usuario, Depends(requiere_permiso(Permiso.X))]`."""

    async def verificar(usuario: UsuarioActual) -> Usuario:
        if not usuario.puede(permiso):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Tu rol no tiene el permiso {permiso}")
        return usuario

    return verificar


def con_permiso(permiso: Permiso):
    """Tipo para las firmas de las rutas: `usuario: PuedeX` con
    `PuedeX = con_permiso(Permiso.X)` definido a nivel de módulo."""
    return Annotated[Usuario, Depends(requiere_permiso(permiso))]


VerPanel = con_permiso(Permiso.VER_PANEL)
