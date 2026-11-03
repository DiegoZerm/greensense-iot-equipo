"""Las mismas pruebas para cada implementación de los repositorios.

Las de PostgreSQL corren si GREENSENSE_PRUEBAS_DB tiene la URL de una base de datos
de pruebas, que se borra y se migra al inicio. Ejemplo:
GREENSENSE_PRUEBAS_DB=postgresql+psycopg://greensense:clave@localhost:5432/greensense_pruebas
"""

import os
from dataclasses import replace
from datetime import timedelta
from typing import NamedTuple

import pytest
from sqlalchemy import create_engine, text

from greensense.adaptadores.salida import memoria, postgres
from greensense.aplicacion.errores import CorreoDuplicado
from greensense.cli import migrar
from greensense.dominio.alertas import Severidad, TipoAlerta
from greensense.dominio.bitacora import Accion, Objeto, RegistroBitacora
from greensense.dominio.cultivo import CULTIVO_PREDETERMINADO, Cultivo, RiesgoHongos, Umbral
from greensense.dominio.modelos import EstadoNodo, Invernadero, SensorAire, Variable
from greensense.dominio.notificaciones import Envio, EstadoEnvio, SuscripcionPush
from greensense.dominio.usuarios import Rol
from tests.fabricas import AHORA, crear_alerta, crear_lectura, crear_nodo, crear_usuario

pytestmark = pytest.mark.anyio

URL_PRUEBAS = os.environ.get("GREENSENSE_PRUEBAS_DB")


@pytest.fixture(scope="session")
def base_de_pruebas() -> str:
    if not URL_PRUEBAS:
        if os.environ.get("CI"):
            pytest.fail("En la CI las pruebas de PostgreSQL son obligatorias")
        pytest.skip("GREENSENSE_PRUEBAS_DB no está definida")
    motor = create_engine(URL_PRUEBAS)
    with motor.begin() as conexion:
        conexion.execute(text("DROP SCHEMA public CASCADE"))
        conexion.execute(text("CREATE SCHEMA public"))
    motor.dispose()
    migrar(URL_PRUEBAS)
    return URL_PRUEBAS


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=pytest.mark.postgres)])
async def repos(request):
    if request.param == "memoria":
        suscripciones = memoria.RepositorioSuscripcionesMemoria()
        yield Repos(
            memoria.RepositorioInvernaderosMemoria(),
            memoria.RepositorioNodosMemoria(),
            memoria.RepositorioLecturasMemoria(),
            memoria.RepositorioCultivosMemoria(CULTIVO_PREDETERMINADO),
            memoria.RepositorioAlertasMemoria(),
            suscripciones,
            memoria.RepositorioEnviosMemoria(suscripciones),
            memoria.RepositorioUsuariosMemoria(),
            memoria.RepositorioBitacoraMemoria(),
        )
        return

    motor = postgres.crear_motor(request.getfixturevalue("base_de_pruebas"))
    async with motor.begin() as conexion:
        await conexion.execute(
            text(
                "TRUNCATE envio_push, suscripcion_push, alerta, lectura, nodo, invernadero,"
                " bitacora, usuario CASCADE;"
                "DELETE FROM cultivo WHERE id <> 'hortalizas-hoja'"
            )
        )
    yield Repos(
        postgres.RepositorioInvernaderosPostgres(motor),
        postgres.RepositorioNodosPostgres(motor),
        postgres.RepositorioLecturasPostgres(motor),
        postgres.RepositorioCultivosPostgres(motor),
        postgres.RepositorioAlertasPostgres(motor),
        postgres.RepositorioSuscripcionesPostgres(motor),
        postgres.RepositorioEnviosPostgres(motor),
        postgres.RepositorioUsuariosPostgres(motor),
        postgres.RepositorioBitacoraPostgres(motor),
    )
    await motor.dispose()


class Repos(NamedTuple):
    invernaderos: object
    nodos: object
    lecturas: object
    cultivos: object
    alertas: object
    suscripciones: object
    envios: object
    usuarios: object
    bitacora: object


