"""Configuración del servidor, leída de variables de entorno o de infra/.env."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_REPO = Path(__file__).resolve().parents[2]


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=RAIZ_REPO / "infra" / ".env", extra="ignore")

    almacenamiento: Literal["postgres", "memoria"] = "postgres"
    mqtt_habilitado: bool = True
    nivel_log: str = "INFO"

    db_host: str = "localhost"
    db_puerto: int = 5432
    db_nombre: str = "greensense"
    db_usuario: str = "greensense"
    db_contrasena: str = ""

    mqtt_host: str = "localhost"
    mqtt_puerto: int = 1883
    mqtt_usuario_servidor: str = "servidor"
    mqtt_contrasena_servidor: str = ""

    # Web Push. Generar con: greensense vapid
    vapid_privada: str = ""
    vapid_publica: str = ""
    vapid_contacto: str = "mailto:admin@greensense.local"

    # Sesiones. Generar el secreto con: python -c "import secrets; print(secrets.token_urlsafe(48))"
    # Si está vacío se genera uno al arrancar y las sesiones se pierden al reiniciar.
    jwt_secreto: str = ""
    sesion_horas: float = 12.0
    # Administrador que se crea al arrancar si todavía no hay usuarios.
    admin_correo: str = ""
    admin_contrasena: str = ""
    # Solo para las pruebas: Argon2 con parámetros mínimos.
    hash_rapido: bool = False

    # Tareas periódicas
    revision_nodos_s: float = 30.0
    envio_notificaciones_s: float = 15.0

    @property
    def push_habilitado(self) -> bool:
        return bool(self.vapid_privada and self.vapid_publica)

    @property
    def url_db(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_usuario}:{self.db_contrasena}"
            f"@{self.db_host}:{self.db_puerto}/{self.db_nombre}"
        )
