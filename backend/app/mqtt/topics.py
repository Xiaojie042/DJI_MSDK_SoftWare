"""MQTT topic helpers."""

from app.config import settings


def normalize_prefix(prefix: str) -> str:
    normalized = str(prefix or "").strip().strip("/")
    return normalized or "drone/telemetry"


def telemetry(prefix: str) -> str:
    return f"{normalize_prefix(prefix)}/data"


def alert(prefix: str, category: str) -> str:
    return f"{normalize_prefix(prefix)}/alert/{str(category).strip('/')}"


def psdk(prefix: str, device_type: str) -> str:
    normalized_device_type = str(device_type or "").strip().strip("/") or "unknown"
    return f"{normalize_prefix(prefix)}/psdk/{normalized_device_type}"


def psdk_weather(prefix: str) -> str:
    return psdk(prefix, "weather")


def battery_alert(prefix: str) -> str:
    return alert(prefix, "battery")


def gps_lost_alert(prefix: str) -> str:
    return alert(prefix, "gps")


def flight_status(prefix: str) -> str:
    return f"{normalize_prefix(prefix)}/status"


def heartbeat(prefix: str) -> str:
    return f"{normalize_prefix(prefix)}/heartbeat"


PREFIX = normalize_prefix(settings.mqtt_topic_prefix)
TELEMETRY = telemetry(PREFIX)
BATTERY_ALERT = battery_alert(PREFIX)
GPS_LOST_ALERT = gps_lost_alert(PREFIX)
FLIGHT_STATUS = flight_status(PREFIX)
HEARTBEAT = heartbeat(PREFIX)
