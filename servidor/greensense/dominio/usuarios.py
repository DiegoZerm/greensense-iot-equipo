"""Usuarios, roles y la matriz de permisos de la propuesta."""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from greensense.dominio.alertas import TipoAlerta


class Rol(StrEnum):
    OPERADOR = "operador"
    SUPERVISOR = "supervisor"
    TECNICO = "tecnico"
    ADMINISTRADOR = "administrador"


class Permiso(StrEnum):
    VER_PANEL = "ver_panel"
    NOTIFICACIONES_CULTIVO = "notificaciones_cultivo"
    NOTIFICACIONES_DISPOSITIVO = "notificaciones_dispositivo"
    CONSULTAR_HISTORIAL = "consultar_historial"
    ATENDER_ALERTAS = "atender_alertas"
    EXPORTAR_REPORTES = "exportar_reportes"
    GESTIONAR_NODOS = "gestionar_nodos"
    CONFIGURAR_CULTIVOS = "configurar_cultivos"
    ADMINISTRAR_USUARIOS = "administrar_usuarios"
    CONSULTAR_BITACORA = "consultar_bitacora"


_TODOS = (
    Permiso.VER_PANEL,
    Permiso.CONSULTAR_HISTORIAL,
    Permiso.ATENDER_ALERTAS,
)

# Tabla "Permisos por tipo de usuario" de la propuesta.
PERMISOS: dict[Rol, frozenset[Permiso]] = {
    Rol.OPERADOR: frozenset({*_TODOS, Permiso.NOTIFICACIONES_CULTIVO}),
    Rol.SUPERVISOR: frozenset(
        {
            *_TODOS,
            Permiso.NOTIFICACIONES_CULTIVO,
            Permiso.EXPORTAR_REPORTES,
            Permiso.CONSULTAR_BITACORA,
        }
    ),
    Rol.TECNICO: frozenset({*_TODOS, Permiso.NOTIFICACIONES_DISPOSITIVO, Permiso.GESTIONAR_NODOS}),
    Rol.ADMINISTRADOR: frozenset(Permiso),
}

# Las alertas de cultivo avisan de las condiciones del invernadero; las de dispositivo,
# de fallas del nodo.
_PERMISO_ALERTA = {
    TipoAlerta.UMBRAL: Permiso.NOTIFICACIONES_CULTIVO,
    TipoAlerta.HONGOS: Permiso.NOTIFICACIONES_CULTIVO,
    TipoAlerta.SENSOR: Permiso.NOTIFICACIONES_DISPOSITIVO,
    TipoAlerta.DESCONEXION: Permiso.NOTIFICACIONES_DISPOSITIVO,
}


def permiso_para_notificar(tipo: TipoAlerta) -> Permiso:
    return _PERMISO_ALERTA[tipo]


_PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LONGITUD_MINIMA_CONTRASENA = 8


class DatosUsuarioInvalidos(ValueError):
    pass


def normalizar_correo(correo: str) -> str:
    correo = correo.strip().lower()
    if not _PATRON_CORREO.match(correo) or len(correo) > 254:
        raise DatosUsuarioInvalidos(f"'{correo}' no es un correo válido")
    return correo


def validar_contrasena(contrasena: str) -> str:
    if len(contrasena) < LONGITUD_MINIMA_CONTRASENA:
        raise DatosUsuarioInvalidos(
            f"la contraseña debe tener al menos {LONGITUD_MINIMA_CONTRASENA} caracteres"
        )
    return contrasena


def validar_nombre(nombre: str) -> str:
    nombre = nombre.strip()
    if not nombre or len(nombre) > 100:
        raise DatosUsuarioInvalidos("el nombre debe tener entre 1 y 100 caracteres")
    return nombre


@dataclass(frozen=True)
class Usuario:
    nombre: str
    correo: str
    rol: Rol
    hash_contrasena: str
    creado_en: datetime
    activo: bool = True
    id: int | None = None

    @property
    def permisos(self) -> frozenset[Permiso]:
        return PERMISOS[self.rol] if self.activo else frozenset()

    def puede(self, permiso: Permiso) -> bool:
        return permiso in self.permisos
