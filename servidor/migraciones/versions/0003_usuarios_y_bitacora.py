"""Usuarios, bitácora, nodos dados de baja y quién atendió cada alerta

Revisión: 0003
Anterior: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usuario",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("correo", sa.String(254), nullable=False, unique=True),
        sa.Column("rol", sa.String(16), nullable=False),
        sa.Column("hash_contrasena", sa.Text, nullable=False),
        sa.Column("activo", sa.Boolean, nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "rol IN ('operador', 'supervisor', 'tecnico', 'administrador')", name="usuario_rol"
        ),
    )
    op.create_table(
        "bitacora",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("usuario_id", sa.BigInteger, sa.ForeignKey("usuario.id")),
        sa.Column("accion", sa.String(16), nullable=False),
        sa.Column("objeto", sa.String(16), nullable=False),
        sa.Column("objeto_id", sa.String(64), nullable=False),
        sa.Column("detalle", sa.Text, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
    )

    op.add_column("nodo", sa.Column("activo", sa.Boolean, nullable=False, server_default=sa.true()))
    op.add_column("alerta", sa.Column("atendida_por", sa.BigInteger, sa.ForeignKey("usuario.id")))
    op.add_column("alerta", sa.Column("atendida_por_nombre", sa.String(100)))

    # Cada suscripción es ahora de un usuario. Las anteriores no tenían dueño: se borran
    # (con sus envíos, en cascada) y el navegador se vuelve a suscribir al iniciar sesión.
    op.execute("DELETE FROM suscripcion_push")
    op.add_column(
        "suscripcion_push",
        sa.Column(
            "usuario_id",
            sa.BigInteger,
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("suscripcion_push", "usuario_id")
    op.drop_column("alerta", "atendida_por_nombre")
    op.drop_column("alerta", "atendida_por")
    op.drop_column("nodo", "activo")
    op.drop_table("bitacora")
    op.drop_table("usuario")
