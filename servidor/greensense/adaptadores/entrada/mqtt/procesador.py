"""Convierte mensajes MQTT en llamadas a los casos de uso. No depende del broker."""

import logging
from enum import StrEnum

from pydantic import ValidationError

from greensense.adaptadores.entrada.mqtt.mensajes import MensajeEstado, MensajeLectura, parsear_tema
from greensense.aplicacion.casos_uso.registrar_estado import EstadoReportado, RegistrarEstado
from greensense.aplicacion.casos_uso.registrar_lectura import RegistrarLectura
from greensense.aplicacion.errores import NodoNoRegistrado
from greensense.dominio.modelos import Lectura, SensorAire
from greensense.dominio.validacion import LecturaRechazada

log = logging.getLogger(__name__)


class Resultado(StrEnum):
    GUARDADA = "guardada"
    DUPLICADA = "duplicada"
    ESTADO = "estado"
    TEMA_DESCONOCIDO = "tema_desconocido"
    INVALIDO = "invalido"
    RECHAZADO = "rechazado"


def a_lectura(mensaje: MensajeLectura) -> Lectura:
    return Lectura(
        nodo_id=mensaje.nodo,
        arranque=mensaje.arranque,
        seq=mensaje.seq,
        ts=mensaje.ts,
        temperatura=mensaje.temperatura,
        humedad_aire=mensaje.humedad_aire,
        humedad_sustrato=mensaje.humedad_sustrato,
        muestras=mensaje.muestras,
        rssi=mensaje.rssi,
    )


def a_estado(mensaje: MensajeEstado) -> EstadoReportado:
    return EstadoReportado(
        conectado=mensaje.estado == "conectado",
        firmware=mensaje.firmware,
        sensor_aire=SensorAire(mensaje.sensor_aire) if mensaje.sensor_aire else None,
        sensor_suelo=mensaje.sensor_suelo,
        periodo_s=mensaje.periodo_s,
    )


class ProcesadorMensajes:
    def __init__(self, registrar_lectura: RegistrarLectura, registrar_estado: RegistrarEstado):
        self._registrar_lectura = registrar_lectura
        self._registrar_estado = registrar_estado

    async def procesar(self, tema: str, carga: bytes) -> Resultado:
        partes = parsear_tema(tema)
        if partes is None:
            log.warning("tema desconocido: %s", tema)
            return Resultado.TEMA_DESCONOCIDO

        try:
            if partes.tipo == "estado":
                estado = MensajeEstado.model_validate_json(carga)
                await self._registrar_estado.ejecutar(
                    partes.invernadero, partes.nodo, a_estado(estado)
                )
                log.info("%s/%s %s", partes.invernadero, partes.nodo, estado.estado)
                return Resultado.ESTADO

            mensaje = MensajeLectura.model_validate_json(carga)
            if mensaje.nodo != partes.nodo:
                log.warning("%s: el mensaje dice ser del nodo %s", tema, mensaje.nodo)
                return Resultado.RECHAZADO
            resultado = await self._registrar_lectura.ejecutar(
                partes.invernadero, a_lectura(mensaje)
            )
        except ValidationError as error:
            log.warning("mensaje inválido en %s: %s", tema, error.errors(include_url=False))
            return Resultado.INVALIDO
        except (NodoNoRegistrado, LecturaRechazada) as error:
            log.warning("%s: %s", tema, error)
            return Resultado.RECHAZADO

        for imposible in resultado.imposibles:
            log.warning(
                "%s: %s=%s fuera del rango del sensor (%s a %s)",
                tema, imposible.variable, imposible.valor, imposible.minimo, imposible.maximo,
            )  # fmt: skip
        return Resultado.GUARDADA if resultado.guardada else Resultado.DUPLICADA
