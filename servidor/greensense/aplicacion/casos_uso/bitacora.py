"""Registro de acciones de los usuarios y su consulta."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from greensense.aplicacion.puertos import Reloj, RepositorioBitacora, RepositorioUsuarios
from greensense.dominio.bitacora import Accion, Objeto, RegistroBitacora
from greensense.dominio.usuarios import Usuario


class Anotador:
    """Lo usan los casos de uso de configuración para dejar constancia de cada cambio."""

    def __init__(self, bitacora: RepositorioBitacora, reloj: Reloj) -> None:
        self._bitacora = bitacora
        self._reloj = reloj

    async def anotar(
        self,
        actor: Usuario | None,
        accion: Accion,
        objeto: Objeto,
        objeto_id: object,
        detalle: str = "",
    ) -> RegistroBitacora:
        registro = RegistroBitacora(
            usuario_id=actor.id if actor else None,
            accion=accion,
            objeto=objeto,
            objeto_id=str(objeto_id),
            detalle=detalle,
            ts=self._reloj.ahora(),
        )
        return await self._bitacora.agregar(registro)


def describir_cambios(antes: Any, despues: Any, campos: Iterable[str]) -> str:
    """'nombre: A → B; rol: operador → supervisor', solo con los campos que cambiaron."""
    cambios = []
    for campo in campos:
        viejo, nuevo = getattr(antes, campo), getattr(despues, campo)
        if viejo != nuevo:
            cambios.append(f"{campo}: {_texto(viejo)} → {_texto(nuevo)}")
    return "; ".join(cambios)


def _texto(valor: Any) -> str:
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    return str(valor)


@dataclass(frozen=True)
class EntradaBitacora:
    registro: RegistroBitacora
    usuario_nombre: str | None
    """None si la acción la hizo el sistema o la línea de comandos."""


class ConsultarBitacora:
    def __init__(self, bitacora: RepositorioBitacora, usuarios: RepositorioUsuarios) -> None:
        self._bitacora = bitacora
        self._usuarios = usuarios

    async def ejecutar(
        self, limite: int = 100, antes_de: int | None = None
    ) -> list[EntradaBitacora]:
        registros = await self._bitacora.listar(limite=limite, antes_de=antes_de)
        nombres = {u.id: u.nombre for u in await self._usuarios.listar()}
        return [EntradaBitacora(r, nombres.get(r.usuario_id)) for r in registros]
