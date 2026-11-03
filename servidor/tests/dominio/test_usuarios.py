import pytest

from greensense.dominio.alertas import TipoAlerta
from greensense.dominio.usuarios import (
    PERMISOS,
    DatosUsuarioInvalidos,
    Permiso,
    Rol,
    normalizar_correo,
    permiso_para_notificar,
    validar_contrasena,
)
from tests.fabricas import crear_usuario

P = Permiso
# Tabla "Permisos por tipo de usuario" de la propuesta, fila por fila:
# (permiso, operador, supervisor, técnico, administrador)
MATRIZ = [
    (P.VER_PANEL, 1, 1, 1, 1),
    (P.NOTIFICACIONES_CULTIVO, 1, 1, 0, 1),
    (P.NOTIFICACIONES_DISPOSITIVO, 0, 0, 1, 1),
    (P.CONSULTAR_HISTORIAL, 1, 1, 1, 1),
    (P.ATENDER_ALERTAS, 1, 1, 1, 1),
    (P.EXPORTAR_REPORTES, 0, 1, 0, 1),
    (P.GESTIONAR_NODOS, 0, 0, 1, 1),
    (P.CONFIGURAR_CULTIVOS, 0, 0, 0, 1),
    (P.ADMINISTRAR_USUARIOS, 0, 0, 0, 1),
    (P.CONSULTAR_BITACORA, 0, 1, 0, 1),
]
ROLES = [Rol.OPERADOR, Rol.SUPERVISOR, Rol.TECNICO, Rol.ADMINISTRADOR]


@pytest.mark.parametrize(("permiso", *[r.value for r in ROLES]), MATRIZ)
def test_matriz_de_permisos_de_la_propuesta(permiso, operador, supervisor, tecnico, administrador):
    for rol, esperado in zip(ROLES, (operador, supervisor, tecnico, administrador), strict=True):
        assert (permiso in PERMISOS[rol]) == bool(esperado), f"{rol} / {permiso}"


def test_la_matriz_cubre_todos_los_permisos():
    assert {fila[0] for fila in MATRIZ} == set(Permiso)


def test_usuario_inactivo_no_tiene_permisos():
    assert crear_usuario(activo=False).permisos == frozenset()
    assert not crear_usuario(activo=False).puede(Permiso.VER_PANEL)


@pytest.mark.parametrize(
    ("tipo", "permiso"),
    [
        (TipoAlerta.UMBRAL, Permiso.NOTIFICACIONES_CULTIVO),
        (TipoAlerta.HONGOS, Permiso.NOTIFICACIONES_CULTIVO),
        (TipoAlerta.SENSOR, Permiso.NOTIFICACIONES_DISPOSITIVO),
        (TipoAlerta.DESCONEXION, Permiso.NOTIFICACIONES_DISPOSITIVO),
    ],
)
def test_permiso_para_notificar_cada_tipo(tipo, permiso):
    assert permiso_para_notificar(tipo) is permiso


def test_correo_se_normaliza():
    assert normalizar_correo("  Diego@Ejemplo.COM ") == "diego@ejemplo.com"


@pytest.mark.parametrize("correo", ["", "sin-arroba", "a@b", "a b@c.com"])
def test_correo_invalido(correo):
    with pytest.raises(DatosUsuarioInvalidos):
        normalizar_correo(correo)


def test_contrasena_corta():
    with pytest.raises(DatosUsuarioInvalidos):
        validar_contrasena("1234567")
    assert validar_contrasena("12345678") == "12345678"
