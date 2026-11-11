"""Bandeja de salida de notificaciones push: programar y enviar con reintentos."""

import logging
from dataclasses import replace
from typing import Any

from greensense.aplicacion.puertos import (
    Despertador,
    ErrorPush,
    Reloj,
    RepositorioAlertas,
    RepositorioEnvios,
    RepositorioNodos,
    RepositorioSuscripciones,
    RepositorioUsuarios,
    ServicioPush,
    SuscripcionVencida,
)
from greensense.dominio.alertas import Alerta, TipoAlerta
from greensense.dominio.modelos import Nodo
from greensense.dominio.notificaciones import (
    MAXIMO_INTENTOS,
    Envio,
    EstadoEnvio,
    SuscripcionPush,
    espera_tras_fallo,
)
from greensense.dominio.usuarios import Usuario, permiso_para_notificar

log = logging.getLogger(__name__)

TITULOS = {
    TipoAlerta.UMBRAL: "Condición crítica",
    TipoAlerta.HONGOS: "Riesgo de hongos",
    TipoAlerta.SENSOR: "Falla de sensor",
    TipoAlerta.DESCONEXION: "Nodo desconectado",
}


def carga_notificacion(alerta: Alerta, nodo: Nodo | None) -> dict[str, Any]:
    """Formato que entiende el service worker de Angular (SwPush)."""
    lugar = nodo.nombre if nodo else alerta.nodo_id
    return {
        "notification": {
            "title": f"GreenSense: {TITULOS[alerta.tipo]}",
            "body": f"{lugar}. {alerta.mensaje}. {alerta.recomendacion}",
            "icon": "/icons/icono-192.png",
            "badge": "/icons/badge-96.png",
            "tag": f"alerta-{alerta.id}",
            "requireInteraction": True,
            "data": {
                "alerta_id": alerta.id,
                "onActionClick": {
                    "default": {"operation": "navigateLastFocusedOrOpen", "url": "/alertas"}
                },
            },
        }
    }


def debe_recibir(usuario: Usuario | None, alerta: Alerta) -> bool:
    """Las alertas de cultivo van a quien atiende el cultivo; las de dispositivo, a quien
    mantiene los nodos (matriz de permisos de la propuesta)."""
    return usuario is not None and usuario.puede(permiso_para_notificar(alerta.tipo))


class ProgramarNotificacion:
    """Crea un envío pendiente de la alerta para cada suscripción de un usuario que deba
    recibirla según su rol."""

    def __init__(
        self,
        suscripciones: RepositorioSuscripciones,
        usuarios: RepositorioUsuarios,
        envios: RepositorioEnvios,
        despertador: Despertador,
        reloj: Reloj,
    ) -> None:
        self._suscripciones = suscripciones
        self._usuarios = usuarios
        self._envios = envios
        self._despertador = despertador
        self._reloj = reloj

    async def ejecutar(self, alerta: Alerta) -> int:
        assert alerta.id is not None, "la alerta debe estar guardada"
        ahora = self._reloj.ahora()
        usuarios = {u.id: u for u in await self._usuarios.listar()}
        envios = [
            Envio(alerta_id=alerta.id, suscripcion_id=s.id, proximo_intento_en=ahora)
            for s in await self._suscripciones.listar()
            if s.id is not None and debe_recibir(usuarios.get(s.usuario_id), alerta)
        ]
        if envios:
            await self._envios.crear(envios)
            self._despertador.avisar()
        return len(envios)


class EnviarNotificaciones:
    def __init__(
        self,
        envios: RepositorioEnvios,
        suscripciones: RepositorioSuscripciones,
        alertas: RepositorioAlertas,
        nodos: RepositorioNodos,
        usuarios: RepositorioUsuarios,
        push: ServicioPush,
        reloj: Reloj,
    ) -> None:
        self._envios = envios
        self._suscripciones = suscripciones
        self._usuarios = usuarios
        self._alertas = alertas
        self._nodos = nodos
        self._push = push
        self._reloj = reloj

    async def ejecutar(self) -> int:
        """Procesa los envíos pendientes. Devuelve cuántos se entregaron."""
        entregados = 0
        for envio in await self._envios.pendientes(self._reloj.ahora()):
            envio = await self._procesar(envio)
            await self._envios.guardar(envio)
            entregados += envio.estado is EstadoEnvio.ENVIADO
        return entregados

    async def _procesar(self, envio: Envio) -> Envio:
        ahora = self._reloj.ahora()
        alerta = await self._alertas.obtener(envio.alerta_id)
        suscripcion = await self._suscripciones.obtener(envio.suscripcion_id)
        if suscripcion is None:
            return replace(envio, estado=EstadoEnvio.DESCARTADO, ultimo_error="sin suscripción")
        if alerta is None or not alerta.activa:
            return replace(
                envio, estado=EstadoEnvio.DESCARTADO, ultimo_error="la alerta ya se resolvió"
            )
        # Entre que se programó y se envía, el usuario pudo ser desactivado o cambiar de rol.
        if not debe_recibir(await self._usuarios.obtener(suscripcion.usuario_id), alerta):
            return replace(
                envio, estado=EstadoEnvio.DESCARTADO, ultimo_error="el usuario ya no la recibe"
            )

        intentos = envio.intentos + 1
        try:
            carga = carga_notificacion(alerta, await self._nodos.obtener(alerta.nodo_id))
            await self._push.enviar(suscripcion, carga)
        except SuscripcionVencida:
            await self._suscripciones.borrar(suscripcion.id)
            log.info("suscripción %s vencida: se borró", suscripcion.id)
            return replace(
                envio, estado=EstadoEnvio.DESCARTADO, intentos=intentos, ultimo_error="vencida"
            )
        except ErrorPush as error:
            if intentos >= MAXIMO_INTENTOS:
                log.warning("envío %s fallido tras %s intentos: %s", envio.id, intentos, error)
                return replace(
                    envio, estado=EstadoEnvio.FALLIDO, intentos=intentos, ultimo_error=str(error)
                )
            return replace(
                envio,
                intentos=intentos,
                proximo_intento_en=ahora + espera_tras_fallo(intentos),
                ultimo_error=str(error),
            )
        return replace(envio, estado=EstadoEnvio.ENVIADO, intentos=intentos, enviado_en=ahora)


class RegistrarSuscripcion:
    def __init__(self, suscripciones: RepositorioSuscripciones, reloj: Reloj) -> None:
        self._suscripciones = suscripciones
        self._reloj = reloj

    async def ejecutar(
        self, usuario: Usuario, endpoint: str, p256dh: str, auth: str
    ) -> SuscripcionPush:
        suscripcion = SuscripcionPush(endpoint, p256dh, auth, self._reloj.ahora(), usuario.id)
        return await self._suscripciones.guardar(suscripcion)


class BorrarSuscripcion:
    def __init__(self, suscripciones: RepositorioSuscripciones) -> None:
        self._suscripciones = suscripciones

    async def ejecutar(self, usuario: Usuario, endpoint: str) -> bool:
        return await self._suscripciones.borrar_por_endpoint(endpoint, usuario.id)
