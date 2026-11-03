"""Validación física de las lecturas según el sensor que tiene cada nodo."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from greensense.dominio.modelos import Lectura, Nodo, SensorAire, Variable

# Rango que cada sensor puede medir según su hoja de datos.
RANGOS_SENSOR_AIRE: dict[SensorAire, dict[Variable, tuple[float, float]]] = {
    SensorAire.DHT11: {Variable.TEMPERATURA: (0.0, 50.0), Variable.HUMEDAD_AIRE: (20.0, 90.0)},
    SensorAire.DHT22: {Variable.TEMPERATURA: (-40.0, 80.0), Variable.HUMEDAD_AIRE: (0.0, 100.0)},
}
RANGO_SUSTRATO = (0.0, 100.0)

# Tolerancia para relojes de nodo ligeramente adelantados.
ADELANTO_MAXIMO = timedelta(minutes=5)


class LecturaRechazada(Exception):
    """La lectura no se puede guardar."""


@dataclass(frozen=True)
class ValorImposible:
    variable: Variable
    valor: float
    minimo: float
    maximo: float


@dataclass(frozen=True)
class LecturaValidada:
    lectura: Lectura
    imposibles: tuple[ValorImposible, ...]


def rango(nodo: Nodo, variable: Variable) -> tuple[float, float]:
    if variable is Variable.HUMEDAD_SUSTRATO:
        return RANGO_SUSTRATO
    return RANGOS_SENSOR_AIRE[nodo.sensor_aire][variable]


def validar_lectura(lectura: Lectura, nodo: Nodo, ahora: datetime) -> LecturaValidada:
    """Valida una lectura de un nodo.

    Los valores fuera del rango físico del sensor indican una falla: se reemplazan
    por None y se reportan, para que la lectura se guarde sin datos falsos.
    Si el nodo no tiene sensor de suelo, la humedad del sustrato siempre es None.
    """
    if lectura.nodo_id != nodo.id:
        raise LecturaRechazada(f"la lectura es de {lectura.nodo_id}, no de {nodo.id}")
    if lectura.ts > ahora + ADELANTO_MAXIMO:
        raise LecturaRechazada(f"la hora {lectura.ts.isoformat()} está en el futuro")

    if not nodo.sensor_suelo:
        lectura = lectura.con_valor(Variable.HUMEDAD_SUSTRATO, None)

    imposibles = []
    for variable in Variable:
        valor = lectura.valor(variable)
        if valor is None:
            continue
        minimo, maximo = rango(nodo, variable)
        if not minimo <= valor <= maximo:
            imposibles.append(ValorImposible(variable, valor, minimo, maximo))
            lectura = lectura.con_valor(variable, None)

    return LecturaValidada(lectura, tuple(imposibles))
