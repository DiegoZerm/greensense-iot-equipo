"""Cultivos con umbrales, alertas y notificaciones push

Revisión: 0002
Anterior: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

PREDETERMINADO = "hortalizas-hoja"


def _momento(nombre: str, **opciones) -> sa.Column:
    return sa.Column(nombre, sa.DateTime(timezone=True), **opciones)


def upgrade() -> None:
    cultivo = op.create_table(
        "cultivo",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("hongos_humedad_minima", sa.REAL, nullable=False),
        sa.Column("hongos_temperatura_minima", sa.REAL, nullable=False),
        sa.Column("hongos_tiempo_minimo_s", sa.Integer, nullable=False),
    )
    umbral = op.create_table(
        "umbral",
        sa.Column(
            "cultivo_id",
            sa.String(32),
            sa.ForeignKey("cultivo.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("variable", sa.String(32), primary_key=True),
        sa.Column("minimo", sa.REAL, nullable=False),
        sa.Column("maximo", sa.REAL, nullable=False),
        sa.Column("margen", sa.REAL, nullable=False),
        sa.Column("tiempo_bajo_s", sa.Integer, nullable=False),
        sa.Column("tiempo_alto_s", sa.Integer, nullable=False),
    )
    # Rangos iniciales de la propuesta para hortalizas de hoja.
    op.bulk_insert(
        cultivo,
        [
            {
                "id": PREDETERMINADO,
                "nombre": "Hortalizas de hoja",
                "hongos_humedad_minima": 85,
                "hongos_temperatura_minima": 20,
                "hongos_tiempo_minimo_s": 3600,
            }
        ],
    )
    op.bulk_insert(
        umbral,
        [
            {"cultivo_id": PREDETERMINADO, "variable": v, "minimo": mn, "maximo": mx,
             "margen": mg, "tiempo_bajo_s": tb, "tiempo_alto_s": ta}
            for v, mn, mx, mg, tb, ta in [
                ("temperatura", 18, 28, 2, 300, 300),
                ("humedad_aire", 60, 80, 5, 300, 300),
                ("humedad_sustrato", 45, 70, 5, 300, 3 * 3600),
            ]
        ],
    )  # fmt: skip

    op.add_column(
        "invernadero",
        sa.Column(
            "cultivo_id",
            sa.String(32),
            sa.ForeignKey("cultivo.id"),
            nullable=False,
            server_default=PREDETERMINADO,
        ),
    )

    op.create_table(
        "alerta",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("nodo_id", sa.String(32), sa.ForeignKey("nodo.id"), nullable=False),
        sa.Column("tipo", sa.String(16), nullable=False),
        sa.Column("variable", sa.String(32)),
        sa.Column("severidad", sa.String(16), nullable=False),
        sa.Column("mensaje", sa.Text, nullable=False),
        sa.Column("recomendacion", sa.Text, nullable=False),
        sa.Column("valor", sa.REAL),
        sa.Column("limite", sa.REAL),
        _momento("iniciada_en", nullable=False),
        _momento("actualizada_en", nullable=False),
        _momento("fuera_desde"),
        _momento("escalada_en"),
        _momento("resuelta_en"),
        _momento("atendida_en"),
    )
    # Solo puede haber una alerta activa por nodo, tipo y variable.
    op.create_index(
        "alerta_activa_unica",
        "alerta",
        ["nodo_id", "tipo", sa.text("coalesce(variable, '')")],
        unique=True,
        postgresql_where=sa.text("resuelta_en IS NULL"),
    )
    op.create_index("alerta_iniciada_en", "alerta", [sa.text("iniciada_en DESC")])

    op.create_table(
        "suscripcion_push",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("endpoint", sa.Text, nullable=False, unique=True),
        sa.Column("p256dh", sa.Text, nullable=False),
        sa.Column("auth", sa.Text, nullable=False),
        _momento("creada_en", nullable=False),
    )
    op.create_table(
        "envio_push",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "alerta_id",
            sa.BigInteger,
            sa.ForeignKey("alerta.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "suscripcion_id",
            sa.BigInteger,
            sa.ForeignKey("suscripcion_push.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("estado", sa.String(16), nullable=False),
        sa.Column("intentos", sa.Integer, nullable=False),
        _momento("proximo_intento_en", nullable=False),
        _momento("enviado_en"),
        sa.Column("ultimo_error", sa.Text),
    )
    op.create_index(
        "envio_push_pendiente",
        "envio_push",
        ["proximo_intento_en"],
        postgresql_where=sa.text("estado = 'pendiente'"),
    )


def downgrade() -> None:
    op.drop_table("envio_push")
    op.drop_table("suscripcion_push")
    op.drop_table("alerta")
    op.drop_column("invernadero", "cultivo_id")
    op.drop_table("umbral")
    op.drop_table("cultivo")
