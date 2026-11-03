from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from greensense.adaptadores.entrada.api.dependencias import ContenedorDep, UsuarioActual
from greensense.adaptadores.entrada.api.esquemas import Contrasena, SesionUsuario
from greensense.aplicacion.errores import CredencialesInvalidas

router = APIRouter(prefix="/auth", tags=["sesión"])


class Credenciales(BaseModel):
    correo: str = Field(max_length=254)
    contrasena: str = Field(max_length=128)


class SesionIniciada(BaseModel):
    token: str
    usuario: SesionUsuario


class CambioContrasena(BaseModel):
    actual: str = Field(max_length=128)
    nueva: Contrasena


@router.post("/login")
async def iniciar_sesion(datos: Credenciales, c: ContenedorDep) -> SesionIniciada:
    try:
        sesion = await c.iniciar_sesion.ejecutar(datos.correo, datos.contrasena)
    except CredencialesInvalidas as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(error)) from error
    return SesionIniciada(token=sesion.token, usuario=SesionUsuario.de(sesion.usuario))


@router.get("/yo")
async def yo(usuario: UsuarioActual) -> SesionUsuario:
    return SesionUsuario.de(usuario)


@router.put("/yo/contrasena", status_code=status.HTTP_204_NO_CONTENT)
async def cambiar_contrasena(
    datos: CambioContrasena, usuario: UsuarioActual, c: ContenedorDep
) -> Response:
    try:
        await c.cambiar_contrasena_propia.ejecutar(usuario, datos.actual, datos.nueva)
    except CredencialesInvalidas as error:
        raise HTTPException(400, "La contraseña actual no es correcta") from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
