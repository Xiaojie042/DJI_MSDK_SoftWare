"""
DJI 无人机实时监控系统 - 全局配置
使用 Pydantic Settings 管理环境变量
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """应用全局配置，从 .env 文件或环境变量加载"""

    # TCP Server
    tcp_server_host: str = Field(default="0.0.0.0", description="TCP 服务器绑定地址")
    tcp_server_port: int = Field(default=9001, description="TCP 服务器端口")

    # FastAPI
    api_host: str = Field(default="0.0.0.0", description="API 服务绑定地址")
    api_port: int = Field(default=8000, description="API 服务端口")

    # MQTT (本地 EMQX)
    mqtt_broker_host: str = Field(default="127.0.0.1", description="MQTT Broker 地址")
    mqtt_broker_port: int = Field(default=1883, description="MQTT Broker 端口")
    mqtt_username: str = Field(default="", description="MQTT 用户名")
    mqtt_password: str = Field(default="", description="MQTT 密码")
    mqtt_client_id: str = Field(default="drone-monitor-backend", description="MQTT 客户端 ID")
    mqtt_topic_prefix: str = Field(default="drone/telemetry", description="MQTT Topic 前缀")

    # 数据库
    database_url: str = Field(
        default="sqlite+aiosqlite:///./drone_monitor.db",
        description="SQLite 数据库连接 URL",
    )

    # 日志
    log_level: str = Field(default="INFO", description="日志等级")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# 全局单例
settings = Settings()
