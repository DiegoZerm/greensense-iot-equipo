"""Datos y dobles de prueba compartidos."""

from datetime import UTC, datetime

from greensense.aplicacion.puertos import Evento
from greensense.dominio.alertas import Alerta, Severidad, TipoAlerta
from greensense.dominio.modelos import Lectura, Nodo, SensorAire, Variable
from greensense.dominio.usuarios import Rol, Usuario
from greensense.dominio.validacion import LecturaValidada

AHORA = datetime(2026, 11, 1, 16, 0, tzinfo=UTC)


class RelojFijo:
    def __init__(self, ahora: datetime = AHORA) -> None:
        self.actual = ahora

    def ahora(self) -> datetime:
        return self.actual


class EventosEnLista:
    def __init__(self) -> None:
        self.publicados: list[Evento] = []

    def publicar(self, evento: Evento) -> None:
        self.publicados.append(evento)

    async def suscribir(self):  # pragma: no cover - no se usa en estas pruebas
        raise NotImplementedError
        yield


def crear_lectura(**cambios) -> Lectura:
    datos = {
        "nodo_id": "nodo1",
        "arranque": 1,
        "seq": 0,
        "ts": AHORA,
        "temperatura": 24.3,
        "humedad_aire": 68.0,
        "humedad_sustrato": 52.0,
        "muestras": 5,
        "rssi": -60,
    } | cambios
    return Lectura(**datos)


def crear_nodo(**cambios) -> Nodo:
    datos = {
        "id": "nodo1",
        "invernadero_id": "inv1",
        "nombre": "Nodo de prueba",
        "sensor_aire": SensorAire.DHT22,
        "sensor_suelo": True,
    } | cambios
    return Nodo(**datos)


def validada(**cambios) -> LecturaValidada:
    return LecturaValidada(crear_lectura(**cambios), ())


class DespertadorFalso:
    def __init__(self) -> None:
        self.avisos = 0

    def avisar(self) -> None:
        self.avisos += 1


class PushFalso:
    """Registra lo enviado; `fallas` define qué excepción lanzar por endpoint."""

    def __init__(self) -> None:
        self.enviados: list[tuple[str, dict]] = []
        self.fallas: dict[str, Exception] = {}

    async def enviar(self, suscripcion, carga) -> None:
        if suscripcion.endpoint in self.fallas:
            raise self.fallas[suscripcion.endpoint]
        self.enviados.append((suscripcion.endpoint, carga))


def crear_alerta(**cambios) -> Alerta:
    datos = {
        "nodo_id": "nodo1",
        "tipo": TipoAlerta.UMBRAL,
        "variable": Variable.TEMPERATURA,
        "severidad": Severidad.ADVERTENCIA,
        "mensaje": "Temperatura alta: 29.0 °C (máximo 28.0 °C)",
        "recomendacion": "Ventilar o sombrear el invernadero.",
        "valor": 29.0,
        "limite": 28.0,
        "iniciada_en": AHORA,
        "actualizada_en": AHORA,
    } | cambios
    return Alerta(**datos)


def crear_usuario(**cambios) -> Usuario:
    """Sin id: el repositorio se lo asigna al guardarlo. El hash no corresponde a ninguna
    contraseña; para iniciar sesión, crear el usuario con el caso de uso CrearUsuario."""
    datos = {
        "nombre": "Ana Administradora",
        "correo": "ana@ejemplo.com",
        "rol": Rol.ADMINISTRADOR,
        "hash_contrasena": "sin-hash",
        "creado_en": AHORA,
    } | cambios
    return Usuario(**datos)
