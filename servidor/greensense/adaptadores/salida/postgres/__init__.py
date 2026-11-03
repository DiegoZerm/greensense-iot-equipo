"""Repositorios sobre PostgreSQL con TimescaleDB."""

from dataclasses import fields, replace
from datetime import datetime, timedelta

from sqlalchemy import delete, func, literal, select, update
from sqlalchemy.dialects.postgresql import INTERVAL, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from greensense.adaptadores.salida.postgres import tablas
from greensense.aplicacion.errores import CorreoDuplicado
from greensense.dominio.alertas import Alerta, Severidad, TipoAlerta
from greensense.dominio.bitacora import Accion, Objeto, RegistroBitacora
from greensense.dominio.cultivo import Cultivo, RiesgoHongos, Umbral
from greensense.dominio.historial import ZONA_HORARIA, Agregado, Estadistica, Periodo
from greensense.dominio.modelos import (
    EstadoNodo,
    Invernadero,
    Lectura,
    Nodo,
    SensorAire,
    Variable,
)
from greensense.dominio.notificaciones import Envio, EstadoEnvio, SuscripcionPush
from greensense.dominio.usuarios import Rol, Usuario

_CAMPOS_LECTURA = (
    "nodo_id", "arranque", "seq", "ts", "temperatura", "humedad_aire",
    "humedad_sustrato", "muestras", "rssi",
)  # fmt: skip


def crear_motor(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True)


class RepositorioLecturasPostgres:
    def __init__(self, motor: AsyncEngine) -> None:
        self._motor = motor

    async def guardar(self, lectura: Lectura) -> bool:
        valores = {campo: getattr(lectura, campo) for campo in _CAMPOS_LECTURA}
        sentencia = (
            insert(tablas.lectura)
            .values(**valores)
            .on_conflict_do_nothing(index_elements=["nodo_id", "arranque", "seq", "ts"])
            # rowcount no es confiable con psycopg asíncrono; RETURNING solo trae
            # una fila si de verdad se insertó.
            .returning(tablas.lectura.c.seq)
        )
        async with self._motor.begin() as conexion:
            resultado = await conexion.execute(sentencia)
            return resultado.first() is not None

    async def ultima(self, nodo_id: str) -> Lectura | None:
        columnas = [tablas.lectura.c[campo] for campo in _CAMPOS_LECTURA]
        sentencia = (
            select(*columnas)
            .where(tablas.lectura.c.nodo_id == nodo_id)
            .order_by(tablas.lectura.c.ts.desc())
            .limit(1)
        )
        async with self._motor.connect() as conexion:
            fila = (await conexion.execute(sentencia)).mappings().first()
        return _a_lectura(fila) if fila else None

    async def primera(self, nodo_id: str) -> Lectura | None:
        t = tablas.lectura
        sentencia = (
            select(*[t.c[campo] for campo in _CAMPOS_LECTURA])
            .where(t.c.nodo_id == nodo_id)
            .order_by(t.c.ts)
            .limit(1)
        )
        async with self._motor.connect() as conexion:
            fila = (await conexion.execute(sentencia)).mappings().first()
        return _a_lectura(fila) if fila else None

    async def en_rango(
        self, nodo_id: str, desde: datetime, hasta: datetime, limite: int
    ) -> list[Lectura]:
        t = tablas.lectura
        sentencia = (
            select(*[t.c[campo] for campo in _CAMPOS_LECTURA])
            .where(t.c.nodo_id == nodo_id, t.c.ts >= desde, t.c.ts < hasta)
            .order_by(t.c.ts, t.c.arranque, t.c.seq)
            .limit(limite)
        )
        async with self._motor.connect() as conexion:
            filas = (await conexion.execute(sentencia)).mappings().all()
        return [_a_lectura(fila) for fila in filas]

    async def agregadas(
        self, nodo_id: str, desde: datetime, hasta: datetime, periodo: Periodo
    ) -> list[Agregado]:
        # Se agrupa directo sobre la hypertable con time_bucket en la hora local. Con un
        # agregado continuo, las lecturas que el nodo reenvía tarde (con hora vieja) no
        # aparecerían hasta el siguiente refresco.
        t = tablas.lectura
        ancho = "1 hour" if periodo is Periodo.HORA else "1 day"
        inicio = func.time_bucket(
            literal(ancho).cast(INTERVAL), t.c.ts, literal(ZONA_HORARIA.key)
        ).label("inicio")
        sentencia = (
            select(inicio, func.count().label("lecturas"), *_columnas_estadisticas(t))
            .where(t.c.nodo_id == nodo_id, t.c.ts >= desde, t.c.ts < hasta)
            .group_by(inicio)
            .order_by(inicio)
        )
        async with self._motor.connect() as conexion:
            filas = (await conexion.execute(sentencia)).mappings().all()
        return [
            Agregado(
                fila["inicio"].astimezone(ZONA_HORARIA), fila["lecturas"], _a_estadisticas(fila)
            )
            for fila in filas
        ]

    async def estadisticas(
        self, nodo_id: str, desde: datetime, hasta: datetime
    ) -> tuple[int, dict[Variable, Estadistica | None]]:
        t = tablas.lectura
        sentencia = select(func.count().label("lecturas"), *_columnas_estadisticas(t)).where(
            t.c.nodo_id == nodo_id, t.c.ts >= desde, t.c.ts < hasta
        )
        async with self._motor.connect() as conexion:
            fila = (await conexion.execute(sentencia)).mappings().one()
        return fila["lecturas"], _a_estadisticas(fila)


