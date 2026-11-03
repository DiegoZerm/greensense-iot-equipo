"""Cultivos, invernaderos y nodos, con su registro en la bitácora."""

from dataclasses import replace
from datetime import timedelta

import pytest

from greensense.aplicacion.casos_uso.configurar_cultivos import (
    BorrarCultivo,
    GuardarCultivo,
    ListarCultivos,
)
from greensense.aplicacion.casos_uso.gestionar_nodos import (
    BorrarInvernadero,
    CambiosNodo,
    ModificarInvernadero,
    ModificarNodo,
    RegistrarInvernadero,
    RegistrarNodo,
)
from greensense.aplicacion.casos_uso.registrar_lectura import RegistrarLectura
from greensense.aplicacion.casos_uso.revisar_nodos import RevisarNodos
from greensense.aplicacion.errores import Conflicto, NodoNoRegistrado, NoEncontrado
from greensense.dominio.bitacora import Accion, Objeto
from greensense.dominio.cultivo import CULTIVO_PREDETERMINADO, UmbralInvalido
from greensense.dominio.modelos import IdInvalido, SensorAire
from tests.fabricas import AHORA, crear_alerta, crear_lectura, crear_usuario

pytestmark = pytest.mark.anyio

ADMIN = crear_usuario(id=1)
TOMATE = replace(CULTIVO_PREDETERMINADO, id="tomate", nombre="Jitomate")


@pytest.fixture
def guardar(cultivos, anotador):
    return GuardarCultivo(cultivos, anotador)


async def test_crear_y_modificar_cultivo(guardar, cultivos, bitacora):
    await guardar.ejecutar(ADMIN, TOMATE, nuevo=True)
    caluroso = replace(TOMATE, umbrales=(replace(TOMATE.umbrales[0], maximo=32.0),))
    await guardar.ejecutar(ADMIN, caluroso, nuevo=False)

    assert await cultivos.obtener("tomate") == caluroso
    assert [c.id for c in await ListarCultivos(cultivos).ejecutar()] == [
        "hortalizas-hoja",
        "tomate",
    ]
    modificado, creado = await bitacora.listar()
    assert (creado.accion, modificado.accion) == (Accion.CREAR, Accion.MODIFICAR)
    assert modificado.objeto is Objeto.CULTIVO
    assert "temperatura 18 a 32" in modificado.detalle


async def test_cultivo_duplicado_o_inexistente(guardar):
    with pytest.raises(Conflicto):
        await guardar.ejecutar(ADMIN, CULTIVO_PREDETERMINADO, nuevo=True)
    with pytest.raises(NoEncontrado):
        await guardar.ejecutar(ADMIN, TOMATE, nuevo=False)


@pytest.mark.parametrize(
    "cultivo",
    [
        replace(TOMATE, id="Con Espacios"),
        replace(TOMATE, nombre=" "),
        replace(TOMATE, umbrales=TOMATE.umbrales + TOMATE.umbrales[:1]),
        replace(TOMATE, hongos=replace(TOMATE.hongos, humedad_minima=120)),
        replace(TOMATE, hongos=replace(TOMATE.hongos, tiempo_minimo=timedelta(seconds=-1))),
    ],
    ids=["id", "nombre", "variable-repetida", "humedad-hongos", "tiempo-hongos"],
)
async def test_cultivo_invalido(guardar, cultivo):
    with pytest.raises((UmbralInvalido, IdInvalido)):
        await guardar.ejecutar(ADMIN, cultivo, nuevo=True)


async def test_borrar_cultivo(guardar, cultivos, invernaderos, anotador):
    borrar = BorrarCultivo(cultivos, invernaderos, anotador)
    await guardar.ejecutar(ADMIN, TOMATE, nuevo=True)
    await RegistrarInvernadero(invernaderos).ejecutar("inv1", "Invernadero", "tomate")

    with pytest.raises(Conflicto, match="inv1"):
        await borrar.ejecutar(ADMIN, "tomate")
    with pytest.raises(Conflicto, match="predeterminado"):
        await borrar.ejecutar(ADMIN, "hortalizas-hoja")
    with pytest.raises(NoEncontrado):
        await borrar.ejecutar(ADMIN, "no-existe")

    await ModificarInvernadero(invernaderos, cultivos, anotador).ejecutar(
        ADMIN, "inv1", cultivo_id="hortalizas-hoja"
    )
    await borrar.ejecutar(ADMIN, "tomate")
    assert await cultivos.obtener("tomate") is None


async def test_invernadero_nuevo_valida_id_y_cultivo(invernaderos, cultivos, anotador, bitacora):
    registrar = RegistrarInvernadero(invernaderos, cultivos, anotador)

    await registrar.ejecutar("inv1", "Invernadero", actor=ADMIN, nuevo=True)

    with pytest.raises(Conflicto):
        await registrar.ejecutar("inv1", "Otro", actor=ADMIN, nuevo=True)
    with pytest.raises(NoEncontrado):
        await registrar.ejecutar("inv2", "Otro", "no-existe", actor=ADMIN, nuevo=True)
    (registro,) = await bitacora.listar()
    assert (registro.accion, registro.objeto, registro.objeto_id) == (
        Accion.CREAR,
        Objeto.INVERNADERO,
        "inv1",
    )


