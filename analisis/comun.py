"""Funciones de los notebooks de análisis. Leen el CSV que exporta la app."""

import math
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

AQUI = Path(__file__).resolve().parent
ZONA = "America/Mexico_City"
VARIABLES = ("temperatura", "humedad_aire", "humedad_sustrato")
NOMBRES = {
    "temperatura": "Temperatura (°C)",
    "humedad_aire": "Humedad del aire (%)",
    "humedad_sustrato": "Humedad del sustrato (%)",
}
# Rangos adecuados del cultivo predeterminado: dominio/cultivo.py del servidor.
RANGOS = {
    "temperatura": (18.0, 28.0),
    "humedad_aire": (60.0, 80.0),
    "humedad_sustrato": (45.0, 70.0),
}
# Por debajo de esta desviación, la variable casi no cambia y no hay nada que predecir.
VARIACION_MINIMA = 0.5


def ruta_de_datos() -> Path:
    """GS_CSV o, si no está definida, el CSV más reciente de analisis/datos."""
    if ruta := os.environ.get("GS_CSV"):
        return Path(ruta)
    archivos = sorted((AQUI / "datos").glob("lecturas_*.csv"), key=lambda a: a.stat().st_mtime)
    if not archivos:
        raise FileNotFoundError(
            "No hay datos: exporta las lecturas desde la app (Historial, Lecturas CSV) "
            "y guarda el archivo en analisis/datos/."
        )
    return archivos[-1]


def cargar(ruta: Path | str | None = None) -> pd.DataFrame:
    """Lecturas ordenadas por hora local, sin repetidas. La marca BOM del CSV se ignora."""
    datos = pd.read_csv(ruta or ruta_de_datos(), encoding="utf-8-sig")
    datos["fecha_hora"] = pd.to_datetime(datos["fecha_hora"], utc=True).dt.tz_convert(ZONA)
    datos = datos.set_index("fecha_hora").sort_index()
    return datos[~datos.index.duplicated()]


@dataclass(frozen=True)
class Calidad:
    lecturas: int
    esperadas: int
    primera: pd.Timestamp
    ultima: pd.Timestamp
    huecos: pd.DataFrame

    @property
    def perdidas(self) -> int:
        return self.esperadas - self.lecturas

    @property
    def porcentaje_perdidas(self) -> float:
        return 100 * self.perdidas / self.esperadas if self.esperadas else 0.0

    @property
    def horas(self) -> float:
        return (self.ultima - self.primera).total_seconds() / 3600