def _columnas_estadisticas(t) -> list:
    columnas = []
    for variable in Variable:
        c = t.c[variable.value]
        columnas += [
            func.min(c).label(f"{variable.value}_min"),
            func.max(c).label(f"{variable.value}_max"),
            func.avg(c).label(f"{variable.value}_prom"),
            func.count(c).label(f"{variable.value}_n"),
        ]
    return columnas


def _a_estadisticas(fila) -> dict[Variable, Estadistica | None]:
    resultado: dict[Variable, Estadistica | None] = {}
    for v in Variable:
        n = fila[f"{v.value}_n"]
        resultado[v] = (
            Estadistica(
                minimo=round(fila[f"{v.value}_min"], 2),
                maximo=round(fila[f"{v.value}_max"], 2),
                promedio=round(float(fila[f"{v.value}_prom"]), 2),
                n=n,
            )
            if n
            else None
        )
    return resultado


def _a_lectura(fila) -> Lectura:
    # REAL es de 4 bytes: 24.3 regresa como 24.2999992. Se redondea a la precisión
    # que tienen los sensores.
    datos = dict(fila)
    for variable in Variable:
        if datos[variable.value] is not None:
            datos[variable.value] = round(datos[variable.value], 2)
    return Lectura(**datos)


def _a_nodo(fila) -> Nodo:
    return Nodo(
        id=fila["id"],
        invernadero_id=fila["invernadero_id"],
        nombre=fila["nombre"],
        sensor_aire=SensorAire(fila["sensor_aire"]),
        sensor_suelo=fila["sensor_suelo"],
        estado=EstadoNodo(fila["estado"]),
        firmware=fila["firmware"],
        periodo_s=fila["periodo_s"],
        ultima_lectura_en=fila["ultima_lectura_en"],
        activo=fila["activo"],
    )


class RepositorioNodosPostgres:
    def __init__(self, motor: AsyncEngine) -> None:
        self._motor = motor
        self._columnas = [c for c in tablas.nodo.c if c.name != "creado_en"]

    async def obtener(self, nodo_id: str) -> Nodo | None:
        sentencia = select(*self._columnas).where(tablas.nodo.c.id == nodo_id)
        async with self._motor.connect() as conexion:
            fila = (await conexion.execute(sentencia)).mappings().first()
        return _a_nodo(fila) if fila else None

    async def listar(self) -> list[Nodo]:
        async with self._motor.connect() as conexion:
            filas = (await conexion.execute(select(*self._columnas))).mappings().all()
        return [_a_nodo(fila) for fila in filas]

    async def guardar(self, nodo: Nodo) -> None:
        valores = {
            "id": nodo.id,
            "invernadero_id": nodo.invernadero_id,
            "nombre": nodo.nombre,
            "sensor_aire": nodo.sensor_aire.value,
            "sensor_suelo": nodo.sensor_suelo,
            "estado": nodo.estado.value,
            "firmware": nodo.firmware,
            "periodo_s": nodo.periodo_s,
            "ultima_lectura_en": nodo.ultima_lectura_en,
            "activo": nodo.activo,
        }
        sentencia = insert(tablas.nodo).values(**valores)
        sentencia = sentencia.on_conflict_do_update(
            index_elements=["id"], set_={k: v for k, v in valores.items() if k != "id"}
        )
        async with self._motor.begin() as conexion:
            await conexion.execute(sentencia)


