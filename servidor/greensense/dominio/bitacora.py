"""Bitácora: quién cambió la configuración, dio de alta o de baja algo, o exportó datos."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Accion(StrEnum):
    INICIAR_SESION = "iniciar_sesion"
    CREAR = "crear"
    MODIFICAR = "modificar"
    BORRAR = "borrar"
    ALTA = "alta"
    BAJA = "baja"
    EXPORTAR = "exportar"


class Objeto(StrEnum):
    USUARIO = "usuario"
    CULTIVO = "cultivo"
    INVERNADERO = "invernadero"
    NODO = "nodo"
    REPORTE = "reporte"


@dataclass(frozen=True)
class RegistroBitacora:
    usuario_id: int | None
    """None si lo hizo el sistema o la línea de comandos."""
    accion: Accion
    objeto: Objeto
    objeto_id: str
    detalle: str
    ts: datetime
    id: int | None = None
