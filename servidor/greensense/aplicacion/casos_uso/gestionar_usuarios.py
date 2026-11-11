"""Alta y modificación de usuarios. No se borran: se desactivan, para conservar la
bitácora y quién atendió cada alerta."""

from dataclasses import dataclass, replace

from greensense.aplicacion.casos_uso.bitacora import Anotador, describir_cambios
from greensense.aplicacion.errores import Conflicto, NoEncontrado
from greensense.aplicacion.puertos import HasherContrasenas, Reloj, RepositorioUsuarios
from greensense.dominio.bitacora import Accion, Objeto
from greensense.dominio.usuarios import (
    Rol,
    Usuario,
    normalizar_correo,
    validar_contrasena,
    validar_nombre,
)


class UltimoAdministrador(Conflicto):
    def __init__(self) -> None:
        super().__init__("debe quedar al menos un administrador activo")


@dataclass(frozen=True)
class CambiosUsuario:
    nombre: str | None = None
    correo: str | None = None
    rol: Rol | None = None
    activo: bool | None = None
    contrasena: str | None = None


class ListarUsuarios:
    def __init__(self, usuarios: RepositorioUsuarios) -> None:
        self._usuarios = usuarios

    async def ejecutar(self) -> list[Usuario]:
        return sorted(await self._usuarios.listar(), key=lambda u: u.nombre.lower())


class CrearUsuario:
    def __init__(
        self,
        usuarios: RepositorioUsuarios,
        hasher: HasherContrasenas,
        reloj: Reloj,
        anotador: Anotador,
    ) -> None:
        self._usuarios = usuarios
        self._hasher = hasher
        self._reloj = reloj
        self._anotador = anotador

    async def ejecutar(
        self, actor: Usuario | None, nombre: str, correo: str, rol: Rol, contrasena: str
    ) -> Usuario:
        usuario = await self._usuarios.guardar(
            Usuario(
                nombre=validar_nombre(nombre),
                correo=normalizar_correo(correo),
                rol=rol,
                hash_contrasena=self._hasher.generar(validar_contrasena(contrasena)),
                creado_en=self._reloj.ahora(),
            )
        )
        await self._anotador.anotar(
            actor, Accion.ALTA, Objeto.USUARIO, usuario.id, f"{usuario.correo} ({rol})"
        )
        return usuario


class ModificarUsuario:
    def __init__(
        self, usuarios: RepositorioUsuarios, hasher: HasherContrasenas, anotador: Anotador
    ) -> None:
        self._usuarios = usuarios
        self._hasher = hasher
        self._anotador = anotador

    async def ejecutar(self, actor: Usuario | None, usuario_id: int, cambios: CambiosUsuario):
        antes = await self._usuarios.obtener(usuario_id)
        if antes is None:
            raise NoEncontrado("el usuario", usuario_id)

        despues = antes
        if cambios.nombre is not None:
            despues = replace(despues, nombre=validar_nombre(cambios.nombre))
        if cambios.correo is not None:
            despues = replace(despues, correo=normalizar_correo(cambios.correo))
        if cambios.rol is not None:
            despues = replace(despues, rol=cambios.rol)
        if cambios.activo is not None:
            despues = replace(despues, activo=cambios.activo)
        if cambios.contrasena is not None:
            nuevo_hash = self._hasher.generar(validar_contrasena(cambios.contrasena))
            despues = replace(despues, hash_contrasena=nuevo_hash)

        if _es_admin_activo(antes) and not _es_admin_activo(despues):
            otros = [u for u in await self._usuarios.listar() if u.id != antes.id]
            if not any(_es_admin_activo(u) for u in otros):
                raise UltimoAdministrador()

        despues = await self._usuarios.guardar(despues)
        await self._anotar(actor, antes, despues, cambios.contrasena is not None)
        return despues

    async def _anotar(self, actor, antes: Usuario, despues: Usuario, contrasena: bool) -> None:
        if antes.activo != despues.activo:
            accion = Accion.ALTA if despues.activo else Accion.BAJA
            await self._anotador.anotar(actor, accion, Objeto.USUARIO, despues.id, despues.correo)
        detalle = describir_cambios(antes, despues, ("nombre", "correo", "rol"))
        if contrasena:
            detalle = "; ".join(filter(None, [detalle, "contraseña restablecida"]))
        if detalle:
            await self._anotador.anotar(
                actor, Accion.MODIFICAR, Objeto.USUARIO, despues.id, detalle
            )


def _es_admin_activo(usuario: Usuario) -> bool:
    return usuario.activo and usuario.rol is Rol.ADMINISTRADOR


class CrearAdministradorInicial:
    """Al arrancar sin usuarios, crea el administrador indicado en la configuración."""

    def __init__(self, usuarios: RepositorioUsuarios, crear: CrearUsuario) -> None:
        self._usuarios = usuarios
        self._crear = crear

    async def ejecutar(self, correo: str, contrasena: str) -> Usuario | None:
        if await self._usuarios.listar():
            return None
        return await self._crear.ejecutar(
            None, "Administrador", correo, Rol.ADMINISTRADOR, contrasena
        )
