from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "Device Registry Service"
    debug: bool = False

    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/device_registry"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret_key: str = "your-secret-key-here"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # API
    api_v1_prefix: str = "/api/v1"

    # Security
    api_key_prefix: str = "dvc_"

    # Logging
    log_level: str = "INFO"

    # Health Check
    health_check_interval: int = 300  # seconds

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
