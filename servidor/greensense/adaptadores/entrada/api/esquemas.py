"""Formato JSON de las respuestas de la API."""

from datetime import datetime, timedelta
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from greensense.aplicacion.casos_uso.bitacora import EntradaBitacora
from greensense.aplicacion.puertos import Evento
from greensense.dominio.cultivo import Cultivo, RiesgoHongos, Umbral
from greensense.dominio.modelos import SensorAire, Variable
from greensense.dominio.usuarios import Permiso, Rol, Usuario


class _Salida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LecturaSalida(_Salida):
    ts: datetime
    arranque: int
    seq: int
    temperatura: float | None
    humedad_aire: float | None
    humedad_sustrato: float | None
    muestras: int | None
    rssi: int | None


class NodoSalida(_Salida):
    id: str
    invernadero_id: str
    nombre: str
    sensor_aire: str
    sensor_suelo: bool
    estado: str
    firmware: str | None
    periodo_s: int
    ultima_lectura_en: datetime | None
    activo: bool


class AlertaSalida(_Salida):
    id: int
    nodo_id: str
    tipo: str
    variable: str | None
    severidad: str
    mensaje: str
    recomendacion: str
    valor: float | None
    limite: float | None
    iniciada_en: datetime
    actualizada_en: datetime
    fuera_desde: datetime | None
    escalada_en: datetime | None
    resuelta_en: datetime | None
    atendida_en: datetime | None
    atendida_por: int | None
    atendida_por_nombre: str | None
    activa: bool


class EstadoActualSalida(_Salida):
    nodo: NodoSalida
    ultima: LecturaSalida | None
    alertas: list[AlertaSalida]


# --- Usuarios -------------------------------------------------------------------------


class UsuarioSalida(_Salida):
    id: int
    nombre: str
    correo: str
    rol: Rol
    activo: bool
    creado_en: datetime


class SesionUsuario(UsuarioSalida):
    """El usuario de la sesión, con sus permisos para que la app sepa qué mostrar."""

    permisos: list[Permiso]

    @classmethod
    def de(cls, usuario: Usuario) -> "SesionUsuario":
        datos = UsuarioSalida.model_validate(usuario).model_dump()
        return cls(**datos, permisos=sorted(usuario.permisos))


Contrasena = Annotated[str, Field(min_length=8, max_length=128)]
Nombre = Annotated[str, Field(min_length=1, max_length=100)]


class UsuarioNuevo(BaseModel):
    nombre: Nombre
    correo: str = Field(max_length=254)
    rol: Rol
    contrasena: Contrasena


class UsuarioCambios(BaseModel):
    nombre: Nombre | None = None
    correo: str | None = Field(None, max_length=254)
    rol: Rol | None = None
    activo: bool | None = None
    contrasena: Contrasena | None = None


# --- Cultivos e invernaderos ----------------------------------------------------------

Segundos = Annotated[int, Field(ge=0, le=7 * 24 * 3600)]


class UmbralEsquema(BaseModel):
    variable: Variable
    minimo: float
    maximo: float
    margen: float = Field(ge=0)
    tiempo_bajo_s: Segundos = 300
    tiempo_alto_s: Segundos = 300

    @classmethod
    def de(cls, umbral: Umbral) -> "UmbralEsquema":
        return cls(
            variable=umbral.variable,
            minimo=umbral.minimo,
            maximo=umbral.maximo,
            margen=umbral.margen,
            tiempo_bajo_s=int(umbral.tiempo_bajo.total_seconds()),
            tiempo_alto_s=int(umbral.tiempo_alto.total_seconds()),
        )

    def a_dominio(self) -> Umbral:
        return Umbral(
            self.variable,
            self.minimo,
            self.maximo,
            self.margen,
            timedelta(seconds=self.tiempo_bajo_s),
            timedelta(seconds=self.tiempo_alto_s),
        )


class HongosEsquema(BaseModel):
    humedad_minima: float = Field(85.0, ge=0, le=100)
    temperatura_minima: float = 20.0
    tiempo_minimo_s: Segundos = 3600


class CultivoDatos(BaseModel):
    nombre: Nombre
    umbrales: list[UmbralEsquema] = Field(max_length=len(Variable))
    hongos: HongosEsquema = HongosEsquema()

    def a_dominio(self, cultivo_id: str) -> Cultivo:
        return Cultivo(
            id=cultivo_id,
            nombre=self.nombre,
            umbrales=tuple(u.a_dominio() for u in self.umbrales),
            hongos=RiesgoHongos(
                self.hongos.humedad_minima,
                self.hongos.temperatura_minima,
                timedelta(seconds=self.hongos.tiempo_minimo_s),
            ),
        )


class CultivoNuevo(CultivoDatos):
    id: str = Field(max_length=32)


class CultivoSalida(CultivoNuevo):
    @classmethod
    def de(cls, cultivo: Cultivo) -> "CultivoSalida":
        return cls(
            id=cultivo.id,
            nombre=cultivo.nombre,
            umbrales=[UmbralEsquema.de(u) for u in cultivo.umbrales],
            hongos=HongosEsquema(
                humedad_minima=cultivo.hongos.humedad_minima,
                temperatura_minima=cultivo.hongos.temperatura_minima,
                tiempo_minimo_s=int(cultivo.hongos.tiempo_minimo.total_seconds()),
            ),
        )


class InvernaderoSalida(_Salida):
    id: str
    nombre: str
    cultivo_id: str


class InvernaderoNuevo(BaseModel):
    id: str = Field(max_length=32)
    nombre: Nombre
    cultivo_id: str = "hortalizas-hoja"


class InvernaderoCambios(BaseModel):
    nombre: Nombre | None = None
    cultivo_id: str | None = None


class NodoNuevo(BaseModel):
    id: str = Field(max_length=32)
    invernadero_id: str
    nombre: Nombre
    sensor_aire: SensorAire = SensorAire.DHT11
    sensor_suelo: bool = False


class NodoCambios(BaseModel):
    nombre: Nombre | None = None
    sensor_aire: SensorAire | None = None
    sensor_suelo: bool | None = None
    activo: bool | None = None


class BitacoraSalida(BaseModel):
    id: int
    ts: datetime
    usuario_id: int | None
    usuario_nombre: str | None
    accion: str
    objeto: str
    objeto_id: str
    detalle: str

    @classmethod
    def de(cls, entrada: EntradaBitacora) -> "BitacoraSalida":
        r = entrada.registro
        return cls(
            id=r.id,
            ts=r.ts,
            usuario_id=r.usuario_id,
            usuario_nombre=entrada.usuario_nombre,
            accion=r.accion,
            objeto=r.objeto,
            objeto_id=r.objeto_id,
            detalle=r.detalle,
        )


def evento_a_json(evento: Evento) -> dict[str, Any]:
    """Convierte los objetos del dominio de un evento al mismo formato que la API."""
    datos: dict[str, Any] = {}
    if "nodo" in evento.datos:
        datos["nodo"] = NodoSalida.model_validate(evento.datos["nodo"]).model_dump(mode="json")
    if "lectura" in evento.datos:
        lectura = LecturaSalida.model_validate(evento.datos["lectura"])
        datos["lectura"] = lectura.model_dump(mode="json")
    if "alerta" in evento.datos:
        alerta = AlertaSalida.model_validate(evento.datos["alerta"])
        datos["alerta"] = alerta.model_dump(mode="json")
    return datos
