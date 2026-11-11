from dataclasses import replace
from datetime import timedelta

import pytest

from greensense.aplicacion.casos_uso.notificaciones import (
    EnviarNotificaciones,
    ProgramarNotificacion,
    RegistrarSuscripcion,
    carga_notificacion,
)
from greensense.aplicacion.puertos import ErrorPush, SuscripcionVencida
from greensense.dominio.alertas import Severidad, TipoAlerta
from greensense.dominio.notificaciones import MAXIMO_INTENTOS, Envio, EstadoEnvio, SuscripcionPush
from greensense.dominio.usuarios import Rol
from tests.fabricas import AHORA, crear_alerta, crear_nodo, crear_usuario

pytestmark = pytest.mark.anyio


@pytest.fixture
async def alerta(alertas, nodos):
    await nodos.guardar(crear_nodo(nombre="Nodo de la puerta"))
    return await alertas.guardar(crear_alerta(severidad=Severidad.CRITICA))


@pytest.fixture
async def dos_suscripciones(suscripciones):
    for n in (1, 2):
        await suscripciones.guardar(SuscripcionPush(f"https://push/{n}", "k", "a", AHORA, 1))


@pytest.fixture
def programar(suscripciones, usuarios, envios, despertador, reloj):
    return ProgramarNotificacion(suscripciones, usuarios, envios, despertador, reloj)


@pytest.fixture
def enviar(envios, suscripciones, alertas, nodos, usuarios, push, reloj):
    return EnviarNotificaciones(envios, suscripciones, alertas, nodos, usuarios, push, reloj)


async def test_programa_un_envio_por_suscripcion(
    programar, alerta, dos_suscripciones, envios, despertador
):
    assert await programar.ejecutar(alerta) == 2

    assert {e.suscripcion_id for e in envios.todos()} == {1, 2}
    assert despertador.avisos == 1


async def test_sin_suscripciones_no_programa_nada(programar, alerta, envios, despertador):
    assert await programar.ejecutar(alerta) == 0
    assert despertador.avisos == 0


async def test_envia_a_todas_las_suscripciones(
    programar, enviar, alerta, dos_suscripciones, push, envios
):
    await programar.ejecutar(alerta)

    assert await enviar.ejecutar() == 2

    assert sorted(endpoint for endpoint, _ in push.enviados) == ["https://push/1", "https://push/2"]
    assert all(e.estado is EstadoEnvio.ENVIADO and e.enviado_en == AHORA for e in envios.todos())
    assert await enviar.ejecutar() == 0  # no se repiten


async def test_suscripcion_vencida_se_borra(
    programar, enviar, alerta, dos_suscripciones, push, envios, suscripciones
):
    push.fallas["https://push/1"] = SuscripcionVencida("410")
    await programar.ejecutar(alerta)

    assert await enviar.ejecutar() == 1

    assert [s.endpoint for s in await suscripciones.listar()] == ["https://push/2"]


async def test_falla_temporal_se_reintenta_con_espera(
    programar, enviar, alerta, suscripciones, push, envios, reloj
):
    await suscripciones.guardar(SuscripcionPush("https://push/1", "k", "a", AHORA, 1))
    push.fallas["https://push/1"] = ErrorPush("HTTP 503")
    await programar.ejecutar(alerta)

    await enviar.ejecutar()

    (envio,) = envios.todos()
    assert envio.estado is EstadoEnvio.PENDIENTE
    assert (envio.intentos, envio.ultimo_error) == (1, "HTTP 503")
    assert envio.proximo_intento_en == AHORA + timedelta(seconds=30)
    assert await enviar.ejecutar() == 0  # todavía no toca

    del push.fallas["https://push/1"]
    reloj.actual = AHORA + timedelta(seconds=30)
    assert await enviar.ejecutar() == 1


async def test_se_rinde_tras_el_maximo_de_intentos(
    programar, enviar, alerta, suscripciones, push, envios, reloj
):
    await suscripciones.guardar(SuscripcionPush("https://push/1", "k", "a", AHORA, 1))
    push.fallas["https://push/1"] = ErrorPush("sin conexión")
    await programar.ejecutar(alerta)

    for _ in range(MAXIMO_INTENTOS):
        reloj.actual += timedelta(hours=1)
        await enviar.ejecutar()

    (envio,) = envios.todos()
    assert envio.estado is EstadoEnvio.FALLIDO
    assert envio.intentos == MAXIMO_INTENTOS


