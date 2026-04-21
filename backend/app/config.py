"""
Application configuration.

Uses Pydantic settings to load values from `.env` or environment variables.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings."""

    # TCP server
    tcp_server_host: str = Field(default="0.0.0.0", description="TCP server bind host")
    tcp_server_port: int = Field(default=9001, description="TCP server port")

    # FastAPI
    api_host: str = Field(default="0.0.0.0", description="API server bind host")
    api_port: int = Field(default=8000, description="API server port")

    # MQTT
    mqtt_broker_host: str = Field(default="127.0.0.1", description="MQTT broker host")
    mqtt_broker_port: int = Field(default=1883, description="MQTT broker port")
    mqtt_username: str = Field(default="", description="MQTT username")
    mqtt_password: str = Field(default="", description="MQTT password")
    mqtt_client_id: str = Field(default="drone-monitor-backend", description="MQTT client id")
    mqtt_topic_prefix: str = Field(default="drone/telemetry", description="MQTT topic prefix")

    # Local persistence
    database_url: str = Field(
        default="sqlite+aiosqlite:///./drone_monitor.db",
        description="SQLite database URL",
    )
    raw_history_path: str = Field(
        default="./data/telemetry_raw.jsonl",
        description="Raw telemetry JSONL path",
    )
    flight_sessions_path: str = Field(
        default="./data/flights",
        description="Flight session JSON directory",
    )
    runtime_config_path: str = Field(
        default="./data/runtime_config.json",
        description="Runtime config JSON path",
    )

    # Logging
    log_level: str = Field(default="INFO", description="Log level")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


settings = Settings()