class RepositorioInvernaderosPostgres:
    def __init__(self, motor: AsyncEngine) -> None:
        self._motor = motor

    async def obtener(self, invernadero_id: str) -> Invernadero | None:
        t = tablas.invernadero
        sentencia = select(t.c.id, t.c.nombre, t.c.cultivo_id).where(t.c.id == invernadero_id)
        async with self._motor.connect() as conexion:
            fila = (await conexion.execute(sentencia)).mappings().first()
        return Invernadero(**fila) if fila else None

    async def listar(self) -> list[Invernadero]:
        t = tablas.invernadero
        async with self._motor.connect() as conexion:
            filas = (await conexion.execute(select(t.c.id, t.c.nombre, t.c.cultivo_id))).mappings()
            return [Invernadero(**fila) for fila in filas.all()]

    async def guardar(self, invernadero: Invernadero) -> None:
        valores = {"nombre": invernadero.nombre, "cultivo_id": invernadero.cultivo_id}
        sentencia = insert(tablas.invernadero).values(id=invernadero.id, **valores)
        sentencia = sentencia.on_conflict_do_update(index_elements=["id"], set_=valores)
        async with self._motor.begin() as conexion:
            await conexion.execute(sentencia)

    async def borrar(self, invernadero_id: str) -> None:
        t = tablas.invernadero
        async with self._motor.begin() as conexion:
            await conexion.execute(delete(t).where(t.c.id == invernadero_id))


def _a_cultivo(fila, umbrales) -> Cultivo:
    orden = list(Variable)
    return Cultivo(
        id=fila["id"],
        nombre=fila["nombre"],
        umbrales=tuple(
            Umbral(
                Variable(f["variable"]),
                f["minimo"],
                f["maximo"],
                f["margen"],
                timedelta(seconds=f["tiempo_bajo_s"]),
                timedelta(seconds=f["tiempo_alto_s"]),
            )
            for f in sorted(umbrales, key=lambda f: orden.index(Variable(f["variable"])))
        ),
        hongos=RiesgoHongos(
            fila["hongos_humedad_minima"],
            fila["hongos_temperatura_minima"],
            timedelta(seconds=fila["hongos_tiempo_minimo_s"]),
        ),
    )


