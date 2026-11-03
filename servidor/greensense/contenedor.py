"""Casos de uso ya armados, listos para que los usen los adaptadores de entrada."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from greensense.aplicacion.casos_uso.bitacora import ConsultarBitacora
from greensense.aplicacion.casos_uso.configurar_cultivos import (
    BorrarCultivo,
    GuardarCultivo,
    ListarCultivos,
)
from greensense.aplicacion.casos_uso.consultar_estado_actual import ConsultarEstadoActual
from greensense.aplicacion.casos_uso.consultar_historial import (
    ConsultarAgregados,
    ConsultarLecturas,
    ConsultarResumen,
    ExportarAlertas,
    ExportarLecturas,
)
from greensense.aplicacion.casos_uso.gestionar_alertas import AtenderAlerta, ConsultarAlertas
from greensense.aplicacion.casos_uso.gestionar_nodos import (
    BorrarInvernadero,
    ListarInvernaderos,
    ListarNodos,
    ModificarInvernadero,
    ModificarNodo,
    RegistrarInvernadero,
    RegistrarNodo,
)
from greensense.aplicacion.casos_uso.gestionar_usuarios import (
    CrearAdministradorInicial,
    CrearUsuario,
    ListarUsuarios,
    ModificarUsuario,
)
from greensense.aplicacion.casos_uso.notificaciones import (
    BorrarSuscripcion,
    EnviarNotificaciones,
    RegistrarSuscripcion,
)
from greensense.aplicacion.casos_uso.registrar_estado import RegistrarEstado
from greensense.aplicacion.casos_uso.registrar_lectura import RegistrarLectura
from greensense.aplicacion.casos_uso.revisar_nodos import RevisarNodos
from greensense.aplicacion.casos_uso.sesion import (
    CambiarContrasenaPropia,
    IniciarSesion,
    UsuarioDelToken,
)
from greensense.aplicacion.puertos import PublicadorEventos


@dataclass
class Contenedor:
    # Lecturas y alertas
    registrar_lectura: RegistrarLectura
    registrar_estado: RegistrarEstado
    consultar_estado_actual: ConsultarEstadoActual
    revisar_nodos: RevisarNodos
    consultar_alertas: ConsultarAlertas
    atender_alerta: AtenderAlerta
    # Notificaciones
    registrar_suscripcion: RegistrarSuscripcion
    borrar_suscripcion: BorrarSuscripcion
    enviar_notificaciones: EnviarNotificaciones
    # Sesión y usuarios
    iniciar_sesion: IniciarSesion
    usuario_del_token: UsuarioDelToken
    cambiar_contrasena_propia: CambiarContrasenaPropia
    listar_usuarios: ListarUsuarios
    crear_usuario: CrearUsuario
    modificar_usuario: ModificarUsuario
    crear_administrador_inicial: CrearAdministradorInicial
    # Configuración
    listar_cultivos: ListarCultivos
    guardar_cultivo: GuardarCultivo
    borrar_cultivo: BorrarCultivo
    listar_invernaderos: ListarInvernaderos
    registrar_invernadero: RegistrarInvernadero
    modificar_invernadero: ModificarInvernadero
    borrar_invernadero: BorrarInvernadero
    listar_nodos: ListarNodos
    registrar_nodo: RegistrarNodo
    modificar_nodo: ModificarNodo
    consultar_bitacora: ConsultarBitacora
    # Historial
    consultar_lecturas: ConsultarLecturas
    consultar_agregados: ConsultarAgregados
    consultar_resumen: ConsultarResumen
    exportar_lecturas: ExportarLecturas
    exportar_alertas: ExportarAlertas

    eventos: PublicadorEventos
    clave_publica_push: str = ""
    al_cerrar: list[Callable[[], Awaitable[None]]] = field(default_factory=list)

    async def cerrar(self) -> None:
        for cerrar in self.al_cerrar:
            await cerrar()
