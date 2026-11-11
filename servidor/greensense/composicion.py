"""Único lugar donde se eligen las clases concretas y se arma la aplicación.

Uso: uvicorn --factory greensense.composicion:crear_aplicacion
"""

import asyncio
import contextlib
import logging
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from datetime import timedelta

from fastapi import FastAPI

from greensense.adaptadores.entrada.api import crear_api
from greensense.adaptadores.entrada.mqtt.procesador import ProcesadorMensajes
from greensense.adaptadores.entrada.mqtt.receptor import ReceptorMqtt
from greensense.adaptadores.salida import memoria, postgres
from greensense.adaptadores.salida.despertador import DespertadorAsyncio
from greensense.adaptadores.salida.eventos import DifusorEventos
from greensense.adaptadores.salida.reloj import RelojSistema
from greensense.adaptadores.salida.seguridad import EmisorJwt, HasherArgon2
from greensense.adaptadores.salida.webpush import ServicioPushDeshabilitado, ServicioWebPush
from greensense.aplicacion.casos_uso.bitacora import Anotador, ConsultarBitacora
from greensense.aplicacion.casos_uso.configurar_cultivos import (
    BorrarCultivo,
    GuardarCultivo,
    ListarCultivos,
)
from greensense.aplicacion.casos_uso.consultar_estado_actual import ConsultarEstadoActual
from greensense.aplicacion.casos_uso.consultar_historial import (
    ConsultarAgregados,
    ConsultarLecturas,
    ConsultarResumen,
    ExportarAlertas,
    ExportarLecturas,
)
from greensense.aplicacion.casos_uso.evaluar_alertas import EvaluarAlertas
from greensense.aplicacion.casos_uso.gestionar_alertas import AtenderAlerta, ConsultarAlertas
from greensense.aplicacion.casos_uso.gestionar_nodos import (
    BorrarInvernadero,
    ListarInvernaderos,
    ListarNodos,
    ModificarInvernadero,
    ModificarNodo,
    RegistrarInvernadero,
    RegistrarNodo,
)
from greensense.aplicacion.casos_uso.gestionar_usuarios import (
    CrearAdministradorInicial,
    CrearUsuario,
    ListarUsuarios,
    ModificarUsuario,
)
from greensense.aplicacion.casos_uso.notificaciones import (
    BorrarSuscripcion,
    EnviarNotificaciones,
    ProgramarNotificacion,
    RegistrarSuscripcion,
)
from greensense.aplicacion.casos_uso.registrar_estado import RegistrarEstado
from greensense.aplicacion.casos_uso.registrar_lectura import RegistrarLectura
from greensense.aplicacion.casos_uso.revisar_nodos import RevisarNodos
from greensense.aplicacion.casos_uso.sesion import (
    CambiarContrasenaPropia,
    IniciarSesion,
    UsuarioDelToken,
)
from greensense.aplicacion.puertos import Reloj
from greensense.config import Config
from greensense.contenedor import Contenedor
from greensense.dominio.cultivo import CULTIVO_PREDETERMINADO

log = logging.getLogger(__name__)


