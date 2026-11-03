"""ServicioWebPush contra un servicio push falso que corre en un hilo local."""

import base64
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from greensense.adaptadores.salida.webpush import ServicioWebPush, generar_claves_vapid
from greensense.aplicacion.puertos import ErrorPush, SuscripcionVencida
from greensense.dominio.notificaciones import SuscripcionPush
from tests.fabricas import AHORA

pytestmark = pytest.mark.anyio


def _b64url(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


class ServicioPushFalso:
    def __init__(self, estado: int) -> None:
        self.recibidas: list[tuple[dict, bytes]] = []
        servicio = self

        class Manejador(BaseHTTPRequestHandler):
            def do_POST(self):
                cuerpo = self.rfile.read(int(self.headers["Content-Length"]))
                # Los nombres de las cabeceras HTTP no distinguen mayúsculas.
                cabeceras = {k.lower(): v for k, v in self.headers.items()}
                servicio.recibidas.append((cabeceras, cuerpo))
                self.send_response(estado)
                self.end_headers()

            def log_message(self, *args):
                pass

        self.servidor = HTTPServer(("127.0.0.1", 0), Manejador)
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.servidor.server_port}/push/abc"

    def cerrar(self) -> None:
        self.servidor.shutdown()


@pytest.fixture
def servicio_push(request):
    falso = ServicioPushFalso(getattr(request, "param", 201))
    yield falso
    falso.cerrar()


def _suscripcion(endpoint: str) -> SuscripcionPush:
    # Claves como las que genera un navegador al suscribirse.
    cliente = ec.generate_private_key(ec.SECP256R1()).public_key()
    p256dh = cliente.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return SuscripcionPush(endpoint, _b64url(p256dh), _b64url(os.urandom(16)), AHORA, 1)


@pytest.fixture
def push() -> ServicioWebPush:
    privada, _ = generar_claves_vapid()
    return ServicioWebPush(privada, "mailto:pruebas@greensense.local")


async def test_envia_cifrado_y_firmado_con_vapid(push, servicio_push):
    await push.enviar(_suscripcion(servicio_push.url), {"notification": {"title": "Hola"}})

    ((cabeceras, cuerpo),) = servicio_push.recibidas
    assert cabeceras["content-encoding"] == "aes128gcm"
    assert cabeceras["authorization"].startswith("vapid t=")
    assert cabeceras["urgency"] == "high"
    assert cabeceras["ttl"] == "86400"
    assert b"Hola" not in cuerpo  # va cifrado


@pytest.mark.parametrize("servicio_push", [404, 410], indirect=True)
async def test_suscripcion_vencida(push, servicio_push):
    with pytest.raises(SuscripcionVencida):
        await push.enviar(_suscripcion(servicio_push.url), {})


@pytest.mark.parametrize("servicio_push", [429, 500], indirect=True)
async def test_error_temporal(push, servicio_push):
    with pytest.raises(ErrorPush, match=r"HTTP (429|500)"):
        await push.enviar(_suscripcion(servicio_push.url), {})


async def test_servicio_inalcanzable(push):
    with pytest.raises(ErrorPush, match="sin conexión"):
        await push.enviar(_suscripcion("http://127.0.0.1:9/push"), {})


def test_claves_vapid_tienen_el_tamano_correcto():
    privada, publica = generar_claves_vapid()

    assert len(base64.urlsafe_b64decode(privada + "==")) == 32
    publica_bytes = base64.urlsafe_b64decode(publica + "==")
    assert len(publica_bytes) == 65 and publica_bytes[0] == 4