class RepositorioCultivosPostgres:
    def __init__(self, motor: AsyncEngine) -> None:
        self._motor = motor

    async def obtener(self, cultivo_id: str) -> Cultivo | None:
        cultivos = await self._leer(cultivo_id)
        return cultivos[0] if cultivos else None

    async def listar(self) -> list[Cultivo]:
        return await self._leer()

    async def borrar(self, cultivo_id: str) -> None:
        t = tablas.cultivo
        async with self._motor.begin() as conexion:
            await conexion.execute(delete(t).where(t.c.id == cultivo_id))

    async def _leer(self, cultivo_id: str | None = None) -> list[Cultivo]:
        c, u = tablas.cultivo, tablas.umbral
        de_cultivos, de_umbrales = select(c).order_by(c.c.id), select(u)
        if cultivo_id is not None:
            de_cultivos = de_cultivos.where(c.c.id == cultivo_id)
            de_umbrales = de_umbrales.where(u.c.cultivo_id == cultivo_id)
        async with self._motor.connect() as conexion:
            filas = (await conexion.execute(de_cultivos)).mappings().all()
            umbrales = (await conexion.execute(de_umbrales)).mappings().all()
        return [
            _a_cultivo(fila, [f for f in umbrales if f["cultivo_id"] == fila["id"]])
            for fila in filas
        ]

    async def guardar(self, cultivo: Cultivo) -> None:
        valores = {
            "nombre": cultivo.nombre,
            "hongos_humedad_minima": cultivo.hongos.humedad_minima,
            "hongos_temperatura_minima": cultivo.hongos.temperatura_minima,
            "hongos_tiempo_minimo_s": int(cultivo.hongos.tiempo_minimo.total_seconds()),
        }
        async with self._motor.begin() as conexion:
            await conexion.execute(
                insert(tablas.cultivo)
                .values(id=cultivo.id, **valores)
                .on_conflict_do_update(index_elements=["id"], set_=valores)
            )
            await conexion.execute(
                delete(tablas.umbral).where(tablas.umbral.c.cultivo_id == cultivo.id)
            )
            if cultivo.umbrales:
                await conexion.execute(
                    insert(tablas.umbral),
                    [
                        {
                            "cultivo_id": cultivo.id,
                            "variable": u.variable.value,
                            "minimo": u.minimo,
                            "maximo": u.maximo,
                            "margen": u.margen,
                            "tiempo_bajo_s": int(u.tiempo_bajo.total_seconds()),
                            "tiempo_alto_s": int(u.tiempo_alto.total_seconds()),
                        }
                        for u in cultivo.umbrales
                    ],
                )


_CAMPOS_ALERTA = [f.name for f in fields(Alerta) if f.name != "id"]


def _a_alerta(fila) -> Alerta:
    datos = {campo: fila[campo] for campo in _CAMPOS_ALERTA}
    datos["tipo"] = TipoAlerta(datos["tipo"])
    datos["severidad"] = Severidad(datos["severidad"])
    datos["variable"] = Variable(datos["variable"]) if datos["variable"] else None
    for campo in ("valor", "limite"):
        if datos[campo] is not None:
            datos[campo] = round(datos[campo], 2)
    return Alerta(id=fila["id"], **datos)


class RepositorioAlertasPostgres:
    def __init__(self, motor: AsyncEngine) -> None:
        self._motor = motor

    async def guardar(self, alerta: Alerta) -> Alerta:
        valores = {campo: getattr(alerta, campo) for campo in _CAMPOS_ALERTA}
        valores["variable"] = alerta.variable.value if alerta.variable else None
        t = tablas.alerta
        async with self._motor.begin() as conexion:
            if alerta.id is None:
                nuevo_id = (
                    await conexion.execute(insert(t).values(**valores).returning(t.c.id))
                ).scalar_one()
                return replace(alerta, id=nuevo_id)
            await conexion.execute(update(t).where(t.c.id == alerta.id).values(**valores))
        return alerta

    async def obtener(self, alerta_id: int) -> Alerta | None:
        t = tablas.alerta
        async with self._motor.connect() as conexion:
            fila = (await conexion.execute(select(t).where(t.c.id == alerta_id))).mappings().first()
        return _a_alerta(fila) if fila else None

    async def activas(self, nodo_id: str | None = None) -> list[Alerta]:
        t = tablas.alerta
        sentencia = select(t).where(t.c.resuelta_en.is_(None))
        if nodo_id is not None:
            sentencia = sentencia.where(t.c.nodo_id == nodo_id)
        async with self._motor.connect() as conexion:
            filas = (await conexion.execute(sentencia)).mappings().all()
        return [_a_alerta(f) for f in filas]

    async def listar(self, solo_activas: bool = False, limite: int = 100) -> list[Alerta]:
        t = tablas.alerta
        sentencia = select(t).order_by(t.c.iniciada_en.desc(), t.c.id.desc()).limit(limite)
        if solo_activas:
            sentencia = sentencia.where(t.c.resuelta_en.is_(None))
        async with self._motor.connect() as conexion:
            filas = (await conexion.execute(sentencia)).mappings().all()
        return [_a_alerta(f) for f in filas]

    async def en_rango(
        self, desde: datetime, hasta: datetime, nodo_id: str | None = None
    ) -> list[Alerta]:
        t = tablas.alerta
        sentencia = (
            select(t)
            .where(t.c.iniciada_en >= desde, t.c.iniciada_en < hasta)
            .order_by(t.c.iniciada_en, t.c.id)
        )
        if nodo_id is not None:
            sentencia = sentencia.where(t.c.nodo_id == nodo_id)
        async with self._motor.connect() as conexion:
            filas = (await conexion.execute(sentencia)).mappings().all()
        return [_a_alerta(f) for f in filas]


