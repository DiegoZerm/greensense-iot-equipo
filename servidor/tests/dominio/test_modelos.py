from datetime import timedelta

import pytest

from greensense.dominio.modelos import EstadoNodo, IdInvalido, validar_id
from tests.fabricas import AHORA, crear_nodo


@pytest.mark.parametrize("valido", ["nodo1", "invernadero-norte", "a", "x" * 32])
def test_id_valido(valido):
    assert validar_id(valido) == valido


@pytest.mark.parametrize("invalido", ["", "Nodo1", "nodo 1", "nodo/1", "nodo_1", "x" * 33])
def test_id_invalido(invalido):
    with pytest.raises(IdInvalido):
        validar_id(invalido)


def test_con_lectura_marca_conectado_y_actualiza_la_hora():
    nodo = crear_nodo().con_lectura(AHORA)

    assert nodo.estado is EstadoNodo.CONECTADO
    assert nodo.ultima_lectura_en == AHORA


def test_lectura_reenviada_no_retrocede_la_ultima_hora():
    nodo = crear_nodo().con_lectura(AHORA).con_lectura(AHORA - timedelta(hours=1))

    assert nodo.ultima_lectura_en == AHORA
