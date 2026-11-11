from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from greensense.adaptadores.entrada.api.dependencias import UsuarioActual, contenedor
from greensense.contenedor import Contenedor

router = APIRouter(prefix="/push", tags=["notificaciones"])


class ClavePublica(BaseModel):
    habilitado: bool
    clave: str


class ClavesSuscripcion(BaseModel):
    p256dh: str = Field(min_length=1)
    auth: str = Field(min_length=1)


class Suscripcion(BaseModel):
    """Lo que entrega PushSubscription.toJSON() en el navegador."""

    endpoint: str = Field(pattern=r"^https://", max_length=2048)
    keys: ClavesSuscripcion


class SuscripcionRegistrada(BaseModel):
    id: int


@router.get("/clave-publica")
async def clave_publica(c: Annotated[Contenedor, Depends(contenedor)]) -> ClavePublica:
    return ClavePublica(habilitado=bool(c.clave_publica_push), clave=c.clave_publica_push)


@router.post("/suscripciones", status_code=status.HTTP_201_CREATED)
async def suscribir(
    datos: Suscripcion, usuario: UsuarioActual, c: Annotated[Contenedor, Depends(contenedor)]
) -> SuscripcionRegistrada:
    """Liga el navegador al usuario. Solo recibe las alertas que su rol permite."""
    if not c.clave_publica_push:
        raise HTTPException(503, "Las notificaciones push no están configuradas")
    suscripcion = await c.registrar_suscripcion.ejecutar(
        usuario, datos.endpoint, datos.keys.p256dh, datos.keys.auth
    )
    return SuscripcionRegistrada(id=suscripcion.id)


@router.delete("/suscripciones", status_code=status.HTTP_204_NO_CONTENT)
async def desuscribir(
    endpoint: str, usuario: UsuarioActual, c: Annotated[Contenedor, Depends(contenedor)]
) -> Response:
    if not await c.borrar_suscripcion.ejecutar(usuario, endpoint):
        raise HTTPException(404, "No existe esa suscripción")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
