"""CSV sintético con el formato que exporta la app, para probar sin datos reales."""

import numpy as np
import pandas as pd


def lecturas(
    horas: int = 72,
    sustrato: str = "normal",
    sin_minutos: range | None = None,
    semilla: int = 3,
) -> pd.DataFrame:
    """`sustrato`: normal (se seca y se riega), cero (como el sensor al aire) o ninguno."""
    azar = np.random.default_rng(semilla)
    n = horas * 60
    indice = pd.date_range("2026-11-07 00:00", periods=n, freq="1min", tz="America/Mexico_City")
    hora = indice.hour + indice.minute / 60
    ciclo = np.cos(2 * np.pi * (hora - 15) / 24)
    if sustrato == "normal":
        valor, serie = 62.0, []
        for t in ciclo:
            valor -= (1 + 0.4 * t) / 60
            valor = 66.0 if valor < 50 else valor
            serie.append(valor)
        humedad_sustrato = np.round(np.array(serie) + azar.normal(0, 0.2, n), 1)
    elif sustrato == "cero":
        humedad_sustrato = np.zeros(n)
    else:
        humedad_sustrato = np.full(n, np.nan)
    datos = pd.DataFrame(
        {
            "fecha_hora": indice.strftime("%Y-%m-%dT%H:%M:%S-06:00"),
            "nodo": "maceta1",
            "arranque": 1,
            "seq": range(n),
            "temperatura": np.round(23 + 3 * ciclo + azar.normal(0, 0.2, n), 1),
            "humedad_aire": np.round(68 - 6 * ciclo + azar.normal(0, 0.5, n), 1),
            "humedad_sustrato": humedad_sustrato,
            "muestras": 5,
            "rssi": -60,
        }
    )
    if sin_minutos is not None:
        datos = datos.drop(index=list(sin_minutos))
    return datos


def guardar(datos: pd.DataFrame, ruta) -> None:
    # Con la marca BOM, igual que el archivo de la app.
    datos.to_csv(ruta, index=False, encoding="utf-8-sig")
