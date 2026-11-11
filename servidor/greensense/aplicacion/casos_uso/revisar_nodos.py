from dataclasses import replace
from datetime import datetime

from greensense.aplicacion.casos_uso.notificaciones import ProgramarNotificacion
from greensense.aplicacion.puertos import (
    Evento,
    PublicadorEventos,
    Reloj,
    RepositorioAlertas,
    RepositorioNodos,
)
from greensense.dominio.alertas import Alerta, Severidad, TipoAlerta
from greensense.dominio.modelos import EstadoNodo


class RevisarNodos:
    """Tarea periódica: detecta los nodos que dejaron de enviar lecturas.

    `escuchando_desde` es cuándo arrancó el servidor. Mientras estuvo apagado no podía
    recibir nada, así que el tiempo sin lecturas se cuenta desde ahí: al prender la
    computadora, el nodo tiene su plazo normal para mandar lo que guardó en su cola antes
    de considerarlo desconectado.
    """

    def __init__(
        self,
        nodos: RepositorioNodos,
        alertas: RepositorioAlertas,
        programar: ProgramarNotificacion,
        eventos: PublicadorEventos,
        reloj: Reloj,
        escuchando_desde: datetime | None = None,
    ) -> None:
        self._escuchando_desde = escuchando_desde
        self._nodos = nodos
        self._alertas = alertas
        self._programar = programar
        self._eventos = eventos
        self._reloj = reloj

    async def ejecutar(self) -> list[Alerta]:
        ahora = self._reloj.ahora()
        nuevas = []
        for nodo in await self._nodos.listar():
            ultima = nodo.ultima_lectura_en
            if not nodo.activo or ultima is None:
                continue
            referencia = max(ultima, self._escuchando_desde or ultima)
            if ahora - referencia < nodo.tiempo_desconexion():
                continue

            if nodo.estado is not EstadoNodo.DESCONECTADO:
                nodo = replace(nodo, estado=EstadoNodo.DESCONECTADO)
                await self._nodos.guardar(nodo)
                self._eventos.publicar(Evento("nodo", {"nodo": nodo}))

            activas = await self._alertas.activas(nodo.id)
            if any(a.tipo is TipoAlerta.DESCONEXION for a in activas):
                continue
            # El texto no menciona cuánto tiempo lleva: seguiría ahí, desactualizado, mientras
            # la alerta esté activa. La hora de la última lectura queda en fuera_desde.
            limite_min = int(nodo.tiempo_desconexion().total_seconds() // 60)
            alerta = await self._alertas.guardar(
                Alerta(
                    nodo_id=nodo.id,
                    tipo=TipoAlerta.DESCONEXION,
                    variable=None,
                    severidad=Severidad.CRITICA,
                    mensaje=f"El nodo lleva más de {limite_min} min sin enviar lecturas",
                    recomendacion="Revisar la alimentación, el WiFi y la conexión del nodo.",
                    valor=None,
                    limite=None,
                    iniciada_en=ahora,
                    actualizada_en=ahora,
                    fuera_desde=ultima,
                    escalada_en=ahora,
                )
            )
            self._eventos.publicar(Evento("alerta", {"alerta": alerta}))
            await self._programar.ejecutar(alerta)
            nuevas.append(alerta)
        return nuevas
