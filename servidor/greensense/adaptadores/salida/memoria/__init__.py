"""Repositorios en memoria, para pruebas y para correr el servidor sin base de datos."""

from dataclasses import replace
from datetime import datetime
from itertools import count

from greensense.aplicacion.errores import CorreoDuplicado
from greensense.dominio.alertas import Alerta
from greensense.dominio.bitacora import RegistroBitacora
from greensense.dominio.cultivo import Cultivo
from greensense.dominio.historial import (
    Agregado,
    Estadistica,
    Periodo,
    estadistica,
    inicio_del_intervalo,
)
from greensense.dominio.modelos import Invernadero, Lectura, Nodo, Variable
from greensense.dominio.notificaciones import Envio, EstadoEnvio, SuscripcionPush
from greensense.dominio.usuarios import Usuario


class RepositorioLecturasMemoria:
    def __init__(self) -> None:
        self._lecturas: dict[tuple, Lectura] = {}

    async def guardar(self, lectura: Lectura) -> bool:
        clave = (lectura.nodo_id, lectura.arranque, lectura.seq, lectura.ts)
        if clave in self._lecturas:
            return False
        self._lecturas[clave] = lectura
        return True

    async def ultima(self, nodo_id: str) -> Lectura | None:
        return max(self._del_nodo(nodo_id), key=lambda lectura: lectura.ts, default=None)

    async def primera(self, nodo_id: str) -> Lectura | None:
        return min(self._del_nodo(nodo_id), key=lambda lectura: lectura.ts, default=None)

    async def en_rango(
        self, nodo_id: str, desde: datetime, hasta: datetime, limite: int
    ) -> list[Lectura]:
        return self._rango(nodo_id, desde, hasta)[:limite]

    async def agregadas(
        self, nodo_id: str, desde: datetime, hasta: datetime, periodo: Periodo
    ) -> list[Agregado]:
        grupos: dict[datetime, list[Lectura]] = {}
        for lectura in self._rango(nodo_id, desde, hasta):
            grupos.setdefault(inicio_del_intervalo(lectura.ts, periodo), []).append(lectura)
        return [
            Agregado(inicio, len(lecturas), _estadisticas(lecturas))
            for inicio, lecturas in sorted(grupos.items())
        ]

    async def estadisticas(
        self, nodo_id: str, desde: datetime, hasta: datetime
    ) -> tuple[int, dict[Variable, Estadistica | None]]:
        lecturas = self._rango(nodo_id, desde, hasta)
        return len(lecturas), _estadisticas(lecturas)

    def _del_nodo(self, nodo_id: str) -> list[Lectura]:
        return [lectura for lectura in self._lecturas.values() if lectura.nodo_id == nodo_id]

    def _rango(self, nodo_id: str, desde: datetime, hasta: datetime) -> list[Lectura]:
        en_rango = [lectura for lectura in self._del_nodo(nodo_id) if desde <= lectura.ts < hasta]
        return sorted(en_rango, key=lambda lectura: (lectura.ts, lectura.arranque, lectura.seq))


def _estadisticas(lecturas: list[Lectura]) -> dict[Variable, Estadistica | None]:
    return {
        variable: estadistica([v for lec in lecturas if (v := lec.valor(variable)) is not None])
        for variable in Variable
    }


class RepositorioNodosMemoria:
    def __init__(self) -> None:
        self._nodos: dict[str, Nodo] = {}

    async def obtener(self, nodo_id: str) -> Nodo | None:
        return self._nodos.get(nodo_id)

    async def listar(self) -> list[Nodo]:
        return list(self._nodos.values())

    async def guardar(self, nodo: Nodo) -> None:
        self._nodos[nodo.id] = nodo


class RepositorioInvernaderosMemoria:
    def __init__(self) -> None:
        self._invernaderos: dict[str, Invernadero] = {}

    async def obtener(self, invernadero_id: str) -> Invernadero | None:
        return self._invernaderos.get(invernadero_id)

    async def listar(self) -> list[Invernadero]:
        return list(self._invernaderos.values())

    async def guardar(self, invernadero: Invernadero) -> None:
        self._invernaderos[invernadero.id] = invernadero

    async def borrar(self, invernadero_id: str) -> None:
        self._invernaderos.pop(invernadero_id, None)


class RepositorioCultivosMemoria:
    def __init__(self, *iniciales: Cultivo) -> None:
        self._cultivos = {c.id: c for c in iniciales}

    async def obtener(self, cultivo_id: str) -> Cultivo | None:
        return self._cultivos.get(cultivo_id)

    async def listar(self) -> list[Cultivo]:
        return list(self._cultivos.values())

    async def guardar(self, cultivo: Cultivo) -> None:
        self._cultivos[cultivo.id] = cultivo

    async def borrar(self, cultivo_id: str) -> None:
        self._cultivos.pop(cultivo_id, None)


