from dataclasses import dataclass, field
from datetime import timedelta

from greensense.aplicacion.casos_uso.evaluar_alertas import EvaluarAlertas
from greensense.aplicacion.errores import NodoNoRegistrado
from greensense.aplicacion.puertos import (
    Evento,
    PublicadorEventos,
    Reloj,
    RepositorioLecturas,
    RepositorioNodos,
)
from greensense.dominio.alertas import Transicion
from greensense.dominio.modelos import Lectura
from greensense.dominio.validacion import ValorImposible, validar_lectura


@dataclass(frozen=True)
class ResultadoRegistro:
    guardada: bool
    """False si la lectura ya existía porque el nodo la reenvió."""
    lectura: Lectura
    imposibles: tuple[ValorImposible, ...]
    transiciones: list[Transicion] = field(default_factory=list)


# Las lecturas más viejas que esto (por ejemplo, las que el nodo reenvía tras horas sin
# conexión) se guardan, pero no generan alertas: ya no describen el estado actual.
ANTIGUEDAD_MAXIMA_PARA_ALERTAS = timedelta(minutes=10)


class RegistrarLectura:
    def __init__(
        self,
        lecturas: RepositorioLecturas,
        nodos: RepositorioNodos,
        reloj: Reloj,
        eventos: PublicadorEventos,
        alertas: EvaluarAlertas | None = None,
    ) -> None:
        self._alertas = alertas
        self._lecturas = lecturas
        self._nodos = nodos
        self._reloj = reloj
        self._eventos = eventos

    async def ejecutar(self, invernadero_id: str, lectura: Lectura) -> ResultadoRegistro:
        nodo = await self._nodos.obtener(lectura.nodo_id)
        if nodo is None or not nodo.activo or nodo.invernadero_id != invernadero_id:
            raise NodoNoRegistrado(invernadero_id, lectura.nodo_id)

        ahora = self._reloj.ahora()
        validada = validar_lectura(lectura, nodo, ahora)
        guardada = await self._lecturas.guardar(validada.lectura)
        if not guardada:
            return ResultadoRegistro(False, validada.lectura, validada.imposibles)

        es_la_mas_reciente = nodo.ultima_lectura_en is None or lectura.ts >= nodo.ultima_lectura_en
        nodo = nodo.con_lectura(validada.lectura.ts)
        await self._nodos.guardar(nodo)
        self._eventos.publicar(Evento("lectura", {"nodo": nodo, "lectura": validada.lectura}))

        transiciones = []
        if (
            self._alertas is not None
            and es_la_mas_reciente
            and ahora - lectura.ts <= ANTIGUEDAD_MAXIMA_PARA_ALERTAS
        ):
            transiciones = await self._alertas.ejecutar(nodo, validada)
        return ResultadoRegistro(True, validada.lectura, validada.imposibles, transiciones)
