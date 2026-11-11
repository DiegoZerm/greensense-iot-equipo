from dataclasses import replace
from datetime import timedelta

import pytest

from greensense.adaptadores.salida.memoria import RepositorioUsuariosMemoria
from greensense.adaptadores.salida.seguridad import EmisorJwt
from greensense.aplicacion.casos_uso.gestionar_usuarios import (
    CambiosUsuario,
    CrearAdministradorInicial,
    CrearUsuario,
    ModificarUsuario,
    UltimoAdministrador,
)
from greensense.aplicacion.casos_uso.sesion import (
    CambiarContrasenaPropia,
    IniciarSesion,
    UsuarioDelToken,
)
from greensense.aplicacion.errores import CorreoDuplicado, CredencialesInvalidas, NoEncontrado
from greensense.aplicacion.puertos import TokenInvalido
from greensense.dominio.bitacora import Accion, Objeto
from greensense.dominio.usuarios import DatosUsuarioInvalidos, Rol

pytestmark = pytest.mark.anyio

CONTRASENA = "contrasena-segura"


@pytest.fixture
def repo() -> RepositorioUsuariosMemoria:
    """Sin usuarios: estas pruebas crean los suyos con contraseña real."""
    return RepositorioUsuariosMemoria()


@pytest.fixture
def tokens(reloj):
    return EmisorJwt("s" * 40, timedelta(hours=12), reloj)


@pytest.fixture
def crear(repo, hasher, reloj, anotador):
    return CrearUsuario(repo, hasher, reloj, anotador)


@pytest.fixture
def modificar(repo, hasher, anotador):
    return ModificarUsuario(repo, hasher, anotador)


@pytest.fixture
async def admin(crear):
    return await crear.ejecutar(None, "Ana", "ana@ejemplo.com", Rol.ADMINISTRADOR, CONTRASENA)


@pytest.fixture
async def operador(crear, admin):
    return await crear.ejecutar(admin, "Óscar", "Oscar@Ejemplo.com", Rol.OPERADOR, CONTRASENA)


async def test_crear_usuario_guarda_hash_y_anota(operador, admin, bitacora, hasher):
    assert operador.correo == "oscar@ejemplo.com"
    assert operador.hash_contrasena != CONTRASENA
    assert hasher.verificar(operador.hash_contrasena, CONTRASENA)

    ultimo = (await bitacora.listar())[0]
    assert (ultimo.usuario_id, ultimo.accion, ultimo.objeto) == (
        admin.id,
        Accion.ALTA,
        Objeto.USUARIO,
    )
    assert ultimo.objeto_id == str(operador.id)


async def test_correo_repetido_se_rechaza(crear, operador):
    with pytest.raises(CorreoDuplicado):
        await crear.ejecutar(None, "Otro", "OSCAR@ejemplo.com", Rol.TECNICO, CONTRASENA)


async def test_datos_invalidos_se_rechazan(crear):
    with pytest.raises(DatosUsuarioInvalidos):
        await crear.ejecutar(None, "X", "x@ejemplo.com", Rol.OPERADOR, "corta")
    with pytest.raises(DatosUsuarioInvalidos):
        await crear.ejecutar(None, "  ", "x@ejemplo.com", Rol.OPERADOR, CONTRASENA)


async def test_iniciar_sesion(repo, hasher, tokens, anotador, bitacora, operador):
    iniciar = IniciarSesion(repo, hasher, tokens, anotador)

    sesion = await iniciar.ejecutar(" OSCAR@ejemplo.com", CONTRASENA)

    assert sesion.usuario == operador
    assert tokens.leer(sesion.token) == operador.id
    assert (await bitacora.listar())[0].accion is Accion.INICIAR_SESION


@pytest.mark.parametrize(
    ("correo", "contrasena"),
    [("oscar@ejemplo.com", "equivocada"), ("nadie@ejemplo.com", CONTRASENA), ("no-correo", "x")],
)
async def test_credenciales_invalidas(repo, hasher, tokens, anotador, operador, correo, contrasena):
    with pytest.raises(CredencialesInvalidas):
        await IniciarSesion(repo, hasher, tokens, anotador).ejecutar(correo, contrasena)


