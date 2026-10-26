"""Utilidades geográficas y de predicción de aterrizaje."""

from dataclasses import dataclass
from math import radians, degrees, sin, cos, asin, sqrt, atan2
from typing import Optional


EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class Coordinates:
    latitude: float
    longitude: float
    altitude_m: float = 0.0


@dataclass(frozen=True)
class SondeData:
    """Datos normalizados de una sonda desde sondehub."""
    serial: str
    latitude: float
    longitude: float
    altitude_m: float
    velocity_ms: float
    heading_deg: float
    ascent_rate_ms: float
    frequency_mhz: float
    sonde_type: str
    datetime: str  # ISO format
    predictor: Optional[str] = None  # URL predictor si existe


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia gran círculo entre dos puntos (km)."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Rumbo inicial desde punto 1 a punto 2 (grados, 0=Norte)."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    y = sin(dlon) * cos(lat2)
    x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
    brng = degrees(atan2(y, x))
    return (brng + 360) % 360


def distance_to_station(sonde: SondeData, station: Coordinates) -> float:
    """Distancia horizontal sonda-estación (km)."""
    return haversine_km(sonde.latitude, sonde.longitude, station.latitude, station.longitude)


def is_descending(sonde: SondeData, threshold_ms: float = -0.5) -> bool:
    """True si la sonda está descendiendo (ascend_rate < threshold)."""
    return sonde.ascent_rate_ms < threshold_ms


def estimate_landing_point(
    sonde: SondeData,
    station: Coordinates,
    ground_altitude_m: float = 0.0,
    wind_model: str = "constant"
) -> Optional[Coordinates]:
    """
    Estima punto de aterrizaje extrapolando la deriva actual.

    Modelo simple: asume que la deriva horizontal se mantiene constante
    hasta el suelo. Más preciso requeriría modelo atmosférico.
    """
    if sonde.altitude_m <= ground_altitude_m:
        return None

    if sonde.ascent_rate_ms >= 0:
        return None  # Aún subiendo

    # Tiempo estimado hasta el suelo (segundos)
    altitude_above_ground = sonde.altitude_m - ground_altitude_m
    time_to_ground_sec = altitude_above_ground / abs(sonde.ascent_rate_ms)

    # Deriva horizontal actual (m/s)
    # velocity_ms es velocidad horizontal, heading_deg es dirección
    vx = sonde.velocity_ms * sin(radians(sonde.heading_deg))
    vy = sonde.velocity_ms * cos(radians(sonde.heading_deg))

    # Desplazamiento estimado (metros)
    dx = vx * time_to_ground_sec
    dy = vy * time_to_ground_sec

    # Convertir a grados (aproximación local)
    # 1 grado lat ≈ 111 km, 1 grado lon ≈ 111 km * cos(lat)
    lat_offset = dy / 111000.0
    lon_offset = dx / (111000.0 * cos(radians(sonde.latitude)))

    landing_lat = sonde.latitude + lat_offset
    landing_lon = sonde.longitude + lon_offset

    return Coordinates(
        latitude=landing_lat,
        longitude=landing_lon,
        altitude_m=ground_altitude_m
    )


def will_land_in_radius(
    sonde: SondeData,
    station: Coordinates,
    radius_km: float,
    ground_altitude_m: float = 0.0
) -> tuple[bool, Optional[float]]:
    """
    Verifica si la sonda aterrizará dentro del radio.

    Returns:
        (bool: dentro_del_radio, float: distancia_estimada_km)
    """
    landing = estimate_landing_point(sonde, station, ground_altitude_m)
    if landing is None:
        return False, None

    dist = haversine_km(landing.latitude, landing.longitude, station.latitude, station.longitude)
    return dist <= radius_km, dist


def parse_sondehub_message(msg: dict) -> Optional[SondeData]:
    """
    Convierte mensaje crudo de sondehub a SondeData.

    Formato típico:
    {
        "serial": "ABC123",
        "lat": 40.123, "lon": -3.456, "alt": 12000,
        "vel_h": 15.2, "vel_v": -5.3, "heading": 245,
        "freq": 403.2, "type": "RS41", "time": "2024-01-15T10:30:00Z"
    }
    """
    try:
        return SondeData(
            serial=str(msg.get("serial", "")),
            latitude=float(msg.get("lat", 0)),
            longitude=float(msg.get("lon", 0)),
            altitude_m=float(msg.get("alt", 0)),
            velocity_ms=float(msg.get("vel_h", 0)),
            heading_deg=float(msg.get("heading", 0)),
            ascent_rate_ms=float(msg.get("vel_v", 0)),
            frequency_mhz=float(msg.get("freq", 0)),
            sonde_type=str(msg.get("type", "unknown")),
            datetime=str(msg.get("time", "")),
            predictor=msg.get("predictor")
        )
    except (KeyError, ValueError, TypeError):
        return None


def format_distance(km: float) -> str:
    """Formatea distancia legible."""
    if km < 1:
        return f"{km * 1000:.0f} m"
    return f"{km:.1f} km"


def format_altitude(m: float) -> str:
    """Formatea altitud legible."""
    if m >= 1000:
        return f"{m / 1000:.1f} km"
    return f"{m:.0f} m"