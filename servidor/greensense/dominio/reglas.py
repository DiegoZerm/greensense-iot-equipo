"""Reglas que evalúan cada lectura. Agregar una regla no obliga a cambiar las demás."""

from dataclasses import dataclass
from typing import Protocol

from greensense.dominio.alertas import Condicion, EstadoCondicion, TipoAlerta
from greensense.dominio.cultivo import Cultivo, RiesgoHongos, Umbral
from greensense.dominio.modelos import Nodo, Variable
from greensense.dominio.validacion import LecturaValidada

NOMBRES = {
    Variable.TEMPERATURA: ("Temperatura", "°C"),
    Variable.HUMEDAD_AIRE: ("Humedad del aire", "%"),
    Variable.HUMEDAD_SUSTRATO: ("Humedad del sustrato", "%"),
}

RECOMENDACIONES = {
    (Variable.TEMPERATURA, "alto"): "Ventilar o sombrear el invernadero.",
    (Variable.TEMPERATURA, "bajo"): "Cerrar ventilas o calentar el invernadero.",
    (Variable.HUMEDAD_AIRE, "alto"): "Ventilar para bajar la humedad.",
    (Variable.HUMEDAD_AIRE, "bajo"): "Humedecer el ambiente o nebulizar.",
    (Variable.HUMEDAD_SUSTRATO, "alto"): "Suspender el riego: hay riesgo de pudrición de raíz.",
    (Variable.HUMEDAD_SUSTRATO, "bajo"): "Regar.",
}


def _formato(variable: Variable, valor: float) -> str:
    return f"{valor:.1f} {NOMBRES[variable][1]}"


class Regla(Protocol):
    tipo: TipoAlerta
    variable: Variable | None

    def evaluar(self, validada: LecturaValidada) -> Condicion | None:
        """None si la regla no se puede evaluar con esta lectura (falta el dato)."""
        ...


@dataclass(frozen=True)
class ReglaUmbral:
    umbral: Umbral
    tipo: TipoAlerta = TipoAlerta.UMBRAL

    @property
    def variable(self) -> Variable:
        return self.umbral.variable

    def evaluar(self, validada: LecturaValidada) -> Condicion | None:
        u = self.umbral
        valor = validada.lectura.valor(u.variable)
        if valor is None:
            return None
        nombre = NOMBRES[u.variable][0]
        if valor > u.maximo or valor < u.minimo:
            lado = "alto" if valor > u.maximo else "bajo"
            limite = u.maximo if lado == "alto" else u.minimo
            tiempo = u.tiempo_alto if lado == "alto" else u.tiempo_bajo
            palabra = "alta" if lado == "alto" else "baja"
            return Condicion(
                EstadoCondicion.FUERA,
                f"{nombre} {palabra}: {_formato(u.variable, valor)} "
                f"({'máximo' if lado == 'alto' else 'mínimo'} {_formato(u.variable, limite)})",
                RECOMENDACIONES[(u.variable, lado)],
                valor,
                limite,
                tiempo.total_seconds(),
            )
        if valor > u.maximo - u.margen or valor < u.minimo + u.margen:
            lado = "alto" if valor > u.maximo - u.margen else "bajo"
            limite = u.maximo if lado == "alto" else u.minimo
            return Condicion(
                EstadoCondicion.CERCA,
                f"{nombre} cerca del {'máximo' if lado == 'alto' else 'mínimo'}: "
                f"{_formato(u.variable, valor)} (límite {_formato(u.variable, limite)})",
                RECOMENDACIONES[(u.variable, lado)],
                valor,
                limite,
            )
        holgura = u.margen + u.histeresis
        en_holgura = valor > u.maximo - holgura or valor < u.minimo + holgura
        return Condicion(EstadoCondicion.NORMAL, valor=valor, en_holgura=en_holgura)


@dataclass(frozen=True)
class ReglaHongos:
    riesgo: RiesgoHongos
    tipo: TipoAlerta = TipoAlerta.HONGOS
    variable: None = None

    def evaluar(self, validada: LecturaValidada) -> Condicion | None:
        humedad = validada.lectura.humedad_aire
        temperatura = validada.lectura.temperatura
        if humedad is None or temperatura is None:
            return None
        r = self.riesgo
        if humedad >= r.humedad_minima and temperatura >= r.temperatura_minima:
            return Condicion(
                EstadoCondicion.FUERA,
                f"Riesgo de hongos: humedad {humedad:.1f} % y temperatura {temperatura:.1f} °C",
                "Ventilar y revisar hojas y tallos en busca de manchas o moho.",
                humedad,
                r.humedad_minima,
                r.tiempo_minimo.total_seconds(),
            )
        return Condicion(EstadoCondicion.NORMAL)


# Tiempo que un sensor puede fallar antes de que la alerta sea crítica.
TIEMPO_FALLA_SENSOR_S = 15 * 60


@dataclass(frozen=True)
class ReglaSensor:
    """Un sensor que debería medir y no entrega un valor válido está fallando."""

    variable: Variable
    tipo: TipoAlerta = TipoAlerta.SENSOR

    def evaluar(self, validada: LecturaValidada) -> Condicion | None:
        nombre = NOMBRES[self.variable][0].lower()
        imposible = next((i for i in validada.imposibles if i.variable is self.variable), None)
        if imposible is not None:
            mensaje = (
                f"El sensor de {nombre} reportó {_formato(self.variable, imposible.valor)}, "
                "un valor imposible"
            )
            valor = imposible.valor
        elif validada.lectura.valor(self.variable) is None:
            mensaje = f"El sensor de {nombre} no está entregando datos"
            valor = None
        else:
            return Condicion(EstadoCondicion.NORMAL)
        return Condicion(
            EstadoCondicion.FUERA,
            mensaje,
            "Revisar la conexión y el estado del sensor.",
            valor,
            None,
            TIEMPO_FALLA_SENSOR_S,
        )


def reglas_para(nodo: Nodo, cultivo: Cultivo) -> list[Regla]:
    """Las reglas que aplican a un nodo según sus sensores y el cultivo de su invernadero."""
    variables = [Variable.TEMPERATURA, Variable.HUMEDAD_AIRE]
    if nodo.sensor_suelo:
        variables.append(Variable.HUMEDAD_SUSTRATO)

    reglas: list[Regla] = [ReglaSensor(variable) for variable in variables]
    reglas += [ReglaUmbral(u) for v in variables if (u := cultivo.umbral(v)) is not None]
    reglas.append(ReglaHongos(cultivo.hongos))
    return reglas
