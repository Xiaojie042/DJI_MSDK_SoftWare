"""Live RTMP ingress and GB28181 forwarding orchestration.

This module intentionally does not implement an RTMP server or a GB28181
protocol stack in Python. It controls mature external processes, persists
their configuration, probes their health, and keeps recent logs available to
the frontend.
"""

from __future__ import annotations

import asyncio
import ctypes
import ipaddress
import json
import os
import random
import re
import shlex
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_ZLM_SECRET = "035c73f7-bb44-4885-a715-d9eb2d1925cc"
DEFAULT_LOG_LIMIT = 500
BACKEND_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


class LiveGatewayError(RuntimeError):
    """Raised when live gateway operations cannot be completed."""


def _clean_text(value: Any, fallback: str = "") -> str:
    normalized = str(value or "").strip()
    return normalized or fallback


def _clean_path(value: Any) -> str:
    return str(value or "").strip().strip('"')


def _candidate_paths(raw_path: str) -> list[Path]:
    cleaned = _clean_path(raw_path)
    if not cleaned:
        return []

    path = Path(cleaned).expanduser()
    if path.is_absolute():
        return [path]

    candidates = [
        Path.cwd() / path,
        WORKSPACE_ROOT / path,
        BACKEND_ROOT / path,
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    return unique


def _clean_path_segment(value: Any, fallback: str) -> str:
    normalized = _clean_text(value, fallback).strip("/")
    return normalized or fallback


def _now() -> float:
    return time.time()


def _generate_ssrc() -> str:
    return str(random.randint(1000000000, 9999999999))


def _deep_update(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_update(result[key], value)
        else:
            result[key] = value
    return result


def _is_error_line(message: str) -> bool:
    lowered = message.lower()
    if "rtmpsession.cpp" in lowered and ("end of file" in lowered or "断开" in message):
        return False
    if "sslutil.cpp" in lowered and (
        "bio_new_file failed" in lowered or "ssl_ctx_check_private_key failed" in lowered
    ):
        return False
    if "httpsession.cpp" in lowered and (
        "connection reset by peer" in lowered or "断开" in message
    ):
        return False
    if "h264rtmp.cpp" in lowered and "assertion failed" in lowered:
        return False
    if "sip/2.0 401" in lowered or "401 unauthorized" in lowered:
        return False
    return any(
        token in lowered
        for token in (
            "error",
            "failed",
            "exception",
            "timeout",
            "refused",
            "forbidden",
            "403",
            "失败",
            "错误",
            "超时",
            "拒绝",
            "鉴权失败",
        )
    )


def _safe_port_open(host: str, port: int, timeout: float = 0.45) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _format_ts(timestamp: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))


def _command_for_display(command: Union[str, list[str]]) -> str:
    if isinstance(command, str):
        return command
    return " ".join(shlex.quote(str(part)) for part in command)


def _read_xml_text(root: ET.Element, path: str) -> str:
    node = root.find(path)
    return (node.text or "").strip() if node is not None else ""


def _set_xml_text(parent: ET.Element, tag: str, value: Any) -> ET.Element:
    node = parent.find(tag)
    if node is None:
        node = ET.SubElement(parent, tag)
    node.text = str(value)
    return node


def _tail_file(path: Path, max_lines: int = 160) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_lines:])
    except OSError:
        return ""


def _scan_error_from_text(text: str) -> str:
    for line in reversed(text.splitlines()):
        normalized = line.strip()
        if normalized and _is_error_line(normalized):
            return normalized
    return ""


def _windows_process_ids_by_image(image_name: str) -> list[int]:
    if os.name != "nt" or not image_name:
        return []

    target = image_name.lower()
    pids: list[int] = []

    try:
        from ctypes import wintypes

        class ProcessEntry32(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_snapshot = kernel32.CreateToolhelp32Snapshot
        create_snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        create_snapshot.restype = wintypes.HANDLE
        process_first = kernel32.Process32FirstW
        process_first.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32)]
        process_first.restype = wintypes.BOOL
        process_next = kernel32.Process32NextW
        process_next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32)]
        process_next.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL

        snapshot = create_snapshot(0x00000002, 0)
        if snapshot == wintypes.HANDLE(-1).value:
            return []

        try:
            entry = ProcessEntry32()
            entry.dwSize = ctypes.sizeof(ProcessEntry32)
            has_entry = process_first(snapshot, ctypes.byref(entry))
            while has_entry:
                if entry.szExeFile.lower() == target:
                    pids.append(int(entry.th32ProcessID))
                has_entry = process_next(snapshot, ctypes.byref(entry))
        finally:
            close_handle(snapshot)
    except (AttributeError, OSError, ValueError):
        return []

    if pids:
        return sorted(set(pids))

    # Some locked-down Windows sessions block tasklist but still allow Get-Process.
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Get-Process -Name '{Path(image_name).stem}' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1.5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return []

    for line in result.stdout.splitlines():
        try:
            pids.append(int(line.strip()))
        except ValueError:
            continue
    return sorted(set(pids))


class RtmpGatewayConfig(BaseModel):
    service_provider: str = "zlmediakit"
    listen_host: str = "0.0.0.0"
    port: int = Field(default=1935, ge=1, le=65535)
    app: str = "live"
    stream: str = "drone"
    zlm_executable_path: str = ""
    zlm_work_dir: str = ""
    zlm_config_path: str = ""
    zlm_http_host: str = "127.0.0.1"
    zlm_http_port: int = Field(default=18080, ge=1, le=65535)
    zlm_secret: str = DEFAULT_ZLM_SECRET

    @field_validator(
        "service_provider",
        "listen_host",
        "zlm_executable_path",
        "zlm_work_dir",
        "zlm_config_path",
        "zlm_http_host",
        "zlm_secret",
        mode="before",
    )
    @classmethod
    def _normalize_text(cls, value: Any) -> str:
        return _clean_text(value)

    @field_validator("app", mode="before")
    @classmethod
    def _normalize_app(cls, value: Any) -> str:
        return _clean_path_segment(value, "live")

    @field_validator("stream", mode="before")
    @classmethod
    def _normalize_stream(cls, value: Any) -> str:
        return _clean_path_segment(value, "drone")


