"""Suscripciones push y la bandeja de salida de notificaciones."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


@dataclass(frozen=True)
class SuscripcionPush:
    """Datos que entrega el navegador al aceptar notificaciones."""

    endpoint: str
    p256dh: str
    auth: str
    creada_en: datetime
    usuario_id: int
    id: int | None = None


class EstadoEnvio(StrEnum):
    PENDIENTE = "pendiente"
    ENVIADO = "enviado"
    FALLIDO = "fallido"
    """Se agotaron los intentos."""
    DESCARTADO = "descartado"
    """La suscripción ya no existe en el navegador."""


MAXIMO_INTENTOS = 6
ESPERA_INICIAL = timedelta(seconds=30)


@dataclass(frozen=True)
class Envio:
    """Una notificación de una alerta para una suscripción."""

    alerta_id: int
    suscripcion_id: int
    proximo_intento_en: datetime
    estado: EstadoEnvio = EstadoEnvio.PENDIENTE
    intentos: int = 0
    enviado_en: datetime | None = None
    ultimo_error: str | None = None
    id: int | None = None


def espera_tras_fallo(intentos: int) -> timedelta:
    """30 s, 1, 2, 4 y 8 min: unos 15 minutos en total antes de darse por vencido."""
    return ESPERA_INICIAL * 2 ** (intentos - 1)
