"""Datos de demostración: llena una base aparte y sirve la API para probar la app.

gs-demo                    # la API en el puerto 8001; la primera vez genera 7 días
gs-demo --regenerar        # borra la base de demostración y la genera otra vez
gs-demo --regenerar --dias 14 --solo-generar

Los días se simulan con los mismos casos de uso que usa el servidor, con un reloj que
avanza minuto a minuto: las alertas, la bitácora y los resúmenes salen de las reglas
reales, no se escriben a mano. Generar una semana tarda unos 10 minutos; las siguientes
veces se reutiliza la base y solo se simula el tiempo que estuvo apagada. La base de los
datos reales nunca se toca.

Usuarios (contraseña demo12345): ana@greensense.local (administradora),
bruno@ (supervisor), carla@ (técnica) y daniel@ (operador).
"""

import argparse
import asyncio
import contextlib
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, time, timedelta

from greensense.adaptadores.salida.despertador import DespertadorAsyncio
from greensense.aplicacion.casos_uso.gestionar_nodos import CambiosNodo
from greensense.aplicacion.casos_uso.gestionar_usuarios import CambiosUsuario
from greensense.aplicacion.casos_uso.registrar_estado import EstadoReportado
from greensense.aplicacion.errores import CredencialesInvalidas
from greensense.contenedor import Contenedor
from greensense.dominio.alertas import TipoAlerta
from greensense.dominio.cultivo import Cultivo, RiesgoHongos, Umbral
from greensense.dominio.historial import ZONA_HORARIA
from greensense.dominio.modelos import Lectura, SensorAire, Variable
from greensense.dominio.usuarios import Rol, Usuario
from simulador.generador import Escenario, Generador

log = logging.getLogger("demo")

BASE_DEMO = "greensense_demo"
CONTRASENA_DEMO = "demo12345"
PERIODO = timedelta(seconds=60)
MUY_ATRAS = datetime(2000, 1, 1, tzinfo=UTC)
FIRMWARE = "0.3.0"

# Más estables que los escenarios del simulador, para que las alertas salgan de los
# episodios y no de cada tarde o madrugada.
LECHUGA = Escenario(
    "Lechuga en condiciones normales",
    temperatura_media=23.0,
    temperatura_amplitud=2.2,
    humedad_media=70.0,
    humedad_amplitud=2.5,
    riego_bajo=54.0,
    sustrato_tras_riego=63.0,
    ruido_humedad=0.6,
)
TOMATE = Escenario(
    "Tomate en condiciones normales",
    temperatura_media=25.0,
    temperatura_amplitud=2.0,
    humedad_media=72.0,
    humedad_amplitud=3.0,
    riego_bajo=58.0,
    sustrato_tras_riego=66.0,
    ruido_humedad=0.6,
)

TOMATE_CULTIVO = Cultivo(
    id="tomate",
    nombre="Tomate",
    umbrales=(
        Umbral(Variable.TEMPERATURA, 20.0, 30.0, 2.0),
        Umbral(Variable.HUMEDAD_AIRE, 60.0, 85.0, 5.0),
        Umbral(Variable.HUMEDAD_SUSTRATO, 50.0, 75.0, 5.0, tiempo_alto=timedelta(hours=3)),
    ),
    hongos=RiesgoHongos(humedad_minima=90.0, temperatura_minima=18.0),
)


class RelojDemo:
    """Mientras se generan los datos marca la hora simulada; después, la hora real."""

    def __init__(self) -> None:
        self._fijo: datetime | None = None

    def fijar(self, ts: datetime | None) -> None:
        self._fijo = ts

    def ahora(self) -> datetime:
        return self._fijo or datetime.now(UTC)


Valor = float | None | tuple[float, float]
"""Un valor fijo, None (sensor sin dato) o (inicio, fin) para que cambie poco a poco."""


