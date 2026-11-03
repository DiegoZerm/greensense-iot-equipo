from dataclasses import dataclass, replace

from greensense.aplicacion.errores import NodoNoRegistrado
from greensense.aplicacion.puertos import Evento, PublicadorEventos, RepositorioNodos
from greensense.dominio.modelos import EstadoNodo, Nodo, SensorAire


@dataclass(frozen=True)
class EstadoReportado:
    """Lo que el nodo informa de sí mismo al conectarse o al caerse."""

    conectado: bool
    firmware: str | None = None
    sensor_aire: SensorAire | None = None
    sensor_suelo: bool | None = None
    periodo_s: int | None = None


class RegistrarEstado:
    def __init__(self, nodos: RepositorioNodos, eventos: PublicadorEventos) -> None:
        self._nodos = nodos
        self._eventos = eventos

    async def ejecutar(self, invernadero_id: str, nodo_id: str, estado: EstadoReportado) -> Nodo:
        nodo = await self._nodos.obtener(nodo_id)
        if nodo is None or not nodo.activo or nodo.invernadero_id != invernadero_id:
            raise NodoNoRegistrado(invernadero_id, nodo_id)

        if estado.conectado:
            # El nodo conoce su propio hardware: su configuración reemplaza a la registrada.
            nodo = replace(
                nodo,
                estado=EstadoNodo.CONECTADO,
                firmware=estado.firmware or nodo.firmware,
                sensor_aire=estado.sensor_aire or nodo.sensor_aire,
                sensor_suelo=nodo.sensor_suelo
                if estado.sensor_suelo is None
                else estado.sensor_suelo,
                periodo_s=estado.periodo_s or nodo.periodo_s,
            )
        else:
            nodo = replace(nodo, estado=EstadoNodo.DESCONECTADO)

        await self._nodos.guardar(nodo)
        self._eventos.publicar(Evento("nodo", {"nodo": nodo}))
        return nodo
