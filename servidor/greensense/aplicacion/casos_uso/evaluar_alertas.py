from dataclasses import replace
from datetime import datetime

from greensense.aplicacion.casos_uso.notificaciones import ProgramarNotificacion
from greensense.aplicacion.puertos import (
    Evento,
    PublicadorEventos,
    RepositorioAlertas,
    RepositorioCultivos,
    RepositorioInvernaderos,
)
from greensense.dominio.alertas import Alerta, Cambio, Transicion, aplicar_condicion
from greensense.dominio.cultivo import CULTIVO_PREDETERMINADO, Cultivo
from greensense.dominio.modelos import Nodo
from greensense.dominio.reglas import reglas_para
from greensense.dominio.validacion import LecturaValidada


class EvaluarAlertas:
    """Aplica las reglas del nodo a una lectura nueva y actualiza sus alertas."""

    def __init__(
        self,
        alertas: RepositorioAlertas,
        invernaderos: RepositorioInvernaderos,
        cultivos: RepositorioCultivos,
        programar: ProgramarNotificacion,
        eventos: PublicadorEventos,
    ) -> None:
        self._alertas = alertas
        self._invernaderos = invernaderos
        self._cultivos = cultivos
        self._programar = programar
        self._eventos = eventos

    async def ejecutar(self, nodo: Nodo, validada: LecturaValidada) -> list[Transicion]:
        ts = validada.lectura.ts
        activas = {a.clave: a for a in await self._alertas.activas(nodo.id)}
        transiciones: list[Transicion] = []
        evaluadas = set()

        for regla in reglas_para(nodo, await self._cultivo_de(nodo)):
            clave = (nodo.id, regla.tipo, regla.variable)
            evaluadas.add(clave)
            condicion = regla.evaluar(validada)
            if condicion is None:
                continue
            transicion = aplicar_condicion(
                activas.get(clave), condicion, nodo.id, regla.tipo, regla.variable, ts
            )
            if transicion is not None:
                transiciones.append(transicion)

        # Llegó una lectura: el nodo ya no está desconectado. Y las alertas de reglas que
        # dejaron de aplicar (por ejemplo, se quitó el sensor de suelo) se resuelven.
        for clave, alerta in activas.items():
            if clave not in evaluadas:
                transiciones.append(_resolver(alerta, ts))

        for transicion in transiciones:
            await self._guardar(transicion)
        return transiciones

    async def _cultivo_de(self, nodo: Nodo) -> Cultivo:
        invernadero = await self._invernaderos.obtener(nodo.invernadero_id)
        if invernadero is not None:
            cultivo = await self._cultivos.obtener(invernadero.cultivo_id)
            if cultivo is not None:
                return cultivo
        return CULTIVO_PREDETERMINADO

    async def _guardar(self, transicion: Transicion) -> None:
        alerta = await self._alertas.guardar(transicion.alerta)
        if transicion.cambio is not Cambio.ACTUALIZADA:
            self._eventos.publicar(Evento("alerta", {"alerta": alerta}))
        if transicion.notificar:
            await self._programar.ejecutar(alerta)


def _resolver(alerta: Alerta, ts: datetime) -> Transicion:
    resuelta = replace(alerta, resuelta_en=ts, actualizada_en=ts)
    return Transicion(resuelta, Cambio.RESUELTA)
