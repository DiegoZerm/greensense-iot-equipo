"""Historial: series de lecturas, agregados, resumen y reportes CSV."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel

from greensense.adaptadores.entrada.api.dependencias import ContenedorDep, con_permiso
from greensense.adaptadores.entrada.api.esquemas import LecturaSalida
from greensense.aplicacion.casos_uso.consultar_historial import ArchivoCsv
from greensense.dominio.historial import Agregado, Estadistica, Periodo, Resumen
from greensense.dominio.modelos import Variable
from greensense.dominio.usuarios import Permiso

router = APIRouter(tags=["historial"])

Historial = con_permiso(Permiso.CONSULTAR_HISTORIAL)
Exportador = con_permiso(Permiso.EXPORTAR_REPORTES)

Desde = Annotated[datetime, Query(description="ISO 8601 con zona, incluido")]
Hasta = Annotated[datetime, Query(description="ISO 8601 con zona, no incluido")]


class EstadisticaSalida(BaseModel):
    minimo: float
    maximo: float
    promedio: float
    n: int


def _variables(datos: dict[Variable, Estadistica | None]) -> dict[str, EstadisticaSalida | None]:
    return {
        v.value: EstadisticaSalida(**vars(e)) if e is not None else None for v, e in datos.items()
    }


class SerieSalida(BaseModel):
    lecturas: list[LecturaSalida]
    completa: bool


class AgregadoSalida(BaseModel):
    inicio: datetime
    lecturas: int
    variables: dict[str, EstadisticaSalida | None]

    @classmethod
    def de(cls, a: Agregado) -> "AgregadoSalida":
        return cls(inicio=a.inicio, lecturas=a.lecturas, variables=_variables(a.variables))


class ResumenSalida(BaseModel):
    nodo_id: str
    desde: datetime
    hasta: datetime
    lecturas: int
    esperadas: int
    perdidas: int
    porcentaje_perdidas: float | None
    variables: dict[str, EstadisticaSalida | None]

    @classmethod
    def de(cls, r: Resumen) -> "ResumenSalida":
        return cls(
            nodo_id=r.nodo_id,
            desde=r.desde,
            hasta=r.hasta,
            lecturas=r.lecturas,
            esperadas=r.esperadas,
            perdidas=r.perdidas,
            porcentaje_perdidas=r.porcentaje_perdidas,
            variables=_variables(r.variables),
        )


@router.get("/lecturas")
async def lecturas(
    _: Historial, c: ContenedorDep, nodo: str, desde: Desde, hasta: Hasta
) -> SerieSalida:
    """Lecturas en el rango, en orden. Con `completa: false` el rango pasó del máximo
    (20 000) y conviene pedir los agregados."""
    serie = await c.consultar_lecturas.ejecutar(nodo, desde, hasta)
    return SerieSalida(
        lecturas=[LecturaSalida.model_validate(lec) for lec in serie.lecturas],
        completa=serie.completa,
    )


@router.get("/lecturas/agregadas")
async def agregadas(
    _: Historial,
    c: ContenedorDep,
    nodo: str,
    desde: Desde,
    hasta: Hasta,
    periodo: Periodo = Periodo.HORA,
) -> list[AgregadoSalida]:
    """Mínimo, máximo y promedio por hora o por día, en hora de México."""
    return [
        AgregadoSalida.de(a)
        for a in await c.consultar_agregados.ejecutar(nodo, desde, hasta, periodo)
    ]


@router.get("/reportes/resumen")
async def resumen(
    _: Historial, c: ContenedorDep, nodo: str, desde: Desde, hasta: Hasta
) -> ResumenSalida:
    """Estadísticas del rango y lecturas esperadas contra recibidas."""
    return ResumenSalida.de(await c.consultar_resumen.ejecutar(nodo, desde, hasta))


def _descarga(archivo: ArchivoCsv) -> Response:
    return Response(
        archivo.contenido.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{archivo.nombre}"'},
    )


@router.get("/reportes/lecturas.csv", response_class=Response)
async def lecturas_csv(
    actor: Exportador, c: ContenedorDep, nodo: str, desde: Desde, hasta: Hasta
) -> Response:
    """Queda registrado en la bitácora."""
    return _descarga(await c.exportar_lecturas.ejecutar(actor, nodo, desde, hasta))


@router.get("/reportes/alertas.csv", response_class=Response)
async def alertas_csv(
    actor: Exportador, c: ContenedorDep, desde: Desde, hasta: Hasta, nodo: str | None = None
) -> Response:
    """Queda registrado en la bitácora."""
    return _descarga(await c.exportar_alertas.ejecutar(actor, desde, hasta, nodo))
