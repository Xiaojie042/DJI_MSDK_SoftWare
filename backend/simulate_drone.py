"""TCP telemetry simulator for local development and testing."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import time
from datetime import datetime
from typing import Optional

from app.config import settings
from app.services.telemetry_scenarios import (
    build_m400_fault_scenario,
    build_m400_mission_scenario,
    build_m400_mixed_stream_scenario,
    build_m400_weather_device_scenario,
)


async def simulate_random_telemetry(
    host: str,
    port: int,
    drone_id: str,
    interval: float,
    seed: Optional[int],
) -> None:
    """Send a continuous random telemetry stream."""
    print(f"Connecting to TCP server {host}:{port} ...")

    try:
        _reader, writer = await asyncio.open_connection(host, port)
        print(f"Connected, random stream started for {drone_id} (interval={interval}s)")
    except ConnectionRefusedError:
        print(f"Connection failed: {host}:{port} is not accepting connections.")
        return

    rng = random.Random(seed)
    base_lat = round(rng.uniform(27.0, 29.2), 7)
    base_lng = round(rng.uniform(110.0, 113.7), 7)
    altitude = 0.0
    battery = 100.0
    step = 0
    east_offset_m = 0.0
    north_offset_m = 0.0
    heading = rng.uniform(35.0, 145.0)
    cruise_speed = rng.uniform(9.2, 10.8)
    max_radius_m = rng.uniform(520.0, 860.0)
    previous_altitude = altitude

    try:
        while True:
            step += 1
            t = step * interval

            if step < 8:
                altitude = min(altitude + 3.5, 24.0)
                current_speed = max(1.5, cruise_speed * 0.35)
            elif step < 18:
                altitude = min(altitude + 2.4, 72.0)
                current_speed = cruise_speed * 0.75
            elif step % 90 > 68:
                altitude = max(16.0, altitude - 1.8)
                current_speed = max(4.0, cruise_speed * 0.65)
            else:
                altitude = max(22.0, min(118.0, 78.0 + 24.0 * math.sin(t * 0.09)))
                current_speed = max(6.0, cruise_speed + math.sin(t * 0.21) * 1.8 + rng.uniform(-0.6, 0.6))

            if math.hypot(east_offset_m, north_offset_m) >= max_radius_m:
                heading = (heading + 165.0 + rng.uniform(-20.0, 20.0)) % 360.0
            else:
                heading = (heading + math.sin(t * 0.08) * 6.0 + rng.uniform(-2.5, 2.5)) % 360.0

            east_offset_m += math.cos(math.radians(heading)) * current_speed * interval
            north_offset_m += math.sin(math.radians(heading)) * current_speed * interval

            lat = base_lat + north_offset_m / 111_320.0
            lng = base_lng + east_offset_m / (111_320.0 * math.cos(math.radians(base_lat)))

            battery = max(0.0, 100.0 - step * 0.12 + rng.uniform(-0.4, 0.3))
            vertical_speed = round((altitude - previous_altitude) / max(interval, 1e-3), 1)
            previous_altitude = altitude

            data = {
                "droneId": drone_id,
                "timestamp": time.time(),
                "latitude": round(lat, 8),
                "longitude": round(lng, 8),
                "altitude": round(altitude, 1),
                "horizontalSpeed": round(current_speed, 1),
                "verticalSpeed": vertical_speed,
                "heading": round(heading, 1),
                "batteryPercent": int(battery),
                "batteryVoltage": round(22.0 + battery * 0.03, 1),
                "batteryTemperature": round(30.0 + rng.uniform(0.0, 9.0), 1),
                "gpsSignal": rng.choice([4, 4, 5, 5, 5]),
                "flightMode": "GPS" if current_speed >= 5.0 else "HOVER",
                "isFlying": step > 5,
                "homeDistance": round(math.hypot(east_offset_m, north_offset_m), 1),
                "gimbalPitch": round(-30.0 + rng.uniform(-5.0, 5.0), 1),
                "rcSignal": rng.choice([88, 90, 92, 95, 98, 100]),
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


async def replay_scripted_scenario(
    host: str,
    port: int,
    scenario: str,
    duration_seconds: float,
    loop_count: int,
    loop_forever: bool,
    dry_run: bool,
    seed: Optional[int],
) -> None:
    """Replay a deterministic scripted telemetry scenario."""
    scenario_builders = {
        "m400_mission": build_m400_mission_scenario,
        "m400_faults": build_m400_fault_scenario,
        "m400_mixed": build_m400_mixed_stream_scenario,
        "m400_weather": build_m400_weather_device_scenario,
    }
    builder = scenario_builders[scenario]

    def build_steps():
        return builder(
            start_time=datetime.now().replace(microsecond=0),
            cycle_seconds=duration_seconds,
            seed=seed,
        )

    steps = build_steps()
    reference_steps = [step for step in steps if step.payload.get("type") != "psdk_data"] or steps
    average_interval = duration_seconds / max(1, len(reference_steps) - 1)

    if dry_run:
        for index, step in enumerate(steps, start=1):
            payload = step.payload
            payload_type = payload.get("type", "flight_data")
            summary = (
                f"mode={payload.get('flight_mode', payload_type)} "
                f"alt={payload.get('relative_altitude', '--')}m "
                f"bat={payload.get('battery_status', {}).get('main_battery', {}).get('percentage', '--')}%"
            )
            if payload_type == "psdk_data":
                summary = f"device={payload.get('payload_index', '--')} data={payload.get('data', '')[:48]}"
            print(f"[dry-run #{index:02d}] {step.name} type={payload_type} {summary}")
        return

    print(f"Connecting to TCP server {host}:{port} ...")
    try:
        _reader, writer = await asyncio.open_connection(host, port)
        print(
            f"Connected, replaying {scenario} "
            f"(cycle={duration_seconds}s, avg_interval={average_interval:.2f}s, "
            f"loops={'infinite' if loop_forever else loop_count})"
        )
    except ConnectionRefusedError:
        print(f"Connection failed: {host}:{port} is not accepting connections.")
        return

    try:
        loop_index = 0
        while loop_forever or loop_index < loop_count:
            steps = build_steps()
            loop_label = f"{loop_index + 1}/inf" if loop_forever else str(loop_index + 1)
            for step_index, step in enumerate(steps, start=1):
                payload = step.payload
                writer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n")
                await writer.drain()

                payload_type = payload.get("type", "flight_data")
                summary = (
                    f"mode={payload.get('flight_mode', payload_type)} "
                    f"alt={payload.get('relative_altitude', '--')}m "
                    f"bat={payload.get('battery_status', {}).get('main_battery', {}).get('percentage', '--')}%"
                )
                if payload_type == "psdk_data":
                    summary = f"device={payload.get('payload_index', '--')} data={payload.get('data', '')[:48]}"

                print(f"[scenario {loop_label} step {step_index:02d}] {step.name} type={payload_type} {summary}")
                if step_index < len(steps):
                    current_time = _parse_payload_timestamp(payload["timestamp"])
                    next_time = _parse_payload_timestamp(steps[step_index].payload["timestamp"])
                    await asyncio.sleep(max(0.0, (next_time - current_time).total_seconds()))
            loop_index += 1
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
    parser.add_argument("--interval", type=float, default=1.0, help="Send interval in seconds (random scenario only)")
    parser.add_argument("--duration-seconds", type=float, default=30.0, help="Scripted scenario cycle duration")
    parser.add_argument("--drone-id", default="DJI-001", help="Drone ID for random mode")
    parser.add_argument(
        "--scenario",
        choices=["random", "m400_mission", "m400_faults", "m400_mixed", "m400_weather"],
        default="random",
        help="Scenario to run",
    )
    parser.add_argument("--loop-count", type=int, default=1, help="Replay count for scripted scenarios")
    parser.add_argument("--loop-forever", action="store_true", help="Replay scripted scenario continuously")
    parser.add_argument("--dry-run", action="store_true", help="Print scripted scenario without connecting")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducible scenarios")
    return parser.parse_args()


def _parse_payload_timestamp(timestamp: str):
    return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")


async def _main(args: argparse.Namespace) -> None:
    interval = max(0.0, args.interval)
    if args.scenario != "random":
        await replay_scripted_scenario(
            host=args.host,
            port=args.port,
            scenario=args.scenario,
            duration_seconds=max(5.0, args.duration_seconds),
            loop_count=max(1, args.loop_count),
            loop_forever=bool(args.loop_forever),
            dry_run=bool(args.dry_run),
            seed=args.seed,
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
        seed=args.seed,
    )


if __name__ == "__main__":
    asyncio.run(_main(_parse_args()))
