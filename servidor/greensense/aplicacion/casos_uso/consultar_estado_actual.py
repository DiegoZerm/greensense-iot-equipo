from collections import defaultdict
from dataclasses import dataclass, field

from greensense.aplicacion.puertos import RepositorioAlertas, RepositorioLecturas, RepositorioNodos
from greensense.dominio.alertas import Alerta
from greensense.dominio.modelos import Lectura, Nodo


@dataclass(frozen=True)
class EstadoActualNodo:
    nodo: Nodo
    ultima: Lectura | None
    alertas: list[Alerta] = field(default_factory=list)


class ConsultarEstadoActual:
    """Datos del panel: cada nodo con su lectura más reciente."""

    def __init__(
        self,
        lecturas: RepositorioLecturas,
        nodos: RepositorioNodos,
        alertas: RepositorioAlertas,
    ) -> None:
        self._lecturas = lecturas
        self._nodos = nodos
        self._alertas = alertas

    async def ejecutar(self) -> list[EstadoActualNodo]:
        nodos = sorted(
            (n for n in await self._nodos.listar() if n.activo),
            key=lambda n: (n.invernadero_id, n.id),
        )
        por_nodo: dict[str, list[Alerta]] = defaultdict(list)
        for alerta in await self._alertas.activas():
            por_nodo[alerta.nodo_id].append(alerta)
        return [
            EstadoActualNodo(nodo, await self._lecturas.ultima(nodo.id), por_nodo[nodo.id])
            for nodo in nodos
        ]
