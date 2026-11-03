"""Entidades del invernadero."""

import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

_PATRON_ID = re.compile(r"^[a-z0-9-]{1,32}$")


class IdInvalido(ValueError):
    pass


def validar_id(valor: str) -> str:
    """Los identificadores de invernaderos y nodos se usan en los temas MQTT."""
    if not _PATRON_ID.match(valor):
        raise IdInvalido(f"'{valor}' no es válido: usar minúsculas, dígitos y guiones (máx. 32)")
    return valor


class Variable(StrEnum):
    TEMPERATURA = "temperatura"
    HUMEDAD_AIRE = "humedad_aire"
    HUMEDAD_SUSTRATO = "humedad_sustrato"


class SensorAire(StrEnum):
    DHT11 = "DHT11"
    DHT22 = "DHT22"


class EstadoNodo(StrEnum):
    DESCONOCIDO = "desconocido"
    CONECTADO = "conectado"
    DESCONECTADO = "desconectado"


@dataclass(frozen=True)
class Invernadero:
    id: str
    nombre: str
    cultivo_id: str = "hortalizas-hoja"


@dataclass(frozen=True)
class Nodo:
    id: str
    invernadero_id: str
    nombre: str
    sensor_aire: SensorAire = SensorAire.DHT11
    sensor_suelo: bool = False
    estado: EstadoNodo = EstadoNodo.DESCONOCIDO
    firmware: str | None = None
    periodo_s: int = 60
    ultima_lectura_en: datetime | None = None
    activo: bool = True
    """Un nodo dado de baja conserva su historial, pero no recibe lecturas ni alertas."""

    def tiempo_desconexion(self) -> timedelta:
        """Sin lecturas durante este tiempo, el nodo se considera desconectado."""
        return max(timedelta(minutes=5), 3 * timedelta(seconds=self.periodo_s))

    def con_lectura(self, ts: datetime) -> "Nodo":
        """El nodo envió una lectura: está conectado y se actualiza su última hora."""
        ultima = ts if self.ultima_lectura_en is None else max(self.ultima_lectura_en, ts)
        return replace(self, estado=EstadoNodo.CONECTADO, ultima_lectura_en=ultima)


@dataclass(frozen=True)
class Lectura:
    nodo_id: str
    arranque: int
    seq: int
    ts: datetime
    temperatura: float | None
    humedad_aire: float | None
    humedad_sustrato: float | None
    muestras: int | None = None
    rssi: int | None = None

    def valor(self, variable: Variable) -> float | None:
        return getattr(self, variable.value)

    def con_valor(self, variable: Variable, valor: float | None) -> "Lectura":
        return replace(self, **{variable.value: valor})
