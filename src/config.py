"""Carga y validación de configuración."""

from pathlib import Path
from typing import Any
import os
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


# Cargar .env al importar
load_dotenv()


class LocationConfig(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    altitude_m: float = Field(default=0, ge=0)


class TelegramConfig(BaseModel):
    bot_token: str
    chat_id: str

    @field_validator("bot_token", "chat_id", mode="before")
    @classmethod
    def expand_env(cls, v: str) -> str:
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            env_var = v[2:-1]
            value = os.getenv(env_var)
            if not value:
                raise ValueError(f"Variable de entorno {env_var} no definida")
            return value
        return v


class SondehubConfig(BaseModel):
    ws_url: str = "wss://sondehub.org/ws"
    reconnect_delay_sec: int = 10
    max_reconnect_delay_sec: int = 300
    ping_interval_sec: int = 30


class FiltersConfig(BaseModel):
    frequency_mhz_min: float | None = None
    frequency_mhz_max: float | None = None
    sonde_type: str | None = None
    min_altitude_m: float | None = None


class AlertsConfig(BaseModel):
    notify_on_descent_start: bool = True
    notify_on_landing: bool = True
    alert_once_per_sonde: bool = True  # Solo una alerta total por sonda
    min_alert_interval_sec: int = 300
    include_map_link: bool = True


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "json"
    file: str = ""


class Config(BaseModel):
    location: LocationConfig
    alert_radius_km: float = Field(default=30, gt=0)
    telegram: TelegramConfig
    sondehub: SondehubConfig = SondehubConfig()
    filters: FiltersConfig = FiltersConfig()
    alerts: AlertsConfig = AlertsConfig()
    logging: LoggingConfig = LoggingConfig()


def load_config(config_path: Path | None = None) -> Config:
    """
    Carga configuración desde YAML.

    Prioridad:
    1. config_path explícito
    2. config/config.yaml
    3. config/config.example.yaml (solo como fallback desarrollo)
    """
    if config_path is None:
        base = Path(__file__).parent.parent
        candidates = [
            base / "config" / "config.yaml",
            base / "config" / "config.example.yaml",
        ]
        for c in candidates:
            if c.exists():
                config_path = c
                break

    if config_path is None or not config_path.exists():
        raise FileNotFoundError(
            "No se encontró archivo de configuración. "
            "Copia config/config.example.yaml a config/config.yaml"
        )

    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    return Config(**raw)


# Instancia global (carga perezosa)
_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config(config_path: Path | None = None) -> Config:
    global _config
    _config = load_config(config_path)
    return _config