"""Envío de notificaciones con el protocolo Web Push (RFC 8030) y claves VAPID."""

import asyncio
import base64
import json
import logging
from typing import Any

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush

from greensense.aplicacion.puertos import ErrorPush, SuscripcionVencida
from greensense.dominio.notificaciones import SuscripcionPush

log = logging.getLogger(__name__)

# Una notificación que no se pudo entregar en un día ya no sirve.
TTL_S = 24 * 3600


def _b64url(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def generar_claves_vapid() -> tuple[str, str]:
    """Devuelve (privada, pública) en base64url. La pública es la que usa el navegador."""
    privada = ec.generate_private_key(ec.SECP256R1())
    numero = privada.private_numbers().private_value.to_bytes(32, "big")
    publica = privada.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return _b64url(numero), _b64url(publica)


class ServicioWebPush:
    def __init__(self, clave_privada: str, contacto: str) -> None:
        self._clave_privada = clave_privada
        self._contacto = contacto

    async def enviar(self, suscripcion: SuscripcionPush, carga: dict[str, Any]) -> None:
        # pywebpush es síncrono: se ejecuta en un hilo para no detener el servidor.
        await asyncio.to_thread(self._enviar, suscripcion, json.dumps(carga))

    def _enviar(self, suscripcion: SuscripcionPush, datos: str) -> None:
        try:
            webpush(
                subscription_info={
                    "endpoint": suscripcion.endpoint,
                    "keys": {"p256dh": suscripcion.p256dh, "auth": suscripcion.auth},
                },
                data=datos,
                vapid_private_key=self._clave_privada,
                vapid_claims={"sub": self._contacto},
                ttl=TTL_S,
                headers={"Urgency": "high"},
                timeout=10,
            )
        except WebPushException as error:
            estado = error.response.status_code if error.response is not None else None
            # 404 y 410: el navegador ya no acepta esta suscripción.
            if estado in (404, 410):
                raise SuscripcionVencida(str(error)) from error
            raise ErrorPush(f"HTTP {estado}: {error.message}") from error
        except requests.RequestException as error:
            raise ErrorPush(f"sin conexión con el servicio push: {error}") from error


class ServicioPushDeshabilitado:
    """Se usa cuando no hay claves VAPID configuradas."""

    async def enviar(self, suscripcion: SuscripcionPush, carga: dict[str, Any]) -> None:
        raise ErrorPush("Web Push no está configurado (faltan las claves VAPID)")
