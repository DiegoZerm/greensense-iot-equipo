"""Alertas: qué condición se detectó, qué tan grave es y en qué estado está."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from greensense.dominio.modelos import Variable


class TipoAlerta(StrEnum):
    UMBRAL = "umbral"
    HONGOS = "hongos"
    SENSOR = "sensor"
    DESCONEXION = "desconexion"


class Severidad(StrEnum):
    ADVERTENCIA = "advertencia"
    CRITICA = "critica"


class EstadoCondicion(StrEnum):
    NORMAL = "normal"
    CERCA = "cerca"
    """Dentro del rango, pero cerca de un límite."""
    FUERA = "fuera"


@dataclass(frozen=True)
class Condicion:
    """Resultado de evaluar una regla con una lectura."""

    estado: EstadoCondicion
    mensaje: str = ""
    recomendacion: str = ""
    valor: float | None = None
    limite: float | None = None
    tiempo_minimo_s: float = 0.0
    """Segundos fuera de rango antes de pasar a crítica."""
    en_holgura: bool = False
    """Normal, pero todavía pegado al margen: no basta para resolver una alerta abierta.

    Sin esta holgura, un valor que oscila en el borde del margen (por el ruido del sensor)
    abriría y cerraría una advertencia en cada lectura.
    """


@dataclass(frozen=True)
class Alerta:
    nodo_id: str
    tipo: TipoAlerta
    variable: Variable | None
    severidad: Severidad
    mensaje: str
    recomendacion: str
    valor: float | None
    limite: float | None
    iniciada_en: datetime
    actualizada_en: datetime
    fuera_desde: datetime | None = None
    escalada_en: datetime | None = None
    resuelta_en: datetime | None = None
    atendida_en: datetime | None = None
    atendida_por: int | None = None
    """Id del usuario que la marcó como atendida."""
    atendida_por_nombre: str | None = None
    """Nombre del usuario en ese momento, para mostrarlo sin consultar usuarios."""
    id: int | None = None

    @property
    def activa(self) -> bool:
        return self.resuelta_en is None

    @property
    def clave(self) -> tuple[str, TipoAlerta, Variable | None]:
        return (self.nodo_id, self.tipo, self.variable)


@dataclass(frozen=True)
class FiltroAlertas:
    """Criterios del historial. Lo que quede en None no filtra."""

    severidad: Severidad | None = None
    variable: Variable | None = None
    desde: datetime | None = None
    """Incluido: alertas iniciadas a partir de este momento."""
    hasta: datetime | None = None
    """No incluido."""

    def __post_init__(self) -> None:
        if self.desde is not None and self.hasta is not None and self.desde >= self.hasta:
            raise ValueError("'desde' debe ser anterior a 'hasta'")

    def acepta(self, alerta: Alerta) -> bool:
        return (
            self.severidad in (None, alerta.severidad)
            and self.variable in (None, alerta.variable)
            and (self.desde is None or alerta.iniciada_en >= self.desde)
            and (self.hasta is None or alerta.iniciada_en < self.hasta)
        )


class Cambio(StrEnum):
    CREADA = "creada"
    ESCALADA = "escalada"
    RESUELTA = "resuelta"
    ACTUALIZADA = "actualizada"


@dataclass(frozen=True)
class Transicion:
    alerta: Alerta
    cambio: Cambio

    @property
    def notificar(self) -> bool:
        """Solo se avisa por push cuando una alerta llega a crítica."""
        return self.alerta.severidad is Severidad.CRITICA and self.cambio in (
            Cambio.CREADA,
            Cambio.ESCALADA,
        )


def aplicar_condicion(
    activa: Alerta | None,
    condicion: Condicion,
    nodo_id: str,
    tipo: TipoAlerta,
    variable: Variable | None,
    ts: datetime,
) -> Transicion | None:
    """Decide qué pasa con la alerta de una regla al llegar una lectura nueva.

    - Normal: la alerta activa se resuelve, salvo que el valor siga en la holgura del
      margen; ahí la alerta se queda abierta y deja de contar tiempo fuera de rango.
    - Cerca del límite: se abre una advertencia, o la activa sigue como está.
    - Fuera de rango: se abre una advertencia que pasa a crítica cuando lleva el tiempo
      mínimo fuera. Una crítica se mantiene hasta que la variable vuelve a la normalidad.
    """
    if condicion.estado is EstadoCondicion.NORMAL:
        if activa is None:
            return None
        if condicion.en_holgura:
            if activa.fuera_desde is None:
                return None
            return Transicion(
                replace(activa, fuera_desde=None, actualizada_en=ts), Cambio.ACTUALIZADA
            )
        return Transicion(replace(activa, resuelta_en=ts, actualizada_en=ts), Cambio.RESUELTA)

    datos = {
        "mensaje": condicion.mensaje,
        "recomendacion": condicion.recomendacion,
        "valor": condicion.valor,
        "limite": condicion.limite,
        "actualizada_en": ts,
    }
    fuera = condicion.estado is EstadoCondicion.FUERA

    if activa is None:
        critica_inmediata = fuera and condicion.tiempo_minimo_s <= 0
        alerta = Alerta(
            nodo_id=nodo_id,
            tipo=tipo,
            variable=variable,
            severidad=Severidad.CRITICA if critica_inmediata else Severidad.ADVERTENCIA,
            iniciada_en=ts,
            fuera_desde=ts if fuera else None,
            escalada_en=ts if critica_inmediata else None,
            **datos,
        )
        return Transicion(alerta, Cambio.CREADA)

    fuera_desde = (activa.fuera_desde or ts) if fuera else None
    alerta = replace(activa, fuera_desde=fuera_desde, **datos)
    lleva_fuera = (ts - fuera_desde).total_seconds() if fuera_desde else 0.0
    if (
        fuera
        and activa.severidad is Severidad.ADVERTENCIA
        and lleva_fuera >= condicion.tiempo_minimo_s
    ):
        alerta = replace(alerta, severidad=Severidad.CRITICA, escalada_en=ts)
        return Transicion(alerta, Cambio.ESCALADA)
    return Transicion(alerta, Cambio.ACTUALIZADA)
