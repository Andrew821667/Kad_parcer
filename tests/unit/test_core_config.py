"""Tests for core configuration module."""

import os

import pytest

from src.core.config import Settings, get_settings


def test_settings_defaults() -> None:
    """Test that settings have correct default values."""
    # Clear environment variables for this test
    env_vars = [
        "POSTGRES_HOST",
        "POSTGRES_USER",
        "REDIS_HOST",
        "DATABASE_URL",
    ]
    old_values = {}
    for var in env_vars:
        old_values[var] = os.environ.pop(var, None)

    try:
        settings = Settings(_env_file=None)  # type: ignore

        assert settings.app_name == "kad-parser"
        assert settings.app_env == "development"
        assert settings.api_port == 8000
        assert settings.postgres_port == 5432
        assert settings.redis_port == 6379
    finally:
        # Restore environment
        for var, value in old_values.items():
            if value is not None:
                os.environ[var] = value


def test_async_database_url_format() -> None:
    """Test async database URL contains correct driver."""
    settings = Settings(_env_file=None)  # type: ignore
    assert "postgresql+asyncpg://" in settings.async_database_url


def test_sync_database_url_format() -> None:
    """Test sync database URL contains correct driver."""
    settings = Settings(_env_file=None)  # type: ignore
    assert "postgresql+psycopg2://" in settings.sync_database_url


def test_redis_dsn_format() -> None:
    """Test Redis DSN format."""
    settings = Settings(_env_file=None)  # type: ignore
    assert settings.redis_dsn.startswith("redis://")


def test_broker_url() -> None:
    """Test Celery broker URL defaults to Redis."""
    settings = Settings(_env_file=None)  # type: ignore
    assert settings.broker_url == settings.redis_dsn


def test_result_backend() -> None:
    """Test Celery result backend defaults to Redis."""
    settings = Settings(_env_file=None)  # type: ignore
    assert settings.result_backend == settings.redis_dsn


def test_get_settings_cached() -> None:
    """Test that get_settings returns cached instance."""
    settings1 = get_settings()
    settings2 = get_settings()

    assert settings1 is settings2
