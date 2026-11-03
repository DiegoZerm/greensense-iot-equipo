import asyncio
from contextlib import aclosing

import pytest

from greensense.adaptadores.salida.eventos import DifusorEventos
from greensense.aplicacion.puertos import Evento

pytestmark = pytest.mark.anyio


async def _recibir(difusor: DifusorEventos, cantidad: int) -> list[Evento]:
    recibidos = []
    async with aclosing(difusor.suscribir()) as flujo:
        async for evento in flujo:
            recibidos.append(evento)
            if len(recibidos) == cantidad:
                break
    return recibidos


async def test_cada_suscriptor_recibe_todos_los_eventos():
    difusor = DifusorEventos()
    tareas = [asyncio.create_task(_recibir(difusor, 2)) for _ in range(2)]
    await asyncio.sleep(0)

    difusor.publicar(Evento("lectura", {"n": 1}))
    difusor.publicar(Evento("nodo", {"n": 2}))

    for tarea in tareas:
        assert [e.tipo for e in await tarea] == ["lectura", "nodo"]


async def test_al_salir_se_quita_la_suscripcion():
    difusor = DifusorEventos()
    tarea = asyncio.create_task(_recibir(difusor, 1))
    await asyncio.sleep(0)
    assert difusor.suscriptores == 1

    difusor.publicar(Evento("lectura"))
    await tarea

    assert difusor.suscriptores == 0


async def test_un_cliente_lento_pierde_eventos_sin_bloquear():
    difusor = DifusorEventos(capacidad=1)
    tarea = asyncio.create_task(_recibir(difusor, 1))
    await asyncio.sleep(0)

    for n in range(5):
        difusor.publicar(Evento("lectura", {"n": n}))

    assert (await tarea)[0].datos == {"n": 0}


async def test_publicar_sin_suscriptores_no_falla():
    DifusorEventos().publicar(Evento("lectura"))