def _a_suscripcion(fila) -> SuscripcionPush:
    return SuscripcionPush(
        endpoint=fila["endpoint"],
        p256dh=fila["p256dh"],
        auth=fila["auth"],
        creada_en=fila["creada_en"],
        usuario_id=fila["usuario_id"],
        id=fila["id"],
    )


class RepositorioSuscripcionesPostgres:
    def __init__(self, motor: AsyncEngine) -> None:
        self._motor = motor

    async def guardar(self, suscripcion: SuscripcionPush) -> SuscripcionPush:
        t = tablas.suscripcion_push
        sentencia = (
            insert(t)
            .values(
                endpoint=suscripcion.endpoint,
                p256dh=suscripcion.p256dh,
                auth=suscripcion.auth,
                creada_en=suscripcion.creada_en,
                usuario_id=suscripcion.usuario_id,
            )
            .on_conflict_do_update(
                index_elements=["endpoint"],
                set_={"p256dh": suscripcion.p256dh, "auth": suscripcion.auth},
            )
            .returning(t.c.id)
        )
        async with self._motor.begin() as conexion:
            # Si el navegador era de otro usuario, se borra la suscripción anterior y, en
            # cascada, sus envíos pendientes.
            await conexion.execute(
                delete(t).where(
                    t.c.endpoint == suscripcion.endpoint,
                    t.c.usuario_id != suscripcion.usuario_id,
                )
            )
            identificador = (await conexion.execute(sentencia)).scalar_one()
        return replace(suscripcion, id=identificador)

    async def obtener(self, suscripcion_id: int) -> SuscripcionPush | None:
        t = tablas.suscripcion_push
        async with self._motor.connect() as conexion:
            fila = (
                (await conexion.execute(select(t).where(t.c.id == suscripcion_id)))
                .mappings()
                .first()
            )
        return _a_suscripcion(fila) if fila else None

    async def listar(self) -> list[SuscripcionPush]:
        t = tablas.suscripcion_push
        async with self._motor.connect() as conexion:
            filas = (await conexion.execute(select(t).order_by(t.c.id))).mappings().all()
        return [_a_suscripcion(f) for f in filas]

    async def borrar(self, suscripcion_id: int) -> None:
        t = tablas.suscripcion_push
        async with self._motor.begin() as conexion:
            await conexion.execute(delete(t).where(t.c.id == suscripcion_id))

    async def borrar_por_endpoint(self, endpoint: str, usuario_id: int) -> bool:
        t = tablas.suscripcion_push
        async with self._motor.begin() as conexion:
            resultado = await conexion.execute(
                delete(t)
                .where(t.c.endpoint == endpoint, t.c.usuario_id == usuario_id)
                .returning(t.c.id)
            )
            return resultado.first() is not None


_CAMPOS_ENVIO = [f.name for f in fields(Envio) if f.name != "id"]


def _a_envio(fila) -> Envio:
    datos = {campo: fila[campo] for campo in _CAMPOS_ENVIO}
    datos["estado"] = EstadoEnvio(datos["estado"])
    return Envio(id=fila["id"], **datos)