@pytest.fixture
async def con_nodo(repos):
    await repos.invernaderos.guardar(Invernadero("inv1", "Invernadero"))
    await repos.nodos.guardar(crear_nodo())
    return repos


@pytest.fixture
async def usuario(repos):
    return await repos.usuarios.guardar(crear_usuario())


async def test_invernadero_se_guarda_y_se_actualiza(repos):
    invernaderos = repos.invernaderos

    await invernaderos.guardar(Invernadero("inv1", "Viejo"))
    await invernaderos.guardar(Invernadero("inv1", "Nuevo"))

    assert await invernaderos.obtener("inv1") == Invernadero("inv1", "Nuevo")
    assert await invernaderos.obtener("inv9") is None


async def test_invernaderos_se_listan_y_se_borran(repos):
    await repos.invernaderos.guardar(Invernadero("inv1", "Uno"))
    await repos.invernaderos.guardar(Invernadero("inv2", "Dos"))

    await repos.invernaderos.borrar("inv1")

    assert await repos.invernaderos.listar() == [Invernadero("inv2", "Dos")]


async def test_nodo_se_guarda_y_se_actualiza(con_nodo):
    nodos = con_nodo.nodos
    actualizado = replace(
        crear_nodo(),
        estado=EstadoNodo.CONECTADO,
        sensor_aire=SensorAire.DHT11,
        firmware="0.1.0",
        ultima_lectura_en=AHORA,
        activo=False,
    )

    await nodos.guardar(actualizado)

    assert await nodos.obtener("nodo1") == actualizado
    assert await nodos.listar() == [actualizado]
    assert await nodos.obtener("nodo9") is None


async def test_lectura_se_guarda_una_sola_vez(con_nodo):
    lecturas = con_nodo.lecturas

    assert await lecturas.guardar(crear_lectura()) is True
    assert await lecturas.guardar(crear_lectura()) is False
    assert await lecturas.ultima("nodo1") == crear_lectura()


async def test_mismo_seq_en_otro_arranque_es_otra_lectura(con_nodo):
    lecturas = con_nodo.lecturas
    await lecturas.guardar(crear_lectura(arranque=1, seq=0))

    nueva = crear_lectura(arranque=2, seq=0, ts=AHORA + timedelta(minutes=1))

    assert await lecturas.guardar(nueva) is True
    assert await lecturas.ultima("nodo1") == nueva


async def test_ultima_es_la_mas_reciente_aunque_llegue_antes(con_nodo):
    lecturas = con_nodo.lecturas
    reciente = crear_lectura(seq=5, ts=AHORA)
    reenviada = crear_lectura(seq=4, ts=AHORA - timedelta(minutes=1))

    await lecturas.guardar(reciente)
    await lecturas.guardar(reenviada)

    assert await lecturas.ultima("nodo1") == reciente


async def test_valores_nulos_se_conservan(con_nodo):
    lecturas = con_nodo.lecturas
    sin_datos = crear_lectura(
        temperatura=None, humedad_aire=None, humedad_sustrato=None, muestras=None, rssi=None
    )

    await lecturas.guardar(sin_datos)

    assert await lecturas.ultima("nodo1") == sin_datos


async def test_nodo_sin_lecturas(con_nodo):
    lecturas = con_nodo.lecturas

    assert await lecturas.ultima("nodo1") is None


async def test_invernadero_guarda_su_cultivo(repos):
    await repos.cultivos.guardar(replace(CULTIVO_PREDETERMINADO, id="tomate", nombre="Tomate"))
    await repos.invernaderos.guardar(Invernadero("inv1", "Invernadero", cultivo_id="tomate"))

    assert (await repos.invernaderos.obtener("inv1")).cultivo_id == "tomate"


async def test_cultivo_predeterminado_existe(repos):
    assert await repos.cultivos.obtener("hortalizas-hoja") == CULTIVO_PREDETERMINADO


