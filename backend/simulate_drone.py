"""
TCP 模拟器
模拟 DJI MSDK Android 端发送遥测数据到 TCP Server
用于开发和测试环境
"""

import asyncio
import json
import math
import random
import time


async def simulate_drone(
    host: str = "127.0.0.1",
    port: int = 8888,
    drone_id: str = "DJI-001",
    interval: float = 1.0,
):
    """
    模拟无人机遥测数据发送

    在一个圆形轨迹上飞行，逐步变化各项参数。

    Args:
        host: TCP Server 地址
        port: TCP Server 端口
        drone_id: 无人机 ID
        interval: 发送间隔 (秒)
    """
    print(f"正在连接 TCP Server {host}:{port} ...")

    try:
        reader, writer = await asyncio.open_connection(host, port)
        print(f"✓ 已连接! 开始发送 {drone_id} 模拟数据 (间隔 {interval}s)")
    except ConnectionRefusedError:
        print(f"✗ 连接失败: {host}:{port} 未响应，请确认 TCP Server 已启动")
        return

    # 起飞点 (上海)
    base_lat = 31.2304
    base_lng = 121.4737
    altitude = 0.0
    battery = 100
    heading = 0.0
    step = 0

    try:
        while True:
            step += 1
            t = step * 0.05  # 参数化时间

            # 模拟圆形飞行轨迹
            radius = 0.002  # 约 200m 半径
            lat = base_lat + radius * math.sin(t)
            lng = base_lng + radius * math.cos(t)

            # 高度渐变
            if step < 20:
                altitude = min(altitude + 5.0, 100.0)  # 起飞
            else:
                altitude = 100.0 + 20.0 * math.sin(t * 0.5)  # 波动

            # 电量缓慢下降
            battery = max(0, 100 - step * 0.1 + random.uniform(-0.5, 0.5))

            # 航向跟随飞行方向
            heading = (math.degrees(t) + 90) % 360

            data = {
                "droneId": drone_id,
                "timestamp": time.time(),
                "latitude": round(lat, 8),
                "longitude": round(lng, 8),
                "altitude": round(altitude, 1),
                "horizontalSpeed": round(random.uniform(3.0, 12.0), 1),
                "verticalSpeed": round(random.uniform(-1.0, 1.0), 1),
                "heading": round(heading, 1),
                "batteryPercent": int(battery),
                "batteryVoltage": round(22.0 + battery * 0.03, 1),
                "batteryTemperature": round(30.0 + random.uniform(0, 10), 1),
                "gpsSignal": random.choice([4, 4, 5, 5, 5]),
                "flightMode": "GPS",
                "isFlying": step > 5,
                "homeDistance": round(radius * 111000 * abs(math.sin(t)), 1),
                "gimbalPitch": round(-30.0 + random.uniform(-5, 5), 1),
                "rcSignal": random.choice([90, 92, 95, 98, 100]),
            }

            line = json.dumps(data).encode("utf-8") + b"\n"
            writer.write(line)
            await writer.drain()

            print(
                f"[{step:4d}] "
                f"lat={data['latitude']:.6f} "
                f"lng={data['longitude']:.6f} "
                f"alt={data['altitude']}m "
                f"bat={data['batteryPercent']}% "
                f"spd={data['horizontalSpeed']}m/s"
            )

            await asyncio.sleep(interval)

    except KeyboardInterrupt:
        print("\n模拟器已停止")
    except ConnectionResetError:
        print("服务器断开连接")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(simulate_drone())