class RepositorioAlertasMemoria:
    def __init__(self) -> None:
        self._alertas: dict[int, Alerta] = {}
        self._siguiente = count(1)

    async def guardar(self, alerta: Alerta) -> Alerta:
        if alerta.id is None:
            alerta = replace(alerta, id=next(self._siguiente))
        self._alertas[alerta.id] = alerta
        return alerta

    async def obtener(self, alerta_id: int) -> Alerta | None:
        return self._alertas.get(alerta_id)

    async def activas(self, nodo_id: str | None = None) -> list[Alerta]:
        return [a for a in self._alertas.values() if a.activa and nodo_id in (None, a.nodo_id)]

    async def listar(self, solo_activas: bool = False, limite: int = 100) -> list[Alerta]:
        alertas = [a for a in self._alertas.values() if a.activa or not solo_activas]
        alertas.sort(key=lambda a: (a.iniciada_en, a.id), reverse=True)
        return alertas[:limite]

    async def en_rango(
        self, desde: datetime, hasta: datetime, nodo_id: str | None = None
    ) -> list[Alerta]:
        alertas = [
            a
            for a in self._alertas.values()
            if desde <= a.iniciada_en < hasta and nodo_id in (None, a.nodo_id)
        ]
        return sorted(alertas, key=lambda a: (a.iniciada_en, a.id))


class RepositorioSuscripcionesMemoria:
    def __init__(self) -> None:
        self._suscripciones: dict[int, SuscripcionPush] = {}
        self._siguiente = count(1)

    async def guardar(self, suscripcion: SuscripcionPush) -> SuscripcionPush:
        existente = next(
            (s for s in self._suscripciones.values() if s.endpoint == suscripcion.endpoint), None
        )
        identificador = existente.id if existente else next(self._siguiente)
        if existente and existente.usuario_id != suscripcion.usuario_id:
            # Otro usuario inició sesión en el mismo navegador: los envíos pendientes del
            # anterior ya no son para él (en PostgreSQL pasa igual con la cascada).
            del self._suscripciones[existente.id]
            identificador = next(self._siguiente)
        suscripcion = replace(suscripcion, id=identificador)
        self._suscripciones[identificador] = suscripcion
        return suscripcion

    async def obtener(self, suscripcion_id: int) -> SuscripcionPush | None:
        return self._suscripciones.get(suscripcion_id)

    async def listar(self) -> list[SuscripcionPush]:
        return list(self._suscripciones.values())

    async def borrar(self, suscripcion_id: int) -> None:
        self._suscripciones.pop(suscripcion_id, None)

    def existe(self, suscripcion_id: int) -> bool:
        return suscripcion_id in self._suscripciones

    async def borrar_por_endpoint(self, endpoint: str, usuario_id: int) -> bool:
        for s in list(self._suscripciones.values()):
            if s.endpoint == endpoint and s.usuario_id == usuario_id:
                del self._suscripciones[s.id]
                return True
        return False


class RepositorioEnviosMemoria:
    """Al borrar una suscripción, sus envíos pendientes desaparecen (como en cascada)."""

    def __init__(self, suscripciones: RepositorioSuscripcionesMemoria | None = None) -> None:
        self._envios: dict[int, Envio] = {}
        self._siguiente = count(1)
        self._suscripciones = suscripciones

    async def crear(self, envios: list[Envio]) -> None:
        for envio in envios:
            envio = replace(envio, id=next(self._siguiente))
            self._envios[envio.id] = envio

    async def pendientes(self, ahora: datetime, limite: int = 50) -> list[Envio]:
        pendientes = [
            e
            for e in self._envios.values()
            if e.estado is EstadoEnvio.PENDIENTE
            and e.proximo_intento_en <= ahora
            and (
                self._suscripciones is None
                or e.suscripcion_id in self._suscripciones._suscripciones
            )
        ]
        return sorted(pendientes, key=lambda e: (e.proximo_intento_en, e.id))[:limite]

    async def guardar(self, envio: Envio) -> None:
        self._envios[envio.id] = envio

    def todos(self) -> list[Envio]:
        return list(self._envios.values())


class RepositorioUsuariosMemoria:
    def __init__(self) -> None:
        self._usuarios: dict[int, Usuario] = {}
        self._siguiente = count(1)

    async def obtener(self, usuario_id: int) -> Usuario | None:
        return self._usuarios.get(usuario_id)

    async def por_correo(self, correo: str) -> Usuario | None:
        return next((u for u in self._usuarios.values() if u.correo == correo), None)

    async def listar(self) -> list[Usuario]:
        return sorted(self._usuarios.values(), key=lambda u: u.id)

    async def guardar(self, usuario: Usuario) -> Usuario:
        otro = await self.por_correo(usuario.correo)
        if otro is not None and otro.id != usuario.id:
            raise CorreoDuplicado(usuario.correo)
        if usuario.id is None:
            usuario = replace(usuario, id=next(self._siguiente))
        self._usuarios[usuario.id] = usuario
        return usuario


class RepositorioBitacoraMemoria:
    def __init__(self) -> None:
        self._registros: list[RegistroBitacora] = []

    async def agregar(self, registro: RegistroBitacora) -> RegistroBitacora:
        registro = replace(registro, id=len(self._registros) + 1)
        self._registros.append(registro)
        return registro

    async def listar(
        self, limite: int = 100, antes_de: int | None = None
    ) -> list[RegistroBitacora]:
        registros = [r for r in reversed(self._registros) if antes_de is None or r.id < antes_de]
        return registros[:limite]
