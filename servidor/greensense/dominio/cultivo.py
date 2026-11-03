"""Cultivos y sus rangos adecuados. Los valores son parámetros editables, no constantes."""

from dataclasses import dataclass
from datetime import timedelta

from greensense.dominio.modelos import Variable


class UmbralInvalido(ValueError):
    pass


@dataclass(frozen=True)
class Umbral:
    """Rango adecuado de una variable.

    Dentro de `margen` de un límite la variable está cerca de salirse (advertencia).
    Fuera del rango pasa a crítica cuando lleva el tiempo mínimo de ese lado. Una alerta
    abierta se resuelve hasta que el valor se aleja del margen otra `histeresis`.
    """

    variable: Variable
    minimo: float
    maximo: float
    margen: float
    tiempo_bajo: timedelta = timedelta(minutes=5)
    tiempo_alto: timedelta = timedelta(minutes=5)

    def __post_init__(self) -> None:
        if self.minimo >= self.maximo:
            raise UmbralInvalido(f"{self.variable}: el mínimo debe ser menor que el máximo")
        if self.margen < 0 or 2 * self.margen >= self.maximo - self.minimo:
            raise UmbralInvalido(f"{self.variable}: el margen no cabe en el rango")
        if self.tiempo_bajo < timedelta(0) or self.tiempo_alto < timedelta(0):
            raise UmbralInvalido(f"{self.variable}: los tiempos no pueden ser negativos")

    @property
    def histeresis(self) -> float:
        return self.margen / 2


@dataclass(frozen=True)
class RiesgoHongos:
    """Humedad y temperatura altas a la vez favorecen enfermedades por hongos."""

    humedad_minima: float = 85.0
    temperatura_minima: float = 20.0
    tiempo_minimo: timedelta = timedelta(hours=1)


@dataclass(frozen=True)
class Cultivo:
    id: str
    nombre: str
    umbrales: tuple[Umbral, ...]
    hongos: RiesgoHongos = RiesgoHongos()

    def umbral(self, variable: Variable) -> Umbral | None:
        return next((u for u in self.umbrales if u.variable is variable), None)


# Rangos iniciales de la propuesta para hortalizas de hoja. La humedad alta del sustrato
# solo es crítica si se mantiene horas (riesgo de pudrición de raíz).
CULTIVO_PREDETERMINADO = Cultivo(
    id="hortalizas-hoja",
    nombre="Hortalizas de hoja",
    umbrales=(
        Umbral(Variable.TEMPERATURA, 18.0, 28.0, 2.0),
        Umbral(Variable.HUMEDAD_AIRE, 60.0, 80.0, 5.0),
        Umbral(Variable.HUMEDAD_SUSTRATO, 45.0, 70.0, 5.0, tiempo_alto=timedelta(hours=3)),
    ),
)