async def test_usuario_inactivo_no_entra_y_pierde_su_sesion(
    repo, hasher, tokens, anotador, modificar, admin, operador
):
    token = (
        await IniciarSesion(repo, hasher, tokens, anotador).ejecutar(operador.correo, CONTRASENA)
    ).token
    assert await UsuarioDelToken(repo, tokens).ejecutar(token) == operador

    await modificar.ejecutar(admin, operador.id, CambiosUsuario(activo=False))

    with pytest.raises(TokenInvalido):
        await UsuarioDelToken(repo, tokens).ejecutar(token)
    with pytest.raises(CredencialesInvalidas):
        await IniciarSesion(repo, hasher, tokens, anotador).ejecutar(operador.correo, CONTRASENA)


async def test_cambio_de_rol_aplica_sin_volver_a_entrar(repo, tokens, modificar, admin, operador):
    token = tokens.emitir(operador)

    await modificar.ejecutar(admin, operador.id, CambiosUsuario(rol=Rol.SUPERVISOR))

    assert (await UsuarioDelToken(repo, tokens).ejecutar(token)).rol is Rol.SUPERVISOR


async def test_modificar_anota_solo_lo_que_cambio(modificar, admin, operador, bitacora):
    await modificar.ejecutar(
        admin, operador.id, CambiosUsuario(nombre="Óscar", rol=Rol.TECNICO, contrasena="nueva-123")
    )

    ultimo = (await bitacora.listar())[0]
    assert ultimo.accion is Accion.MODIFICAR
    assert ultimo.detalle == "rol: operador → tecnico; contraseña restablecida"


async def test_desactivar_y_reactivar_se_anota_como_baja_y_alta(
    modificar, admin, operador, bitacora
):
    await modificar.ejecutar(admin, operador.id, CambiosUsuario(activo=False))
    await modificar.ejecutar(admin, operador.id, CambiosUsuario(activo=True))

    assert [r.accion for r in (await bitacora.listar())[:2]] == [Accion.ALTA, Accion.BAJA]


async def test_no_se_puede_quitar_el_ultimo_administrador(modificar, crear, admin):
    with pytest.raises(UltimoAdministrador):
        await modificar.ejecutar(admin, admin.id, CambiosUsuario(activo=False))
    with pytest.raises(UltimoAdministrador):
        await modificar.ejecutar(admin, admin.id, CambiosUsuario(rol=Rol.OPERADOR))

    otro = await crear.ejecutar(admin, "Beto", "beto@ejemplo.com", Rol.ADMINISTRADOR, CONTRASENA)
    cambiado = await modificar.ejecutar(otro, admin.id, CambiosUsuario(rol=Rol.OPERADOR))
    assert cambiado.rol is Rol.OPERADOR


async def test_modificar_usuario_inexistente(modificar, admin):
    with pytest.raises(NoEncontrado):
        await modificar.ejecutar(admin, 99, CambiosUsuario(nombre="X"))


async def test_cambiar_contrasena_propia(repo, hasher, anotador, operador):
    cambiar = CambiarContrasenaPropia(repo, hasher, anotador)

    with pytest.raises(CredencialesInvalidas):
        await cambiar.ejecutar(operador, "equivocada", "nueva-contrasena")
    await cambiar.ejecutar(operador, CONTRASENA, "nueva-contrasena")

    guardado = await repo.obtener(operador.id)
    assert hasher.verificar(guardado.hash_contrasena, "nueva-contrasena")


async def test_administrador_inicial_solo_si_no_hay_usuarios(repo, crear):
    inicial = CrearAdministradorInicial(repo, crear)

    primero = await inicial.ejecutar("admin@ejemplo.com", CONTRASENA)
    segundo = await inicial.ejecutar("otro@ejemplo.com", CONTRASENA)

    assert primero.rol is Rol.ADMINISTRADOR
    assert segundo is None
    assert [u.correo for u in await repo.listar()] == ["admin@ejemplo.com"]


async def test_hash_viejo_no_coincide_tras_restablecer(modificar, admin, operador, hasher, repo):
    await modificar.ejecutar(admin, operador.id, CambiosUsuario(contrasena="otra-contrasena"))
    guardado = await repo.obtener(operador.id)
    assert not hasher.verificar(guardado.hash_contrasena, CONTRASENA)
    assert replace(guardado, hash_contrasena=operador.hash_contrasena) == operador
