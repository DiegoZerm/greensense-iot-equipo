import asyncio
import contextlib


class DespertadorAsyncio:
    """Despierta a la tarea de envío en cuanto hay notificaciones nuevas."""

    def __init__(self) -> None:
        self._evento = asyncio.Event()

    def avisar(self) -> None:
        self._evento.set()

    async def esperar(self, maximo_s: float) -> None:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._evento.wait(), maximo_s)
        self._evento.clear()
