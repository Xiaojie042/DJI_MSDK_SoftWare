"""
数据持久化服务
使用 SQLAlchemy + aiosqlite 异步写入 SQLite
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.config import settings
from app.models.drone import Base, FlightRecord, DroneState
from app.utils.logger import get_logger

logger = get_logger(__name__)


class StorageService:
    """
    异步数据库存储服务

    将无人机遥测数据持久化到 SQLite 数据库。
    """

    def __init__(self):
        self._engine = create_async_engine(
            settings.database_url,
            echo=False,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def init_db(self) -> None:
        """初始化数据库，创建表"""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表已创建")

    async def save_telemetry(self, state: DroneState) -> None:
        """
        保存遥测数据到数据库

        Args:
            state: 无人机状态数据
        """
        record = FlightRecord(
            drone_id=state.drone_id,
            timestamp=state.timestamp,
            latitude=state.position.latitude,
            longitude=state.position.longitude,
            altitude=state.position.altitude,
            heading=state.heading,
            horizontal_speed=state.velocity.horizontal,
            vertical_speed=state.velocity.vertical,
            battery_percent=state.battery.percent,
            battery_voltage=state.battery.voltage,
            battery_temperature=state.battery.temperature,
            gps_signal=state.gps_signal,
            flight_mode=state.flight_mode,
            is_flying=1 if state.is_flying else 0,
            home_distance=state.home_distance,
            gimbal_pitch=state.gimbal_pitch,
            rc_signal=state.rc_signal,
            raw_data=state.model_dump_json(),
        )

        async with self._session_factory() as session:
            session.add(record)
            await session.commit()
            logger.debug("遥测数据已入库", drone_id=state.drone_id)

    async def get_flight_history(
        self,
        drone_id: str = "DJI-001",
        limit: int = 1000,
    ) -> list[dict]:
        """
        查询飞行历史记录

        Args:
            drone_id: 无人机 ID
            limit: 返回记录数上限

        Returns:
            飞行记录字典列表
        """
        from sqlalchemy import select

        async with self._session_factory() as session:
            stmt = (
                select(FlightRecord)
                .where(FlightRecord.drone_id == drone_id)
                .order_by(FlightRecord.timestamp.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            records = result.scalars().all()

            return [
                {
                    "id": r.id,
                    "drone_id": r.drone_id,
                    "timestamp": r.timestamp,
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "altitude": r.altitude,
                    "heading": r.heading,
                    "horizontal_speed": r.horizontal_speed,
                    "vertical_speed": r.vertical_speed,
                    "battery_percent": r.battery_percent,
                    "flight_mode": r.flight_mode,
                    "is_flying": bool(r.is_flying),
                }
                for r in records
            ]

    async def close(self) -> None:
        """关闭数据库连接"""
        await self._engine.dispose()
        logger.info("数据库连接已关闭")
