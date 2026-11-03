import json

import pytest

from greensense.adaptadores.entrada.mqtt.procesador import ProcesadorMensajes, Resultado
from greensense.aplicacion.casos_uso.registrar_estado import RegistrarEstado
from greensense.aplicacion.casos_uso.registrar_lectura import RegistrarLectura
from greensense.config import RAIZ_REPO
from greensense.dominio.modelos import EstadoNodo, SensorAire
from tests.fabricas import crear_nodo

pytestmark = pytest.mark.anyio

EJEMPLOS = RAIZ_REPO / "docs" / "contrato" / "ejemplos"
TEMA_LECTURAS = "greensense/inv1/nodo1/lecturas"
TEMA_ESTADO = "greensense/inv1/nodo1/estado"


def _ejemplo(nombre: str, **cambios) -> bytes:
    datos = json.loads((EJEMPLOS / nombre).read_text()) | cambios
    return json.dumps(datos).encode()


@pytest.fixture
async def procesador(lecturas, nodos, reloj, eventos) -> ProcesadorMensajes:
    await nodos.guardar(crear_nodo())
    return ProcesadorMensajes(
        RegistrarLectura(lecturas, nodos, reloj, eventos), RegistrarEstado(nodos, eventos)
    )


async def test_lectura_del_contrato_se_guarda(procesador, lecturas):
    resultado = await procesador.procesar(TEMA_LECTURAS, _ejemplo("lectura_completa.json"))

    assert resultado is Resultado.GUARDADA
    guardada = await lecturas.ultima("nodo1")
    assert (guardada.arranque, guardada.seq, guardada.temperatura) == (12, 1234, 24.3)


async def test_lectura_repetida_es_duplicada(procesador):
    carga = _ejemplo("lectura_completa.json")
    await procesador.procesar(TEMA_LECTURAS, carga)

    assert await procesador.procesar(TEMA_LECTURAS, carga) is Resultado.DUPLICADA


async def test_estado_conectado_actualiza_el_nodo(procesador, nodos):
    resultado = await procesador.procesar(TEMA_ESTADO, _ejemplo("estado_conectado.json"))

    assert resultado is Resultado.ESTADO
    nodo = await nodos.obtener("nodo1")
    assert nodo.estado is EstadoNodo.CONECTADO
    assert nodo.sensor_aire is SensorAire.DHT11
    assert nodo.sensor_suelo is False


async def test_estado_desconectado(procesador, nodos):
    await procesador.procesar(TEMA_ESTADO, _ejemplo("estado_desconectado.json"))

    assert (await nodos.obtener("nodo1")).estado is EstadoNodo.DESCONECTADO


@pytest.mark.parametrize("carga", [b"no es json", b"{}", b'{"v": 2}'])
async def test_mensaje_invalido_no_detiene_nada(procesador, carga):
    assert await procesador.procesar(TEMA_LECTURAS, carga) is Resultado.INVALIDO


async def test_nodo_del_mensaje_distinto_al_del_tema_se_rechaza(procesador, lecturas):
    carga = _ejemplo("lectura_completa.json", nodo="nodo2")

    assert await procesador.procesar(TEMA_LECTURAS, carga) is Resultado.RECHAZADO
    assert await lecturas.ultima("nodo2") is None


async def test_nodo_no_registrado_se_rechaza(procesador):
    tema = "greensense/inv1/nodo9/lecturas"
    carga = _ejemplo("lectura_completa.json", nodo="nodo9")

    assert await procesador.procesar(tema, carga) is Resultado.RECHAZADO


async def test_tema_desconocido_se_ignora(procesador):
    resultado = await procesador.procesar("otra/cosa", b"{}")

    assert resultado is Resultado.TEMA_DESCONOCIDO
