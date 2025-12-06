from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Application
    app_name: str = "Data Ingestion Service"
    debug: bool = False

    # API
    api_v1_prefix: str = "/api/v1"

    # Authentication
    jwt_secret_key: str = "your-secret-key-here"
    jwt_algorithm: str = "HS256"
    service_token: str = "service-token"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_data: str = "iot-data"
    kafka_topic_alerts: str = "iot-alerts"
    kafka_topic_health: str = "iot-health"
    kafka_topic_errors: str = "iot-errors"

    # Redis
    redis_url: str = "redis://localhost:6379/1"

    # MQTT
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None

    # Device Registry Service
    device_registry_url: str = "http://device-registry:8001"

    # Processing
    max_batch_size: int = 1000
    processing_timeout: int = 30
    retry_attempts: int = 3

    # Rate Limiting
    rate_limit_per_device: int = 100  # messages per minute
    rate_limit_window: int = 60  # seconds

    # Data Validation
    max_data_points_per_message: int = 1000
    max_message_size: int = 1024 * 1024  # 1MB

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()