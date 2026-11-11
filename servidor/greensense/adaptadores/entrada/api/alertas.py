from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from greensense.adaptadores.entrada.api.dependencias import ContenedorDep, VerPanel, con_permiso
from greensense.adaptadores.entrada.api.esquemas import AlertaSalida
from greensense.aplicacion.errores import AlertaNoEncontrada
from greensense.dominio.alertas import FiltroAlertas, Severidad
from greensense.dominio.modelos import Variable
from greensense.dominio.usuarios import Permiso

router = APIRouter(tags=["alertas"])

Atiende = con_permiso(Permiso.ATENDER_ALERTAS)


@router.get("/alertas")
async def consultar_alertas(
    _: VerPanel,
    c: ContenedorDep,
    activas: bool = False,
    limite: Annotated[int, Query(ge=1, le=500)] = 100,
    severidad: Severidad | None = None,
    variable: Variable | None = None,
    desde: Annotated[datetime | None, Query(description="ISO 8601 con zona, incluido")] = None,
    hasta: Annotated[datetime | None, Query(description="ISO 8601 con zona, no incluido")] = None,
) -> list[AlertaSalida]:
    """Alertas más recientes primero. Con `activas=true`, solo las que no se han resuelto.

    `severidad`, `variable`, `desde` y `hasta` filtran el historial; las fechas se comparan
    con el inicio de la alerta.
    """
    filtro = FiltroAlertas(severidad, variable, desde, hasta)
    alertas = await c.consultar_alertas.ejecutar(solo_activas=activas, limite=limite, filtro=filtro)
    return [AlertaSalida.model_validate(a) for a in alertas]


@router.post("/alertas/{alerta_id}/atender")
async def atender_alerta(alerta_id: int, usuario: Atiende, c: ContenedorDep) -> AlertaSalida:
    """Registra quién atendió la alerta y cuándo."""
    try:
        alerta = await c.atender_alerta.ejecutar(alerta_id, usuario)
    except AlertaNoEncontrada as error:
        raise HTTPException(404, str(error)) from error
    return AlertaSalida.model_validate(alerta)
