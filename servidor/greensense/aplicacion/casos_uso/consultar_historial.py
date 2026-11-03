"""Historial de un nodo: lecturas, agregados, resumen y exportación a CSV."""

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timedelta

from greensense.aplicacion.casos_uso.bitacora import Anotador
from greensense.aplicacion.errores import NoEncontrado
from greensense.aplicacion.puertos import (
    Reloj,
    RepositorioAlertas,
    RepositorioLecturas,
    RepositorioNodos,
)
from greensense.dominio.alertas import Alerta
from greensense.dominio.bitacora import Accion, Objeto
from greensense.dominio.historial import (
    LECTURAS_MAXIMAS,
    ZONA_HORARIA,
    Agregado,
    Periodo,
    RangoInvalido,
    Resumen,
    lecturas_esperadas,
    validar_rango,
)
from greensense.dominio.modelos import Lectura, Nodo, Variable
from greensense.dominio.usuarios import Usuario


async def _nodo(nodos: RepositorioNodos, nodo_id: str) -> Nodo:
    nodo = await nodos.obtener(nodo_id)
    if nodo is None:
        raise NoEncontrado("el nodo", nodo_id)
    return nodo


@dataclass(frozen=True)
class Serie:
    lecturas: list[Lectura]
    completa: bool
    """False si el rango tenía más de LECTURAS_MAXIMAS y se recortó."""


class ConsultarLecturas:
    def __init__(self, lecturas: RepositorioLecturas, nodos: RepositorioNodos) -> None:
        self._lecturas = lecturas
        self._nodos = nodos

    async def ejecutar(self, nodo_id: str, desde: datetime, hasta: datetime) -> Serie:
        validar_rango(desde, hasta)
        await _nodo(self._nodos, nodo_id)
        lecturas = await self._lecturas.en_rango(nodo_id, desde, hasta, LECTURAS_MAXIMAS + 1)
        return Serie(lecturas[:LECTURAS_MAXIMAS], len(lecturas) <= LECTURAS_MAXIMAS)


class ConsultarAgregados:
    def __init__(self, lecturas: RepositorioLecturas, nodos: RepositorioNodos) -> None:
        self._lecturas = lecturas
        self._nodos = nodos

    async def ejecutar(
        self, nodo_id: str, desde: datetime, hasta: datetime, periodo: Periodo
    ) -> list[Agregado]:
        validar_rango(desde, hasta)
        await _nodo(self._nodos, nodo_id)
        return await self._lecturas.agregadas(nodo_id, desde, hasta, periodo)


class ConsultarResumen:
    """Mínimos, máximos y promedios, y cuántas lecturas faltan.

    Las esperadas se cuentan desde la primera lectura del nodo (antes no existía) y hasta
    ahora (el futuro todavía no pasa), según su periodo de muestreo.
    """

    def __init__(
        self, lecturas: RepositorioLecturas, nodos: RepositorioNodos, reloj: Reloj
    ) -> None:
        self._lecturas = lecturas
        self._nodos = nodos
        self._reloj = reloj

    async def ejecutar(self, nodo_id: str, desde: datetime, hasta: datetime) -> Resumen:
        validar_rango(desde, hasta)
        nodo = await _nodo(self._nodos, nodo_id)
        cantidad, variables = await self._lecturas.estadisticas(nodo_id, desde, hasta)
        primera = await self._lecturas.primera(nodo_id)
        esperadas = 0
        if primera is not None:
            esperadas = lecturas_esperadas(
                max(desde, primera.ts), min(hasta, self._reloj.ahora()), nodo.periodo_s
            )
        return Resumen(nodo_id, desde, hasta, cantidad, max(esperadas, cantidad), variables)


@dataclass(frozen=True)
class ArchivoCsv:
    nombre: str
    contenido: str


def _fecha(ts: datetime) -> str:
    return ts.astimezone(ZONA_HORARIA).isoformat(timespec="seconds")


def _numero(valor: float | None) -> str:
    return "" if valor is None else f"{valor:g}"


def _escribir(encabezados: list[str], filas: list[list[str]]) -> str:
    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator="\n")
    escritor.writerow(encabezados)
    escritor.writerows(filas)
    # La marca BOM hace que Excel abra el archivo como UTF-8 (acentos y °).
    return "﻿" + salida.getvalue()


