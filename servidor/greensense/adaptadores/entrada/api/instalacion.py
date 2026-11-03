"""Invernaderos y nodos."""

from fastapi import APIRouter, Response, status

from greensense.adaptadores.entrada.api.dependencias import ContenedorDep, VerPanel, con_permiso
from greensense.adaptadores.entrada.api.esquemas import (
    InvernaderoCambios,
    InvernaderoNuevo,
    InvernaderoSalida,
    NodoCambios,
    NodoNuevo,
    NodoSalida,
)
from greensense.aplicacion.casos_uso.gestionar_nodos import CambiosNodo
from greensense.dominio.usuarios import Permiso

router = APIRouter(tags=["invernaderos y nodos"])

Configurador = con_permiso(Permiso.CONFIGURAR_CULTIVOS)
Tecnico = con_permiso(Permiso.GESTIONAR_NODOS)


@router.get("/invernaderos")
async def listar_invernaderos(_: VerPanel, c: ContenedorDep) -> list[InvernaderoSalida]:
    return [InvernaderoSalida.model_validate(i) for i in await c.listar_invernaderos.ejecutar()]


@router.post("/invernaderos", status_code=status.HTTP_201_CREATED)
async def crear_invernadero(
    datos: InvernaderoNuevo, actor: Configurador, c: ContenedorDep
) -> InvernaderoSalida:
    invernadero = await c.registrar_invernadero.ejecutar(
        datos.id, datos.nombre, datos.cultivo_id, actor=actor, nuevo=True
    )
    return InvernaderoSalida.model_validate(invernadero)


@router.patch("/invernaderos/{invernadero_id}")
async def modificar_invernadero(
    invernadero_id: str, datos: InvernaderoCambios, actor: Configurador, c: ContenedorDep
) -> InvernaderoSalida:
    invernadero = await c.modificar_invernadero.ejecutar(
        actor, invernadero_id, datos.nombre, datos.cultivo_id
    )
    return InvernaderoSalida.model_validate(invernadero)


@router.delete("/invernaderos/{invernadero_id}", status_code=status.HTTP_204_NO_CONTENT)
async def borrar_invernadero(invernadero_id: str, actor: Configurador, c: ContenedorDep):
    await c.borrar_invernadero.ejecutar(actor, invernadero_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/nodos")
async def listar_nodos(_: VerPanel, c: ContenedorDep) -> list[NodoSalida]:
    """Todos los nodos, incluidos los dados de baja (`activo: false`)."""
    return [NodoSalida.model_validate(n) for n in await c.listar_nodos.ejecutar()]


@router.post("/nodos", status_code=status.HTTP_201_CREATED)
async def crear_nodo(datos: NodoNuevo, actor: Tecnico, c: ContenedorDep) -> NodoSalida:
    """Registra el nodo en el servidor. Su usuario MQTT se crea aparte (infra/.env)."""
    nodo = await c.registrar_nodo.ejecutar(
        datos.invernadero_id,
        datos.id,
        datos.nombre,
        datos.sensor_aire,
        datos.sensor_suelo,
        actor=actor,
        nuevo=True,
    )
    return NodoSalida.model_validate(nodo)


@router.patch("/nodos/{nodo_id}")
async def modificar_nodo(
    nodo_id: str, datos: NodoCambios, actor: Tecnico, c: ContenedorDep
) -> NodoSalida:
    """Con `activo: false` el nodo se da de baja: conserva su historial, deja de aparecer
    en el panel y el servidor ignora sus lecturas."""
    cambios = CambiosNodo(**datos.model_dump(exclude_unset=True))
    return NodoSalida.model_validate(await c.modificar_nodo.ejecutar(actor, nodo_id, cambios))