async def test_cultivo_se_guarda_con_sus_umbrales(repos):
    cultivo = Cultivo(
        "tomate",
        "Tomate",
        (
            Umbral(Variable.TEMPERATURA, 15, 30, 2, timedelta(minutes=10), timedelta(minutes=3)),
            Umbral(Variable.HUMEDAD_AIRE, 55, 85, 5),
        ),
        RiesgoHongos(90, 18, timedelta(hours=2)),
    )

    await repos.cultivos.guardar(cultivo)
    assert await repos.cultivos.obtener("tomate") == cultivo

    menos = replace(cultivo, umbrales=cultivo.umbrales[:1])
    await repos.cultivos.guardar(menos)
    assert await repos.cultivos.obtener("tomate") == menos
    assert await repos.cultivos.obtener("no-existe") is None


async def test_cultivos_se_listan_y_se_borran(repos):
    tomate = replace(CULTIVO_PREDETERMINADO, id="tomate", nombre="Tomate")
    await repos.cultivos.guardar(tomate)

    assert {c.id for c in await repos.cultivos.listar()} == {"hortalizas-hoja", "tomate"}
    assert tomate in await repos.cultivos.listar()

    await repos.cultivos.borrar("tomate")
    assert [c.id for c in await repos.cultivos.listar()] == ["hortalizas-hoja"]


async def test_usuario_recibe_id_y_se_actualiza(repos):
    usuario = await repos.usuarios.guardar(crear_usuario())
    assert usuario.id is not None

    cambiado = replace(usuario, rol=Rol.TECNICO, activo=False, nombre="Ana")
    await repos.usuarios.guardar(cambiado)

    assert await repos.usuarios.obtener(usuario.id) == cambiado
    assert await repos.usuarios.por_correo("ana@ejemplo.com") == cambiado
    assert await repos.usuarios.por_correo("nadie@ejemplo.com") is None
    assert await repos.usuarios.listar() == [cambiado]


async def test_correo_duplicado_se_rechaza(repos):
    await repos.usuarios.guardar(crear_usuario())
    otro = await repos.usuarios.guardar(crear_usuario(correo="otro@ejemplo.com"))

    with pytest.raises(CorreoDuplicado):
        await repos.usuarios.guardar(crear_usuario(nombre="Copia"))
    with pytest.raises(CorreoDuplicado):
        await repos.usuarios.guardar(replace(otro, correo="ana@ejemplo.com"))


async def test_bitacora_mas_reciente_primero_y_paginada(repos, usuario):
    for n in range(3):
        await repos.bitacora.agregar(
            RegistroBitacora(
                usuario.id if n else None, Accion.MODIFICAR, Objeto.CULTIVO, "x", f"{n}", AHORA
            )
        )

    registros = await repos.bitacora.listar()
    assert [r.detalle for r in registros] == ["2", "1", "0"]
    assert registros[-1].usuario_id is None
    assert registros[0].usuario_id == usuario.id
    siguiente = await repos.bitacora.listar(limite=2, antes_de=registros[0].id)
    assert [r.detalle for r in siguiente] == ["1", "0"]


async def test_alerta_guarda_quien_la_atendio(con_nodo, usuario):
    alerta = await con_nodo.alertas.guardar(
        crear_alerta(atendida_en=AHORA, atendida_por=usuario.id, atendida_por_nombre="Ana")
    )

    assert await con_nodo.alertas.obtener(alerta.id) == alerta


async def test_alerta_recibe_id_y_se_actualiza(con_nodo):
    alertas = con_nodo.alertas

    alerta = await alertas.guardar(crear_alerta())
    assert alerta.id is not None
    assert await alertas.obtener(alerta.id) == alerta

    critica = replace(alerta, severidad=Severidad.CRITICA, escalada_en=AHORA, valor=31.5)
    assert await alertas.guardar(critica) == critica
    assert await alertas.obtener(alerta.id) == critica
    assert await alertas.obtener(9999) is None


async def test_alertas_activas_por_nodo(con_nodo):
    alertas = con_nodo.alertas
    await con_nodo.nodos.guardar(crear_nodo(id="nodo2"))
    activa = await alertas.guardar(crear_alerta())
    await alertas.guardar(crear_alerta(tipo=TipoAlerta.HONGOS, variable=None, resuelta_en=AHORA))
    otra = await alertas.guardar(
        crear_alerta(nodo_id="nodo2", tipo=TipoAlerta.DESCONEXION, variable=None)
    )

    assert await alertas.activas("nodo1") == [activa]
    assert sorted(a.id for a in await alertas.activas()) == sorted([activa.id, otra.id])


