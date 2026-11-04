"""La demostración genera, con las reglas reales, todo lo que la app necesita mostrar."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from greensense.adaptadores.salida.despertador import DespertadorAsyncio
from greensense.composicion import crear_contenedor
from greensense.config import Config
from greensense.dominio.alertas import Severidad, TipoAlerta
from greensense.dominio.bitacora import Accion
from greensense.dominio.modelos import EstadoNodo, Variable
from simulador.demo import MUY_ATRAS, Demostracion, RelojDemo


@pytest.fixture(scope="module")
def demo():
    async def generar():
        config = Config(
            _env_file=None, almacenamiento="memoria", mqtt_habilitado=False, hash_rapido=True
        )
        fin = datetime(2026, 11, 3, 18, 0, tzinfo=UTC)
        reloj = RelojDemo()
        reloj.fijar(MUY_ATRAS)
        contenedor = crear_contenedor(config, DespertadorAsyncio(), reloj)
        demostracion = Demostracion(contenedor, reloj, fin, dias=7)
        await demostracion.preparar()
        lecturas = await demostracion.simular(lambda: demostracion.fin)
        alertas = await contenedor.consultar_alertas.ejecutar(limite=10_000)
        nodos = {n.id: n for n in await contenedor.listar_nodos.ejecutar()}
        bitacora = await contenedor.consultar_bitacora.ejecutar()
        return lecturas, alertas, nodos, bitacora

    return asyncio.run(generar())


def test_genera_una_semana_de_lecturas(demo):
    lecturas, *_ = demo
    # Seis nodos cada minuto, menos los huecos y el nodo que se dio de baja.
    assert 50_000 < lecturas < 6 * 7 * 1440


def test_hay_alertas_de_los_cuatro_tipos_sin_ruido(demo):
    _, alertas, *_ = demo
    assert {a.tipo for a in alertas} == set(TipoAlerta)
    # Sin la holgura del margen eran miles de advertencias.
    assert len(alertas) < 60


def test_quedan_activas_una_de_cada_estado_para_el_panel(demo):
    _, alertas, *_ = demo
    activas = {(a.nodo_id, a.tipo, a.variable, a.severidad) for a in alertas if a.activa}
    assert activas == {
        ("lechuga-1", TipoAlerta.UMBRAL, Variable.HUMEDAD_AIRE, Severidad.ADVERTENCIA),
        ("semillero", TipoAlerta.DESCONEXION, None, Severidad.CRITICA),
        ("tomate-1", TipoAlerta.UMBRAL, Variable.TEMPERATURA, Severidad.CRITICA),
        ("tomate-2", TipoAlerta.UMBRAL, Variable.HUMEDAD_SUSTRATO, Severidad.ADVERTENCIA),
    }


def test_las_criticas_pasadas_las_atendio_alguien(demo):
    _, alertas, *_ = demo
    pasadas = [a for a in alertas if a.severidad is Severidad.CRITICA and not a.activa]
    assert pasadas
    assert all(a.atendida_por_nombre for a in pasadas)


def test_estado_de_los_nodos(demo):
    _, _, nodos, _ = demo
    assert nodos["semillero"].estado is EstadoNodo.DESCONECTADO
    assert nodos["semillero"].nombre == "Semillero, charolas"
    assert not nodos["prueba-1"].activo
    assert nodos["lechuga-1"].estado is EstadoNodo.CONECTADO


def test_la_bitacora_tiene_altas_bajas_cambios_sesiones_y_exportaciones(demo):
    *_, bitacora = demo
    acciones = {e.registro.accion for e in bitacora}
    assert set(Accion) <= acciones | {Accion.BORRAR}


def test_reanudar_se_pone_al_dia_sin_desconexiones_ni_lecturas_repetidas():
    async def probar():
        config = Config(
            _env_file=None, almacenamiento="memoria", mqtt_habilitado=False, hash_rapido=True
        )
        fin = datetime(2026, 11, 3, 18, 0, tzinfo=UTC)
        reloj = RelojDemo()
        reloj.fijar(MUY_ATRAS)
        contenedor = crear_contenedor(config, DespertadorAsyncio(), reloj)
        primera = Demostracion(contenedor, reloj, fin, dias=1)
        await primera.preparar()
        await primera.simular(lambda: primera.fin)
        antes = len(await contenedor.consultar_alertas.ejecutar(limite=10_000))

        # Se apagó dos horas y vuelve a arrancar.
        despues = fin + timedelta(hours=2)
        segunda = Demostracion(contenedor, reloj, despues, dias=1)
        await segunda.reanudar()
        lecturas = await segunda.simular(lambda: despues)
        alertas = await contenedor.consultar_alertas.ejecutar(limite=10_000)
        estados = {e.nodo.id: e for e in await contenedor.consultar_estado_actual.ejecutar()}
        return lecturas, antes, alertas, estados

    lecturas, antes, alertas, estados = asyncio.run(probar())
    # Cuatro nodos mandan (el semillero sigue callado y el de prueba está de baja).
    assert lecturas == 4 * 120
    assert len(alertas) == antes
    assert estados["lechuga-1"].ultima.ts == datetime(2026, 11, 3, 20, 0, tzinfo=UTC)
    assert "prueba-1" not in estados
