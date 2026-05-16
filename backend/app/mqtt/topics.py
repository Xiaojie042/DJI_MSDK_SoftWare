"""MQTT topic helpers using uav/{drone_id}/... format."""

DEFAULT_DRONE_ID = "1581F8DBW256G00A2PXY"


def safe_drone_id(drone_id: str) -> str:
    normalized = str(drone_id or "").strip().strip("/")
    return normalized or DEFAULT_DRONE_ID


def data(drone_id: str = "") -> str:
    return f"uav/{safe_drone_id(drone_id)}/data"


def alert(drone_id: str, category: str) -> str:
    return f"uav/{safe_drone_id(drone_id)}/alert/{str(category).strip('/')}"


def heartbeat(drone_id: str = "") -> str:
    return f"uav/{safe_drone_id(drone_id)}/heartbeat"
