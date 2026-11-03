from datetime import timedelta

import pytest

from greensense.aplicacion.casos_uso.consultar_estado_actual import ConsultarEstadoActual
from greensense.dominio.alertas import TipoAlerta
from tests.fabricas import AHORA, crear_alerta, crear_lectura, crear_nodo

pytestmark = pytest.mark.anyio


async def test_cada_nodo_con_su_lectura_mas_reciente(lecturas, nodos, alertas):
    await nodos.guardar(crear_nodo(id="nodo2"))
    await nodos.guardar(crear_nodo(id="nodo1"))
    await lecturas.guardar(crear_lectura(seq=1, ts=AHORA))
    await lecturas.guardar(crear_lectura(seq=0, ts=AHORA - timedelta(minutes=1)))

    estados = await ConsultarEstadoActual(lecturas, nodos, alertas).ejecutar()

    assert [e.nodo.id for e in estados] == ["nodo1", "nodo2"]
    assert estados[0].ultima.seq == 1
    assert estados[1].ultima is None


async def test_incluye_las_alertas_activas_de_cada_nodo(lecturas, nodos, alertas):
    await nodos.guardar(crear_nodo(id="nodo1"))
    await nodos.guardar(crear_nodo(id="nodo2"))
    activa = await alertas.guardar(crear_alerta(nodo_id="nodo1"))
    await alertas.guardar(crear_alerta(nodo_id="nodo1", tipo=TipoAlerta.HONGOS, resuelta_en=AHORA))

    estados = await ConsultarEstadoActual(lecturas, nodos, alertas).ejecutar()

    assert estados[0].alertas == [activa]
    assert estados[1].alertas == []
