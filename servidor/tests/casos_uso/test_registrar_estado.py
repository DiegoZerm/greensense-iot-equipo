import pytest

from greensense.aplicacion.casos_uso.registrar_estado import EstadoReportado, RegistrarEstado
from greensense.aplicacion.errores import NodoNoRegistrado
from greensense.dominio.modelos import EstadoNodo, SensorAire
from tests.fabricas import crear_nodo

pytestmark = pytest.mark.anyio


@pytest.fixture
async def caso(nodos, eventos) -> RegistrarEstado:
    await nodos.guardar(crear_nodo(sensor_aire=SensorAire.DHT22, sensor_suelo=True))
    return RegistrarEstado(nodos, eventos)


async def test_conectado_actualiza_la_configuracion_que_reporta_el_nodo(caso, nodos):
    reportado = EstadoReportado(
        conectado=True,
        firmware="0.2.0",
        sensor_aire=SensorAire.DHT11,
        sensor_suelo=False,
        periodo_s=30,
    )

    nodo = await caso.ejecutar("inv1", "nodo1", reportado)

    assert nodo == await nodos.obtener("nodo1")
    assert nodo.estado is EstadoNodo.CONECTADO
    assert (nodo.firmware, nodo.sensor_aire, nodo.sensor_suelo, nodo.periodo_s) == (
        "0.2.0",
        SensorAire.DHT11,
        False,
        30,
    )


async def test_desconectado_conserva_la_configuracion(caso):
    nodo = await caso.ejecutar("inv1", "nodo1", EstadoReportado(conectado=False))

    assert nodo.estado is EstadoNodo.DESCONECTADO
    assert nodo.sensor_aire is SensorAire.DHT22
    assert nodo.sensor_suelo is True


async def test_publica_el_cambio_de_estado(caso, eventos):
    await caso.ejecutar("inv1", "nodo1", EstadoReportado(conectado=False))

    (evento,) = eventos.publicados
    assert evento.tipo == "nodo"
    assert evento.datos["nodo"].estado is EstadoNodo.DESCONECTADO


async def test_nodo_no_registrado_se_rechaza(caso):
    with pytest.raises(NodoNoRegistrado):
        await caso.ejecutar("inv1", "otro", EstadoReportado(conectado=True))
