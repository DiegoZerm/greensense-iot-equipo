"""Verifica que los mensajes del servidor coincidan con docs/contrato."""

import json

import pytest
from pydantic import ValidationError

from greensense.adaptadores.entrada.mqtt.mensajes import (
    MensajeEstado,
    MensajeLectura,
    Tema,
    parsear_tema,
)
from greensense.config import RAIZ_REPO

CONTRATO = RAIZ_REPO / "docs" / "contrato"


def _cargar(nombre: str) -> dict:
    return json.loads((CONTRATO / nombre).read_text())


@pytest.mark.parametrize(
    ("modelo", "esquema"),
    [(MensajeLectura, "lectura.schema.json"), (MensajeEstado, "estado.schema.json")],
)
def test_modelo_tiene_los_mismos_campos_que_el_esquema(modelo, esquema):
    esquema = _cargar(esquema)

    assert set(modelo.model_fields) == set(esquema["properties"])
    obligatorios = {nombre for nombre, campo in modelo.model_fields.items() if campo.is_required()}
    assert obligatorios == set(esquema["required"])


@pytest.mark.parametrize("archivo", sorted((CONTRATO / "ejemplos").glob("lectura_*.json")))
def test_ejemplos_de_lectura_son_validos(archivo):
    MensajeLectura.model_validate_json(archivo.read_text())


@pytest.mark.parametrize("archivo", sorted((CONTRATO / "ejemplos").glob("estado_*.json")))
def test_ejemplos_de_estado_son_validos(archivo):
    MensajeEstado.model_validate_json(archivo.read_text())


def test_lectura_sin_sensor_de_suelo_acepta_null():
    lectura = MensajeLectura.model_validate(_cargar("ejemplos/lectura_sin_suelo.json"))

    assert lectura.humedad_sustrato is None


@pytest.mark.parametrize(
    "cambio",
    [
        {"v": 2},
        {"nodo": "Nodo 1"},
        {"seq": -1},
        {"ts": "2026-11-01T16:00:00"},  # sin zona horaria
        {"rssi": 5},
        {"campo_extra": 1},
    ],
)
def test_lectura_invalida_se_rechaza(cambio):
    datos = _cargar("ejemplos/lectura_completa.json") | cambio

    with pytest.raises(ValidationError):
        MensajeLectura.model_validate(datos)


def test_lectura_sin_campo_obligatorio_se_rechaza():
    datos = _cargar("ejemplos/lectura_completa.json")
    del datos["humedad_sustrato"]

    with pytest.raises(ValidationError):
        MensajeLectura.model_validate(datos)


def test_estado_conectado_sin_configuracion_se_rechaza():
    with pytest.raises(ValidationError, match="sensor_aire"):
        MensajeEstado.model_validate(
            {
                "v": 1,
                "estado": "conectado",
                "arranque": 1,
                "firmware": "0.1.0",
                "sensor_suelo": False,
                "periodo_s": 60,
            }
        )


@pytest.mark.parametrize(
    ("tema", "esperado"),
    [
        ("greensense/inv1/nodo1/lecturas", Tema("inv1", "nodo1", "lecturas")),
        ("greensense/inv1/nodo-2/estado", Tema("inv1", "nodo-2", "estado")),
        ("greensense/inv1/nodo1/comandos", None),
        ("greensense/inv1/lecturas", None),
        ("otro/inv1/nodo1/lecturas", None),
        ("greensense/INV1/nodo1/lecturas", None),
    ],
)
def test_parsear_tema(tema, esperado):
    assert parsear_tema(tema) == esperado