def calidad(datos: pd.DataFrame, periodo_s: int = 60) -> Calidad:
    """Lecturas contra las esperadas entre la primera y la última, y huecos de más de 3 periodos."""
    if datos.empty:
        raise ValueError("el archivo no tiene lecturas")
    primera, ultima = datos.index[0], datos.index[-1]
    esperadas = int((ultima - primera).total_seconds() // periodo_s) + 1
    separacion = datos.index.to_series().diff()
    largos = separacion[separacion > pd.Timedelta(seconds=3 * periodo_s)]
    huecos = pd.DataFrame(
        {
            "desde": (largos.index - largos.to_numpy()),
            "hasta": largos.index,
            "minutos": (largos.dt.total_seconds() / 60).round(1).to_numpy(),
        }
    )
    return Calidad(len(datos), max(esperadas, len(datos)), primera, ultima, huecos)


def estadisticas(datos: pd.DataFrame) -> pd.DataFrame:
    """Mínimo, máximo, promedio, desviación y cuántos valores válidos tiene cada variable."""
    filas = {}
    for variable in VARIABLES:
        serie = datos[variable].dropna()
        if not serie.empty:
            filas[NOMBRES[variable]] = {
                "n": len(serie),
                "mínimo": serie.min(),
                "máximo": serie.max(),
                "promedio": serie.mean(),
                "desviación": serie.std(),
            }
    return pd.DataFrame.from_dict(filas, orient="index").round(2)


def ciclo_diario(datos: pd.DataFrame, variable: str) -> pd.DataFrame:
    """Promedio y percentiles 10 y 90 por hora del día."""
    serie = datos[variable].dropna()
    grupos = serie.groupby(serie.index.hour)
    return pd.DataFrame(
        {"promedio": grupos.mean(), "p10": grupos.quantile(0.1), "p90": grupos.quantile(0.9)}
    ).rename_axis("hora")


def tiempo_en_rango(datos: pd.DataFrame, rangos: dict | None = None) -> pd.DataFrame:
    """Porcentaje de las lecturas válidas debajo, dentro y arriba del rango del cultivo."""
    filas = {}
    for variable, (minimo, maximo) in (rangos or RANGOS).items():
        serie = datos[variable].dropna()
        if not serie.empty:
            filas[NOMBRES[variable]] = {
                "debajo": 100 * (serie < minimo).mean(),
                "dentro": 100 * serie.between(minimo, maximo).mean(),
                "arriba": 100 * (serie > maximo).mean(),
            }
    return pd.DataFrame.from_dict(filas, orient="index").round(1)


def tiene_variacion(datos: pd.DataFrame, variable: str) -> bool:
    serie = datos[variable].dropna()
    return len(serie) >= 0.5 * len(datos) and serie.std() >= VARIACION_MINIMA


def elegir_objetivo(datos: pd.DataFrame) -> str:
    """La propuesta estima el sustrato; sin sensor o sin variación se usa la temperatura."""
    if tiene_variacion(datos, "humedad_sustrato"):
        return "humedad_sustrato"
    if tiene_variacion(datos, "temperatura"):
        return "temperatura"
    raise ValueError("ni el sustrato ni la temperatura varían: no hay nada que predecir")


def matriz_de_regresion(
    datos: pd.DataFrame, objetivo: str, horizonte_min: int = 60, paso_min: int = 5
) -> tuple[pd.DataFrame, pd.Series]:
    """Variables explicativas en t y el objetivo en t + horizonte.

    Se trabaja en una rejilla regular para que un desplazamiento siempre signifique el mismo
    tiempo: donde faltan lecturas queda vacío y esa fila se descarta, sin inventar datos.
    """
    rejilla = (
        datos[list(VARIABLES)].resample(f"{paso_min}min").median().astype(float)
    )
    pasos = horizonte_min // paso_min
    explicativas = pd.DataFrame(index=rejilla.index)
    explicativas["actual"] = rejilla[objetivo]
    explicativas["hace_1h"] = rejilla[objetivo].shift(60 // paso_min)
    for variable in VARIABLES:
        if variable != objetivo and variable != "humedad_sustrato":
            explicativas[variable] = rejilla[variable]
    hora = rejilla.index.hour + rejilla.index.minute / 60
    explicativas["hora_sen"] = np.sin(2 * math.pi * hora / 24)
    explicativas["hora_cos"] = np.cos(2 * math.pi * hora / 24)
    futuro = rejilla[objetivo].shift(-pasos).rename("futuro")
    filas_validas = explicativas.notna().all(axis=1) & futuro.notna()
    return explicativas[filas_validas], futuro[filas_validas]


def dividir_en_el_tiempo(
    x: pd.DataFrame, y: pd.Series, proporcion: float = 2 / 3, separacion_min: int = 60
):
    """Entrena con lo primero y evalúa con lo último, sin barajar.

    La separación evita que el objetivo del entrenamiento caiga dentro de la evaluación.
    """
    corte = x.index[int(len(x) * proporcion)]
    inicio_prueba = corte + pd.Timedelta(minutes=separacion_min)
    entrena = x.index < corte
    prueba = x.index >= inicio_prueba
    return x[entrena], x[prueba], y[entrena], y[prueba]


def metricas(reales, predichos) -> dict[str, float]:
    return {
        "MAE": float(mean_absolute_error(reales, predichos)),
        "RMSE": float(math.sqrt(mean_squared_error(reales, predichos))),
        "R²": float(r2_score(reales, predichos)),
    }
