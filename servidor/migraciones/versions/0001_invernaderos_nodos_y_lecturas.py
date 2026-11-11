"""Invernaderos, nodos y lecturas

Revisión: 0001
Anterior:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _momento(nombre: str, **opciones) -> sa.Column:
    return sa.Column(nombre, sa.DateTime(timezone=True), **opciones)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.create_table(
        "invernadero",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("nombre", sa.String(100), nullable=False),
        _momento("creado_en", nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "nodo",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("invernadero_id", sa.String(32), sa.ForeignKey("invernadero.id"), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("sensor_aire", sa.String(16), nullable=False),
        sa.Column("sensor_suelo", sa.Boolean, nullable=False),
        sa.Column("estado", sa.String(16), nullable=False),
        sa.Column("firmware", sa.String(16)),
        sa.Column("periodo_s", sa.Integer, nullable=False),
        _momento("ultima_lectura_en"),
        _momento("creado_en", nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "lectura",
        sa.Column("nodo_id", sa.String(32), sa.ForeignKey("nodo.id"), nullable=False),
        sa.Column("arranque", sa.Integer, nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        _momento("ts", nullable=False),
        sa.Column("temperatura", sa.REAL),
        sa.Column("humedad_aire", sa.REAL),
        sa.Column("humedad_sustrato", sa.REAL),
        sa.Column("muestras", sa.SmallInteger),
        sa.Column("rssi", sa.SmallInteger),
        _momento("recibida_en", nullable=False, server_default=sa.func.now()),
    )
    op.execute("SELECT create_hypertable('lectura', by_range('ts', INTERVAL '7 days'))")
    op.create_index(
        "lectura_identidad", "lectura", ["nodo_id", "arranque", "seq", "ts"], unique=True
    )
    op.create_index("lectura_nodo_ts", "lectura", ["nodo_id", "ts"])


def downgrade() -> None:
    op.drop_table("lectura")
    op.drop_table("nodo")
    op.drop_table("invernadero")
