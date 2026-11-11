from dataclasses import replace

from greensense.aplicacion.errores import AlertaNoEncontrada
from greensense.aplicacion.puertos import Evento, PublicadorEventos, Reloj, RepositorioAlertas
from greensense.dominio.alertas import Alerta, FiltroAlertas
from greensense.dominio.usuarios import Usuario


class ConsultarAlertas:
    def __init__(self, alertas: RepositorioAlertas) -> None:
        self._alertas = alertas

    async def ejecutar(
        self,
        solo_activas: bool = False,
        limite: int = 100,
        filtro: FiltroAlertas | None = None,
    ) -> list[Alerta]:
        return await self._alertas.listar(solo_activas=solo_activas, limite=limite, filtro=filtro)


class AtenderAlerta:
    """Marca que alguien ya vio la alerta. No la resuelve: eso depende de las lecturas."""

    def __init__(self, alertas: RepositorioAlertas, eventos: PublicadorEventos, reloj: Reloj):
        self._alertas = alertas
        self._eventos = eventos
        self._reloj = reloj

    async def ejecutar(self, alerta_id: int, usuario: Usuario | None = None) -> Alerta:
        alerta = await self._alertas.obtener(alerta_id)
        if alerta is None:
            raise AlertaNoEncontrada(alerta_id)
        if alerta.atendida_en is None:
            alerta = await self._alertas.guardar(
                replace(
                    alerta,
                    atendida_en=self._reloj.ahora(),
                    atendida_por=usuario.id if usuario else None,
                    atendida_por_nombre=usuario.nombre if usuario else None,
                )
            )
            self._eventos.publicar(Evento("alerta", {"alerta": alerta}))
        return alerta
