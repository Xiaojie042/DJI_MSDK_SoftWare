"""
日志配置模块
使用 structlog 提供结构化日志
"""

import logging
import sys

import structlog

from app.config import settings


def setup_logging() -> None:
    """初始化日志系统"""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # 配置标准 logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # 配置 structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """获取命名 Logger"""
    return structlog.get_logger(name)