async def test_modificar_invernadero_anota_el_cambio(invernaderos, cultivos, anotador, bitacora):
    await cultivos.guardar(TOMATE)
    await RegistrarInvernadero(invernaderos).ejecutar("inv1", "Invernadero")

    await ModificarInvernadero(invernaderos, cultivos, anotador).ejecutar(
        ADMIN, "inv1", cultivo_id="tomate"
    )

    assert (await invernaderos.obtener("inv1")).cultivo_id == "tomate"
    assert (await bitacora.listar())[0].detalle == "cultivo_id: hortalizas-hoja → tomate"


async def test_invernadero_con_nodos_no_se_borra(invernaderos, nodos, anotador):
    await RegistrarInvernadero(invernaderos).ejecutar("inv1", "Invernadero")
    await RegistrarInvernadero(invernaderos).ejecutar("inv2", "Vacío")
    await RegistrarNodo(invernaderos, nodos).ejecutar("inv1", "nodo1", "Nodo")
    borrar = BorrarInvernadero(invernaderos, nodos, anotador)

    with pytest.raises(Conflicto):
        await borrar.ejecutar(ADMIN, "inv1")
    await borrar.ejecutar(ADMIN, "inv2")

    assert [i.id for i in await invernaderos.listar()] == ["inv1"]


async def test_alta_de_nodo_por_la_api_rechaza_duplicados(invernaderos, nodos, anotador, bitacora):
    await RegistrarInvernadero(invernaderos).ejecutar("inv1", "Invernadero")
    registrar = RegistrarNodo(invernaderos, nodos, anotador)

    await registrar.ejecutar("inv1", "nodo1", "Nodo", SensorAire.DHT22, True, ADMIN, nuevo=True)

    with pytest.raises(Conflicto):
        await registrar.ejecutar("inv1", "nodo1", "Otra vez", actor=ADMIN, nuevo=True)
    (registro,) = await bitacora.listar()
    assert registro.accion is Accion.ALTA
    assert registro.detalle == "Nodo en inv1, DHT22 con sensor de suelo"


@pytest.fixture
async def nodo_con_alerta(invernaderos, nodos, alertas):
    await RegistrarInvernadero(invernaderos).ejecutar("inv1", "Invernadero")
    nodo = await RegistrarNodo(invernaderos, nodos).ejecutar("inv1", "nodo1", "Nodo")
    await nodos.guardar(nodo.con_lectura(AHORA - timedelta(hours=1)))
    return await alertas.guardar(crear_alerta())


@pytest.fixture
def modificar_nodo(nodos, alertas, eventos, reloj, anotador):
    return ModificarNodo(nodos, alertas, eventos, reloj, anotador)


async def test_baja_de_nodo(
    modificar_nodo, nodo_con_alerta, nodos, alertas, lecturas, eventos, reloj, bitacora, usuarios
):
    nodo = await modificar_nodo.ejecutar(ADMIN, "nodo1", CambiosNodo(activo=False))

    assert nodo.activo is False
    # Sus alertas se resuelven y avisan al panel.
    assert await alertas.activas("nodo1") == []
    assert [e.tipo for e in eventos.publicados] == ["alerta", "nodo"]
    assert (await bitacora.listar())[0].accion is Accion.BAJA
    # Ya no se aceptan sus lecturas ni se revisa si está desconectado.
    with pytest.raises(NodoNoRegistrado):
        await RegistrarLectura(lecturas, nodos, reloj, eventos).ejecutar("inv1", crear_lectura())
    revisar = RevisarNodos(nodos, alertas, _SinNotificar(), eventos, reloj)
    assert await revisar.ejecutar() == []


async def test_modificar_datos_del_nodo(modificar_nodo, nodo_con_alerta, alertas, bitacora):
    nodo = await modificar_nodo.ejecutar(
        ADMIN, "nodo1", CambiosNodo(nombre="Junto a la puerta", sensor_suelo=True)
    )

    assert (nodo.nombre, nodo.sensor_suelo, nodo.activo) == ("Junto a la puerta", True, True)
    assert len(await alertas.activas("nodo1")) == 1
    assert (await bitacora.listar())[0].detalle == (
        "nombre: Nodo → Junto a la puerta; sensor_suelo: no → sí"
    )


async def test_modificar_nodo_inexistente(modificar_nodo):
    with pytest.raises(NoEncontrado):
        await modificar_nodo.ejecutar(ADMIN, "nodo9", CambiosNodo(nombre="X"))


class _SinNotificar:
    async def ejecutar(self, alerta):  # pragma: no cover - no debe llamarse
        raise AssertionError("no debería notificar")
