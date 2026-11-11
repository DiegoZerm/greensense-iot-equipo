"""Cliente MQTT del servidor: se suscribe a los temas de los nodos y se reconecta solo."""

import asyncio
import logging

import aiomqtt

from greensense.adaptadores.entrada.mqtt.procesador import ProcesadorMensajes

log = logging.getLogger(__name__)

TEMAS = ("greensense/+/+/lecturas", "greensense/+/+/estado")


class ReceptorMqtt:
    def __init__(
        self,
        procesador: ProcesadorMensajes,
        host: str,
        puerto: int,
        usuario: str,
        contrasena: str,
        reintento_s: float = 5.0,
    ) -> None:
        self._procesador = procesador
        self._host = host
        self._puerto = puerto
        self._usuario = usuario
        self._contrasena = contrasena
        self._reintento_s = reintento_s

    async def correr(self) -> None:
        while True:
            try:
                # Sesión persistente: si el servidor se reinicia, el broker guarda los
                # mensajes QoS 1 que lleguen mientras tanto y los entrega al reconectar.
                async with aiomqtt.Client(
                    self._host,
                    self._puerto,
                    username=self._usuario,
                    password=self._contrasena,
                    identifier="greensense-servidor",
                    clean_session=False,
                ) as cliente:
                    for tema in TEMAS:
                        await cliente.subscribe(tema, qos=1)
                    log.info("conectado a MQTT en %s:%s", self._host, self._puerto)
                    async for mensaje in cliente.messages:
                        await self._atender(str(mensaje.topic), mensaje.payload)
            except aiomqtt.MqttError as error:
                log.warning("sin conexión MQTT (%s); reintento en %ss", error, self._reintento_s)
                await asyncio.sleep(self._reintento_s)

    async def _atender(self, tema: str, carga) -> None:
        if not isinstance(carga, bytes | bytearray):
            carga = str(carga).encode()
        try:
            await self._procesador.procesar(tema, bytes(carga))
        except Exception:
            # Un error inesperado (por ejemplo, la base de datos caída) no debe
            # detener la recepción del resto de los mensajes.
            log.exception("error al procesar un mensaje de %s", tema)