@dataclass(frozen=True)
class Episodio:
    desde: datetime
    hasta: datetime | None
    """None: sigue hasta el final y también en vivo."""
    valores: dict[Variable, Valor] = field(default_factory=dict)
    sin_lecturas: bool = False
    reinicia: bool = False
    """Al terminar, el nodo vuelve con un arranque nuevo (se quedó sin corriente)."""

    def activo(self, ts: datetime) -> bool:
        return self.desde <= ts and (self.hasta is None or ts < self.hasta)

    def valor(self, variable: Variable, ts: datetime) -> float | None:
        valor = self.valores[variable]
        if not isinstance(valor, tuple):
            return valor
        inicio, fin = valor
        if self.hasta is None:
            return fin
        avance = (ts - self.desde) / (self.hasta - self.desde)
        return inicio + (fin - inicio) * avance


@dataclass
class NodoDemo:
    invernadero: str
    id: str
    nombre: str
    sensor_aire: SensorAire
    sensor_suelo: bool
    escenario: Escenario
    episodios: list[Episodio] = field(default_factory=list)
    picos_imposibles: bool = False
    """De vez en cuando el sensor entrega un valor imposible que el servidor descarta."""
    baja_en: datetime | None = None
    desde: datetime | None = None
    """Al reanudar una demostración: el nodo ya tiene lecturas hasta antes de esta hora."""
    arranque: int = 1
    seq: int = 0
    generador: Generador | None = None
    _apagado: bool = False

    def iniciar(self, semilla: int) -> None:
        self.generador = Generador(
            self.escenario, self.sensor_aire, self.sensor_suelo, semilla=semilla
        )

    def lectura(self, ts: datetime, azar: random.Random) -> Lectura | None:
        """La lectura de este minuto, o None si el nodo no manda nada."""
        if self.baja_en is not None and ts >= self.baja_en:
            return None
        if self.desde is not None and ts < self.desde:
            return None
        episodios = [e for e in self.episodios if e.activo(ts)]
        if any(e.sin_lecturas for e in episodios):
            self._apagado = self._apagado or any(e.reinicia for e in episodios)
            return None
        if self._apagado:
            self._apagado = False
            self.arranque += 1
            self.seq = 0

        assert self.generador is not None
        valores = self.generador.siguiente(ts)
        for episodio in episodios:
            for variable in episodio.valores:
                valor = episodio.valor(variable, ts)
                if valor is not None:
                    valor += azar.gauss(0, 0.25)
                    valor = float(round(valor)) if self._dht11(variable) else round(valor, 1)
                valores[variable.value] = valor
        if self.picos_imposibles and azar.random() < 0.0005:
            valores["temperatura"] = 127.0
        if not self.sensor_suelo:
            valores["humedad_sustrato"] = None

        lectura = Lectura(
            nodo_id=self.id,
            arranque=self.arranque,
            seq=self.seq,
            ts=ts,
            muestras=5,
            rssi=azar.randint(-78, -52),
            **valores,
        )
        self.seq += 1
        return lectura

    def _dht11(self, variable: Variable) -> bool:
        return self.sensor_aire is SensorAire.DHT11 and variable is not Variable.HUMEDAD_SUSTRATO


def _a_las(fin: datetime, dias_antes: int, hora: float) -> datetime:
    """La hora local de Querétaro de hace `dias_antes` días, en UTC."""
    dia = fin.astimezone(ZONA_HORARIA).date() - timedelta(days=dias_antes)
    local = datetime.combine(dia, time(), ZONA_HORARIA) + timedelta(hours=hora)
    return local.astimezone(UTC)


