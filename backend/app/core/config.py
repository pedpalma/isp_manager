from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

_COMMON_CONFIG = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore",
    case_sensitive=False,
)


class AppSettings(BaseSettings):
    # Configurações gerais do app

    model_config = _COMMON_CONFIG

    app_name: str = "ISP Manager"
    app_env: Literal["dev", "staging", "prod"] = "dev"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Define se o erro 500 vai expor stack trace na resposta (NUNCA em prod)
    @computed_field
    @property
    def expose_internal_errors(self) -> bool:
        return self.app_env == "dev" and self.app_debug


class DatabaseSettings(BaseSettings):
    # isp_app: runtime do app (SELECT, UPDATE, INSERT, DELETE)
    # isp_migrator: Alembic (CREATE, ALTER, DROP)

    model_config = _COMMON_CONFIG

    #  Conexão
    db_host: str = "postgres"
    db_port: int = 5432
    db_name: str = "isp_manager"

    # Role de runtime
    isp_app_db_user: str = "isp_app"
    isp_app_db_password: SecretStr

    # Role Alembic
    isp_migrator_db_user: str = "isp_migrator"
    isp_migrator_db_user: SecretStr

    # Pool de conexões
    db_pool_size: int = 10
    db_max_overflow: int = 10
    db_pool_timeout_seconds: int = 30

    # Util apenas para dev, nunca levar para prod
    db_echo_sql: bool = False

    def build_app_url(self) -> str:
        # Async para uso normal
        password = self.isp_app_db_password.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.isp_app_db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


class SecuritySettings(BaseSettings):
    # Configurações de segurança e autenticação

    model_config = _COMMON_CONFIG

    # Segredo JWT
    jwt_secret: SecretStr
    jwt_algorithm: Literal["HS256", "HS512", "RS256"] = "HS256"
    jwt_access_token_ttl_minutes: int = 30
    jwt_access_token_ttl_days: int = 7


class LogginSettings(BaseSettings):
    # Configurações de Logs

    model_config = _COMMON_CONFIG

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"


class Settings(BaseSettings):
    """
    Cada módulo importa só o que precisa via:
    from app.core.config import get_settings
    settings = get_settings()
    db_url = settings.database.build_app_url()
    """

    model_config = _COMMON_CONFIG

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    logging: LogginSettings = Field(default_factory=LogginSettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Retorna uma instancia única e com cache de Settings
    return Settings()