class Gb28181Config(BaseModel):
    sip_server_ip: str = ""
    sip_server_port: int = Field(default=5060, ge=1, le=65535)
    sip_domain: str = ""
    sip_server_id: str = ""
    device_id: str = ""
    channel_id: str = ""
    local_sip_port: int = Field(default=5062, ge=0, le=65535)
    local_rtp_port_start: int = Field(default=30000, ge=1, le=65535)
    local_rtp_port_end: int = Field(default=30100, ge=1, le=65535)
    password: str = ""
    transport: str = "UDP"
    ssrc: str = Field(default_factory=_generate_ssrc)
    auto_reconnect: bool = True
    heartbeat_interval: int = Field(default=60, ge=5, le=3600)
    rtmp_input_url: str = "rtmp://127.0.0.1/live/drone"
    bridge_executable_path: str = ""
    bridge_work_dir: str = ""
    bridge_config_path: str = ""
    bridge_command_template: str = ""

    @field_validator(
        "sip_server_ip",
        "sip_domain",
        "sip_server_id",
        "device_id",
        "channel_id",
        "password",
        "rtmp_input_url",
        "bridge_executable_path",
        "bridge_work_dir",
        "bridge_config_path",
        "bridge_command_template",
        mode="before",
    )
    @classmethod
    def _normalize_text(cls, value: Any) -> str:
        return _clean_text(value)

    @field_validator("transport", mode="before")
    @classmethod
    def _normalize_transport(cls, value: Any) -> str:
        normalized = _clean_text(value, "UDP").upper()
        return normalized if normalized in {"UDP", "TCP"} else "UDP"

    @field_validator("ssrc", mode="before")
    @classmethod
    def _normalize_ssrc(cls, value: Any) -> str:
        normalized = re.sub(r"\D", "", str(value or ""))
        return normalized or _generate_ssrc()

    @model_validator(mode="after")
    def _normalize_port_range(self) -> "Gb28181Config":
        if self.local_rtp_port_end < self.local_rtp_port_start:
            self.local_rtp_port_end = self.local_rtp_port_start
        return self


class LiveGatewayConfig(BaseModel):
    rtmp: RtmpGatewayConfig = Field(default_factory=RtmpGatewayConfig)
    gb28181: Gb28181Config = Field(default_factory=Gb28181Config)
    updated_at: Optional[float] = None


class LiveDependencyStatus(BaseModel):
    zlm_executable_found: bool = False
    zlm_executable_path: str = ""
    gb_bridge_configured: bool = False
    gb_bridge_executable_path: str = ""
    ffmpeg_found: bool = False
    ffmpeg_path: str = ""


class LiveConfigResponse(BaseModel):
    rtmp: RtmpGatewayConfig
    gb28181: Gb28181Config
    updated_at: Optional[float] = None
    lan_ip: str
    rtmp_push_url: str
    dependencies: LiveDependencyStatus


class RtmpStatusResponse(BaseModel):
    running: bool = False
    process_running: bool = False
    service_reachable: bool = False
    service_source: str = "stopped"
    zlm_api_ok: bool = False
    has_drone_stream: bool = False
    lan_ip: str
    push_url: str
    online_clients: int = 0
    bitrate_kbps: float = 0.0
    fps: Optional[float] = None
    pid: Optional[int] = None
    last_error: str = ""
    media_info: dict[str, Any] = Field(default_factory=dict)
    dependencies: LiveDependencyStatus


class Gb28181StatusResponse(BaseModel):
    configured: bool = False
    process_running: bool = False
    managed_process_running: bool = False
    service_source: str = "stopped"
    registration_status: str = "not_configured"
    streaming_status: str = "stopped"
    bitrate_kbps: float = 0.0
    fps: Optional[float] = None
    pid: Optional[int] = None
    external_process_pids: list[int] = Field(default_factory=list)
    process_warning: str = ""
    recent_error: str = ""
    last_started_at: Optional[float] = None
    command: str = ""


class LiveLogEntry(BaseModel):
    timestamp: float
    time: str
    source: str
    level: str = "INFO"
    message: str


class LiveLogsResponse(BaseModel):
    lines: list[LiveLogEntry]
    limit: int