def plan_de_nodos(fin: datetime) -> list[NodoDemo]:
    """Seis nodos; cada uno prueba una parte distinta del sistema."""
    h = timedelta(hours=1)
    m = timedelta(minutes=1)
    t, ha, hs = Variable.TEMPERATURA, Variable.HUMEDAD_AIRE, Variable.HUMEDAD_SUSTRATO
    return [
        # Normal. Hace 5 días falló el riego y el sustrato se secó; ahora la humedad del
        # aire está cerca del máximo (advertencia activa).
        NodoDemo(
            "norte",
            "lechuga-1",
            "Lechugas, cama 1",
            SensorAire.DHT22,
            True,
            LECHUGA,
            [
                Episodio(_a_las(fin, 5, 9), _a_las(fin, 5, 16), {hs: (55.0, 38.0)}),
                Episodio(fin - 3 * h, None, {ha: 77.5}),
            ],
        ),
        # DHT11 sin sensor de suelo: valores enteros y sin reglas de sustrato. Hace 3 días
        # hubo una noche con riesgo de hongos.
        NodoDemo(
            "norte",
            "espinaca-1",
            "Espinacas, cama 2",
            SensorAire.DHT11,
            False,
            LECHUGA,
            [Episodio(_a_las(fin, 3, 1), _a_las(fin, 3, 4), {ha: 88.0, t: 21.0})],
        ),
        # Se quedó sin corriente 4 horas hace 2 días y ahora está desconectado.
        NodoDemo(
            "norte",
            "semillero",
            "Semillero",
            SensorAire.DHT22,
            True,
            LECHUGA,
            [
                Episodio(_a_las(fin, 2, 10), _a_las(fin, 2, 14), sin_lecturas=True, reinicia=True),
                Episodio(fin - 25 * m, None, sin_lecturas=True),
            ],
        ),
        # Una tarde de calor hace 4 días y otra ahora mismo (crítica activa).
        NodoDemo(
            "sur",
            "tomate-1",
            "Tomates, surco 1",
            SensorAire.DHT22,
            True,
            TOMATE,
            [
                Episodio(_a_las(fin, 4, 13), _a_las(fin, 4, 17), {t: (29.0, 32.5)}),
                Episodio(fin - 90 * m, None, {t: (30.5, 32.0)}),
            ],
        ),
        # Falla del sensor de aire hace 6 días, valores imposibles de vez en cuando y
        # el sustrato encharcado ahora (advertencia: espera 3 h para ser crítica).
        NodoDemo(
            "sur",
            "tomate-2",
            "Tomates, surco 2",
            SensorAire.DHT22,
            True,
            TOMATE,
            [
                Episodio(_a_las(fin, 6, 11), _a_las(fin, 6, 11.75), {t: None, ha: None}),
                Episodio(fin - 70 * m, None, {hs: 81.0}),
            ],
            picos_imposibles=True,
        ),
        # Nodo de prueba que se dio de baja hace 3 días: conserva su historial.
        NodoDemo(
            "sur",
            "prueba-1",
            "Nodo de prueba",
            SensorAire.DHT11,
            False,
            TOMATE,
            baja_en=_a_las(fin, 3, 12),
        ),
    ]


Accion = Callable[[], Awaitable[object]]


