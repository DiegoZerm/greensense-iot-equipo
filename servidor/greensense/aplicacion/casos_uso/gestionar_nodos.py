"""Invernaderos y nodos: alta, modificación y baja. Los usan la API y la línea de comandos.

Registrar un nodo aquí no crea su usuario MQTT: eso se hace en infra/.env
(MQTT_NODOS) y con infra/mosquitto/crear_usuarios.sh.
"""

from dataclasses import dataclass, replace

from greensense.aplicacion.casos_uso.bitacora import Anotador, describir_cambios
from greensense.aplicacion.errores import (
    Conflicto,
    DatosInvalidos,
    InvernaderoNoRegistrado,
    NoEncontrado,
)
from greensense.aplicacion.puertos import (
    Evento,
    PublicadorEventos,
    Reloj,
    RepositorioAlertas,
    RepositorioCultivos,
    RepositorioInvernaderos,
    RepositorioNodos,
)
from greensense.dominio.bitacora import Accion, Objeto
from greensense.dominio.cultivo import CULTIVO_PREDETERMINADO
from greensense.dominio.modelos import Invernadero, Nodo, SensorAire, validar_id
from greensense.dominio.usuarios import Usuario


def _validar_nombre(nombre: str) -> str:
    nombre = nombre.strip()
    if not nombre or len(nombre) > 100:
        raise DatosInvalidos("el nombre debe tener entre 1 y 100 caracteres")
    return nombre


async def _validar_cultivo(cultivos: RepositorioCultivos | None, cultivo_id: str) -> None:
    if cultivos is not None and await cultivos.obtener(cultivo_id) is None:
        raise NoEncontrado("el cultivo", cultivo_id)


class ListarInvernaderos:
    def __init__(self, invernaderos: RepositorioInvernaderos) -> None:
        self._invernaderos = invernaderos

    async def ejecutar(self) -> list[Invernadero]:
        return sorted(await self._invernaderos.listar(), key=lambda i: i.id)


class RegistrarInvernadero:
    """Con `nuevo=True` rechaza un id existente; si no, actualiza el que haya (CLI)."""

    def __init__(
        self,
        invernaderos: RepositorioInvernaderos,
        cultivos: RepositorioCultivos | None = None,
        anotador: Anotador | None = None,
    ) -> None:
        self._invernaderos = invernaderos
        self._cultivos = cultivos
        self._anotador = anotador

    async def ejecutar(
        self,
        invernadero_id: str,
        nombre: str,
        cultivo_id: str = CULTIVO_PREDETERMINADO.id,
        actor: Usuario | None = None,
        nuevo: bool = False,
    ) -> Invernadero:
        invernadero = Invernadero(validar_id(invernadero_id), _validar_nombre(nombre), cultivo_id)
        existente = await self._invernaderos.obtener(invernadero_id)
        if nuevo and existente is not None:
            raise Conflicto(f"ya existe el invernadero '{invernadero_id}'")
        await _validar_cultivo(self._cultivos, cultivo_id)
        await self._invernaderos.guardar(invernadero)
        if self._anotador:
            accion = Accion.MODIFICAR if existente else Accion.CREAR
            detalle = f"{invernadero.nombre}, cultivo {cultivo_id}"
            await self._anotador.anotar(actor, accion, Objeto.INVERNADERO, invernadero.id, detalle)
        return invernadero


class ModificarInvernadero:
    def __init__(
        self,
        invernaderos: RepositorioInvernaderos,
        cultivos: RepositorioCultivos,
        anotador: Anotador,
    ) -> None:
        self._invernaderos = invernaderos
        self._cultivos = cultivos
        self._anotador = anotador

    async def ejecutar(
        self,
        actor: Usuario | None,
        invernadero_id: str,
        nombre: str | None = None,
        cultivo_id: str | None = None,
    ) -> Invernadero:
        antes = await self._invernaderos.obtener(invernadero_id)
        if antes is None:
            raise NoEncontrado("el invernadero", invernadero_id)
        despues = antes
        if nombre is not None:
            despues = replace(despues, nombre=_validar_nombre(nombre))
        if cultivo_id is not None:
            await _validar_cultivo(self._cultivos, cultivo_id)
            despues = replace(despues, cultivo_id=cultivo_id)
        await self._invernaderos.guardar(despues)
        detalle = describir_cambios(antes, despues, ("nombre", "cultivo_id"))
        if detalle:
            await self._anotador.anotar(
                actor, Accion.MODIFICAR, Objeto.INVERNADERO, invernadero_id, detalle
            )
        return despues


class BorrarInvernadero:
    """Solo se borra un invernadero sin nodos: los nodos guardan el historial de lecturas."""

    def __init__(
        self,
        invernaderos: RepositorioInvernaderos,
        nodos: RepositorioNodos,
        anotador: Anotador,
    ) -> None:
        self._invernaderos = invernaderos
        self._nodos = nodos
        self._anotador = anotador

    async def ejecutar(self, actor: Usuario | None, invernadero_id: str) -> None:
        invernadero = await self._invernaderos.obtener(invernadero_id)
        if invernadero is None:
            raise NoEncontrado("el invernadero", invernadero_id)
        if any(n.invernadero_id == invernadero_id for n in await self._nodos.listar()):
            raise Conflicto("el invernadero tiene nodos registrados")
        await self._invernaderos.borrar(invernadero_id)
        await self._anotador.anotar(
            actor, Accion.BORRAR, Objeto.INVERNADERO, invernadero_id, invernadero.nombre
        )