class LiveRestartResponse(BaseModel):
    rtmp: RtmpStatusResponse
    gb28181: Gb28181StatusResponse
    restarted_gb28181: bool = False
    message: str = ""


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class _ManagedProcess:
    def __init__(self, name: str, log_callback) -> None:
        self.name = name
        self.log_callback = log_callback
        self.process: Optional[subprocess.Popen[str]] = None
        self.command: Union[str, list[str], None] = None
        self.cwd: Optional[str] = None
        self.started_at: Optional[float] = None
        self.last_error = ""
        self.last_exit_code: Optional[int] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    @property
    def pid(self) -> Optional[int]:
        if self.process and self.is_running:
            return self.process.pid
        return None

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self, command: Union[str, list[str]], cwd: Optional[str] = None) -> None:
        with self._lock:
            if self.is_running:
                return

            self.command = command
            self.cwd = cwd
            self.started_at = _now()
            self.last_error = ""
            self.last_exit_code = None

            launch_command: Union[str, list[str]] = command
            if isinstance(command, str) and os.name != "nt":
                launch_command = shlex.split(command)

            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
                    subprocess,
                    "CREATE_NEW_PROCESS_GROUP",
                    0,
                )

            self.process = subprocess.Popen(
                launch_command,
                cwd=cwd or None,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                creationflags=creationflags,
            )
            self.log_callback(
                self.name,
                f"Started process pid={self.process.pid}: {_command_for_display(command)}",
            )
            self._reader_thread = threading.Thread(target=self._read_stdout, daemon=True)
            self._reader_thread.start()

    def stop(self, timeout: float = 8.0) -> None:
        with self._lock:
            process = self.process
            if process is None:
                return

            if process.poll() is not None:
                self.last_exit_code = process.returncode
                self.process = None
                return

            self.log_callback(self.name, f"Stopping process pid={process.pid}")
            process.terminate()
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.log_callback(self.name, f"Process pid={process.pid} did not stop in time; killing", "WARNING")
                process.kill()
                process.wait(timeout=3)

            self.last_exit_code = process.returncode
            self.log_callback(self.name, f"Process stopped exit_code={self.last_exit_code}")
            self.process = None

    def refresh_exit_state(self) -> None:
        with self._lock:
            if self.process is None:
                return
            code = self.process.poll()
            if code is None:
                return
            self.last_exit_code = code
            self.log_callback(self.name, f"Process exited exit_code={code}", "WARNING" if code else "INFO")
            self.process = None

    def _read_stdout(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return

        for raw_line in iter(process.stdout.readline, ""):
            line = raw_line.strip()
            if not line:
                continue
            level = "ERROR" if _is_error_line(line) else "INFO"
            if level == "ERROR":
                self.last_error = line
            self.log_callback(self.name, line, level)


class LiveGatewayService:
    """Orchestrates RTMP ingress and GB28181 forwarding helper processes."""

    def __init__(
        self,
        *,
        config_path: Union[str, Path] = settings.live_config_path,
        log_path: Union[str, Path] = settings.live_log_path,
    ) -> None:
        self.config_path = Path(config_path)
        self.log_path = Path(log_path)
        self._config = LiveGatewayConfig()
        self._lock = asyncio.Lock()
        self._log_lock = threading.Lock()
        self._logs: deque[LiveLogEntry] = deque(maxlen=DEFAULT_LOG_LIMIT)
        self._rtmp_process = _ManagedProcess("rtmp", self._append_log)
        self._gb_process = _ManagedProcess("gb28181", self._append_log)

    async def initialize(self) -> LiveGatewayConfig:
        async with self._lock:
            self._config = self._load()
            self._persist(self._config)
            self._append_log("system", f"Live gateway initialized config={self.config_path}")
            return self.get_config()

    async def shutdown(self) -> None:
        async with self._lock:
            self._gb_process.stop()
            self._rtmp_process.stop()
            self._append_log("system", "Live gateway shutdown complete")

    def get_config(self) -> LiveGatewayConfig:
        return self._config.model_copy(deep=True)

    def get_config_response(self) -> LiveConfigResponse:
        config = self.get_config()
        return LiveConfigResponse(
            **config.model_dump(mode="json"),
            lan_ip=self.get_lan_ip(),
            rtmp_push_url=self.build_rtmp_push_url(config.rtmp),
            dependencies=self.detect_dependencies(config),
        )

    async def update_config(self, payload: Union[LiveGatewayConfig, dict[str, Any]]) -> LiveConfigResponse:
        async with self._lock:
            previous_local_rtmp_url = self.build_local_rtmp_url(self._config.rtmp)
            if isinstance(payload, LiveGatewayConfig):
                next_config = payload.model_copy(deep=True)
            else:
                current = self._config.model_dump(mode="json")
                next_config = LiveGatewayConfig.model_validate(_deep_update(current, payload if isinstance(payload, dict) else {}))

            if not next_config.gb28181.rtmp_input_url or next_config.gb28181.rtmp_input_url == previous_local_rtmp_url:
                next_config.gb28181.rtmp_input_url = self.build_local_rtmp_url(next_config.rtmp)

            next_config.updated_at = _now()
            self._config = next_config
            self._persist(next_config)
            self._append_log("system", "Live gateway configuration saved")
            return self.get_config_response()

    async def start_rtmp(self) -> RtmpStatusResponse:
        async with self._lock:
            config = self._config.rtmp
            if self._rtmp_process.is_running:
                self._append_log("rtmp", "RTMP service already running")
                return self.get_rtmp_status()

            zlm_executable = self._resolve_zlm_executable(config)
            if not zlm_executable:
                if _safe_port_open("127.0.0.1", config.port):
                    self._append_log(
                        "rtmp",
                        f"RTMP port {config.port} is already reachable; treating it as an external service",
                        "WARNING",
                    )
                    return self.get_rtmp_status()
                raise LiveGatewayError(
                    "ZLMediaKit MediaServer executable was not found. Configure "
                    "rtmp.zlm_executable_path or place MediaServer.exe under tools/zlmediakit/."
                )

            if _safe_port_open("127.0.0.1", config.port):
                self._append_log(
                    "rtmp",
                    f"RTMP port {config.port} is already occupied before managed startup",
                    "WARNING",
                )
                return self.get_rtmp_status()

            if _safe_port_open("127.0.0.1", config.zlm_http_port):
                raise LiveGatewayError(
                    f"ZLMediaKit HTTP port {config.zlm_http_port} is already occupied. "
                    "Change rtmp.zlm_http_port in the live forwarding panel."
                )

            config_path = self._prepare_zlm_config(config)
            work_dir = _clean_path(config.zlm_work_dir) or str(Path(zlm_executable).resolve().parent)
            command = [zlm_executable, "-c", config_path]

            try:
                self._rtmp_process.start(command, cwd=work_dir)
            except OSError as exc:
                self._append_log("rtmp", f"Failed to start ZLMediaKit: {exc}", "ERROR")
                raise LiveGatewayError(f"Failed to start ZLMediaKit: {exc}") from exc

            await asyncio.sleep(0.5)
            return self.get_rtmp_status()

    async def stop_rtmp(self) -> RtmpStatusResponse:
        async with self._lock:
            if self._rtmp_process.is_running:
                self._rtmp_process.stop()
            else:
                self._append_log("rtmp", "No managed RTMP process is running")
            return self.get_rtmp_status()

    def get_rtmp_status(self) -> RtmpStatusResponse:
        self._rtmp_process.refresh_exit_state()
        config = self.get_config()
        process_running = self._rtmp_process.is_running
        service_reachable = _safe_port_open("127.0.0.1", config.rtmp.port)
        media_probe = self._probe_zlm_media(config)
        zlm_api_ok = bool(media_probe.get("api_ok"))
        has_stream = bool(media_probe.get("has_stream"))
        service_source = "managed" if process_running else "external" if service_reachable else "stopped"
        last_error = self._rtmp_process.last_error or ("" if service_reachable or process_running else "")

        return RtmpStatusResponse(
            running=process_running or service_reachable,
            process_running=process_running,
            service_reachable=service_reachable,
            service_source=service_source,
            zlm_api_ok=zlm_api_ok,
            has_drone_stream=has_stream,
            lan_ip=self.get_lan_ip(),
            push_url=self.build_rtmp_push_url(config.rtmp),
            online_clients=int(media_probe.get("online_clients") or 0),
            bitrate_kbps=round(float(media_probe.get("bitrate_kbps") or 0.0), 2),
            fps=media_probe.get("fps"),
            pid=self._rtmp_process.pid,
            last_error=last_error,
            media_info=media_probe.get("media_info") or {},
            dependencies=self.detect_dependencies(config),
        )

    async def start_gb28181(self) -> Gb28181StatusResponse:
        async with self._lock:
            config = self._apply_gb_bridge_defaults(self._config)
            gb_config = config.gb28181
            self._config = config
            self._persist(config)

            if self._gb_process.is_running:
                self._append_log("gb28181", "GB28181 bridge already running")
                return self.get_gb28181_status()

            self._validate_gb_config(gb_config)
            existing_pids = self._list_gb_bridge_process_ids(gb_config)
            if existing_pids:
                self._append_log(
                    "gb28181",
                    "检测到后端外部已有 GB28181 桥接进程；"
                    f"pids={existing_pids}。请先停止它，再启动新的转发实例。",
                    "WARNING",
                )
                return self.get_gb28181_status()

            bridge_config_path = self._write_gb_bridge_config(config)
            command = self._build_gb_bridge_command(gb_config, bridge_config_path)
            cwd = self._resolve_gb_work_dir(gb_config)

            try:
                self._gb_process.start(command, cwd=cwd)
            except OSError as exc:
                self._append_log("gb28181", f"Failed to start GB28181 bridge: {exc}", "ERROR")
                raise LiveGatewayError(f"Failed to start GB28181 bridge: {exc}") from exc

            await asyncio.sleep(0.5)
            return self.get_gb28181_status()

    async def stop_gb28181(self) -> Gb28181StatusResponse:
        async with self._lock:
            if self._gb_process.is_running:
                self._gb_process.stop()
            else:
                self._append_log("gb28181", "No managed GB28181 bridge process is running")
            return self.get_gb28181_status()

    async def restart_related_services(self) -> LiveRestartResponse:
        """Restart the live forwarding chain in a safe order."""
        previous_gb_status = self.get_gb28181_status()
        should_restart_gb = previous_gb_status.process_running
        self._append_log("system", "Restarting live services: stop GB28181, restart RTMP, then restore GB28181")

        await self.stop_gb28181()
        await self.stop_rtmp()
        await asyncio.sleep(0.35)

        rtmp_status = await self.start_rtmp()
        gb_status = self.get_gb28181_status()
        restarted_gb = False
        message = "RTMP service restarted. GB28181 was not running before restart."

        if should_restart_gb:
            try:
                gb_status = await self.start_gb28181()
                restarted_gb = gb_status.process_running
                message = "RTMP service restarted. GB28181 forwarding restart requested."
            except LiveGatewayError as exc:
                message = f"RTMP service restarted, but GB28181 restart failed: {exc}"
                self._append_log("gb28181", message, "ERROR")

        return LiveRestartResponse(
            rtmp=rtmp_status,
            gb28181=gb_status,
            restarted_gb28181=restarted_gb,
            message=message,
        )

    def get_gb28181_status(self) -> Gb28181StatusResponse:
        self._gb_process.refresh_exit_state()
        config = self.get_config()
        configured = self._is_gb_bridge_configured(config.gb28181)
        managed_process_running = self._gb_process.is_running
        managed_pid = self._gb_process.pid
        known_pids = self._list_gb_bridge_process_ids(config.gb28181)
        external_pids = [pid for pid in known_pids if pid != managed_pid]
        process_running = managed_process_running or bool(known_pids)
        service_source = "managed" if managed_process_running else "external" if known_pids else "stopped"
        process_warning = ""
        if external_pids:
            process_warning = (
                f"检测到外部 GB28181 桥接进程：{external_pids}。"
                "重复设备桥接可能导致 WVP 显示旧设备、通道串号或点播失败。"
            )
        media_probe = self._probe_zlm_media(config)
        recent_text = self._recent_gb_bridge_text(config.gb28181, count=800)
        registration_status = self._infer_registration_status(configured, process_running, recent_text)
        streaming_status = self._infer_streaming_status(
            configured,
            process_running,
            bool(media_probe.get("has_stream")),
            recent_text,
        )

        return Gb28181StatusResponse(
            configured=configured,
            process_running=process_running,
            managed_process_running=managed_process_running,
            service_source=service_source,
            registration_status=registration_status,
            streaming_status=streaming_status,
            bitrate_kbps=round(float(media_probe.get("bitrate_kbps") or 0.0), 2),
            fps=media_probe.get("fps"),
            pid=managed_pid or (known_pids[0] if known_pids else None),
            external_process_pids=external_pids,
            process_warning=process_warning,
            recent_error=self._gb_process.last_error or self._scan_recent_error("gb28181") or _scan_error_from_text(recent_text),
            last_started_at=self._gb_process.started_at,
            command=_command_for_display(self._gb_process.command or ""),
        )

    def get_logs(self, limit: int = 200) -> LiveLogsResponse:
        bounded_limit = max(1, min(int(limit or 200), DEFAULT_LOG_LIMIT))
        with self._log_lock:
            lines = list(self._logs)[-bounded_limit:]
        return LiveLogsResponse(lines=lines, limit=bounded_limit)

    def build_rtmp_push_url(self, config: Optional[RtmpGatewayConfig] = None) -> str:
        rtmp_config = config or self._config.rtmp
        host = self.get_lan_ip()
        port = "" if rtmp_config.port == 1935 else f":{rtmp_config.port}"
        return f"rtmp://{host}{port}/{rtmp_config.app}/{rtmp_config.stream}"

    def build_local_rtmp_url(self, config: Optional[RtmpGatewayConfig] = None) -> str:
        rtmp_config = config or self._config.rtmp
        port = "" if rtmp_config.port == 1935 else f":{rtmp_config.port}"
        return f"rtmp://127.0.0.1{port}/{rtmp_config.app}/{rtmp_config.stream}"

    def get_lan_ip(self) -> str:
        candidates: list[str] = []

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                candidates.append(sock.getsockname()[0])
        except OSError:
            pass

        try:
            hostname = socket.gethostname()
            _, _, addresses = socket.gethostbyname_ex(hostname)
            candidates.extend(addresses)
        except OSError:
            pass

        for candidate in candidates:
            try:
                address = ipaddress.ip_address(candidate)
            except ValueError:
                continue
            if address.version == 4 and not address.is_loopback and not address.is_link_local:
                return str(address)

        return "127.0.0.1"

    def detect_dependencies(self, config: Optional[LiveGatewayConfig] = None) -> LiveDependencyStatus:
        live_config = config or self.get_config()
        zlm_path = self._resolve_zlm_executable(live_config.rtmp) or ""
        gb_path = self._resolve_gb_bridge_executable(live_config.gb28181) or ""
        ffmpeg_path = shutil.which("ffmpeg") or ""
        return LiveDependencyStatus(
            zlm_executable_found=bool(zlm_path),
            zlm_executable_path=zlm_path,
            gb_bridge_configured=bool(gb_path or live_config.gb28181.bridge_command_template),
            gb_bridge_executable_path=gb_path,
            ffmpeg_found=bool(ffmpeg_path),
            ffmpeg_path=ffmpeg_path,
        )

    def _load(self) -> LiveGatewayConfig:
        if not self.config_path.exists():
            return LiveGatewayConfig()
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
            return LiveGatewayConfig.model_validate(payload if isinstance(payload, dict) else {})
        except Exception as exc:
            self._append_log("system", f"Failed to load live gateway config, using defaults: {exc}", "WARNING")
            return LiveGatewayConfig()

    def _persist(self, config: LiveGatewayConfig) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(config.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _append_log(self, source: str, message: str, level: str = "INFO") -> None:
        timestamp = _now()
        entry = LiveLogEntry(
            timestamp=timestamp,
            time=_format_ts(timestamp),
            source=source,
            level=level,
            message=message,
        )

        with self._log_lock:
            self._logs.append(entry)

        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as file:
                file.write(f"{entry.time} [{entry.level}] [{entry.source}] {entry.message}\n")
        except OSError:
            pass

        log_method = logger.warning if level == "WARNING" else logger.error if level == "ERROR" else logger.info
        log_method("Live gateway log", source=source, message=message)

    def _scan_recent_error(self, source: str) -> str:
        with self._log_lock:
            for entry in reversed(self._logs):
                if entry.source == source and entry.level == "ERROR":
                    return entry.message
        return ""

    def _resolve_zlm_executable(self, config: RtmpGatewayConfig) -> str:
        candidates = [
            _clean_path(config.zlm_executable_path),
            str(Path("tools") / "zlmediakit" / "MediaServer.exe"),
            str(Path("tools") / "ZLMediaKit" / "MediaServer.exe"),
            str(Path("Scripts") / "release" / "tools" / "zlmediakit" / "MediaServer.exe"),
            str(Path("Scripts") / "release" / "tools" / "ZLMediaKit" / "MediaServer.exe"),
            shutil.which("MediaServer") or "",
            shutil.which("MediaServer.exe") or "",
        ]

        for candidate in candidates:
            if not candidate:
                continue
            for path in _candidate_paths(candidate):
                if path.exists() and path.is_file():
                    return str(path.resolve())
        return ""

    def _resolve_gb_bridge_executable(self, config: Gb28181Config) -> str:
        candidates = [
            _clean_path(config.bridge_executable_path),
            str(Path("tools") / "gb28181-bridge" / "happytime-gb28181-device-x64" / "GB28181Device.exe"),
            str(Path("tools") / "gb28181-bridge" / "gb28181-bridge.exe"),
            str(Path("Scripts") / "release" / "tools" / "gb28181-bridge" / "gb28181-bridge.exe"),
        ]

        for candidate in candidates:
            if not candidate:
                continue
            for path in _candidate_paths(candidate):
                if path.exists() and path.is_file():
                    return str(path.resolve())
        return ""

    def _is_happytime_bridge(self, executable: str) -> bool:
        return Path(executable).name.lower() == "gb28181device.exe"

    def _list_gb_bridge_process_ids(self, config: Gb28181Config) -> list[int]:
        executable = self._resolve_gb_bridge_executable(config)
        if not executable:
            return []
        return _windows_process_ids_by_image(Path(executable).name)

    def _happytime_config_path(self, config: Gb28181Config, executable: str) -> Path:
        configured_path = _clean_path(config.bridge_config_path)
        if configured_path:
            candidates = _candidate_paths(configured_path)
            return candidates[0] if candidates else Path(configured_path)
        return Path(executable).resolve().parent / "gb28181device.cfg"

    def _read_happytime_config_values(self, config_path: Path) -> dict[str, str]:
        if not config_path.exists():
            return {}
        try:
            root = ET.parse(config_path).getroot()
        except ET.ParseError:
            return {}

        return {
            "sip_server_ip": _read_xml_text(root, "server_ip"),
            "sip_server_port": _read_xml_text(root, "server_port"),
            "sip_server_id": _read_xml_text(root, "server_id"),
            "sip_domain": _read_xml_text(root, "server_domain"),
            "device_id": _read_xml_text(root, "device_id"),
            "channel_id": _read_xml_text(root, "channel/cid"),
            "local_sip_port": _read_xml_text(root, "local_port"),
            "local_rtp_port_start": _read_xml_text(root, "media_base_port"),
            "password": _read_xml_text(root, "password"),
            "transport": _read_xml_text(root, "protocol").upper(),
            "heartbeat_interval": _read_xml_text(root, "heartbeat_interval"),
            "rtmp_input_url": _read_xml_text(root, "channel/media_url"),
        }

    def _apply_gb_bridge_defaults(self, config: LiveGatewayConfig) -> LiveGatewayConfig:
        executable = self._resolve_gb_bridge_executable(config.gb28181)
        if not executable or not self._is_happytime_bridge(executable):
            return config

        xml_path = self._happytime_config_path(config.gb28181, executable)
        existing = self._read_happytime_config_values(xml_path)
        gb_config = config.gb28181
        updates: dict[str, Any] = {
            "bridge_executable_path": gb_config.bridge_executable_path or executable,
            "bridge_work_dir": gb_config.bridge_work_dir or str(Path(executable).resolve().parent),
        }

        text_fields = (
            "sip_server_ip",
            "sip_domain",
            "sip_server_id",
            "device_id",
            "channel_id",
            "password",
            "rtmp_input_url",
        )
        for field_name in text_fields:
            fallback = existing.get(field_name, "")
            if not getattr(gb_config, field_name) and fallback:
                updates[field_name] = fallback

        if gb_config.sip_server_port == 5060 and existing.get("sip_server_port"):
            try:
                updates["sip_server_port"] = int(existing["sip_server_port"])
            except ValueError:
                pass
        if gb_config.transport == "UDP" and existing.get("transport") in {"UDP", "TCP"}:
            updates["transport"] = existing["transport"]
        if gb_config.local_sip_port == 5062 and existing.get("local_sip_port"):
            try:
                updates["local_sip_port"] = int(existing["local_sip_port"])
            except ValueError:
                pass
        if gb_config.local_rtp_port_start == 30000 and existing.get("local_rtp_port_start"):
            try:
                updates["local_rtp_port_start"] = int(existing["local_rtp_port_start"])
            except ValueError:
                pass
        if gb_config.heartbeat_interval == 60 and existing.get("heartbeat_interval"):
            try:
                updates["heartbeat_interval"] = int(existing["heartbeat_interval"])
            except ValueError:
                pass

        return config.model_copy(update={"gb28181": gb_config.model_copy(update=updates)})

    def _prepare_zlm_config(self, config: RtmpGatewayConfig) -> str:
        configured_path = _clean_path(config.zlm_config_path)
        config_path = Path(configured_path) if configured_path else Path("data") / "live" / "zlm_config.ini"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        if configured_path and config_path.exists():
            self._append_log("rtmp", f"Using existing ZLMediaKit config {config_path}")
            return str(config_path.resolve())

        content = f"""[api]
apiDebug=0
secret={config.zlm_secret or DEFAULT_ZLM_SECRET}

[general]
enableVhost=0

[http]
allow_cross_domains=1
port={config.zlm_http_port}
sslport=0

[rtmp]
enhanced=0
port={config.port}
sslport=0

[rtsp]
port=18554
sslport=0

[rtc]
enableTurn=0
port=18100
tcpPort=18100
signalingPort=18101
signalingSslPort=0
icePort=18102
iceTcpPort=18102

[rtp_proxy]
port=18110
port_range=18111-18190

[shell]
port=18120

[srt]
port=18130
"""
        config_path.write_text(content, encoding="utf-8")
        self._append_log("rtmp", f"Generated ZLMediaKit config {config_path}")
        return str(config_path.resolve())

    def _probe_zlm_media(self, config: LiveGatewayConfig) -> dict[str, Any]:
        rtmp_config = config.rtmp
        params = urllib.parse.urlencode(
            {
                "secret": rtmp_config.zlm_secret or DEFAULT_ZLM_SECRET,
                "schema": "rtmp",
                "vhost": "__defaultVhost__",
                "app": rtmp_config.app,
                "stream": rtmp_config.stream,
            }
        )
        url = f"http://{rtmp_config.zlm_http_host}:{rtmp_config.zlm_http_port}/index/api/getMediaList?{params}"

        try:
            with urllib.request.urlopen(url, timeout=0.8) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            return {
                "api_ok": False,
                "has_stream": False,
                "online_clients": 0,
                "bitrate_kbps": 0.0,
                "fps": None,
                "media_info": {},
            }

        items = payload.get("data") if isinstance(payload, dict) else []
        if not isinstance(items, list):
            items = []

        media_items = [
            item
            for item in items
            if isinstance(item, dict)
            and item.get("app") == rtmp_config.app
            and item.get("stream") == rtmp_config.stream
        ]
        media = media_items[0] if media_items else {}
        tracks = media.get("tracks") if isinstance(media.get("tracks"), list) else []
        fps_values = [
            float(track.get("fps"))
            for track in tracks
            if isinstance(track, dict) and isinstance(track.get("fps"), (int, float))
        ]
        bytes_speed = float(media.get("bytesSpeed") or media.get("bytes_speed") or 0)
        reader_count = int(media.get("readerCount") or media.get("totalReaderCount") or 0)

        return {
            "api_ok": isinstance(payload, dict) and payload.get("code") == 0,
            "has_stream": bool(media_items),
            "online_clients": max(0, reader_count),
            "bitrate_kbps": bytes_speed * 8 / 1000,
            "fps": max(fps_values) if fps_values else None,
            "media_info": media,
        }

    def _validate_gb_config(self, config: Gb28181Config) -> None:
        if not self._is_gb_bridge_configured(config):
            raise LiveGatewayError(
                "GB28181 device bridge is not configured. ZLMediaKit startSendRtp/FFmpeg alone is not a complete "
                "GB28181 device-side SIP registration chain; configure bridge_executable_path or bridge_command_template."
            )

        missing = []
        for field_name in ("sip_server_ip", "device_id", "channel_id"):
            if not getattr(config, field_name):
                missing.append(field_name)
        if not (config.sip_domain or config.sip_server_id):
            missing.append("sip_domain_or_sip_server_id")
        if missing:
            raise LiveGatewayError(f"GB28181 config is incomplete: {', '.join(missing)}")

        invalid = []
        for field_name in ("device_id", "channel_id"):
            value = getattr(config, field_name)
            if value and not re.fullmatch(r"\d{20}", value):
                invalid.append(f"{field_name}_must_be_20_digits")
        if config.sip_server_id and not re.fullmatch(r"\d{20}", config.sip_server_id):
            invalid.append("sip_server_id_must_be_20_digits")
        if config.sip_domain and not re.fullmatch(r"\d{10}", config.sip_domain):
            invalid.append("sip_domain_must_be_10_digits")
        if invalid:
            raise LiveGatewayError(f"GB28181 config is invalid: {', '.join(invalid)}")

    def _is_gb_bridge_configured(self, config: Gb28181Config) -> bool:
        return bool(config.bridge_command_template or self._resolve_gb_bridge_executable(config))

    def _write_gb_bridge_config(self, config: LiveGatewayConfig) -> str:
        gb_config = config.gb28181
        executable = self._resolve_gb_bridge_executable(gb_config)
        if executable and self._is_happytime_bridge(executable):
            return self._write_happytime_bridge_config(config, executable)

        configured_path = _clean_path(gb_config.bridge_config_path)
        path = Path(configured_path) if configured_path else Path("data") / "live" / "gb28181_bridge_config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "rtmp": {
                "input_url": gb_config.rtmp_input_url or self.build_local_rtmp_url(config.rtmp),
                "app": config.rtmp.app,
                "stream": config.rtmp.stream,
            },
            "gb28181": gb_config.model_dump(mode="json"),
            "notes": [
                "This file is consumed by an external GB28181 device-side bridge.",
                "The bridge must implement SIP REGISTER, heartbeat, auth, INVITE handling, and PS-RTP sending.",
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._append_log("gb28181", f"Wrote GB28181 bridge config {path}")
        return str(path.resolve())

    def _write_happytime_bridge_config(self, config: LiveGatewayConfig, executable: str) -> str:
        gb_config = config.gb28181
        path = self._happytime_config_path(gb_config, executable)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            try:
                tree = ET.parse(path)
                root = tree.getroot()
            except ET.ParseError:
                root = ET.Element("config")
                tree = ET.ElementTree(root)
        else:
            root = ET.Element("config")
            tree = ET.ElementTree(root)

        _set_xml_text(root, "version", _read_xml_text(root, "version") or "2016")
        _set_xml_text(root, "server_ip", gb_config.sip_server_ip)
        _set_xml_text(root, "server_port", gb_config.sip_server_port)
        _set_xml_text(root, "server_id", gb_config.sip_server_id or gb_config.sip_domain)
        _set_xml_text(root, "server_domain", gb_config.sip_domain or gb_config.sip_server_id[:10])
        _set_xml_text(root, "local_port", gb_config.local_sip_port)
        _set_xml_text(root, "device_id", gb_config.device_id)
        _set_xml_text(root, "device_name", _read_xml_text(root, "device_name") or "DroneMonitor")
        _set_xml_text(root, "password", gb_config.password)
        _set_xml_text(root, "protocol", gb_config.transport.lower())
        _set_xml_text(root, "media_protocol", gb_config.transport.lower())
        _set_xml_text(root, "reg_expires", _read_xml_text(root, "reg_expires") or "3600")
        _set_xml_text(root, "heartbeat_interval", gb_config.heartbeat_interval)
        _set_xml_text(root, "heartbeat_count", _read_xml_text(root, "heartbeat_count") or "0")
        _set_xml_text(root, "media_base_port", gb_config.local_rtp_port_start)
        _set_xml_text(root, "log_enable", _read_xml_text(root, "log_enable") or "1")
        _set_xml_text(root, "log_level", _read_xml_text(root, "log_level") or "1")
        _set_xml_text(root, "log_path", _read_xml_text(root, "log_path"))
        _set_xml_text(root, "log_mode", _read_xml_text(root, "log_mode") or "loop")
        _set_xml_text(root, "log_max_size", _read_xml_text(root, "log_max_size"))
        _set_xml_text(root, "log_max_index", _read_xml_text(root, "log_max_index"))

        channel = root.find("channel")
        if channel is None:
            channel = ET.SubElement(root, "channel")
        _set_xml_text(channel, "cid", gb_config.channel_id)
        _set_xml_text(channel, "cname", _read_xml_text(channel, "cname") or "drone")
        _set_xml_text(channel, "media_url", gb_config.rtmp_input_url or self.build_local_rtmp_url(config.rtmp))
        _set_xml_text(channel, "ondemand", "0")

        try:
            ET.indent(tree, space="    ")
        except AttributeError:
            pass
        tree.write(path, encoding="utf-8", xml_declaration=True)
        self._append_log("gb28181", f"Wrote Happytime GB28181 config {path}")
        return str(path.resolve())

    def _build_gb_bridge_command(self, config: Gb28181Config, bridge_config_path: str) -> Union[str, list[str]]:
        mapping = _SafeFormatDict(
            config_path=bridge_config_path,
            rtmp_input_url=config.rtmp_input_url,
            sip_server_ip=config.sip_server_ip,
            sip_server_port=str(config.sip_server_port),
            sip_domain=config.sip_domain,
            sip_server_id=config.sip_server_id or config.sip_domain,
            device_id=config.device_id,
            channel_id=config.channel_id,
            local_sip_port=str(config.local_sip_port),
            local_rtp_port_start=str(config.local_rtp_port_start),
            local_rtp_port_end=str(config.local_rtp_port_end),
            password=config.password,
            transport=config.transport,
            ssrc=config.ssrc,
            heartbeat_interval=str(config.heartbeat_interval),
        )

        if config.bridge_command_template:
            return config.bridge_command_template.format_map(mapping)

        executable = self._resolve_gb_bridge_executable(config)
        if not executable:
            raise LiveGatewayError("GB28181 bridge executable was not found")
        if self._is_happytime_bridge(executable):
            return [executable]
        return [executable, "--config", bridge_config_path]

    def _resolve_gb_work_dir(self, config: Gb28181Config) -> Optional[str]:
        if config.bridge_work_dir:
            candidates = _candidate_paths(config.bridge_work_dir)
            return str(candidates[0].resolve()) if candidates else str(Path(config.bridge_work_dir).resolve())
        executable = self._resolve_gb_bridge_executable(config)
        if executable:
            return str(Path(executable).resolve().parent)
        return None

    def _recent_gb_bridge_text(self, config: Gb28181Config, count: int = 160) -> str:
        snippets = [self._recent_log_text("gb28181", count)]
        executable = self._resolve_gb_bridge_executable(config)
        if executable and self._is_happytime_bridge(executable):
            log_dir = Path(executable).resolve().parent
            try:
                logs = sorted(
                    log_dir.glob("gb28181device-*.log"),
                    key=lambda item: item.stat().st_mtime,
                    reverse=True,
                )
            except OSError:
                logs = []
            if logs:
                snippets.append(_tail_file(logs[0], count))
        return "\n".join(snippet for snippet in snippets if snippet)

    def _infer_registration_status(
        self,
        configured: bool,
        process_running: bool,
        recent_text: str = "",
    ) -> str:
        if not configured:
            return "not_configured"
        if not process_running:
            return "stopped"

        recent = recent_text or self._recent_log_text("gb28181")
        lowered = recent.lower()
        if any(
            token in lowered
            for token in (
                "register ok",
                "registered",
                "registration success",
                "注册成功",
                "keepalive",
                "keep alive",
            )
        ):
            return "registered"
        if "sip/2.0 200 ok" in lowered and "register" in lowered:
            return "registered"
        if any(
            token in lowered
            for token in ("register failed", "registration failed", "403", "auth failed", "鉴权失败", "注册失败")
        ):
            return "failed"
        if any(token in lowered for token in ("register", "sip", "注册")):
            return "registering"
        return "starting"

    def _infer_streaming_status(
        self,
        configured: bool,
        process_running: bool,
        has_rtmp_stream: bool,
        recent_text: str = "",
    ) -> str:
        if not configured:
            return "not_configured"
        if not process_running:
            return "stopped"

        recent = recent_text or self._recent_log_text("gb28181")
        lowered = recent.lower()
        if any(
            token in lowered
            for token in (
                "startsendrtp",
                "start send rtp",
                "send rtp",
                "rtp sending",
                "streaming",
                "start video",
                "推流中",
            )
        ):
            return "streaming"
        if not has_rtmp_stream:
            return "waiting_rtmp"
        if any(token in lowered for token in ("invite", "play", "invite received", "收到invite")):
            return "negotiating"
        return "waiting_invite"

    def _recent_log_text(self, source: str, count: int = 120) -> str:
        with self._log_lock:
            lines = [entry.message for entry in self._logs if entry.source == source][-count:]
        return "\n".join(lines)