class RepositorioEnviosPostgres:
    def __init__(self, motor: AsyncEngine) -> None:
        self._motor = motor

    async def crear(self, envios: list[Envio]) -> None:
        if not envios:
            return
        filas = [{campo: getattr(e, campo) for campo in _CAMPOS_ENVIO} for e in envios]
        async with self._motor.begin() as conexion:
            await conexion.execute(insert(tablas.envio_push), filas)

    async def pendientes(self, ahora: datetime, limite: int = 50) -> list[Envio]:
        t = tablas.envio_push
        sentencia = (
            select(t)
            .where(t.c.estado == EstadoEnvio.PENDIENTE.value, t.c.proximo_intento_en <= ahora)
            .order_by(t.c.proximo_intento_en, t.c.id)
            .limit(limite)
        )
        async with self._motor.connect() as conexion:
            filas = (await conexion.execute(sentencia)).mappings().all()
        return [_a_envio(f) for f in filas]

    async def guardar(self, envio: Envio) -> None:
        t = tablas.envio_push
        valores = {campo: getattr(envio, campo) for campo in _CAMPOS_ENVIO}
        async with self._motor.begin() as conexion:
            await conexion.execute(update(t).where(t.c.id == envio.id).values(**valores))


_CAMPOS_USUARIO = [f.name for f in fields(Usuario) if f.name != "id"]


def _a_usuario(fila) -> Usuario:
    datos = {campo: fila[campo] for campo in _CAMPOS_USUARIO}
    return Usuario(id=fila["id"], **(datos | {"rol": Rol(datos["rol"])}))


class RepositorioUsuariosPostgres:
    def __init__(self, motor: AsyncEngine) -> None:
        self._motor = motor

    async def _uno(self, condicion) -> Usuario | None:
        async with self._motor.connect() as conexion:
            fila = (
                (await conexion.execute(select(tablas.usuario).where(condicion))).mappings().first()
            )
        return _a_usuario(fila) if fila else None

    async def obtener(self, usuario_id: int) -> Usuario | None:
        return await self._uno(tablas.usuario.c.id == usuario_id)

    async def por_correo(self, correo: str) -> Usuario | None:
        return await self._uno(tablas.usuario.c.correo == correo)

    async def listar(self) -> list[Usuario]:
        t = tablas.usuario
        async with self._motor.connect() as conexion:
            filas = (await conexion.execute(select(t).order_by(t.c.id))).mappings().all()
        return [_a_usuario(f) for f in filas]

    async def guardar(self, usuario: Usuario) -> Usuario:
        t = tablas.usuario
        valores = {campo: getattr(usuario, campo) for campo in _CAMPOS_USUARIO}
        valores["rol"] = usuario.rol.value
        try:
            async with self._motor.begin() as conexion:
                if usuario.id is None:
                    sentencia = insert(t).values(**valores).returning(t.c.id)
                    return replace(usuario, id=(await conexion.execute(sentencia)).scalar_one())
                await conexion.execute(update(t).where(t.c.id == usuario.id).values(**valores))
        except IntegrityError as error:
            raise CorreoDuplicado(usuario.correo) from error
        return usuario


class RepositorioBitacoraPostgres:
    def __init__(self, motor: AsyncEngine) -> None:
        self._motor = motor

    async def agregar(self, registro: RegistroBitacora) -> RegistroBitacora:
        t = tablas.bitacora
        valores = {
            "usuario_id": registro.usuario_id,
            "accion": registro.accion.value,
            "objeto": registro.objeto.value,
            "objeto_id": registro.objeto_id,
            "detalle": registro.detalle,
            "ts": registro.ts,
        }
        async with self._motor.begin() as conexion:
            nuevo_id = (
                await conexion.execute(insert(t).values(**valores).returning(t.c.id))
            ).scalar_one()
        return replace(registro, id=nuevo_id)

    async def listar(
        self, limite: int = 100, antes_de: int | None = None
    ) -> list[RegistroBitacora]:
        t = tablas.bitacora
        sentencia = select(t).order_by(t.c.id.desc()).limit(limite)
        if antes_de is not None:
            sentencia = sentencia.where(t.c.id < antes_de)
        async with self._motor.connect() as conexion:
            filas = (await conexion.execute(sentencia)).mappings().all()
        return [
            RegistroBitacora(
                usuario_id=f["usuario_id"],
                accion=Accion(f["accion"]),
                objeto=Objeto(f["objeto"]),
                objeto_id=f["objeto_id"],
                detalle=f["detalle"],
                ts=f["ts"],
                id=f["id"],
            )
            for f in filas
        ]
