"""API HTTP de GreenSense, versión 1."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from greensense import __version__
from greensense.adaptadores.entrada.api import (
    alertas,
    bitacora,
    cultivos,
    eventos,
    historial,
    instalacion,
    lecturas,
    push,
    salud,
    sesion,
    usuarios,
)
from greensense.aplicacion.errores import Conflicto, InvernaderoNoRegistrado, NoEncontrado
from greensense.contenedor import Contenedor

PREFIJO = "/api/v1"

# Los errores de validación del dominio (IdInvalido, UmbralInvalido, DatosInvalidos...)
# heredan de ValueError y se responden como 422, igual que los de Pydantic.
_ERRORES = {
    NoEncontrado: status.HTTP_404_NOT_FOUND,
    InvernaderoNoRegistrado: status.HTTP_404_NOT_FOUND,
    Conflicto: status.HTTP_409_CONFLICT,
    ValueError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


def _manejador(codigo: int):
    async def responder(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=codigo)

    return responder


def crear_api(
    contenedor: Contenedor,
    ciclo_de_vida: Callable[[FastAPI], AbstractAsyncContextManager[Any]] | None = None,
) -> FastAPI:
    app = FastAPI(title="GreenSense IoT", version=__version__, lifespan=ciclo_de_vida)
    app.state.contenedor = contenedor
    for error, codigo in _ERRORES.items():
        app.add_exception_handler(error, _manejador(codigo))
    for modulo in (
        salud,
        sesion,
        lecturas,
        historial,
        alertas,
        push,
        eventos,
        usuarios,
        cultivos,
        instalacion,
        bitacora,
    ):
        app.include_router(modulo.router, prefix=PREFIJO)
    return app
