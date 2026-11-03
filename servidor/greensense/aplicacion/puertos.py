"""Puertos: lo que los casos de uso necesitan del exterior, sin saber cómo se implementa."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from greensense.dominio.alertas import Alerta
from greensense.dominio.bitacora import RegistroBitacora
from greensense.dominio.cultivo import Cultivo
from greensense.dominio.historial import Agregado, Estadistica, Periodo
from greensense.dominio.modelos import Invernadero, Lectura, Nodo, Variable
from greensense.dominio.notificaciones import Envio, SuscripcionPush
from greensense.dominio.usuarios import Usuario


class RepositorioLecturas(Protocol):
    async def guardar(self, lectura: Lectura) -> bool:
        """Guarda la lectura. Devuelve False si ya existía (reenvío del nodo)."""
        ...

    async def ultima(self, nodo_id: str) -> Lectura | None: ...

    async def primera(self, nodo_id: str) -> Lectura | None: ...

    async def en_rango(
        self, nodo_id: str, desde: datetime, hasta: datetime, limite: int
    ) -> list[Lectura]:
        """Lecturas con desde <= ts < hasta, en orden cronológico, hasta `limite`."""
        ...

    async def agregadas(
        self, nodo_id: str, desde: datetime, hasta: datetime, periodo: Periodo
    ) -> list[Agregado]:
        """Una fila por hora o día local con lecturas, en orden cronológico."""
        ...

    async def estadisticas(
        self, nodo_id: str, desde: datetime, hasta: datetime
    ) -> tuple[int, dict[Variable, Estadistica | None]]:
        """Cuántas lecturas hay en el rango y el mínimo, máximo y promedio de cada variable."""
        ...


class RepositorioNodos(Protocol):
    async def obtener(self, nodo_id: str) -> Nodo | None: ...

    async def listar(self) -> list[Nodo]: ...

    async def guardar(self, nodo: Nodo) -> None: ...


class RepositorioInvernaderos(Protocol):
    async def obtener(self, invernadero_id: str) -> Invernadero | None: ...

    async def listar(self) -> list[Invernadero]: ...

    async def guardar(self, invernadero: Invernadero) -> None: ...

    async def borrar(self, invernadero_id: str) -> None: ...


class RepositorioCultivos(Protocol):
    async def obtener(self, cultivo_id: str) -> Cultivo | None: ...

    async def listar(self) -> list[Cultivo]: ...

    async def guardar(self, cultivo: Cultivo) -> None: ...

    async def borrar(self, cultivo_id: str) -> None: ...


class RepositorioAlertas(Protocol):
    async def guardar(self, alerta: Alerta) -> Alerta:
        """Inserta o actualiza. Devuelve la alerta con su id."""
        ...

    async def obtener(self, alerta_id: int) -> Alerta | None: ...

    async def activas(self, nodo_id: str | None = None) -> list[Alerta]: ...

    async def listar(self, solo_activas: bool = False, limite: int = 100) -> list[Alerta]:
        """Las más recientes primero."""
        ...

    async def en_rango(
        self, desde: datetime, hasta: datetime, nodo_id: str | None = None
    ) -> list[Alerta]:
        """Alertas iniciadas con desde <= iniciada_en < hasta, en orden cronológico."""
        ...


class RepositorioSuscripciones(Protocol):
    async def guardar(self, suscripcion: SuscripcionPush) -> SuscripcionPush:
        """Si el endpoint ya existe, actualiza sus claves y su usuario (el navegador cambió
        de sesión). Devuelve la suscripción con id."""
        ...

    async def obtener(self, suscripcion_id: int) -> SuscripcionPush | None: ...

    async def listar(self) -> list[SuscripcionPush]: ...

    async def borrar(self, suscripcion_id: int) -> None: ...

    async def borrar_por_endpoint(self, endpoint: str, usuario_id: int) -> bool:
        """Solo borra la suscripción si es de ese usuario."""
        ...


class RepositorioEnvios(Protocol):
    async def crear(self, envios: list[Envio]) -> None: ...

    async def pendientes(self, ahora: datetime, limite: int = 50) -> list[Envio]:
        """Envíos pendientes cuyo próximo intento ya llegó."""
        ...

    async def guardar(self, envio: Envio) -> None: ...


class RepositorioUsuarios(Protocol):
    async def obtener(self, usuario_id: int) -> Usuario | None: ...

    async def por_correo(self, correo: str) -> Usuario | None: ...

    async def listar(self) -> list[Usuario]: ...

    async def guardar(self, usuario: Usuario) -> Usuario:
        """Inserta o actualiza. Lanza CorreoDuplicado si el correo ya es de otro usuario."""
        ...


class RepositorioBitacora(Protocol):
    async def agregar(self, registro: RegistroBitacora) -> RegistroBitacora: ...

    async def listar(
        self, limite: int = 100, antes_de: int | None = None
    ) -> list[RegistroBitacora]:
        """Los más recientes primero. `antes_de` sirve para paginar por id."""
        ...


class HasherContrasenas(Protocol):
    def generar(self, contrasena: str) -> str: ...

    def verificar(self, hash_guardado: str, contrasena: str) -> bool: ...


class TokenInvalido(Exception):
    pass


class EmisorTokens(Protocol):
    def emitir(self, usuario: Usuario) -> str: ...

    def leer(self, token: str) -> int:
        """Devuelve el id del usuario. Lanza TokenInvalido si venció o fue alterado."""
        ...


class SuscripcionVencida(Exception):
    """El navegador ya no acepta notificaciones en esa suscripción."""


class ErrorPush(Exception):
    """Falla temporal al enviar una notificación: se puede reintentar."""


class ServicioPush(Protocol):
    async def enviar(self, suscripcion: SuscripcionPush, carga: dict[str, Any]) -> None:
        """Lanza SuscripcionVencida o ErrorPush si no se pudo entregar."""
        ...


class Despertador(Protocol):
    """Avisa a la tarea de envío que hay notificaciones nuevas."""

    def avisar(self) -> None: ...


class Reloj(Protocol):
    def ahora(self) -> datetime:
        """Hora actual con zona horaria."""
        ...


@dataclass(frozen=True)
class Evento:
    tipo: str
    datos: dict[str, Any] = field(default_factory=dict)


class PublicadorEventos(Protocol):
    """Avisa a los clientes conectados (panel en tiempo real)."""

    def publicar(self, evento: Evento) -> None: ...

    def suscribir(self) -> AsyncGenerator[Evento]:
        """Usar con contextlib.aclosing para soltar la suscripción al terminar."""
        ...