async def test_alerta_resuelta_antes_de_enviar_se_descarta(
    programar, enviar, alerta, alertas, dos_suscripciones, push, envios
):
    await programar.ejecutar(alerta)
    await alertas.guardar(replace(alerta, resuelta_en=AHORA))

    assert await enviar.ejecutar() == 0

    assert push.enviados == []
    assert all(e.estado is EstadoEnvio.DESCARTADO for e in envios.todos())


async def test_registrar_la_misma_suscripcion_actualiza_sus_claves(suscripciones, reloj):
    registrar = RegistrarSuscripcion(suscripciones, reloj)
    usuario = crear_usuario(id=1)
    primera = await registrar.ejecutar(usuario, "https://push/1", "k1", "a1")

    segunda = await registrar.ejecutar(usuario, "https://push/1", "k2", "a2")

    assert segunda.id == primera.id
    assert [(s.p256dh, s.auth) for s in await suscripciones.listar()] == [("k2", "a2")]


async def test_otro_usuario_en_el_mismo_navegador_se_queda_con_la_suscripcion(
    suscripciones, envios, reloj
):
    registrar = RegistrarSuscripcion(suscripciones, reloj)
    primera = await registrar.ejecutar(crear_usuario(id=1), "https://push/1", "k", "a")
    await envios.crear([Envio(alerta_id=1, suscripcion_id=primera.id, proximo_intento_en=AHORA)])

    segunda = await registrar.ejecutar(crear_usuario(id=2), "https://push/1", "k", "a")

    assert [s.usuario_id for s in await suscripciones.listar()] == [2]
    assert segunda.id != primera.id
    # Lo pendiente del usuario anterior ya no se envía a este navegador.
    assert await envios.pendientes(AHORA) == []


@pytest.mark.parametrize(
    ("rol", "tipo", "recibe"),
    [
        (Rol.OPERADOR, TipoAlerta.UMBRAL, True),
        (Rol.OPERADOR, TipoAlerta.HONGOS, True),
        (Rol.OPERADOR, TipoAlerta.DESCONEXION, False),
        (Rol.SUPERVISOR, TipoAlerta.UMBRAL, True),
        (Rol.SUPERVISOR, TipoAlerta.SENSOR, False),
        (Rol.TECNICO, TipoAlerta.UMBRAL, False),
        (Rol.TECNICO, TipoAlerta.SENSOR, True),
        (Rol.TECNICO, TipoAlerta.DESCONEXION, True),
        (Rol.ADMINISTRADOR, TipoAlerta.HONGOS, True),
        (Rol.ADMINISTRADOR, TipoAlerta.DESCONEXION, True),
    ],
)
async def test_cada_rol_recibe_solo_sus_notificaciones(
    rol, tipo, recibe, alertas, suscripciones, usuarios, envios, despertador, reloj
):
    usuario = await usuarios.guardar(crear_usuario(correo="otro@ejemplo.com", rol=rol))
    await suscripciones.guardar(SuscripcionPush("https://push/x", "k", "a", AHORA, usuario.id))
    alerta = await alertas.guardar(crear_alerta(tipo=tipo, severidad=Severidad.CRITICA))

    programar = ProgramarNotificacion(suscripciones, usuarios, envios, despertador, reloj)

    assert await programar.ejecutar(alerta) == (1 if recibe else 0)


async def test_usuario_desactivado_ya_no_recibe_lo_pendiente(
    programar, enviar, alerta, suscripciones, usuarios, push
):
    await suscripciones.guardar(SuscripcionPush("https://push/1", "k", "a", AHORA, 1))
    await programar.ejecutar(alerta)
    await usuarios.guardar(replace(await usuarios.obtener(1), activo=False))

    assert await enviar.ejecutar() == 0
    assert push.enviados == []


def test_carga_en_formato_de_angular():
    alerta = crear_alerta(id=7, severidad=Severidad.CRITICA)

    carga = carga_notificacion(alerta, crear_nodo(nombre="Nodo de la puerta"))

    notificacion = carga["notification"]
    assert notificacion["title"] == "GreenSense: Condición crítica"
    assert notificacion["body"].startswith("Nodo de la puerta. Temperatura alta")
    assert notificacion["tag"] == "alerta-7"
    assert notificacion["data"]["onActionClick"]["default"]["url"] == "/alertas"
