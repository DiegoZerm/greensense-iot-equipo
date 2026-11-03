from datetime import timedelta

import pytest

from greensense.dominio.modelos import SensorAire, Variable
from greensense.dominio.validacion import LecturaRechazada, validar_lectura
from tests.fabricas import AHORA, crear_lectura, crear_nodo


def test_lectura_dentro_de_rango_queda_igual():
    lectura = crear_lectura()

    resultado = validar_lectura(lectura, crear_nodo(), AHORA)

    assert resultado.lectura == lectura
    assert resultado.imposibles == ()


@pytest.mark.parametrize(
    ("sensor", "variable", "valor"),
    [
        (SensorAire.DHT11, Variable.TEMPERATURA, -5.0),
        (SensorAire.DHT11, Variable.TEMPERATURA, 55.0),
        (SensorAire.DHT11, Variable.HUMEDAD_AIRE, 95.0),
        (SensorAire.DHT22, Variable.TEMPERATURA, -40.5),
        (SensorAire.DHT22, Variable.HUMEDAD_AIRE, 100.1),
        (SensorAire.DHT22, Variable.HUMEDAD_SUSTRATO, 120.0),
    ],
)
def test_valor_fuera_del_rango_del_sensor_se_descarta(sensor, variable, valor):
    lectura = crear_lectura().con_valor(variable, valor)

    resultado = validar_lectura(lectura, crear_nodo(sensor_aire=sensor), AHORA)

    assert resultado.lectura.valor(variable) is None
    assert [i.variable for i in resultado.imposibles] == [variable]
    assert resultado.imposibles[0].valor == valor


def test_el_mismo_valor_es_valido_en_un_dht22_y_no_en_un_dht11():
    lectura = crear_lectura(temperatura=-10.0)

    assert (
        validar_lectura(lectura, crear_nodo(sensor_aire=SensorAire.DHT22), AHORA).imposibles == ()
    )
    assert validar_lectura(lectura, crear_nodo(sensor_aire=SensorAire.DHT11), AHORA).imposibles


def test_nodo_sin_sensor_de_suelo_nunca_guarda_sustrato():
    lectura = crear_lectura(humedad_sustrato=40.0)

    resultado = validar_lectura(lectura, crear_nodo(sensor_suelo=False), AHORA)

    assert resultado.lectura.humedad_sustrato is None
    assert resultado.imposibles == ()


def test_valores_nulos_se_aceptan():
    lectura = crear_lectura(temperatura=None, humedad_aire=None, humedad_sustrato=None)

    resultado = validar_lectura(lectura, crear_nodo(), AHORA)

    assert resultado.lectura == lectura


def test_lectura_del_futuro_se_rechaza():
    lectura = crear_lectura(ts=AHORA + timedelta(minutes=6))

    with pytest.raises(LecturaRechazada, match="futuro"):
        validar_lectura(lectura, crear_nodo(), AHORA)


def test_reloj_del_nodo_ligeramente_adelantado_se_tolera():
    lectura = crear_lectura(ts=AHORA + timedelta(minutes=4))

    assert validar_lectura(lectura, crear_nodo(), AHORA).lectura == lectura


def test_lectura_de_otro_nodo_se_rechaza():
    with pytest.raises(LecturaRechazada):
        validar_lectura(crear_lectura(nodo_id="nodo2"), crear_nodo(), AHORA)