class Demostracion:
    def __init__(self, contenedor: Contenedor, reloj: RelojDemo, fin: datetime, dias: float):
        self.c = contenedor
        self.reloj = reloj
        self.fin = fin.replace(second=0, microsecond=0)
        self.inicio = self.fin - timedelta(days=dias)
        self.azar = random.Random(7)
        self.nodos = plan_de_nodos(self.fin)
        for i, nodo in enumerate(self.nodos):
            nodo.iniciar(semilla=100 + i)
        self.usuarios: dict[str, Usuario] = {}
        self._acciones: list[tuple[datetime, str, Accion]] = []

    # --- Preparación -----------------------------------------------------------------

    async def preparar(self) -> None:
        """Usuarios, cultivos, invernaderos y nodos, como los daría de alta el equipo."""
        c = self.c
        self.reloj.fijar(self.inicio - timedelta(hours=2))
        ana = await c.crear_usuario.ejecutar(
            None, "Ana López", "ana@greensense.local", Rol.ADMINISTRADOR, CONTRASENA_DEMO
        )
        self.usuarios["ana"] = ana
        await c.iniciar_sesion.ejecutar(ana.correo, CONTRASENA_DEMO)
        for clave, nombre, rol in [
            ("bruno", "Bruno Díaz", Rol.SUPERVISOR),
            ("carla", "Carla Mendoza", Rol.TECNICO),
            ("daniel", "Daniel Ruiz", Rol.OPERADOR),
            ("practicante", "Practicante", Rol.OPERADOR),
        ]:
            self._avanzar(timedelta(minutes=2))
            self.usuarios[clave] = await c.crear_usuario.ejecutar(
                ana, nombre, f"{clave}@greensense.local", rol, CONTRASENA_DEMO
            )

        self._avanzar(timedelta(minutes=5))
        await c.guardar_cultivo.ejecutar(ana, TOMATE_CULTIVO, nuevo=True)
        await c.registrar_invernadero.ejecutar("norte", "Invernadero norte", actor=ana, nuevo=True)
        await c.registrar_invernadero.ejecutar(
            "sur", "Invernadero sur", TOMATE_CULTIVO.id, actor=ana, nuevo=True
        )

        carla = self.usuarios["carla"]
        self._avanzar(timedelta(minutes=30))
        await c.iniciar_sesion.ejecutar(carla.correo, CONTRASENA_DEMO)
        for nodo in self.nodos:
            self._avanzar(timedelta(minutes=3))
            await c.registrar_nodo.ejecutar(
                nodo.invernadero,
                nodo.id,
                nodo.nombre,
                nodo.sensor_aire,
                nodo.sensor_suelo,
                actor=carla,
                nuevo=True,
            )
            await self._conectar(nodo)
        self._programar_acciones()

    async def reanudar(self) -> None:
        """Retoma una demostración ya generada, desde la última lectura de cada nodo.

        Solo siguen los episodios que no terminan (los del estado actual), para que el
        panel se vea igual que cuando se generó.
        """
        estados = {e.nodo.id: e for e in await self.c.consultar_estado_actual.ejecutar()}
        inicios = []
        for nodo in self.nodos:
            nodo.episodios = [
                replace(e, desde=MUY_ATRAS) for e in nodo.episodios if e.hasta is None
            ]
            estado = estados.get(nodo.id)
            if estado is None or estado.ultima is None:
                nodo.baja_en = MUY_ATRAS
                continue
            nodo.arranque, nodo.seq = estado.ultima.arranque, estado.ultima.seq + 1
            nodo.desde = estado.ultima.ts + PERIODO
            if not any(e.sin_lecturas for e in nodo.episodios):
                inicios.append(nodo.desde)
        self.inicio = min(inicios, default=self.fin)
        self._acciones = []

    async def _conectar(self, nodo: NodoDemo) -> None:
        estado = EstadoReportado(
            True, FIRMWARE, nodo.sensor_aire, nodo.sensor_suelo, int(PERIODO.total_seconds())
        )
        await self.c.registrar_estado.ejecutar(nodo.invernadero, nodo.id, estado)

    def _avanzar(self, tiempo: timedelta) -> None:
        self.reloj.fijar(self.reloj.ahora() + tiempo)

    # --- Lo que hacen las personas durante la semana -----------------------------------

    def _en(self, cuando: datetime, descripcion: str, accion: Accion) -> None:
        """Con menos días simulados, lo que tocaba antes del inicio pasa al inicio."""
        if cuando <= self.fin:
            self._acciones.append((max(cuando, self.inicio), descripcion, accion))

    def _programar_acciones(self) -> None:
        u = self.usuarios
        dias = (self.fin - self.inicio).days
        # Cada quien entra a revisar el panel casi todas las mañanas.
        for dia in range(dias, -1, -1):
            for clave, hora in [("daniel", 8.0), ("bruno", 9.5), ("carla", 10.0), ("ana", 18.0)]:
                if self.azar.random() < 0.8:
                    cuando = _a_las(self.fin, dia, hora + self.azar.uniform(0, 50) / 60)
                    if cuando >= self.inicio:
                        self._en(cuando, f"entra {clave}", self._entrar(clave))

        f = self.fin
        self._en(
            _a_las(f, 5, 15.0),
            "Daniel atiende el sustrato seco",
            self._atender("daniel", "lechuga-1"),
        )
        self._en(
            _a_las(f, 6, 11.6),
            "Carla atiende la falla de sensor",
            self._atender("carla", "tomate-2"),
        )
        self._en(_a_las(f, 4, 16.0), "Ana atiende el calor", self._atender("ana", "tomate-1"))
        self._en(
            _a_las(f, 3, 7.5), "Bruno atiende los hongos", self._atender("bruno", "espinaca-1")
        )
        self._en(
            _a_las(f, 2, 15.0),
            "Carla atiende la desconexión",
            self._atender("carla", "semillero", TipoAlerta.DESCONEXION),
        )
        self._en(
            _a_las(f, 5, 17.0),
            "Ana ajusta el riesgo de hongos del tomate",
            lambda: self.c.guardar_cultivo.ejecutar(
                u["ana"],
                replace(TOMATE_CULTIVO, hongos=RiesgoHongos(88.0, 18.0)),
                nuevo=False,
            ),
        )
        self._en(
            _a_las(f, 4, 10.5),
            "Carla renombra el semillero",
            lambda: self.c.modificar_nodo.ejecutar(
                u["carla"], "semillero", CambiosNodo(nombre="Semillero, charolas")
            ),
        )
        self._en(
            _a_las(f, 3, 12.0),
            "Carla da de baja el nodo de prueba",
            lambda: self.c.modificar_nodo.ejecutar(
                u["carla"], "prueba-1", CambiosNodo(activo=False)
            ),
        )
        self._en(
            _a_las(f, 4, 18.5),
            "Ana desactiva al practicante",
            lambda: self.c.modificar_usuario.ejecutar(
                u["ana"], u["practicante"].id, CambiosUsuario(activo=False)
            ),
        )
        self._en(
            _a_las(f, 2, 9.0),
            "Ana corrige el nombre de Daniel",
            lambda: self.c.modificar_usuario.ejecutar(
                u["ana"], u["daniel"].id, CambiosUsuario(nombre="Daniel Ruiz Soto")
            ),
        )
        self._en(_a_las(f, 1, 11.0), "Bruno exporta lecturas", self._exportar())
        self._acciones.sort(key=lambda a: a[0])

    def _entrar(self, clave: str) -> Accion:
        async def entrar() -> None:
            # Un usuario desactivado ya no puede entrar: se salta.
            with contextlib.suppress(CredencialesInvalidas):
                await self.c.iniciar_sesion.ejecutar(self.usuarios[clave].correo, CONTRASENA_DEMO)

        return entrar

    def _atender(
        self,
        clave: str,
        nodo_id: str,
        tipo: TipoAlerta | None = None,
    ) -> Accion:
        """Atiende las alertas críticas de las últimas 8 horas del nodo."""

        async def atender() -> None:
            desde = self.reloj.ahora() - timedelta(hours=8)
            for alerta in await self.c.consultar_alertas.ejecutar(limite=1000):
                if (
                    alerta.nodo_id == nodo_id
                    and alerta.atendida_en is None
                    and alerta.iniciada_en >= desde
                    and (tipo is None or alerta.tipo is tipo)
                    and alerta.escalada_en is not None
                ):
                    await self.c.atender_alerta.ejecutar(alerta.id, self.usuarios[clave])

        return atender

    def _exportar(self) -> Accion:
        async def exportar() -> None:
            hasta = _a_las(self.fin, 1, 0)
            await self.c.exportar_lecturas.ejecutar(
                self.usuarios["bruno"], "lechuga-1", hasta - timedelta(days=3), hasta
            )

        return exportar

    # --- La simulación ---------------------------------------------------------------

    async def simular(self, hasta: Callable[[], datetime]) -> int:
        """Avanza minuto a minuto desde el inicio hasta `hasta()`, que puede ir moviéndose."""
        ts = self.inicio
        lecturas = 0
        siguiente_revision = ts
        while ts <= hasta():
            self.reloj.fijar(ts)
            while self._acciones and self._acciones[0][0] <= ts:
                _, descripcion, accion = self._acciones.pop(0)
                log.debug("%s: %s", ts, descripcion)
                await accion()
            lecturas += await self._lecturas_en(ts)
            if ts >= siguiente_revision:
                await self.c.revisar_nodos.ejecutar()
                siguiente_revision = ts + timedelta(minutes=5)
            ts += PERIODO
            if ts.minute == 0 and ts.hour % 6 == 0:
                log.info("%s lecturas, vamos en %s", lecturas, ts.astimezone(ZONA_HORARIA))
        self.reloj.fijar(None)
        return lecturas

    async def _lecturas_en(self, ts: datetime) -> int:
        """Las lecturas de un minuto. Los nodos no dependen entre sí: van en paralelo."""
        pendientes = []
        for nodo in self.nodos:
            reinicio = nodo._apagado
            lectura = nodo.lectura(ts, self.azar)
            if lectura is not None:
                pendientes.append(self._registrar(nodo, lectura, reinicio))
        await asyncio.gather(*pendientes)
        return len(pendientes)

    async def _registrar(self, nodo: NodoDemo, lectura: Lectura, reinicio: bool) -> None:
        if reinicio:
            await self._conectar(nodo)
        await self.c.registrar_lectura.ejecutar(nodo.invernadero, lectura)

    async def en_vivo(self, periodo_s: float) -> None:
        """Sigue mandando lecturas con la hora real, para ver el panel en tiempo real."""
        while True:
            ahora = datetime.now(UTC)
            for nodo in self.nodos:
                lectura = nodo.lectura(ahora, self.azar)
                if lectura is not None:
                    with contextlib.suppress(Exception):
                        await self.c.registrar_lectura.ejecutar(nodo.invernadero, lectura)
            await asyncio.sleep(periodo_s)


