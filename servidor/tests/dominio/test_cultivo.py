from datetime import timedelta

import pytest

from greensense.dominio.cultivo import CULTIVO_PREDETERMINADO, Umbral, UmbralInvalido
from greensense.dominio.modelos import Variable


def test_cultivo_predeterminado_usa_los_rangos_de_la_propuesta():
    rangos = {u.variable: (u.minimo, u.maximo) for u in CULTIVO_PREDETERMINADO.umbrales}

    assert rangos == {
        Variable.TEMPERATURA: (18, 28),
        Variable.HUMEDAD_AIRE: (60, 80),
        Variable.HUMEDAD_SUSTRATO: (45, 70),
    }


def test_sustrato_alto_solo_es_critico_tras_horas():
    sustrato = CULTIVO_PREDETERMINADO.umbral(Variable.HUMEDAD_SUSTRATO)

    assert sustrato.tiempo_alto == timedelta(hours=3)
    assert sustrato.tiempo_bajo == timedelta(minutes=5)


@pytest.mark.parametrize(
    ("minimo", "maximo", "margen"),
    [(28, 18, 2), (20, 20, 0), (18, 28, 5), (18, 28, -1)],
)
def test_umbral_invalido(minimo, maximo, margen):
    with pytest.raises(UmbralInvalido):
        Umbral(Variable.TEMPERATURA, minimo, maximo, margen)
