"""Genera lecturas realistas de un invernadero, sin depender de MQTT."""

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Hora local de Querétaro, para que el ciclo diario tenga su máximo por la tarde.
ZONA_LOCAL = timezone(timedelta(hours=-6))


@dataclass(frozen=True)
class Escenario:
    descripcion: str
    temperatura_media: float = 23.0
    temperatura_amplitud: float = 4.0
    humedad_media: float = 70.0
    humedad_amplitud: float = 8.0
    secado_por_hora: float = 0.8
    riego_bajo: float | None = 48.0
    """Si el sustrato baja de este valor, se simula un riego. None: nunca se riega."""
    sustrato_tras_riego: float = 68.0
    ruido_humedad: float = 1.5
    """Desviación de la humedad del aire entre una lectura y la siguiente."""


ESCENARIOS = {
    "normal": Escenario("Condiciones dentro de rango, con riego automático"),
    "calor": Escenario("Temperatura por encima del umbral por la tarde", temperatura_media=29.0),
    "seco": Escenario("El sustrato se seca y nadie riega", secado_por_hora=4.0, riego_bajo=None),
    "hongos": Escenario(
        "Humedad y temperatura altas a la vez",
        temperatura_media=26.0,
        humedad_media=86.0,
        humedad_amplitud=3.0,
    ),
}


class Generador:
    def __init__(
        self,
        escenario: Escenario,
        sensor_aire: str = "DHT22",
        sensor_suelo: bool = True,
        semilla: int | None = None,
        sustrato_inicial: float = 62.0,
    ) -> None:
        self._escenario = escenario
        self._sensor_aire = sensor_aire
        self._sensor_suelo = sensor_suelo
        self._azar = random.Random(semilla)
        self._sustrato = sustrato_inicial
        self._ultimo_ts: datetime | None = None

    def siguiente(self, ts: datetime) -> dict[str, float | None]:
        e = self._escenario
        hora = ts.astimezone(ZONA_LOCAL)
        hora_decimal = hora.hour + hora.minute / 60
        # Máximo de temperatura a las 15:00 y mínimo a las 03:00; la humedad hace lo contrario.
        ciclo = math.cos(2 * math.pi * (hora_decimal - 15) / 24)

        temperatura = e.temperatura_media + e.temperatura_amplitud * ciclo
        temperatura += self._azar.gauss(0, 0.3)
        humedad = (
            e.humedad_media - e.humedad_amplitud * ciclo + self._azar.gauss(0, e.ruido_humedad)
        )
        humedad = min(max(humedad, 0.0), 100.0)

        if self._sensor_aire == "DHT11":
            # El DHT11 entrega valores enteros.
            temperatura, humedad = float(round(temperatura)), float(round(humedad))
        else:
            temperatura, humedad = round(temperatura, 1), round(humedad, 1)

        return {
            "temperatura": temperatura,
            "humedad_aire": humedad,
            "humedad_sustrato": self._sustrato_en(ts, temperatura) if self._sensor_suelo else None,
        }

    def _sustrato_en(self, ts: datetime, temperatura: float) -> float:
        if self._ultimo_ts is not None:
            horas = max((ts - self._ultimo_ts).total_seconds() / 3600, 0.0)
            # Con más calor, el sustrato se seca más rápido.
            factor_calor = 1 + max(temperatura - 20, 0) / 10
            self._sustrato -= self._escenario.secado_por_hora * horas * factor_calor
        self._ultimo_ts = ts

        riego = self._escenario.riego_bajo
        if riego is not None and self._sustrato < riego:
            self._sustrato = self._escenario.sustrato_tras_riego
        self._sustrato = max(self._sustrato, 5.0)
        return round(self._sustrato + self._azar.gauss(0, 0.4), 1)
