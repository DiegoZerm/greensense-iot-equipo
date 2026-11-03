from datetime import timedelta

import pytest

from greensense.dominio.alertas import EstadoCondicion, TipoAlerta
from greensense.dominio.cultivo import CULTIVO_PREDETERMINADO, RiesgoHongos
from greensense.dominio.modelos import Variable
from greensense.dominio.reglas import ReglaHongos, ReglaSensor, ReglaUmbral, reglas_para
from greensense.dominio.validacion import LecturaValidada, ValorImposible
from tests.fabricas import crear_lectura, crear_nodo, validada

TEMPERATURA = ReglaUmbral(CULTIVO_PREDETERMINADO.umbral(Variable.TEMPERATURA))
SUSTRATO = ReglaUmbral(CULTIVO_PREDETERMINADO.umbral(Variable.HUMEDAD_SUSTRATO))


@pytest.mark.parametrize(
    ("valor", "estado"),
    [
        (23.0, EstadoCondicion.NORMAL),
        (20.0, EstadoCondicion.NORMAL),
        (26.0, EstadoCondicion.NORMAL),
        (26.1, EstadoCondicion.CERCA),
        (19.9, EstadoCondicion.CERCA),
        (28.0, EstadoCondicion.CERCA),
        (28.1, EstadoCondicion.FUERA),
        (17.9, EstadoCondicion.FUERA),
    ],
)
def test_umbral_de_temperatura(valor, estado):
    assert TEMPERATURA.evaluar(validada(temperatura=valor)).estado is estado


@pytest.mark.parametrize(
    ("valor", "en_holgura"),
    [(23.0, False), (21.0, False), (20.5, True), (25.5, True), (25.0, False)],
)
def test_holgura_de_la_temperatura_es_medio_margen(valor, en_holgura):
    condicion = TEMPERATURA.evaluar(validada(temperatura=valor))

    assert condicion.estado is EstadoCondicion.NORMAL
    assert condicion.en_holgura is en_holgura


def test_temperatura_alta_trae_limite_recomendacion_y_tiempo():
    condicion = TEMPERATURA.evaluar(validada(temperatura=29.5))

    assert condicion.mensaje == "Temperatura alta: 29.5 °C (máximo 28.0 °C)"
    assert condicion.recomendacion == "Ventilar o sombrear el invernadero."
    assert (condicion.valor, condicion.limite, condicion.tiempo_minimo_s) == (29.5, 28.0, 300)


def test_sustrato_bajo_recomienda_regar_y_alto_espera_horas():
    bajo = SUSTRATO.evaluar(validada(humedad_sustrato=40.0))
    alto = SUSTRATO.evaluar(validada(humedad_sustrato=75.0))

    assert bajo.recomendacion == "Regar."
    assert bajo.tiempo_minimo_s == 300
    assert "pudrición" in alto.recomendacion
    assert alto.tiempo_minimo_s == timedelta(hours=3).total_seconds()


def test_umbral_sin_dato_no_se_evalua():
    assert TEMPERATURA.evaluar(validada(temperatura=None)) is None


@pytest.mark.parametrize(
    ("humedad", "temperatura", "estado"),
    [
        (86.0, 24.0, EstadoCondicion.FUERA),
        (86.0, 18.0, EstadoCondicion.NORMAL),
        (80.0, 24.0, EstadoCondicion.NORMAL),
    ],
)
def test_riesgo_de_hongos(humedad, temperatura, estado):
    regla = ReglaHongos(RiesgoHongos())

    condicion = regla.evaluar(validada(humedad_aire=humedad, temperatura=temperatura))

    assert condicion.estado is estado


def test_sensor_que_no_entrega_datos_esta_fallando():
    condicion = ReglaSensor(Variable.TEMPERATURA).evaluar(validada(temperatura=None))

    assert condicion.estado is EstadoCondicion.FUERA
    assert "no está entregando datos" in condicion.mensaje


def test_sensor_con_valor_imposible_esta_fallando():
    lectura = LecturaValidada(
        crear_lectura(temperatura=None),
        (ValorImposible(Variable.TEMPERATURA, 150.0, 0.0, 50.0),),
    )

    condicion = ReglaSensor(Variable.TEMPERATURA).evaluar(lectura)

    assert condicion.estado is EstadoCondicion.FUERA
    assert "150.0 °C" in condicion.mensaje


def test_sensor_que_mide_bien_es_normal():
    condicion = ReglaSensor(Variable.TEMPERATURA).evaluar(validada())

    assert condicion.estado is EstadoCondicion.NORMAL


def test_nodo_sin_sensor_de_suelo_no_tiene_reglas_de_sustrato():
    reglas = reglas_para(crear_nodo(sensor_suelo=False), CULTIVO_PREDETERMINADO)

    assert Variable.HUMEDAD_SUSTRATO not in {r.variable for r in reglas}
    assert {(r.tipo, r.variable) for r in reglas} == {
        (TipoAlerta.SENSOR, Variable.TEMPERATURA),
        (TipoAlerta.SENSOR, Variable.HUMEDAD_AIRE),
        (TipoAlerta.UMBRAL, Variable.TEMPERATURA),
        (TipoAlerta.UMBRAL, Variable.HUMEDAD_AIRE),
        (TipoAlerta.HONGOS, None),
    }


def test_nodo_con_sensor_de_suelo_tiene_siete_reglas():
    assert len(reglas_para(crear_nodo(sensor_suelo=True), CULTIVO_PREDETERMINADO)) == 7
