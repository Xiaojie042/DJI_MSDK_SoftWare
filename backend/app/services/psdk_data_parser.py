"""Parsers for PSDK weather and visibility payloads."""

from __future__ import annotations

from typing import Any, Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)
INVALID_DATA_MARKER = "///"


def parse_psdk_payload(data: str) -> tuple[str, dict[str, Any], list[str]]:
    """Parse raw PSDK `data` payload into structured fields."""
    text = (data or "").rstrip("\r\n")

    if text.startswith(":"):
        parsed, warnings = _parse_weather_payload(text)
        return "weather", parsed, warnings

    parsed, warnings = _parse_visibility_payload(text)
    return "visibility", parsed, warnings


def _parse_weather_payload(frame: str) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    fields = _expand_weather_fields(frame)

    received_lrc = _safe_get(fields, len(fields))
    calculated_lrc = calculate_weather_lrc(frame) if received_lrc else None
    lrc_valid = bool(received_lrc and calculated_lrc and received_lrc.upper() == calculated_lrc)
    if received_lrc and not lrc_valid:
        warning = f"Weather payload LRC mismatch: received={received_lrc}"
        warnings.append(warning)
        logger.warning(
            warning,
            calculated_lrc=calculated_lrc,
            algorithm="ascii_twos_complement_sum",
        )

    parsed = {
        "relative_wind_direction_deg": _to_float_or_marker(_safe_get(fields, 3)),
        "relative_wind_speed_ms": _to_float_or_marker(_safe_get(fields, 4)),
        "temperature_c": _to_float_or_marker(_safe_get(fields, 5)),
        "humidity_percent": _to_float_or_marker(_safe_get(fields, 6)),
        "pressure_hpa": _to_float_or_marker(_safe_get(fields, 7)),
        "compass_heading_deg": _to_float_or_marker(_safe_get(fields, 8)),
        "true_wind_direction_deg": _to_float_or_marker(_safe_get(fields, 23)),
        "true_wind_speed_ms": _to_float_or_marker(_safe_get(fields, 25)),
        "lrc_received": received_lrc or None,
        "lrc_calculated": calculated_lrc,
        "lrc_valid": lrc_valid if received_lrc else None,
        "invalid_data_marker": INVALID_DATA_MARKER,
    }

    return parsed, warnings


def _parse_visibility_payload(frame: str) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    fields = frame.split("-")

    parsed = {
        "visibility_10s_m": _to_int_or_marker(_safe_get(fields, 2)),
        "visibility_1min_m": _to_int_or_marker(_safe_get(fields, 3)),
        "visibility_10min_m": _to_int_or_marker(_safe_get(fields, 4)),
        "power_voltage_v": _to_float_or_marker(_safe_get(fields, 8)),
        "invalid_data_marker": INVALID_DATA_MARKER,
    }

    return parsed, warnings


def _expand_weather_fields(frame: str) -> list[str]:
    parts = frame.split(",")
    if not parts:
        return []

    head = parts[0]
    if not head.startswith(":"):
        raise ValueError("Weather payload must start with ':'")

    return [":", head[1:]] + parts[1:]


def calculate_weather_lrc(frame: str) -> Optional[str]:
    """Calculate weather payload LRC from frame head through the comma before checksum."""
    if not frame or "," not in frame:
        return None

    checksum_source = frame if frame.endswith(",") else frame[: frame.rfind(",") + 1]
    if not checksum_source:
        return None

    ascii_bytes = checksum_source.encode("ascii", errors="ignore")
    return _to_hex(_twos_complement_sum(ascii_bytes))

def _twos_complement_sum(data: bytes) -> int:
    return (-sum(data)) & 0xFF


def _to_hex(value: int) -> str:
    return f"{value:02X}"


def _safe_get(values: list[str], position: int) -> str:
    index = position - 1
    if index < 0 or index >= len(values):
        return ""
    return values[index].strip()


def _normalize_marker(value: str) -> Optional[str]:
    if not value:
        return INVALID_DATA_MARKER
    if set(value) == {"/"}:
        return INVALID_DATA_MARKER
    return None


def _to_float_or_marker(value: str) -> Any:
    marker = _normalize_marker(value)
    if marker is not None:
        return marker
    try:
        return float(value)
    except ValueError:
        return INVALID_DATA_MARKER


def _to_int_or_marker(value: str) -> Any:
    marker = _normalize_marker(value)
    if marker is not None:
        return marker
    try:
        return int(float(value))
    except ValueError:
        return INVALID_DATA_MARKER
