import pytest

from greensense.aplicacion.casos_uso.registrar_lectura import RegistrarLectura
from greensense.aplicacion.errores import NodoNoRegistrado
from greensense.dominio.modelos import EstadoNodo, Variable
from tests.fabricas import AHORA, crear_lectura, crear_nodo

pytestmark = pytest.mark.anyio


@pytest.fixture
async def caso(lecturas, nodos, reloj, eventos) -> RegistrarLectura:
    await nodos.guardar(crear_nodo())
    return RegistrarLectura(lecturas, nodos, reloj, eventos)


async def test_guarda_la_lectura_y_actualiza_el_nodo(caso, lecturas, nodos):
    resultado = await caso.ejecutar("inv1", crear_lectura())

    assert resultado.guardada
    assert await lecturas.ultima("nodo1") == crear_lectura()
    nodo = await nodos.obtener("nodo1")
    assert nodo.estado is EstadoNodo.CONECTADO
    assert nodo.ultima_lectura_en == AHORA


async def test_publica_un_evento_para_el_panel(caso, eventos):
    await caso.ejecutar("inv1", crear_lectura())

    (evento,) = eventos.publicados
    assert evento.tipo == "lectura"
    assert evento.datos["lectura"] == crear_lectura()
    assert evento.datos["nodo"].estado is EstadoNodo.CONECTADO


async def test_lectura_reenviada_no_se_duplica_ni_se_publica(caso, eventos):
    await caso.ejecutar("inv1", crear_lectura())

    resultado = await caso.ejecutar("inv1", crear_lectura())

    assert not resultado.guardada
    assert len(eventos.publicados) == 1


async def test_valor_imposible_se_guarda_como_nulo_y_se_reporta(caso, lecturas):
    resultado = await caso.ejecutar("inv1", crear_lectura(temperatura=150.0))

    assert resultado.guardada
    assert [i.variable for i in resultado.imposibles] == [Variable.TEMPERATURA]
    assert (await lecturas.ultima("nodo1")).temperatura is None


async def test_nodo_no_registrado_se_rechaza(caso, lecturas):
    with pytest.raises(NodoNoRegistrado):
        await caso.ejecutar("inv1", crear_lectura(nodo_id="intruso"))

    assert await lecturas.ultima("intruso") is None


async def test_nodo_de_otro_invernadero_se_rechaza(caso):
    with pytest.raises(NodoNoRegistrado):
        await caso.ejecutar("inv2", crear_lectura())
