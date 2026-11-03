from typing import Annotated

from fastapi import APIRouter, Query

from greensense.adaptadores.entrada.api.dependencias import ContenedorDep, con_permiso
from greensense.adaptadores.entrada.api.esquemas import BitacoraSalida
from greensense.dominio.usuarios import Permiso

router = APIRouter(tags=["bitácora"])

Auditor = con_permiso(Permiso.CONSULTAR_BITACORA)


@router.get("/bitacora")
async def consultar(
    _: Auditor,
    c: ContenedorDep,
    limite: Annotated[int, Query(ge=1, le=500)] = 100,
    antes_de: Annotated[int | None, Query(description="Para pedir la página siguiente")] = None,
) -> list[BitacoraSalida]:
    """Los registros más recientes primero."""
    entradas = await c.consultar_bitacora.ejecutar(limite=limite, antes_de=antes_de)
    return [BitacoraSalida.de(e) for e in entradas]