def _nombre(prefijo: str, desde: datetime, hasta: datetime) -> str:
    inicio = desde.astimezone(ZONA_HORARIA).date().isoformat()
    # `hasta` no se incluye: el último día del archivo es el anterior a esa medianoche.
    fin = (hasta - timedelta(microseconds=1)).astimezone(ZONA_HORARIA).date().isoformat()
    return f"{prefijo}_{inicio}_{fin}.csv"


class ExportarLecturas:
    def __init__(
        self, lecturas: RepositorioLecturas, nodos: RepositorioNodos, anotador: Anotador
    ) -> None:
        self._lecturas = lecturas
        self._nodos = nodos
        self._anotador = anotador

    async def ejecutar(
        self, actor: Usuario | None, nodo_id: str, desde: datetime, hasta: datetime
    ) -> ArchivoCsv:
        validar_rango(desde, hasta)
        await _nodo(self._nodos, nodo_id)
        # Un año de lecturas cada minuto son unas 527 000 filas: cabe completo.
        lecturas = await self._lecturas.en_rango(nodo_id, desde, hasta, 600_000)
        encabezados = ["fecha_hora", "nodo", "arranque", "seq"]
        encabezados += [v.value for v in Variable] + ["muestras", "rssi"]
        filas = [
            [_fecha(lec.ts), lec.nodo_id, str(lec.arranque), str(lec.seq)]
            + [_numero(lec.valor(v)) for v in Variable]
            + [_numero(lec.muestras), _numero(lec.rssi)]
            for lec in lecturas
        ]
        archivo = ArchivoCsv(
            _nombre(f"lecturas_{nodo_id}", desde, hasta), _escribir(encabezados, filas)
        )
        await self._anotador.anotar(
            actor,
            Accion.EXPORTAR,
            Objeto.REPORTE,
            archivo.nombre,
            f"{len(lecturas)} lecturas de {nodo_id}",
        )
        return archivo


class ExportarAlertas:
    def __init__(
        self, alertas: RepositorioAlertas, nodos: RepositorioNodos, anotador: Anotador
    ) -> None:
        self._alertas = alertas
        self._nodos = nodos
        self._anotador = anotador

    async def ejecutar(
        self,
        actor: Usuario | None,
        desde: datetime,
        hasta: datetime,
        nodo_id: str | None = None,
    ) -> ArchivoCsv:
        validar_rango(desde, hasta)
        if nodo_id is not None:
            await _nodo(self._nodos, nodo_id)
        alertas = await self._alertas.en_rango(desde, hasta, nodo_id)
        encabezados = [
            "id", "nodo", "tipo", "variable", "severidad", "mensaje", "valor", "limite",
            "iniciada", "escalada", "resuelta", "atendida", "atendida_por",
        ]  # fmt: skip
        filas = [_fila_alerta(a) for a in alertas]
        prefijo = f"alertas_{nodo_id}" if nodo_id else "alertas"
        archivo = ArchivoCsv(_nombre(prefijo, desde, hasta), _escribir(encabezados, filas))
        await self._anotador.anotar(
            actor, Accion.EXPORTAR, Objeto.REPORTE, archivo.nombre, f"{len(alertas)} alertas"
        )
        return archivo


def _fila_alerta(a: Alerta) -> list[str]:
    def momento(ts: datetime | None) -> str:
        return _fecha(ts) if ts else ""

    return [
        str(a.id),
        a.nodo_id,
        a.tipo.value,
        a.variable.value if a.variable else "",
        a.severidad.value,
        a.mensaje,
        _numero(a.valor),
        _numero(a.limite),
        momento(a.iniciada_en),
        momento(a.escalada_en),
        momento(a.resuelta_en),
        momento(a.atendida_en),
        a.atendida_por_nombre or "",
    ]


__all__ = [
    "ArchivoCsv",
    "ConsultarAgregados",
    "ConsultarLecturas",
    "ConsultarResumen",
    "ExportarAlertas",
    "ExportarLecturas",
    "RangoInvalido",
    "Serie",
]
