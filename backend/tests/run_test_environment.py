"""Check or assist the local integration test environment.

This is intentionally different from run_tests.py. By default it attaches to
the already-running FastAPI backend / Vue frontend and only performs health
checks. It can optionally start helper processes such as the telemetry
simulator. Starting backend/frontend is explicit via flags.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable, Optional


TEST_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = TEST_DIR.parent
REPO_ROOT = BACKEND_ROOT.parent
FRONTEND_ROOT = REPO_ROOT / "frontend"
DEFAULT_DATA_DIR = BACKEND_ROOT / "data" / "test_env"
SCENARIOS = ("random", "m400_mission", "m400_faults", "m400_mixed", "m400_weather")


class ManagedProcess:
    def __init__(self, name: str, process: subprocess.Popen):
        self.name = name
        self.process = process

    @property
    def returncode(self) -> Optional[int]:
        return self.process.poll()


def _display_command(command: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return " ".join(command)


def _can_bind(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
        return True
    except OSError:
        return False


def _ensure_port_available(label: str, host: str, port: int, *, skip: bool) -> None:
    if skip:
        return
    if _can_bind(host, port):
        return
    raise SystemExit(
        f"{label} port is already in use: {host}:{port}. "
        f"Change the port or stop the process that owns it."
    )


def _test_runtime_config(args: argparse.Namespace) -> dict:
    local_mqtt_enabled = bool(args.enable_local_mqtt)
    return {
        "connection": {
            "api_host": args.api_client_host,
            "api_port": args.api_port,
            "device_listen_port": args.tcp_port,
        },
        "mqtt_local": {
            "enabled": local_mqtt_enabled,
            "host": "127.0.0.1" if local_mqtt_enabled else "",
            "port": 1883,
            "client_id": "drone-monitor-test-local",
            "username": "",
            "password": "",
            "topic": "drone/telemetry/test",
            "tls": False,
        },
        "mqtt_cloud": {
            "enabled": False,
            "host": "",
            "port": 8883,
            "client_id": "drone-monitor-test-cloud",
            "username": "",
            "password": "",
            "topic": "drone/telemetry/test/cloud",
            "tls": True,
        },
        "updated_at": time.time(),
    }


def _find_existing_live_config() -> Optional[Path]:
    candidates = [
        REPO_ROOT / "data" / "live_config.json",
        BACKEND_ROOT / "data" / "live_config.json",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _seed_live_config(data_dir: Path, *, fresh: bool) -> None:
    live_config_path = data_dir / "live_config.json"
    if live_config_path.exists() and not fresh:
        return

    payload: dict = {}
    if not fresh:
        existing = _find_existing_live_config()
        if existing is not None:
            payload = _load_json(existing)
            print(f"Seeded live config from {existing}")

    rtmp_config = payload.setdefault("rtmp", {})
    if isinstance(rtmp_config, dict) and not rtmp_config.get("zlm_config_path"):
        rtmp_config["zlm_config_path"] = str((data_dir / "live" / "zlm_config.ini").resolve())

    live_config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _prepare_data_dir(args: argparse.Namespace) -> Path:
    data_dir = Path(args.data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "flights").mkdir(parents=True, exist_ok=True)
    (data_dir / "live").mkdir(parents=True, exist_ok=True)

    runtime_config_path = data_dir / "runtime_config.json"
    runtime_config_path.write_text(
        json.dumps(_test_runtime_config(args), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _seed_live_config(data_dir, fresh=bool(args.fresh_live_config))
    return data_dir


def _build_backend_env(args: argparse.Namespace, data_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    python_path_parts = [str(BACKEND_ROOT)]
    if env.get("PYTHONPATH"):
        python_path_parts.append(env["PYTHONPATH"])

    env.update(
        {
            "PYTHONPATH": os.pathsep.join(python_path_parts),
            "API_HOST": args.api_client_host,
            "API_PORT": str(args.api_port),
            "TCP_SERVER_HOST": args.tcp_bind_host,
            "TCP_SERVER_PORT": str(args.tcp_port),
            "DATABASE_URL": f"sqlite+aiosqlite:///{(data_dir / 'drone_monitor_test.db').as_posix()}",
            "RAW_HISTORY_PATH": str(data_dir / "telemetry_raw.jsonl"),
            "FLIGHT_SESSIONS_PATH": str(data_dir / "flights"),
            "RUNTIME_CONFIG_PATH": str(data_dir / "runtime_config.json"),
            "LIVE_CONFIG_PATH": str(data_dir / "live_config.json"),
            "LIVE_LOG_PATH": str(data_dir / "live" / "live_gateway.log"),
            "LOG_LEVEL": args.log_level,
        }
    )
    return env


def _build_frontend_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "VITE_API_BASE_URL": f"http://{args.api_client_host}:{args.api_port}",
            "VITE_WS_URL": f"ws://{args.api_client_host}:{args.api_port}/ws",
            "VITE_API_HOST": args.api_client_host,
            "VITE_API_PORT": str(args.api_port),
        }
    )
    return env


def _start_process(
    name: str,
    command: list[str],
    *,
    cwd: Path,
    env: Optional[dict[str, str]] = None,
) -> ManagedProcess:
    print(f"\n[{name}] {_display_command(command)}")
    process = subprocess.Popen(command, cwd=str(cwd), env=env)
    return ManagedProcess(name, process)


def _wait_for_backend(args: argparse.Namespace, process: Optional[ManagedProcess], timeout: float) -> bool:
    url = f"http://{args.api_client_host}:{args.api_port}/api/health"
    deadline = time.time() + timeout
    last_error = ""

    while time.time() < deadline:
        if process is not None and process.returncode is not None:
            print(f"Backend exited before becoming ready, code={process.returncode}")
            return False
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    print(f"Backend ready: {url}")
                    return True
        except (OSError, urllib.error.URLError) as exc:
            last_error = str(exc)
        time.sleep(0.4)

    print(f"Backend health check timed out: {url} ({last_error})")
    return False


def _wait_for_frontend(args: argparse.Namespace, process: Optional[ManagedProcess], timeout: float) -> bool:
    url = f"http://127.0.0.1:{args.frontend_port}"
    deadline = time.time() + timeout
    last_error = ""

    while time.time() < deadline:
        if process is not None and process.returncode is not None:
            print(f"Frontend exited before becoming ready, code={process.returncode}")
            return False
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if 200 <= response.status < 500:
                    print(f"Frontend reachable: {url}")
                    return True
        except (OSError, urllib.error.URLError) as exc:
            last_error = str(exc)
        time.sleep(0.4)

    print(f"Frontend check timed out: {url} ({last_error})")
    return False


def _python_command() -> str:
    return sys.executable or "python"


def _npm_command(*, required: bool = True) -> str:
    candidates = ["npm.cmd", "npm"] if os.name == "nt" else ["npm"]
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return path
    if not required:
        return "npm"
    raise SystemExit("npm was not found in PATH. Install Node.js or start frontend manually.")


def _backend_command(args: argparse.Namespace) -> list[str]:
    command = [
        _python_command(),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        args.api_bind_host,
        "--port",
        str(args.api_port),
        "--log-level",
        args.log_level.lower(),
    ]
    if args.reload:
        command.append("--reload")
    return command


def _frontend_command(args: argparse.Namespace) -> list[str]:
    return [
        _npm_command(required=not args.dry_run),
        "run",
        "dev",
        "--",
        "--host",
        args.frontend_bind_host,
        "--port",
        str(args.frontend_port),
    ]


def _simulator_command(args: argparse.Namespace) -> list[str]:
    command = [
        _python_command(),
        "simulate_drone.py",
        "--host",
        "127.0.0.1",
        "--port",
        str(args.tcp_port),
        "--scenario",
        args.scenario,
        "--duration-seconds",
        str(args.duration_seconds),
    ]
    if args.scenario == "random":
        command.extend(["--interval", str(args.interval)])
    if args.loop_forever:
        command.append("--loop-forever")
    else:
        command.extend(["--loop-count", str(max(1, args.loop_count))])
    if args.seed is not None:
        command.extend(["--seed", str(args.seed)])
    return command


def _print_summary(args: argparse.Namespace, data_dir: Path) -> None:
    print("\nTest environment")
    backend_mode = "start" if args.start_backend else "attach"
    frontend_mode = "start" if args.start_frontend else "check" if args.with_frontend else "skip"
    print(f"  Backend:   {backend_mode} http://{args.api_client_host}:{args.api_port}")
    print(f"  WebSocket: ws://{args.api_client_host}:{args.api_port}/ws")
    print(f"  TCP:       {args.tcp_bind_host}:{args.tcp_port}")
    print(f"  Frontend:  {frontend_mode} http://127.0.0.1:{args.frontend_port}")
    if args.start_backend or args.prepare_data:
        print(f"  Data dir:  {data_dir}")
        print(f"  Live log:  {data_dir / 'live' / 'live_gateway.log'}")


def _stop_process(process: ManagedProcess) -> None:
    if process.returncode is not None:
        return

    print(f"Stopping {process.name} ...")
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    process.process.terminate()
    try:
        process.process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.process.kill()


def _stop_all(processes: Iterable[ManagedProcess]) -> None:
    for process in reversed(list(processes)):
        _stop_process(process)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check or assist backend integration test environment.")
    parser.add_argument("--api-bind-host", default="0.0.0.0", help="FastAPI bind host")
    parser.add_argument("--api-client-host", default="127.0.0.1", help="Host shown to frontend/client")
    parser.add_argument("--api-port", type=int, default=8000, help="FastAPI port")
    parser.add_argument("--tcp-bind-host", default="0.0.0.0", help="Telemetry TCP bind host")
    parser.add_argument("--tcp-port", type=int, default=8888, help="Telemetry TCP port")
    parser.add_argument("--frontend-bind-host", default="0.0.0.0", help="Vite bind host")
    parser.add_argument("--frontend-port", type=int, default=3000, help="Vite dev server port")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Isolated test data directory")
    parser.add_argument("--with-frontend", action="store_true", help="Check the already-running Vue/Vite dev server")
    parser.add_argument("--with-simulator", action="store_true", help="Start simulated telemetry sender")
    parser.add_argument("--scenario", choices=SCENARIOS, default="m400_mixed", help="Simulator scenario")
    parser.add_argument("--duration-seconds", type=float, default=30.0, help="Scripted scenario duration")
    parser.add_argument("--loop-count", type=int, default=1, help="Simulator replay count")
    parser.add_argument("--loop-forever", action="store_true", help="Run simulator continuously")
    parser.add_argument("--interval", type=float, default=1.0, help="Random scenario interval")
    parser.add_argument("--seed", type=int, default=None, help="Simulator random seed")
    parser.add_argument("--enable-local-mqtt", action="store_true", help="Enable local MQTT target")
    parser.add_argument("--fresh-live-config", action="store_true", help="Do not copy existing live_config.json")
    parser.add_argument("--start-backend", action="store_true", help="Explicitly start FastAPI backend with isolated test data")
    parser.add_argument("--start-frontend", action="store_true", help="Explicitly start Vue/Vite dev server")
    parser.add_argument("--prepare-data", action="store_true", help="Prepare isolated test data without starting backend")
    parser.add_argument("--reload", action="store_true", help="Start uvicorn with reload when --start-backend is used")
    parser.add_argument("--smoke", action="store_true", help="Run health checks and exit")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without starting processes")
    parser.add_argument("--skip-port-check", action="store_true", help="Skip local port availability checks")
    parser.add_argument("--log-level", default="INFO", help="Backend log level")
    parser.add_argument("--ready-timeout", type=float, default=20.0, help="Backend startup timeout")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if args.start_frontend:
        args.with_frontend = True

    if args.start_backend:
        _ensure_port_available("API", args.api_bind_host, args.api_port, skip=args.skip_port_check)
        _ensure_port_available("Telemetry TCP", args.tcp_bind_host, args.tcp_port, skip=args.skip_port_check)
    if args.start_frontend:
        _ensure_port_available("Frontend", args.frontend_bind_host, args.frontend_port, skip=args.skip_port_check)
        if not (FRONTEND_ROOT / "node_modules").exists():
            print("Warning: frontend/node_modules was not found. Run npm install in frontend if startup fails.")

    data_dir = _prepare_data_dir(args) if args.start_backend or args.prepare_data else Path(args.data_dir).resolve()
    backend_env = _build_backend_env(args, data_dir)
    frontend_env = _build_frontend_env(args) if args.start_frontend else None
    backend_command = _backend_command(args) if args.start_backend else None
    frontend_command = _frontend_command(args) if args.start_frontend else None
    simulator_command = _simulator_command(args) if args.with_simulator else None

    _print_summary(args, data_dir)
    if args.dry_run:
        print("\nDry run commands")
        if backend_command:
            print(f"  backend:   {_display_command(backend_command)}")
        else:
            print(f"  backend:   check http://{args.api_client_host}:{args.api_port}/api/health")
        if frontend_command:
            print(f"  frontend:  {_display_command(frontend_command)}")
        elif args.with_frontend:
            print(f"  frontend:  check http://127.0.0.1:{args.frontend_port}")
        if simulator_command:
            print(f"  simulator: {_display_command(simulator_command)}")
        return 0

    processes: list[ManagedProcess] = []
    try:
        backend: Optional[ManagedProcess] = None
        if backend_command:
            backend = _start_process("backend", backend_command, cwd=BACKEND_ROOT, env=backend_env)
            processes.append(backend)

        if not _wait_for_backend(args, backend, args.ready_timeout):
            return 1

        if frontend_command:
            frontend = _start_process("frontend", frontend_command, cwd=FRONTEND_ROOT, env=frontend_env)
            processes.append(frontend)
            if not _wait_for_frontend(args, frontend, args.ready_timeout):
                return 1
        elif args.with_frontend and not _wait_for_frontend(args, None, args.ready_timeout):
            return 1

        if args.smoke:
            print("Smoke check passed.")
            return 0

        if simulator_command:
            simulator = _start_process("simulator", simulator_command, cwd=BACKEND_ROOT, env=backend_env)
            processes.append(simulator)

        if not processes:
            print("\nTest environment checks passed. Backend/frontend were not started by this script.")
            return 0

        print("\nTest environment helpers are running. Press Ctrl+C to stop helper processes.")
        while True:
            for process in list(processes):
                if process.returncode is None:
                    continue
                print(f"{process.name.capitalize()} exited, code={process.returncode}")
                processes.remove(process)
                if process.name in {"backend", "frontend"}:
                    return int(process.returncode or 0)
            if not processes:
                return 0
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping test environment ...")
        return 0
    finally:
        _stop_all(processes)


if __name__ == "__main__":
    raise SystemExit(main())
