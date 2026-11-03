"""Consultas del historial: rangos, agregados por hora o por día y resúmenes."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from greensense.dominio.modelos import Variable

# Los días y las horas de los agregados empiezan en la hora local del invernadero.
# México no tiene horario de verano desde 2022, así que es UTC-6 todo el año.
ZONA_HORARIA = ZoneInfo("America/Mexico_City")

# Límites para que una consulta no traiga más de lo que la app puede dibujar.
RANGO_MAXIMO = timedelta(days=366)
LECTURAS_MAXIMAS = 20_000


class RangoInvalido(ValueError):
    pass


def validar_rango(desde: datetime, hasta: datetime) -> None:
    if desde.tzinfo is None or hasta.tzinfo is None:
        raise RangoInvalido("las fechas deben llevar zona horaria")
    if desde >= hasta:
        raise RangoInvalido("'desde' debe ser anterior a 'hasta'")
    if hasta - desde > RANGO_MAXIMO:
        raise RangoInvalido("el rango no puede pasar de un año")


class Periodo(StrEnum):
    HORA = "hora"
    DIA = "dia"


@dataclass(frozen=True)
class Estadistica:
    """Mínimo, máximo y promedio de una variable. `n` cuenta los valores no nulos."""

    minimo: float
    maximo: float
    promedio: float
    n: int


@dataclass(frozen=True)
class Agregado:
    """Lecturas de una hora o un día. `inicio` es el principio del intervalo."""

    inicio: datetime
    lecturas: int
    variables: dict[Variable, Estadistica | None]


@dataclass(frozen=True)
class Resumen:
    nodo_id: str
    desde: datetime
    hasta: datetime
    lecturas: int
    esperadas: int
    """Las que debió mandar el nodo según su periodo, desde su primera lectura."""
    variables: dict[Variable, Estadistica | None]

    @property
    def perdidas(self) -> int:
        return max(0, self.esperadas - self.lecturas)

    @property
    def porcentaje_perdidas(self) -> float | None:
        if self.esperadas == 0:
            return None
        return round(100 * self.perdidas / self.esperadas, 2)


def lecturas_esperadas(desde: datetime, hasta: datetime, periodo_s: int) -> int:
    if hasta <= desde or periodo_s <= 0:
        return 0
    return int((hasta - desde).total_seconds() // periodo_s)


def estadistica(valores: list[float]) -> Estadistica | None:
    if not valores:
        return None
    return Estadistica(
        minimo=min(valores),
        maximo=max(valores),
        promedio=round(sum(valores) / len(valores), 2),
        n=len(valores),
    )


def inicio_del_intervalo(ts: datetime, periodo: Periodo) -> datetime:
    """Principio de la hora o del día local que contiene a `ts`."""
    local = ts.astimezone(ZONA_HORARIA)
    if periodo is Periodo.HORA:
        local = local.replace(minute=0, second=0, microsecond=0)
    else:
        local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return local
