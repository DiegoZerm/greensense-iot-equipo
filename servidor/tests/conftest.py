import pytest
from fastapi.testclient import TestClient

from greensense.adaptadores.salida.memoria import (
    RepositorioAlertasMemoria,
    RepositorioBitacoraMemoria,
    RepositorioCultivosMemoria,
    RepositorioEnviosMemoria,
    RepositorioInvernaderosMemoria,
    RepositorioLecturasMemoria,
    RepositorioNodosMemoria,
    RepositorioSuscripcionesMemoria,
    RepositorioUsuariosMemoria,
)
from greensense.adaptadores.salida.seguridad import HasherArgon2
from greensense.aplicacion.casos_uso.bitacora import Anotador
from greensense.composicion import crear_aplicacion
from greensense.config import Config
from greensense.dominio.cultivo import CULTIVO_PREDETERMINADO
from tests.fabricas import DespertadorFalso, EventosEnLista, PushFalso, RelojFijo, crear_usuario


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def config() -> Config:
    return Config(_env_file=None, almacenamiento="memoria", mqtt_habilitado=False, hash_rapido=True)


@pytest.fixture
def cliente(config: Config) -> TestClient:
    return TestClient(crear_aplicacion(config))


@pytest.fixture
def reloj() -> RelojFijo:
    return RelojFijo()


@pytest.fixture
def eventos() -> EventosEnLista:
    return EventosEnLista()


@pytest.fixture
def lecturas() -> RepositorioLecturasMemoria:
    return RepositorioLecturasMemoria()


@pytest.fixture
def nodos() -> RepositorioNodosMemoria:
    return RepositorioNodosMemoria()


@pytest.fixture
def invernaderos() -> RepositorioInvernaderosMemoria:
    return RepositorioInvernaderosMemoria()


@pytest.fixture
def alertas() -> RepositorioAlertasMemoria:
    return RepositorioAlertasMemoria()


@pytest.fixture
def cultivos() -> RepositorioCultivosMemoria:
    return RepositorioCultivosMemoria(CULTIVO_PREDETERMINADO)


@pytest.fixture
def suscripciones() -> RepositorioSuscripcionesMemoria:
    return RepositorioSuscripcionesMemoria()


@pytest.fixture
def envios(suscripciones) -> RepositorioEnviosMemoria:
    return RepositorioEnviosMemoria(suscripciones)


@pytest.fixture
def despertador() -> DespertadorFalso:
    return DespertadorFalso()


@pytest.fixture
def push() -> PushFalso:
    return PushFalso()


@pytest.fixture
async def usuarios() -> RepositorioUsuariosMemoria:
    """Empieza con un administrador (id 1), que recibe todas las notificaciones."""
    repositorio = RepositorioUsuariosMemoria()
    await repositorio.guardar(crear_usuario())
    return repositorio


@pytest.fixture
def bitacora() -> RepositorioBitacoraMemoria:
    return RepositorioBitacoraMemoria()


@pytest.fixture
def anotador(bitacora, reloj) -> Anotador:
    return Anotador(bitacora, reloj)


@pytest.fixture(scope="session")
def hasher() -> HasherArgon2:
    return HasherArgon2(rapido=True)
