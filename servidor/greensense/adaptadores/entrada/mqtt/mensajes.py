"""Mensajes del contrato MQTT v1. Ver docs/contrato-mqtt.md."""

import re
from dataclasses import dataclass
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

PATRON_ID = r"^[a-z0-9-]{1,32}$"
_TEMA = re.compile(r"^greensense/([a-z0-9-]{1,32})/([a-z0-9-]{1,32})/(lecturas|estado)$")

IdNodo = Annotated[str, Field(pattern=PATRON_ID)]


class _Mensaje(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    v: Literal[1]


class MensajeLectura(_Mensaje):
    nodo: IdNodo
    arranque: int = Field(ge=0)
    seq: int = Field(ge=0)
    ts: AwareDatetime
    temperatura: float | None
    humedad_aire: float | None
    humedad_sustrato: float | None
    muestras: int | None = Field(default=None, ge=1, le=20)
    rssi: int | None = Field(default=None, ge=-127, le=0)


class MensajeEstado(_Mensaje):
    estado: Literal["conectado", "desconectado"]
    arranque: int | None = Field(default=None, ge=0)
    firmware: str | None = Field(default=None, max_length=16)
    sensor_aire: Literal["DHT11", "DHT22"] | None = None
    sensor_suelo: bool | None = None
    periodo_s: int | None = Field(default=None, ge=5, le=3600)

    @model_validator(mode="after")
    def _conectado_trae_configuracion(self) -> Self:
        if self.estado == "conectado":
            faltan = [
                campo
                for campo in ("arranque", "firmware", "sensor_aire", "sensor_suelo", "periodo_s")
                if getattr(self, campo) is None
            ]
            if faltan:
                raise ValueError(f"un estado 'conectado' requiere: {', '.join(faltan)}")
        return self


@dataclass(frozen=True)
class Tema:
    invernadero: str
    nodo: str
    tipo: Literal["lecturas", "estado"]


def parsear_tema(tema: str) -> Tema | None:
    """Devuelve las partes del tema, o None si no es un tema que el servidor atienda."""
    coincidencia = _TEMA.match(tema)
    if coincidencia is None:
        return None
    invernadero, nodo, tipo = coincidencia.groups()
    return Tema(invernadero, nodo, tipo)  # type: ignore[arg-type]
