# Configurações da aplicação.

from typing import Literal
from urllib.parse import quote

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configuração comum a todas as classes Settings:
# - Lê do arquivo .env na raiz do projeto.
# - Variáveis de ambiente do SO têm prioridade sobre .env (padrão pydantic-settings).
# - Ignora variáveis extras no .env (não falha se houver lixo).
_COMMON_CONFIG = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore",
    case_sensitive=False,
)


class AppSettings(BaseSettings):
    """Configurações gerais da aplicação."""

    model_config = _COMMON_CONFIG

    app_name: str = Field(default="isp_manager", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    app_env: Literal["development", "staging", "production"] = Field(
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
    def is_production(self) -> bool:
        return self.app_env == "production"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def expose_internal_errors(self) -> bool:
        """Define se erros 500 devem expor stack trace. NUNCA em prod."""
        return self.app_env == "development"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins_list(self) -> list[str]:
        """CORS_ORIGINS é string separada por vírgula; expõe como lista."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


class DatabaseSettings(BaseSettings):
    """Configurações de banco de dados.

    Mantém DUAS URLs porque o sistema tem dois roles Postgres:
    - isp_app: runtime da aplicação (DML)
    - isp_migrator: apenas Alembic (DDL)

    Princípio de segurança: a app nunca usa o role com poder de DDL. Se for
    comprometida via SQL injection, o atacante não consegue alterar schema.
    """

    model_config = _COMMON_CONFIG

    # Conexão (compartilhada entre os dois roles).
    postgres_host: str = Field(default="postgres", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="isp_manager", alias="POSTGRES_DB")

    # Role da aplicação.
    isp_app_db_user: str = Field(default="isp_app", alias="ISP_APP_DB_USER")
    isp_app_db_password: SecretStr = Field(alias="ISP_APP_DB_PASSWORD")

    # Role do Alembic (usado fora do hot path da API; só em migrations).
    isp_migrator_db_user: str = Field(default="isp_migrator", alias="ISP_MIGRATOR_DB_USER")
    isp_migrator_db_password: SecretStr = Field(alias="ISP_MIGRATOR_DB_PASSWORD")

    # Pool de conexões da aplicação.
    pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    pool_recycle: int = Field(default=1800, alias="DB_POOL_RECYCLE")

    statement_timeout_ms: int = Field(default=30_000, alias="DB_STATEMENT_TIMEOUT_MS")

    # Em dev, eco de SQL no log ajuda. Em prod, NUNCA.
    echo_sql: bool = Field(default=False, alias="DB_ECHO_SQL")

    def build_app_url(self) -> str:
        # URL async para o role da aplicação (uso normal)

        password = quote(self.isp_app_db_password.get_secret_value(), safe="")
        return (
            f"postgresql+asyncpg://{self.isp_app_db_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def build_app_sync_url(self) -> str:
        # URL síncrona para o worker Celery
        password = quote(self.isp_app_db_password.get_secret_value(), safe="")
        return (
            f"postgresql+psycopg://{self.isp_app_db_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def build_migrator_url(self) -> str:
        # URL sync para Alembic (Alembic não é async).
        password = quote(self.isp_migrator_db_password.get_secret_value(), safe="")
        return (
            f"postgresql+psycopg://{self.isp_migrator_db_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


class RedisSettings(BaseSettings):
    """Configurações do Redis."""

    model_config = _COMMON_CONFIG

    redis_host: str = Field(default="redis", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: SecretStr | None = Field(default=None, alias="REDIS_PASSWORD")

    cache_db: int = Field(default=0, alias="REDIS_CACHE_DB")
    broker_db: int = Field(default=1, alias="REDIS_BROKER_DB")
    result_db: int = Field(default=2, alias="REDIS_RESULT_DB")

    def _build_url(self, db: int) -> str:
        # Monta redis://[:senha@]host:porta/db
        if self.redis_password is not None:
            auth = f":{quote(self.redis_password.get_secret_value(), safe='')}@"
        else:
            auth = ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{db}"

    def build_broker_url(self) -> str:
        # URL do Broker Celery (fila de tarefas)
        return self._build_url(self.broker_db)

    def build_result_backend_url(self) -> str:
        # URL do Backend de resultados Celery
        return self._build_url(self.result_db)


class SecuritySettings(BaseSettings):
    """Configurações de autenticação e criptografia."""

    model_config = _COMMON_CONFIG

    # Segredo do JWT. Mínimo 32 chars em produção.
    api_secret_key: SecretStr = Field(alias="API_SECRET_KEY")
    jwt_algorithm: Literal["HS256", "HS512", "RS256"] = Field(
        default="HS256", alias="JWT_ALGORITHM"
    )
    access_token_expire_minutes: int = Field(default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_minutes: int = Field(default=10_080, alias="REFRESH_TOKEN_EXPIRE_MINUTES")


class LoggingSettings(BaseSettings):
    """Configurações de logging."""

    model_config = _COMMON_CONFIG

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", alias="LOG_LEVEL"
    )
    log_format: Literal["json", "console"] = Field(default="json", alias="LOG_FORMAT")


class CollectionSettings(BaseSettings):
    """Configurações do domínio collection."""

    model_config = _COMMON_CONFIG

    # Adapter de OLT em uso.
    # ! Mock é default em dev e testes.
    olt_adapter: Literal["mock", "fiberhome", "zte"] = Field(
        default="mock",
        alias="COLLECTION_OLT_ADAPTER",
    )
    # Backend de secrets.
    secret_store: Literal["env"] = Field(
        default="env",
        alias="COLLECTION_SECRET_STORE",
    )


class OpticalSettings(BaseSettings):
    """Configurações do domínio optical."""

    model_config = _COMMON_CONFIG

    # TTL do cache in-process de thresholds resolvidos.
    threshold_cache_ttl_seconds: int = Field(
        default=10,
        alias="OPTICAL_THRESHOLD_CACHE_TTL_SECONDS",
    )

    # Retenção de optical_reading. Partições mais antigas que
    # este horizonte são dropadas pela task drop_old_optical_partitions.
    partition_retention_days: int = Field(
        default=90,
        alias="OPTICAL_PARTITION_RETENTION_DAYS",
    )

    # Idade além da qual um collection_job em 'running' e considerado
    # stale e marcado failed por detect_stale_jobs. Default conservador: 10 minutos.
    stale_job_threshold_minutes: int = Field(
        default=10,
        alias="COLLECTION_STALE_JOB_THRESHOLD_MINUTES",
    )


class ProvisioningSettings(BaseSettings):
    """Configurações do domínio provisioning."""

    model_config = _COMMON_CONFIG

    # TTL do cache in-process de normalized_command resolvidos.
    # Mesmo racional do threshold_cache: resolve por chave
    # (manufacturer, olt_model, command_key, version_constraint),
    # sem invalidação ativa.
    command_cache_ttl_seconds: int = Field(
        default=10,
        alias="PROVISIONING_COMMAND_CACHE_TTL_SECONDS",
    )


class Settings(BaseSettings):
    """
    Settings raiz. Agrega todos os domínios.

    Uso:
        from app.core.config import settings
        url = settings.database.build_app_url()
        debug = settings.app.expose_internal_errors
    """

    model_config = _COMMON_CONFIG

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)  # type: ignore
    redis: RedisSettings = Field(default_factory=RedisSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)  # type: ignore
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    collection: CollectionSettings = Field(default_factory=CollectionSettings)
    optical: OpticalSettings = Field(default_factory=OpticalSettings)
    provisioning: ProvisioningSettings = Field(default_factory=ProvisioningSettings)


# Instância única exposta no módulo. Instanciada no import: se faltar variável
# obrigatória no .env, a aplicação falha rápido no startup (fail-fast).
settings = Settings()
