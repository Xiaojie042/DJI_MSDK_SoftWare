"""TCP telemetry simulator for local development and testing."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import time

from app.config import settings
from app.services.telemetry_scenarios import build_m400_mission_scenario


async def simulate_random_telemetry(
    host: str,
    port: int,
    drone_id: str,
    interval: float,
) -> None:
    """Send a continuous random telemetry stream."""
    print(f"Connecting to TCP server {host}:{port} ...")

    try:
        _reader, writer = await asyncio.open_connection(host, port)
        print(f"Connected, random stream started for {drone_id} (interval={interval}s)")
    except ConnectionRefusedError:
        print(f"Connection failed: {host}:{port} is not accepting connections.")
        return

    base_lat = 31.2304
    base_lng = 121.4737
    altitude = 0.0
    battery = 100.0
    step = 0

    try:
        while True:
            step += 1
            t = step * 0.05
            radius = 0.002
            lat = base_lat + radius * math.sin(t)
            lng = base_lng + radius * math.cos(t)

            if step < 20:
                altitude = min(altitude + 5.0, 100.0)
            else:
                altitude = 100.0 + 20.0 * math.sin(t * 0.5)

            battery = max(0.0, 100.0 - step * 0.1 + random.uniform(-0.5, 0.5))
            heading = (math.degrees(t) + 90.0) % 360.0

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
                "batteryTemperature": round(30.0 + random.uniform(0.0, 10.0), 1),
                "gpsSignal": random.choice([4, 4, 5, 5, 5]),
                "flightMode": "GPS",
                "isFlying": step > 5,
                "homeDistance": round(radius * 111000 * abs(math.sin(t)), 1),
                "gimbalPitch": round(-30.0 + random.uniform(-5.0, 5.0), 1),
                "rcSignal": random.choice([90, 92, 95, 98, 100]),
            }

            writer.write(json.dumps(data).encode("utf-8") + b"\n")
            await writer.drain()

            print(
                f"[random #{step:03d}] "
                f"lat={data['latitude']:.6f} "
                f"lng={data['longitude']:.6f} "
                f"alt={data['altitude']:.1f}m "
                f"bat={data['batteryPercent']}% "
                f"spd={data['horizontalSpeed']:.1f}m/s"
            )
            await asyncio.sleep(interval)
    except KeyboardInterrupt:
        print("\nRandom simulator stopped.")
    except ConnectionResetError:
        print("Server closed the connection.")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def replay_m400_mission(
    host: str,
    port: int,
    interval: float,
    loop_count: int,
    dry_run: bool,
) -> None:
    """Replay the deterministic M400 mission scenario."""
    steps = build_m400_mission_scenario()

    if dry_run:
        for index, step in enumerate(steps, start=1):
            payload = step.payload
            print(
                f"[dry-run #{index:02d}] "
                f"{step.name} mode={payload['flight_mode']} "
                f"alt={payload['relative_altitude']:.1f}m "
                f"bat={payload['battery_status']['main_battery']['percentage']}%"
            )
        return

    print(f"Connecting to TCP server {host}:{port} ...")
    try:
        _reader, writer = await asyncio.open_connection(host, port)
        print(f"Connected, replaying M400 mission (interval={interval}s, loops={loop_count})")
    except ConnectionRefusedError:
        print(f"Connection failed: {host}:{port} is not accepting connections.")
        return

    try:
        for loop_index in range(loop_count):
            for step_index, step in enumerate(steps, start=1):
                writer.write(json.dumps(step.payload, ensure_ascii=False).encode("utf-8") + b"\n")
                await writer.drain()
                print(
                    f"[mission {loop_index + 1}/{loop_count} step {step_index:02d}] "
                    f"{step.name} mode={step.payload['flight_mode']} "
                    f"alt={step.payload['relative_altitude']:.1f}m "
                    f"bat={step.payload['battery_status']['main_battery']['percentage']}%"
                )
                await asyncio.sleep(interval)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telemetry simulator for the backend TCP server.")
    parser.add_argument("--host", default="127.0.0.1", help="TCP server host")
    parser.add_argument("--port", type=int, default=settings.tcp_server_port, help="TCP server port")
    parser.add_argument("--interval", type=float, default=1.0, help="Send interval in seconds")
    parser.add_argument("--drone-id", default="DJI-001", help="Drone ID for random mode")
    parser.add_argument(
        "--scenario",
        choices=["random", "m400_mission"],
        default="random",
        help="Scenario to run",
    )
    parser.add_argument("--loop-count", type=int, default=1, help="Replay count for scripted scenarios")
    parser.add_argument("--dry-run", action="store_true", help="Print scripted scenario without connecting")
    return parser.parse_args()


async def _main(args: argparse.Namespace) -> None:
    interval = max(0.0, args.interval)
    if args.scenario == "m400_mission":
        await replay_m400_mission(
            host=args.host,
            port=args.port,
            interval=interval,
            loop_count=max(1, args.loop_count),
            dry_run=bool(args.dry_run),
        )
        return

    if args.dry_run:
        print("Dry-run is only supported for scripted scenarios such as --scenario m400_mission.")
        return

    await simulate_random_telemetry(
        host=args.host,
        port=args.port,
        drone_id=args.drone_id,
        interval=interval,
    )


if __name__ == "__main__":
    asyncio.run(_main(_parse_args()))
