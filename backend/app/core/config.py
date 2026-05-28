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

    app_name: str = Field(default="isp_manager", alias="APP_NAME")
    app_env: str = Field(default="0.1.0", alias="APP_VERSION")
    app_debug: Literal["development", "staging", "production"] = Field(
        default="development", alias="APP_ENV"
    )
    tz: str = Field(default="America/Sao_Paulo", alias="TZ")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    enable_api_docs: bool = Field(default=True, alias="ENABLE_API_DOCS")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")
    max_request_size: int = Field(default=1_048_576, alias="MAX_REQUEST_SIZE")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def expose_internal_errors(self) -> bool:
        return self.app_env == "development"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins_list(self) -> list[str]:
        # CORS_ORIGINS é string separada por vírgula; expõe como lista.
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


class DatabaseSettings(BaseSettings):
    # isp_app: runtime do app (SELECT, UPDATE, INSERT, DELETE)
    # isp_migrator: Alembic (CREATE, ALTER, DROP)

    model_config = _COMMON_CONFIG

    #  Conexão
    postgres_host: str = Field(default="postgres", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="isp_manager", alias="POSTGRES_DB")

    # Role de runtime
    isp_app_db_user: str = Field(default="isp_app", alias="ISP_APP_DB_USER")
    isp_app_db_password: SecretStr = Field(alias="ISP_APP_DB_PASSWORD")

    # Role Alembic
    isp_migrator_db_user: str = Field(default="isp_migrator", alias="ISP_MIGRATOR_DB_USER")
    isp_migrator_db_password: SecretStr = Field(alias="ISP_MIGRATOR_DB_PASSWORD")

    # Pool de conexões
    pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    pool_recycle: int = Field(default=1800, alias="DB_POOL_RECYCLE")

    statement_timeout_ms: int = Field(default=30_000, alias="DB_STATEMENT_TIMEOUT_MS")

    # Util apenas para dev, nunca levar para prod
    echo_sql: bool = Field(default=False, alias="DB_ECHO_SQL")

    def build_app_url(self) -> str:
        # Async para uso normal
        password = self.isp_app_db_password.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.isp_app_db_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def build_migrator_url(self) -> str:
        # URL sync para o Alembic
        password = self.isp_migrator_db_password.get_secret_value()
        return (
            f"postgresql+psycopg://{self.isp_migrator_db_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


class RedisSettings(BaseSettings):
    # Configurações do Redis

    model_config = _COMMON_CONFIG

    redis_host: str = Field(default="redis", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: SecretStr | None = Field(default=None, alias="REDIS_PASSWORD")

    cache_db: int = Field(default=0, alias="REDIS_CACHE_DB")
    broker_db: int = Field(default=1, alias="REDIS_BROKER_DB")
    result_db: int = Field(default=2, alias="REDIS_RESULT_DB")


class SecuritySettings(BaseSettings):
    # Configurações de segurança e autenticação

    model_config = _COMMON_CONFIG

    # Segredo JWT
    api_secret_key: SecretStr = Field(alias="API_SECRET_KEY")
    jwt_algorithm: Literal["HS256", "HS512", "RS256"] = Field(
        default="HS256", alias="JWT_ALGORITHM"
    )
    access_token_expire_minutes: int = Field(default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_minutes: int = Field(default=10_080, alias="REFRESH_TOKEN_EXPIRE_MINUTES")


class LoggingSettings(BaseSettings):
    # Configurações de Logs

    model_config = _COMMON_CONFIG

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", alias="LOG_LEVEL"
    )
    log_format: Literal["json", "console"] = Field(default="json", alias="LOG_FORMAT")


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
    redis: RedisSettings = Field(default_factory=RedisSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


settings = Settings()