def crear_contenedor(
    config: Config, despertador: DespertadorAsyncio, reloj: Reloj | None = None
) -> Contenedor:
    """`reloj` solo se cambia para generar datos de demostración en el pasado."""
    al_cerrar = []
    if config.almacenamiento == "memoria":
        suscripciones = memoria.RepositorioSuscripcionesMemoria()
        lecturas = memoria.RepositorioLecturasMemoria()
        nodos = memoria.RepositorioNodosMemoria()
        invernaderos = memoria.RepositorioInvernaderosMemoria()
        cultivos = memoria.RepositorioCultivosMemoria(CULTIVO_PREDETERMINADO)
        alertas = memoria.RepositorioAlertasMemoria()
        envios = memoria.RepositorioEnviosMemoria(suscripciones)
        usuarios = memoria.RepositorioUsuariosMemoria()
        bitacora = memoria.RepositorioBitacoraMemoria()
    else:
        motor = postgres.crear_motor(config.url_db)
        lecturas = postgres.RepositorioLecturasPostgres(motor)
        nodos = postgres.RepositorioNodosPostgres(motor)
        invernaderos = postgres.RepositorioInvernaderosPostgres(motor)
        cultivos = postgres.RepositorioCultivosPostgres(motor)
        alertas = postgres.RepositorioAlertasPostgres(motor)
        suscripciones = postgres.RepositorioSuscripcionesPostgres(motor)
        envios = postgres.RepositorioEnviosPostgres(motor)
        usuarios = postgres.RepositorioUsuariosPostgres(motor)
        bitacora = postgres.RepositorioBitacoraPostgres(motor)
        al_cerrar.append(motor.dispose)

    if config.push_habilitado:
        push = ServicioWebPush(config.vapid_privada, config.vapid_contacto)
    else:
        log.warning("Web Push deshabilitado: faltan VAPID_PRIVADA y VAPID_PUBLICA")
        push = ServicioPushDeshabilitado()

    secreto = config.jwt_secreto
    if not secreto:
        log.warning(
            "JWT_SECRETO vacío: se generó uno temporal; las sesiones no sobreviven reinicios"
        )
        secreto = secrets.token_urlsafe(48)

    reloj = reloj or RelojSistema()
    eventos = DifusorEventos()
    hasher = HasherArgon2(rapido=config.hash_rapido)
    tokens = EmisorJwt(secreto, timedelta(hours=config.sesion_horas), reloj)
    anotador = Anotador(bitacora, reloj)
    programar = ProgramarNotificacion(suscripciones, usuarios, envios, despertador, reloj)
    evaluar = EvaluarAlertas(alertas, invernaderos, cultivos, programar, eventos)
    crear_usuario = CrearUsuario(usuarios, hasher, reloj, anotador)
    return Contenedor(
        registrar_lectura=RegistrarLectura(lecturas, nodos, reloj, eventos, evaluar),
        registrar_estado=RegistrarEstado(nodos, eventos),
        consultar_estado_actual=ConsultarEstadoActual(lecturas, nodos, alertas),
        revisar_nodos=RevisarNodos(
            nodos, alertas, programar, eventos, reloj, escuchando_desde=reloj.ahora()
        ),
        consultar_alertas=ConsultarAlertas(alertas),
        atender_alerta=AtenderAlerta(alertas, eventos, reloj),
        registrar_suscripcion=RegistrarSuscripcion(suscripciones, reloj),
        borrar_suscripcion=BorrarSuscripcion(suscripciones),
        enviar_notificaciones=EnviarNotificaciones(
            envios, suscripciones, alertas, nodos, usuarios, push, reloj
        ),
        iniciar_sesion=IniciarSesion(usuarios, hasher, tokens, anotador),
        usuario_del_token=UsuarioDelToken(usuarios, tokens),
        cambiar_contrasena_propia=CambiarContrasenaPropia(usuarios, hasher, anotador),
        listar_usuarios=ListarUsuarios(usuarios),
        crear_usuario=crear_usuario,
        modificar_usuario=ModificarUsuario(usuarios, hasher, anotador),
        crear_administrador_inicial=CrearAdministradorInicial(usuarios, crear_usuario),
        listar_cultivos=ListarCultivos(cultivos),
        guardar_cultivo=GuardarCultivo(cultivos, anotador),
        borrar_cultivo=BorrarCultivo(cultivos, invernaderos, anotador),
        listar_invernaderos=ListarInvernaderos(invernaderos),
        registrar_invernadero=RegistrarInvernadero(invernaderos, cultivos, anotador),
        modificar_invernadero=ModificarInvernadero(invernaderos, cultivos, anotador),
        borrar_invernadero=BorrarInvernadero(invernaderos, nodos, anotador),
        listar_nodos=ListarNodos(nodos),
        registrar_nodo=RegistrarNodo(invernaderos, nodos, anotador),
        modificar_nodo=ModificarNodo(nodos, alertas, eventos, reloj, anotador),
        consultar_bitacora=ConsultarBitacora(bitacora, usuarios),
        consultar_lecturas=ConsultarLecturas(lecturas, nodos),
        consultar_agregados=ConsultarAgregados(lecturas, nodos),
        consultar_resumen=ConsultarResumen(lecturas, nodos, reloj),
        exportar_lecturas=ExportarLecturas(lecturas, nodos, anotador),
        exportar_alertas=ExportarAlertas(alertas, nodos, anotador),
        eventos=eventos,
        clave_publica_push=config.vapid_publica if config.push_habilitado else "",
        al_cerrar=al_cerrar,
    )


async def _repetir(
    nombre: str, accion: Callable[[], Awaitable[object]], esperar: Callable[[], Awaitable[None]]
) -> None:
    """Corre una tarea periódica. Un error en una vuelta no detiene las siguientes."""
    while True:
        try:
            await accion()
        except Exception:
            log.exception("error en la tarea %s", nombre)
        await esperar()


def crear_aplicacion(
    config: Config | None = None,
    contenedor: Contenedor | None = None,
    despertador: DespertadorAsyncio | None = None,
    tareas_extra: Sequence[Callable[[], Awaitable[object]]] = (),
) -> FastAPI:
    """`contenedor` y `tareas_extra` permiten que la demostración use sus propios datos."""
    config = config or Config()
    logging.basicConfig(level=config.nivel_log, format="%(levelname)s %(name)s: %(message)s")
    despertador = despertador or DespertadorAsyncio()
    contenedor = contenedor or crear_contenedor(config, despertador)

    @contextlib.asynccontextmanager
    async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
        if config.admin_correo and config.admin_contrasena:
            creado = await contenedor.crear_administrador_inicial.ejecutar(
                config.admin_correo, config.admin_contrasena
            )
            if creado:
                log.info("se creó el administrador inicial %s", creado.correo)
        tareas = [
            _repetir(
                "revisar-nodos",
                contenedor.revisar_nodos.ejecutar,
                lambda: asyncio.sleep(config.revision_nodos_s),
            ),
            _repetir(
                "enviar-notificaciones",
                contenedor.enviar_notificaciones.ejecutar,
                lambda: despertador.esperar(config.envio_notificaciones_s),
            ),
        ]
        if config.mqtt_habilitado:
            procesador = ProcesadorMensajes(
                contenedor.registrar_lectura, contenedor.registrar_estado
            )
            receptor = ReceptorMqtt(
                procesador,
                config.mqtt_host,
                config.mqtt_puerto,
                config.mqtt_usuario_servidor,
                config.mqtt_contrasena_servidor,
            )
            tareas.append(receptor.correr())
        tareas.extend(tarea() for tarea in tareas_extra)
        corriendo = [asyncio.create_task(t) for t in tareas]
        try:
            yield
        finally:
            for tarea in corriendo:
                tarea.cancel()
            for tarea in corriendo:
                with contextlib.suppress(asyncio.CancelledError):
                    await tarea
            await contenedor.cerrar()

    return crear_api(contenedor, ciclo_de_vida)
