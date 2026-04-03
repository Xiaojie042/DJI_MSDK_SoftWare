"""
无人机遥测数据模型
定义 DroneState 及相关数据结构
"""

from __future__ import annotations

import time
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase


# ─── Pydantic 模型 (运行时数据传输) ───────────────────────────


class GpsPosition(BaseModel):
    """GPS 位置"""
    latitude: float = Field(default=0.0, description="纬度")
    longitude: float = Field(default=0.0, description="经度")
    altitude: float = Field(default=0.0, description="海拔高度 (m)")


class Velocity(BaseModel):
    """速度信息"""
    horizontal: float = Field(default=0.0, description="水平速度 (m/s)")
    vertical: float = Field(default=0.0, description="垂直速度 (m/s)")


class BatteryInfo(BaseModel):
    """电池信息"""
    percent: int = Field(default=0, ge=0, le=100, description="电量百分比")
    voltage: float = Field(default=0.0, description="电压 (V)")
    temperature: float = Field(default=0.0, description="温度 (℃)")


class DroneState(BaseModel):
    """
    无人机完整状态
    由 TCP 解析器生成，分发给 MQTT / WebSocket / DB
    """
    drone_id: str = Field(default="DJI-001", description="无人机唯一标识")
    timestamp: float = Field(default_factory=time.time, description="Unix 时间戳")

    # 位置
    position: GpsPosition = Field(default_factory=GpsPosition)
    heading: float = Field(default=0.0, description="航向角 (°)")

    # 运动
    velocity: Velocity = Field(default_factory=Velocity)

    # 电池
    battery: BatteryInfo = Field(default_factory=BatteryInfo)

    # 飞行状态
    gps_signal: int = Field(default=0, ge=0, le=5, description="GPS 信号强度 (0-5)")
    flight_mode: str = Field(default="UNKNOWN", description="飞行模式")
    is_flying: bool = Field(default=False, description="是否在飞行中")
    home_distance: float = Field(default=0.0, description="距返航点距离 (m)")

    # 云台
    gimbal_pitch: float = Field(default=0.0, description="云台俯仰角 (°)")

    # 遥控器信号
    rc_signal: Optional[int] = Field(default=None, description="遥控器信号强度 (%)")


# ─── SQLAlchemy 模型 (数据库持久化) ─────────────────────────


class Base(DeclarativeBase):
    pass


class FlightRecord(Base):
    """飞行遥测记录表"""
    __tablename__ = "flight_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    drone_id = Column(String(50), nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)

    latitude = Column(Float, nullable=False, default=0.0)
    longitude = Column(Float, nullable=False, default=0.0)
    altitude = Column(Float, nullable=False, default=0.0)

    heading = Column(Float, default=0.0)
    horizontal_speed = Column(Float, default=0.0)
    vertical_speed = Column(Float, default=0.0)

    battery_percent = Column(Integer, default=0)
    battery_voltage = Column(Float, default=0.0)
    battery_temperature = Column(Float, default=0.0)

    gps_signal = Column(Integer, default=0)
    flight_mode = Column(String(30), default="UNKNOWN")
    is_flying = Column(Integer, default=0)  # SQLite 无 Boolean
    home_distance = Column(Float, default=0.0)
    gimbal_pitch = Column(Float, default=0.0)
    rc_signal = Column(Integer, nullable=True)

    raw_data = Column(Text, nullable=True, doc="原始 JSON (调试用)")