class ListarNodos:
    def __init__(self, nodos: RepositorioNodos) -> None:
        self._nodos = nodos

    async def ejecutar(self) -> list[Nodo]:
        return sorted(await self._nodos.listar(), key=lambda n: (n.invernadero_id, n.id))


class RegistrarNodo:
    """Con `nuevo=True` rechaza un id existente; si no, actualiza el que haya (CLI)."""

    def __init__(
        self,
        invernaderos: RepositorioInvernaderos,
        nodos: RepositorioNodos,
        anotador: Anotador | None = None,
    ) -> None:
        self._invernaderos = invernaderos
        self._nodos = nodos
        self._anotador = anotador

    async def ejecutar(
        self,
        invernadero_id: str,
        nodo_id: str,
        nombre: str,
        sensor_aire: SensorAire = SensorAire.DHT11,
        sensor_suelo: bool = False,
        actor: Usuario | None = None,
        nuevo: bool = False,
    ) -> Nodo:
        validar_id(nodo_id)
        if await self._invernaderos.obtener(invernadero_id) is None:
            raise InvernaderoNoRegistrado(invernadero_id)

        datos = {
            "invernadero_id": invernadero_id,
            "nombre": _validar_nombre(nombre),
            "sensor_aire": sensor_aire,
            "sensor_suelo": sensor_suelo,
        }
        existente = await self._nodos.obtener(nodo_id)
        if nuevo and existente is not None:
            raise Conflicto(f"ya existe el nodo '{nodo_id}'")
        # Si ya existía, conserva su estado y lo que reportó al conectarse.
        nodo = replace(existente, **datos) if existente else Nodo(id=nodo_id, **datos)
        await self._nodos.guardar(nodo)
        if self._anotador:
            accion = Accion.MODIFICAR if existente else Accion.ALTA
            suelo = "con" if sensor_suelo else "sin"
            detalle = f"{nodo.nombre} en {invernadero_id}, {sensor_aire} {suelo} sensor de suelo"
            await self._anotador.anotar(actor, accion, Objeto.NODO, nodo_id, detalle)
        return nodo


@dataclass(frozen=True)
class CambiosNodo:
    nombre: str | None = None
    sensor_aire: SensorAire | None = None
    sensor_suelo: bool | None = None
    activo: bool | None = None


class ModificarNodo:
    """Cambia los datos de un nodo, o lo da de baja o de alta.

    El invernadero no se cambia: forma parte de los temas MQTT del nodo y habría que
    volver a cargar su firmware. Al darlo de baja se resuelven sus alertas activas.
    """

    def __init__(
        self,
        nodos: RepositorioNodos,
        alertas: RepositorioAlertas,
        eventos: PublicadorEventos,
        reloj: Reloj,
        anotador: Anotador,
    ) -> None:
        self._nodos = nodos
        self._alertas = alertas
        self._eventos = eventos
        self._reloj = reloj
        self._anotador = anotador

    async def ejecutar(self, actor: Usuario | None, nodo_id: str, cambios: CambiosNodo) -> Nodo:
        antes = await self._nodos.obtener(nodo_id)
        if antes is None:
            raise NoEncontrado("el nodo", nodo_id)
        despues = replace(
            antes,
            nombre=antes.nombre if cambios.nombre is None else _validar_nombre(cambios.nombre),
            sensor_aire=cambios.sensor_aire or antes.sensor_aire,
            sensor_suelo=antes.sensor_suelo
            if cambios.sensor_suelo is None
            else cambios.sensor_suelo,
            activo=antes.activo if cambios.activo is None else cambios.activo,
        )
        await self._nodos.guardar(despues)

        if antes.activo != despues.activo:
            accion = Accion.ALTA if despues.activo else Accion.BAJA
            await self._anotador.anotar(actor, accion, Objeto.NODO, nodo_id, despues.nombre)
            if not despues.activo:
                await self._resolver_alertas(nodo_id)
        detalle = describir_cambios(antes, despues, ("nombre", "sensor_aire", "sensor_suelo"))
        if detalle:
            await self._anotador.anotar(actor, Accion.MODIFICAR, Objeto.NODO, nodo_id, detalle)
        self._eventos.publicar(Evento("nodo", {"nodo": despues}))
        return despues

    async def _resolver_alertas(self, nodo_id: str) -> None:
        ahora = self._reloj.ahora()
        for alerta in await self._alertas.activas(nodo_id):
            alerta = await self._alertas.guardar(
                replace(alerta, resuelta_en=ahora, actualizada_en=ahora)
            )
            self._eventos.publicar(Evento("alerta", {"alerta": alerta}))