# --- Línea de comandos ---------------------------------------------------------------


def _conectar_postgres(config):
    import psycopg

    return psycopg.connect(
        host=config.db_host,
        port=config.db_puerto,
        user=config.db_usuario,
        password=config.db_contrasena,
        dbname="postgres",
        autocommit=True,
    )


def _base_existe(config, base: str) -> bool:
    with _conectar_postgres(config) as conexion:
        fila = conexion.execute("SELECT 1 FROM pg_database WHERE datname = %s", (base,))
        return fila.fetchone() is not None


def _recrear_base(config, base: str) -> None:
    with _conectar_postgres(config) as conexion:
        conexion.execute(f'DROP DATABASE IF EXISTS "{base}" WITH (FORCE)')
        conexion.execute(f'CREATE DATABASE "{base}"')


async def _correr(args: argparse.Namespace) -> None:
    import uvicorn

    from greensense.cli import migrar
    from greensense.composicion import crear_aplicacion, crear_contenedor
    from greensense.config import Config

    real = Config()
    if args.base == real.db_nombre:
        raise SystemExit(f"La base '{args.base}' es la de los datos reales: usar otra")
    config = Config(
        db_nombre=args.base, mqtt_habilitado=False, admin_correo="", admin_contrasena=""
    )
    nueva = args.regenerar or not _base_existe(config, args.base)
    if nueva:
        log.info("creando la base %s", args.base)
        _recrear_base(config, args.base)
    migrar(config.url_db)

    # El servidor "arranca" antes de lo simulado: si no, la revisión de nodos contaría el
    # plazo de desconexión desde la hora real y nunca alertaría.
    reloj = RelojDemo()
    reloj.fijar(MUY_ATRAS)
    despertador = DespertadorAsyncio()
    contenedor = crear_contenedor(config, despertador, reloj)
    demo = Demostracion(contenedor, reloj, datetime.now(UTC), args.dias)
    if nueva:
        await demo.preparar()
        log.info("simulando %s días (unos 10 min por semana)", args.dias)
    else:
        await demo.reanudar()
        log.info("la base ya existe (--regenerar para empezar de cero); se pone al día")
    log.info("desde %s", demo.inicio.astimezone(ZONA_HORARIA))
    total = await demo.simular(lambda: datetime.now(UTC))
    alertas = await contenedor.consultar_alertas.ejecutar(limite=10_000)
    activas = [a for a in alertas if a.resuelta_en is None]
    log.info("%s lecturas y %s alertas (%s activas)", total, len(alertas), len(activas))

    if args.solo_generar:
        await contenedor.cerrar()
        return
    app = crear_aplicacion(
        config, contenedor, despertador, tareas_extra=[lambda: demo.en_vivo(args.periodo_vivo)]
    )
    log.info("API en http://localhost:%s; la app: cd app && npm run demo", args.puerto)
    servidor = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.puerto))
    await servidor.serve()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gs-demo", description=__doc__.splitlines()[0])
    parser.add_argument("--base", default=BASE_DEMO)
    parser.add_argument(
        "--regenerar", action="store_true", help="borra la base y genera todo otra vez"
    )
    parser.add_argument("--dias", type=float, default=7)
    parser.add_argument("--puerto", type=int, default=8001)
    parser.add_argument("--periodo-vivo", type=float, default=15, help="segundos")
    parser.add_argument("--solo-generar", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    args = _parser().parse_args(argv)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_correr(args))


if __name__ == "__main__":
    main()
