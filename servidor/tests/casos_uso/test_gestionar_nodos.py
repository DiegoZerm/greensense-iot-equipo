import pytest

from greensense.aplicacion.casos_uso.gestionar_nodos import RegistrarInvernadero, RegistrarNodo
from greensense.aplicacion.errores import InvernaderoNoRegistrado
from greensense.dominio.modelos import EstadoNodo, IdInvalido, SensorAire
from tests.fabricas import AHORA

pytestmark = pytest.mark.anyio


async def test_registra_invernadero_y_nodo(invernaderos, nodos):
    await RegistrarInvernadero(invernaderos).ejecutar("inv1", "Invernadero de prueba")

    nodo = await RegistrarNodo(invernaderos, nodos).ejecutar(
        "inv1", "nodo1", "Junto a la puerta", SensorAire.DHT11
    )

    assert await nodos.obtener("nodo1") == nodo
    assert nodo.estado is EstadoNodo.DESCONOCIDO


async def test_nodo_en_invernadero_inexistente_se_rechaza(invernaderos, nodos):
    with pytest.raises(InvernaderoNoRegistrado):
        await RegistrarNodo(invernaderos, nodos).ejecutar("inv9", "nodo1", "Nodo")


async def test_id_invalido_se_rechaza(invernaderos, nodos):
    with pytest.raises(IdInvalido):
        await RegistrarInvernadero(invernaderos).ejecutar("Invernadero 1", "Nombre")


async def test_volver_a_registrar_conserva_el_estado(invernaderos, nodos):
    await RegistrarInvernadero(invernaderos).ejecutar("inv1", "Invernadero")
    registrar = RegistrarNodo(invernaderos, nodos)
    nodo = await registrar.ejecutar("inv1", "nodo1", "Nombre viejo")
    await nodos.guardar(nodo.con_lectura(AHORA))

    nodo = await registrar.ejecutar("inv1", "nodo1", "Nombre nuevo", sensor_suelo=True)

    assert nodo.nombre == "Nombre nuevo"
    assert nodo.sensor_suelo is True
    assert nodo.ultima_lectura_en == AHORA