async def test_listar_alertas_mas_recientes_primero(con_nodo):
    alertas = con_nodo.alertas
    vieja = await alertas.guardar(crear_alerta(iniciada_en=AHORA - timedelta(hours=1)))
    resuelta = await alertas.guardar(
        crear_alerta(tipo=TipoAlerta.HONGOS, variable=None, resuelta_en=AHORA)
    )

    assert await alertas.listar() == [resuelta, vieja]
    assert await alertas.listar(solo_activas=True) == [vieja]
    assert await alertas.listar(limite=1) == [resuelta]


async def test_suscripcion_se_identifica_por_endpoint(repos, usuario):
    suscripciones = repos.suscripciones
    u = usuario.id
    primera = await suscripciones.guardar(SuscripcionPush("https://push/1", "k1", "a1", AHORA, u))
    segunda = await suscripciones.guardar(SuscripcionPush("https://push/1", "k2", "a2", AHORA, u))
    otra = await suscripciones.guardar(SuscripcionPush("https://push/2", "k", "a", AHORA, u))

    assert segunda.id == primera.id != otra.id
    assert await suscripciones.obtener(primera.id) == segunda
    assert [s.endpoint for s in await suscripciones.listar()] == [
        "https://push/1",
        "https://push/2",
    ]

    assert await suscripciones.borrar_por_endpoint("https://push/1", u + 1) is False
    assert await suscripciones.borrar_por_endpoint("https://push/1", u) is True
    assert await suscripciones.borrar_por_endpoint("https://push/1", u) is False
    await suscripciones.borrar(otra.id)
    assert await suscripciones.listar() == []


async def test_suscripcion_pasa_a_otro_usuario_sin_sus_envios(con_nodo, usuario):
    otro = await con_nodo.usuarios.guardar(crear_usuario(correo="otro@ejemplo.com"))
    alerta = await con_nodo.alertas.guardar(crear_alerta())
    primera = await con_nodo.suscripciones.guardar(
        SuscripcionPush("https://push/1", "k", "a", AHORA, usuario.id)
    )
    await con_nodo.envios.crear([Envio(alerta.id, primera.id, AHORA)])

    segunda = await con_nodo.suscripciones.guardar(
        SuscripcionPush("https://push/1", "k", "a", AHORA, otro.id)
    )

    assert [s.usuario_id for s in await con_nodo.suscripciones.listar()] == [otro.id]
    assert (await con_nodo.suscripciones.obtener(segunda.id)).usuario_id == otro.id
    assert await con_nodo.envios.pendientes(AHORA) == []


async def test_envios_pendientes_por_hora_y_borrado_en_cascada(con_nodo, usuario):
    alerta = await con_nodo.alertas.guardar(crear_alerta())
    u = usuario.id
    s1 = await con_nodo.suscripciones.guardar(SuscripcionPush("https://push/1", "k", "a", AHORA, u))
    s2 = await con_nodo.suscripciones.guardar(SuscripcionPush("https://push/2", "k", "a", AHORA, u))
    envios = con_nodo.envios
    await envios.crear(
        [
            Envio(alerta.id, s1.id, AHORA),
            Envio(alerta.id, s2.id, AHORA + timedelta(minutes=1)),
        ]
    )

    (pendiente,) = await envios.pendientes(AHORA)
    assert pendiente.suscripcion_id == s1.id
    assert len(await envios.pendientes(AHORA + timedelta(minutes=1))) == 2

    enviado = replace(pendiente, estado=EstadoEnvio.ENVIADO, intentos=1, enviado_en=AHORA)
    await envios.guardar(enviado)
    assert [e.suscripcion_id for e in await envios.pendientes(AHORA + timedelta(hours=1))] == [
        s2.id
    ]

    await con_nodo.suscripciones.borrar(s2.id)
    assert await envios.pendientes(AHORA + timedelta(hours=1)) == []
