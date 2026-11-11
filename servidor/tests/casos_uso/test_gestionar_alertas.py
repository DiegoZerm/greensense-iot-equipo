from datetime import timedelta

import pytest

from greensense.aplicacion.casos_uso.gestionar_alertas import AtenderAlerta, ConsultarAlertas
from greensense.aplicacion.errores import AlertaNoEncontrada
from tests.fabricas import AHORA, crear_alerta

pytestmark = pytest.mark.anyio


async def test_atender_marca_la_hora_una_sola_vez(alertas, eventos, reloj):
    alerta = await alertas.guardar(crear_alerta())
    atender = AtenderAlerta(alertas, eventos, reloj)

    atendida = await atender.ejecutar(alerta.id)
    reloj.actual += timedelta(minutes=5)
    otra_vez = await atender.ejecutar(alerta.id)

    assert atendida.atendida_en == AHORA
    assert otra_vez.atendida_en == AHORA
    assert atendida.activa
    assert len(eventos.publicados) == 1


async def test_atender_alerta_inexistente(alertas, eventos, reloj):
    with pytest.raises(AlertaNoEncontrada):
        await AtenderAlerta(alertas, eventos, reloj).ejecutar(99)


async def test_consultar_mas_recientes_primero_y_solo_activas(alertas):
    vieja = await alertas.guardar(crear_alerta(iniciada_en=AHORA - timedelta(hours=1)))
    resuelta = await alertas.guardar(crear_alerta(resuelta_en=AHORA))

    consultar = ConsultarAlertas(alertas)

    assert await consultar.ejecutar() == [resuelta, vieja]
    assert await consultar.ejecutar(solo_activas=True) == [vieja]
    assert await consultar.ejecutar(limite=1) == [resuelta]
