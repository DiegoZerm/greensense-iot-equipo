"""Cultivos y sus umbrales. Los cambios aplican desde la siguiente lectura de cada nodo."""

from datetime import timedelta

from greensense.aplicacion.casos_uso.bitacora import Anotador
from greensense.aplicacion.errores import Conflicto, NoEncontrado
from greensense.aplicacion.puertos import RepositorioCultivos, RepositorioInvernaderos
from greensense.dominio.bitacora import Accion, Objeto
from greensense.dominio.cultivo import CULTIVO_PREDETERMINADO, Cultivo, UmbralInvalido
from greensense.dominio.modelos import validar_id
from greensense.dominio.usuarios import Usuario


def validar_cultivo(cultivo: Cultivo) -> Cultivo:
    validar_id(cultivo.id)
    if not cultivo.nombre.strip() or len(cultivo.nombre) > 100:
        raise UmbralInvalido("el nombre debe tener entre 1 y 100 caracteres")
    variables = [u.variable for u in cultivo.umbrales]
    if len(variables) != len(set(variables)):
        raise UmbralInvalido("cada variable puede tener un solo umbral")
    hongos = cultivo.hongos
    if not 0 <= hongos.humedad_minima <= 100:
        raise UmbralInvalido("riesgo de hongos: la humedad debe estar entre 0 y 100 %")
    if hongos.tiempo_minimo < timedelta(0):
        raise UmbralInvalido("riesgo de hongos: el tiempo no puede ser negativo")
    return cultivo


def resumen(cultivo: Cultivo) -> str:
    rangos = ", ".join(f"{u.variable} {u.minimo:g} a {u.maximo:g}" for u in cultivo.umbrales)
    hongos = cultivo.hongos
    return (
        f"{cultivo.nombre}: {rangos}; hongos ≥{hongos.humedad_minima:g} % y "
        f"≥{hongos.temperatura_minima:g} °C por {hongos.tiempo_minimo.total_seconds() / 60:g} min"
    )


class ListarCultivos:
    def __init__(self, cultivos: RepositorioCultivos) -> None:
        self._cultivos = cultivos

    async def ejecutar(self) -> list[Cultivo]:
        return sorted(await self._cultivos.listar(), key=lambda c: c.nombre.lower())


class GuardarCultivo:
    """Crea un cultivo nuevo (`nuevo=True`) o reemplaza los datos de uno existente."""

    def __init__(self, cultivos: RepositorioCultivos, anotador: Anotador) -> None:
        self._cultivos = cultivos
        self._anotador = anotador

    async def ejecutar(self, actor: Usuario | None, cultivo: Cultivo, nuevo: bool) -> Cultivo:
        validar_cultivo(cultivo)
        existente = await self._cultivos.obtener(cultivo.id)
        if nuevo and existente is not None:
            raise Conflicto(f"ya existe el cultivo '{cultivo.id}'")
        if not nuevo and existente is None:
            raise NoEncontrado("el cultivo", cultivo.id)
        await self._cultivos.guardar(cultivo)
        accion = Accion.CREAR if nuevo else Accion.MODIFICAR
        await self._anotador.anotar(actor, accion, Objeto.CULTIVO, cultivo.id, resumen(cultivo))
        return cultivo


class BorrarCultivo:
    def __init__(
        self,
        cultivos: RepositorioCultivos,
        invernaderos: RepositorioInvernaderos,
        anotador: Anotador,
    ) -> None:
        self._cultivos = cultivos
        self._invernaderos = invernaderos
        self._anotador = anotador

    async def ejecutar(self, actor: Usuario | None, cultivo_id: str) -> None:
        cultivo = await self._cultivos.obtener(cultivo_id)
        if cultivo is None:
            raise NoEncontrado("el cultivo", cultivo_id)
        if cultivo_id == CULTIVO_PREDETERMINADO.id:
            raise Conflicto("el cultivo predeterminado no se puede borrar")
        en_uso = [i.id for i in await self._invernaderos.listar() if i.cultivo_id == cultivo_id]
        if en_uso:
            raise Conflicto(f"el cultivo está asignado a: {', '.join(sorted(en_uso))}")
        await self._cultivos.borrar(cultivo_id)
        await self._anotador.anotar(
            actor, Accion.BORRAR, Objeto.CULTIVO, cultivo_id, cultivo.nombre
        )
