"""
Replay JSON telemetry samples to TCP server for local integration testing.

Example:
    python replay_sample.py --count 20 --interval 0.5
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.config import settings


def _default_sample_path() -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "示例data.txt"


def _load_samples(file_path: Path) -> list[dict[str, Any]]:
    text = file_path.read_text(encoding="utf-8")
    rows = [line.strip() for line in text.splitlines() if line.strip()]

    samples: list[dict[str, Any]] = []
    for row in rows:
        data = json.loads(row)
        if isinstance(data, dict):
            samples.append(data)
    return samples


async def replay(
    host: str,
    port: int,
    samples: list[dict[str, Any]],
    count: int,
    interval: float,
) -> None:
    if not samples:
        raise RuntimeError("No valid JSON samples found.")

    reader, writer = await asyncio.open_connection(host, port)
    print(f"Connected to {host}:{port}, replay count={count}, interval={interval}s")

    try:
        for idx in range(count):
            payload = samples[idx % len(samples)]
            line = json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"
            writer.write(line)
            await writer.drain()
            print(f"sent #{idx + 1}")
            await asyncio.sleep(interval)
    finally:
        writer.close()
        await writer.wait_closed()
        print("Replay finished.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay JSON telemetry sample to TCP server.")
    parser.add_argument("--host", default="127.0.0.1", help="TCP server host")
    parser.add_argument("--port", type=int, default=settings.tcp_server_port, help="TCP server port")
    parser.add_argument(
        "--sample",
        type=Path,
        default=_default_sample_path(),
        help="Path to sample JSON file (supports JSON per line)",
    )
    parser.add_argument("--count", type=int, default=1, help="Number of payloads to send")
    parser.add_argument("--interval", type=float, default=0.5, help="Send interval in seconds")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sample_file = args.sample.resolve()
    if not sample_file.exists():
        raise SystemExit(f"Sample file not found: {sample_file}")

    data = _load_samples(sample_file)
    asyncio.run(
        replay(
            host=args.host,
            port=args.port,
            samples=data,
            count=max(1, args.count),
            interval=max(0.0, args.interval),
        )
    )
