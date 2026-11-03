"""Tablas de PostgreSQL. Los cambios de esquema se hacen con migraciones de Alembic."""

from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    SmallInteger,
    String,
    Table,
    Text,
    func,
    true,
)

metadata = MetaData()

usuario = Table(
    "usuario",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("nombre", String(100), nullable=False),
    Column("correo", String(254), nullable=False, unique=True),
    Column("rol", String(16), nullable=False),
    Column("hash_contrasena", Text, nullable=False),
    Column("activo", Boolean, nullable=False),
    Column("creado_en", DateTime(timezone=True), nullable=False),
)

bitacora = Table(
    "bitacora",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("usuario_id", BigInteger, ForeignKey("usuario.id")),
    Column("accion", String(16), nullable=False),
    Column("objeto", String(16), nullable=False),
    Column("objeto_id", String(64), nullable=False),
    Column("detalle", Text, nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False),
)

invernadero = Table(
    "invernadero",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("nombre", String(100), nullable=False),
    Column("cultivo_id", String(32), ForeignKey("cultivo.id"), nullable=False),
    Column("creado_en", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

nodo = Table(
    "nodo",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("invernadero_id", String(32), ForeignKey("invernadero.id"), nullable=False),
    Column("nombre", String(100), nullable=False),
    Column("sensor_aire", String(16), nullable=False),
    Column("sensor_suelo", Boolean, nullable=False),
    Column("estado", String(16), nullable=False),
    Column("firmware", String(16)),
    Column("periodo_s", Integer, nullable=False),
    Column("ultima_lectura_en", DateTime(timezone=True)),
    Column("activo", Boolean, nullable=False, server_default=true()),
    Column("creado_en", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

# Hypertable de TimescaleDB particionada por ts. El índice único incluye ts porque
# TimescaleDB lo exige; un reenvío del nodo trae el mismo ts, así que sirve para
# descartar duplicados.
lectura = Table(
    "lectura",
    metadata,
    Column("nodo_id", String(32), ForeignKey("nodo.id"), nullable=False),
    Column("arranque", Integer, nullable=False),
    Column("seq", Integer, nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("temperatura", REAL),
    Column("humedad_aire", REAL),
    Column("humedad_sustrato", REAL),
    Column("muestras", SmallInteger),
    Column("rssi", SmallInteger),
    Column("recibida_en", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Index("lectura_identidad", "nodo_id", "arranque", "seq", "ts", unique=True),
    Index("lectura_nodo_ts", "nodo_id", "ts"),
)

cultivo = Table(
    "cultivo",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("nombre", String(100), nullable=False),
    Column("hongos_humedad_minima", REAL, nullable=False),
    Column("hongos_temperatura_minima", REAL, nullable=False),
    Column("hongos_tiempo_minimo_s", Integer, nullable=False),
)

umbral = Table(
    "umbral",
    metadata,
    Column(
        "cultivo_id", String(32), ForeignKey("cultivo.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("variable", String(32), primary_key=True),
    Column("minimo", REAL, nullable=False),
    Column("maximo", REAL, nullable=False),
    Column("margen", REAL, nullable=False),
    Column("tiempo_bajo_s", Integer, nullable=False),
    Column("tiempo_alto_s", Integer, nullable=False),
)

alerta = Table(
    "alerta",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("nodo_id", String(32), ForeignKey("nodo.id"), nullable=False),
    Column("tipo", String(16), nullable=False),
    Column("variable", String(32)),
    Column("severidad", String(16), nullable=False),
    Column("mensaje", Text, nullable=False),
    Column("recomendacion", Text, nullable=False),
    Column("valor", REAL),
    Column("limite", REAL),
    Column("iniciada_en", DateTime(timezone=True), nullable=False),
    Column("actualizada_en", DateTime(timezone=True), nullable=False),
    Column("fuera_desde", DateTime(timezone=True)),
    Column("escalada_en", DateTime(timezone=True)),
    Column("resuelta_en", DateTime(timezone=True)),
    Column("atendida_en", DateTime(timezone=True)),
    Column("atendida_por", BigInteger, ForeignKey("usuario.id")),
    Column("atendida_por_nombre", String(100)),
)

suscripcion_push = Table(
    "suscripcion_push",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("endpoint", Text, nullable=False, unique=True),
    Column("p256dh", Text, nullable=False),
    Column("auth", Text, nullable=False),
    Column("creada_en", DateTime(timezone=True), nullable=False),
    Column("usuario_id", BigInteger, ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False),
)

envio_push = Table(
    "envio_push",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("alerta_id", BigInteger, ForeignKey("alerta.id", ondelete="CASCADE"), nullable=False),
    Column(
        "suscripcion_id",
        BigInteger,
        ForeignKey("suscripcion_push.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("estado", String(16), nullable=False),
    Column("intentos", Integer, nullable=False),
    Column("proximo_intento_en", DateTime(timezone=True), nullable=False),
    Column("enviado_en", DateTime(timezone=True)),
    Column("ultimo_error", Text),
)
