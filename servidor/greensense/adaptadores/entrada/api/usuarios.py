from fastapi import APIRouter, status

from greensense.adaptadores.entrada.api.dependencias import ContenedorDep, con_permiso
from greensense.adaptadores.entrada.api.esquemas import UsuarioCambios, UsuarioNuevo, UsuarioSalida
from greensense.aplicacion.casos_uso.gestionar_usuarios import CambiosUsuario
from greensense.dominio.usuarios import Permiso

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

Administrador = con_permiso(Permiso.ADMINISTRAR_USUARIOS)


@router.get("")
async def listar(_: Administrador, c: ContenedorDep) -> list[UsuarioSalida]:
    return [UsuarioSalida.model_validate(u) for u in await c.listar_usuarios.ejecutar()]


@router.post("", status_code=status.HTTP_201_CREATED)
async def crear(datos: UsuarioNuevo, actor: Administrador, c: ContenedorDep) -> UsuarioSalida:
    usuario = await c.crear_usuario.ejecutar(
        actor, datos.nombre, datos.correo, datos.rol, datos.contrasena
    )
    return UsuarioSalida.model_validate(usuario)


@router.patch("/{usuario_id}")
async def modificar(
    usuario_id: int, datos: UsuarioCambios, actor: Administrador, c: ContenedorDep
) -> UsuarioSalida:
    cambios = CambiosUsuario(**datos.model_dump(exclude_unset=True))
    usuario = await c.modificar_usuario.ejecutar(actor, usuario_id, cambios)
    return UsuarioSalida.model_validate(usuario)
