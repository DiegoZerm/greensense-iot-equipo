from collections.abc import AsyncIterable
from contextlib import aclosing
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from greensense.adaptadores.entrada.api.dependencias import ContenedorDep, usuario_de_eventos
from greensense.adaptadores.entrada.api.esquemas import evento_a_json
from greensense.dominio.usuarios import Permiso, Usuario

router = APIRouter(tags=["tiempo real"])

RECONEXION_MS = 5000


@router.get("/eventos", response_class=EventSourceResponse)
async def eventos(
    usuario: Annotated[Usuario, Depends(usuario_de_eventos)], c: ContenedorDep
) -> AsyncIterable[ServerSentEvent]:
    """Flujo SSE con los eventos `lectura`, `nodo` y `alerta`.

    EventSource no manda encabezados, así que el token va en `?token=`.
    """
    if not usuario.puede(Permiso.VER_PANEL):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Tu rol no puede ver el panel")
    # aclosing cierra la suscripción en cuanto el cliente se desconecta.
    async with aclosing(c.eventos.suscribir()) as flujo:
        # Un primer mensaje inmediato: los proxys (el de `ng serve`, nginx) no entregan los
        # encabezados hasta recibir algo del cuerpo, y sin esto la app marca "Reconectando"
        # hasta que llega la siguiente lectura (hasta un minuto con un nodo real).
        yield ServerSentEvent(comment="conectado", retry=RECONEXION_MS)
        async for evento in flujo:
            yield ServerSentEvent(event=evento.tipo, data=evento_a_json(evento))
