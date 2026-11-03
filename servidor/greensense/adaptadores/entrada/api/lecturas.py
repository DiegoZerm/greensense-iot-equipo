from fastapi import APIRouter

from greensense.adaptadores.entrada.api.dependencias import ContenedorDep, VerPanel
from greensense.adaptadores.entrada.api.esquemas import EstadoActualSalida

router = APIRouter(tags=["lecturas"])


@router.get("/lecturas/ultimas")
async def consultar_ultimas(_: VerPanel, c: ContenedorDep) -> list[EstadoActualSalida]:
    """Cada nodo activo con su lectura más reciente (datos del panel)."""
    estados = await c.consultar_estado_actual.ejecutar()
    return [EstadoActualSalida.model_validate(estado) for estado in estados]
