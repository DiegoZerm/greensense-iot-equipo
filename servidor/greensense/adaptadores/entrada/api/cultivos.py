from fastapi import APIRouter, Response, status

from greensense.adaptadores.entrada.api.dependencias import ContenedorDep, VerPanel, con_permiso
from greensense.adaptadores.entrada.api.esquemas import CultivoDatos, CultivoNuevo, CultivoSalida
from greensense.dominio.usuarios import Permiso

router = APIRouter(prefix="/cultivos", tags=["cultivos"])

Configurador = con_permiso(Permiso.CONFIGURAR_CULTIVOS)


@router.get("")
async def listar(_: VerPanel, c: ContenedorDep) -> list[CultivoSalida]:
    """Todos los roles pueden ver los rangos: el panel y las gráficas los usan."""
    return [CultivoSalida.de(cultivo) for cultivo in await c.listar_cultivos.ejecutar()]


@router.post("", status_code=status.HTTP_201_CREATED)
async def crear(datos: CultivoNuevo, actor: Configurador, c: ContenedorDep) -> CultivoSalida:
    cultivo = await c.guardar_cultivo.ejecutar(actor, datos.a_dominio(datos.id), nuevo=True)
    return CultivoSalida.de(cultivo)


@router.put("/{cultivo_id}")
async def reemplazar(
    cultivo_id: str, datos: CultivoDatos, actor: Configurador, c: ContenedorDep
) -> CultivoSalida:
    """Reemplaza el nombre, los umbrales y el riesgo de hongos. Aplica desde la
    siguiente lectura de cada nodo."""
    cultivo = await c.guardar_cultivo.ejecutar(actor, datos.a_dominio(cultivo_id), nuevo=False)
    return CultivoSalida.de(cultivo)


@router.delete("/{cultivo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def borrar(cultivo_id: str, actor: Configurador, c: ContenedorDep) -> Response:
    await c.borrar_cultivo.ejecutar(actor, cultivo_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
