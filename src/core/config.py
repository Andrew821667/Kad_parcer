"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Optional

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="kad-parser", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # API
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_workers: int = Field(default=4, alias="API_WORKERS")

    # Database
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="kad_parser", alias="POSTGRES_DB")
    postgres_user: str = Field(default="kad_user", alias="POSTGRES_USER")
    postgres_password: str = Field(default="kad_password", alias="POSTGRES_PASSWORD")
    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")
    database_url_sync: Optional[str] = Field(default=None, alias="DATABASE_URL_SYNC")

    @property
    def async_database_url(self) -> str:
        """Construct async database URL."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """Construct sync database URL for Alembic."""
        if self.database_url_sync:
            return self.database_url_sync
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")

    @property
    def redis_dsn(self) -> str:
        """Construct Redis DSN."""
        if self.redis_url:
            return self.redis_url
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Celery
    celery_broker_url: Optional[str] = Field(default=None, alias="CELERY_BROKER_URL")
    celery_result_backend: Optional[str] = Field(default=None, alias="CELERY_RESULT_BACKEND")
    celery_worker_concurrency: int = Field(default=4, alias="CELERY_WORKER_CONCURRENCY")

    @property
    def broker_url(self) -> str:
        """Get Celery broker URL."""
        return self.celery_broker_url or self.redis_dsn

    @property
    def result_backend(self) -> str:
        """Get Celery result backend URL."""
        return self.celery_result_backend or self.redis_dsn

    # MinIO / S3
    minio_endpoint: str = Field(default="localhost:9000", alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="minioadmin", alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="minioadmin", alias="MINIO_SECRET_KEY")
    minio_bucket: str = Field(default="kad-documents", alias="MINIO_BUCKET")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")

    # Scraper settings
    kad_base_url: str = Field(default="https://kad.arbitr.ru", alias="KAD_BASE_URL")
    scraper_rate_limit: float = Field(default=2.0, alias="SCRAPER_RATE_LIMIT")
    scraper_max_retries: int = Field(default=3, alias="SCRAPER_MAX_RETRIES")
    scraper_timeout: int = Field(default=30, alias="SCRAPER_TIMEOUT")
    scraper_user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        alias="SCRAPER_USER_AGENT",
    )

    # Proxy settings
    use_proxy: bool = Field(default=False, alias="USE_PROXY")
    proxy_list: Optional[str] = Field(default=None, alias="PROXY_LIST")
    proxy_rotation_interval: int = Field(default=300, alias="PROXY_ROTATION_INTERVAL")

    # Cache settings
    cache_ttl_case: int = Field(default=86400, alias="CACHE_TTL_CASE")
    cache_ttl_document: int = Field(default=3600, alias="CACHE_TTL_DOCUMENT")

    # Security
    secret_key: str = Field(default="your-secret-key-change-in-production", alias="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expiration: int = Field(default=3600, alias="JWT_EXPIRATION")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
