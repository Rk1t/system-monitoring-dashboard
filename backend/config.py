import json
import sys
from pathlib import Path

from pydantic import BaseModel, Field


def get_app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_resource_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return get_app_root()


PROJECT_ROOT = get_app_root()
RESOURCE_ROOT = get_resource_root()
CONFIG_PATH = PROJECT_ROOT / "config.json"

if not CONFIG_PATH.exists():
    CONFIG_PATH = RESOURCE_ROOT / "config.json"


class AppConfig(BaseModel):
    server_host: str = "127.0.0.1"
    server_port: int = Field(default=8000, ge=1, le=65535)
    metrics_collect_interval_seconds: int = Field(default=5, ge=1)
    frontend_refresh_interval_seconds: int = Field(default=3, ge=1)
    normal_refresh_interval_seconds: int = Field(default=5, ge=1)
    alert_refresh_interval_seconds: int = Field(default=2, ge=1)
    history_limit_records: int = Field(default=200, ge=20)
    database_path: str = "database/metrics.db"
    trend_threshold_percent: float = Field(default=5, ge=0)
    cpu_anomaly_threshold_percent: float = Field(default=25, ge=0)
    ram_anomaly_threshold_percent: float = Field(default=15, ge=0)
    network_anomaly_threshold_bytes_per_sec: float = Field(default=524288, ge=1)
    network_bottleneck_threshold_bytes_per_sec: float = Field(default=1048576, ge=1)


def _load_config_data() -> dict:
    if not CONFIG_PATH.exists():
        return {}

    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


settings = AppConfig(**_load_config_data())


def resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path
