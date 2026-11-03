from alembic import context
from sqlalchemy import create_engine, pool

from greensense.adaptadores.salida.postgres.tablas import metadata
from greensense.config import Config

target_metadata = metadata


def _url() -> str:
    # Las pruebas pasan su propia URL; si no, se usa la configuración del servidor.
    return context.config.attributes.get("url") or Config().url_db


def correr_migraciones() -> None:
    if context.is_offline_mode():
        context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    motor = create_engine(_url(), poolclass=pool.NullPool)
    with motor.connect() as conexion:
        context.configure(connection=conexion, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


correr_migraciones()
