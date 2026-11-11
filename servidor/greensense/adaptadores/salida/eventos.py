import asyncio
import contextlib
from collections.abc import AsyncGenerator

from greensense.aplicacion.puertos import Evento


class DifusorEventos:
    """Reparte los eventos a cada cliente suscrito, dentro del mismo proceso.

    Cada suscriptor tiene una cola acotada: si un cliente no consume a tiempo,
    pierde eventos en lugar de frenar la recepción de lecturas.
    """

    def __init__(self, capacidad: int = 100) -> None:
        self._capacidad = capacidad
        self._colas: set[asyncio.Queue[Evento]] = set()

    @property
    def suscriptores(self) -> int:
        return len(self._colas)

    def publicar(self, evento: Evento) -> None:
        for cola in list(self._colas):
            with contextlib.suppress(asyncio.QueueFull):
                cola.put_nowait(evento)

    async def suscribir(self) -> AsyncGenerator[Evento]:
        cola: asyncio.Queue[Evento] = asyncio.Queue(self._capacidad)
        self._colas.add(cola)
        try:
            while True:
                yield await cola.get()
        finally:
            self._colas.discard(cola)
