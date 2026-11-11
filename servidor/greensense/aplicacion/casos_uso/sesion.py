"""Inicio de sesión, usuario de cada petición y cambio de la contraseña propia."""

from dataclasses import dataclass, replace

from greensense.aplicacion.casos_uso.bitacora import Anotador
from greensense.aplicacion.errores import CredencialesInvalidas
from greensense.aplicacion.puertos import (
    EmisorTokens,
    HasherContrasenas,
    RepositorioUsuarios,
    TokenInvalido,
)
from greensense.dominio.bitacora import Accion, Objeto
from greensense.dominio.usuarios import (
    DatosUsuarioInvalidos,
    Usuario,
    normalizar_correo,
    validar_contrasena,
)


@dataclass(frozen=True)
class Sesion:
    token: str
    usuario: Usuario


class IniciarSesion:
    def __init__(
        self,
        usuarios: RepositorioUsuarios,
        hasher: HasherContrasenas,
        tokens: EmisorTokens,
        anotador: Anotador,
    ) -> None:
        self._usuarios = usuarios
        self._hasher = hasher
        self._tokens = tokens
        self._anotador = anotador
        # Hash de referencia: se verifica aunque el correo no exista, para que el tiempo de
        # respuesta no revele qué correos están registrados.
        self._hash_falso = hasher.generar("contrasena-que-nadie-usa")

    async def ejecutar(self, correo: str, contrasena: str) -> Sesion:
        try:
            correo = normalizar_correo(correo)
        except DatosUsuarioInvalidos as error:
            raise CredencialesInvalidas() from error
        usuario = await self._usuarios.por_correo(correo)
        hash_guardado = usuario.hash_contrasena if usuario else self._hash_falso
        correcta = self._hasher.verificar(hash_guardado, contrasena)
        if usuario is None or not correcta or not usuario.activo:
            raise CredencialesInvalidas()
        await self._anotador.anotar(usuario, Accion.INICIAR_SESION, Objeto.USUARIO, usuario.id)
        return Sesion(self._tokens.emitir(usuario), usuario)


class UsuarioDelToken:
    """Se consulta el usuario en cada petición: si lo desactivan o le cambian el rol,
    el cambio aplica de inmediato aunque su token siga vigente."""

    def __init__(self, usuarios: RepositorioUsuarios, tokens: EmisorTokens) -> None:
        self._usuarios = usuarios
        self._tokens = tokens

    async def ejecutar(self, token: str) -> Usuario:
        usuario = await self._usuarios.obtener(self._tokens.leer(token))
        if usuario is None or not usuario.activo:
            raise TokenInvalido("el usuario ya no está activo")
        return usuario


class CambiarContrasenaPropia:
    def __init__(
        self, usuarios: RepositorioUsuarios, hasher: HasherContrasenas, anotador: Anotador
    ) -> None:
        self._usuarios = usuarios
        self._hasher = hasher
        self._anotador = anotador

    async def ejecutar(self, usuario: Usuario, actual: str, nueva: str) -> None:
        if not self._hasher.verificar(usuario.hash_contrasena, actual):
            raise CredencialesInvalidas()
        validar_contrasena(nueva)
        await self._usuarios.guardar(replace(usuario, hash_contrasena=self._hasher.generar(nueva)))
        await self._anotador.anotar(
            usuario, Accion.MODIFICAR, Objeto.USUARIO, usuario.id, "cambió su contraseña"
        )
