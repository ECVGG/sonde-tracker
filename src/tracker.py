"""Lógica de tracking y detección de alertas."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from .config import get_config
from .utils import (
    SondeData,
    Coordinates,
    distance_to_station,
    is_descending,
    will_land_in_radius,
    format_distance,
    format_altitude,
)

logger = logging.getLogger(__name__)


@dataclass
class TrackedSonde:
    """Sonda siendo trackeada."""
    data: SondeData
    first_seen: float = field(default_factory=time.time)
    last_alert: float = 0
    descent_alerted: bool = False
    landing_alerted: bool = False
    last_distance_km: float = 0

    def update(self, new_data: SondeData) -> None:
        self.data = new_data
        self.last_distance_km = distance_to_station(new_data, self.station)

    @property
    def station(self) -> Coordinates:
        cfg = get_config()
        return Coordinates(
            latitude=cfg.location.latitude,
            longitude=cfg.location.longitude,
            altitude_m=cfg.location.altitude_m,
        )

    @property
    def alert_radius_km(self) -> float:
        return get_config().alert_radius_km

    @property
    def min_alert_interval(self) -> int:
        return get_config().alerts.min_alert_interval_sec


class SondeTracker:
    """Rastrea sondas y detecta condiciones de alerta."""

    def __init__(self):
        self.config = get_config()
        self.station = Coordinates(
            latitude=self.config.location.latitude,
            longitude=self.config.location.longitude,
            altitude_m=self.config.location.altitude_m,
        )
        self.alert_radius_km = self.config.alert_radius_km
        self._tracked: dict[str, TrackedSonde] = {}
        self._alert_callback: Optional[callable] = None

    def set_alert_callback(self, callback: callable) -> None:
        """Callback async: (sonde: TrackedSonde, alert_type: str, distance_km: float)."""
        self._alert_callback = callback

    def _should_alert(self, tracked: TrackedSonde) -> bool:
        """
        Verifica si se debe alertar.
        Con alert_once_per_sonde=True: solo una alerta total por sonda.
        Con alert_once_per_sonde=False: una por tipo (descent + landing).
        """
        cfg = self.config.alerts
        if cfg.alert_once_per_sonde:
            return tracked.last_alert == 0  # Nunca ha alertado
        return (time.time() - tracked.last_alert) >= cfg.min_alert_interval_sec

    def _matches_filters(self, sonde: SondeData) -> bool:
        """Aplica filtros de configuración."""
        f = self.config.filters

        if f.frequency_mhz_min is not None and sonde.frequency_mhz < f.frequency_mhz_min:
            return False
        if f.frequency_mhz_max is not None and sonde.frequency_mhz > f.frequency_mhz_max:
            return False
        if f.sonde_type and sonde.sonde_type != f.sonde_type:
            return False
        if f.min_altitude_m is not None and sonde.altitude_m < f.min_altitude_m:
            return False

        # Filtrar por distancia horizontal actual (optimización)
        dist = distance_to_station(sonde, self.station)
        if dist > self.alert_radius_km * 3:  # Margen 3x para capturar descendentes
            return False

        return True

    async def process_sonde(self, sonde: SondeData) -> None:
        """Procesa una sonda recibida."""
        if not self._matches_filters(sonde):
            return

        serial = sonde.serial
        tracked = self._tracked.get(serial)

        if tracked is None:
            tracked = TrackedSonde(data=sonde)
            self._tracked[serial] = tracked
            logger.debug(f"Nueva sonda trackeada: {serial}")

        tracked.update(sonde)

        # Verificar condiciones de alerta
        await self._check_alerts(tracked)

        # Limpiar sondas viejas (no vistas en 30 min)
        self._cleanup_old()

    async def _check_alerts(self, tracked: TrackedSonde) -> None:
        """Verifica y dispara alertas para una sonda."""
        sonde = tracked.data
        descending = is_descending(sonde)

        # Alerta: inicio de descenso
        if (descending and not tracked.descent_alerted and
                self.config.alerts.notify_on_descent_start and
                self._should_alert(tracked)):

            in_radius, est_dist = will_land_in_radius(
                sonde, self.station, self.alert_radius_km, self.station.altitude_m
            )

            if in_radius:
                await self._fire_alert(tracked, "descent_start", est_dist)
                tracked.descent_alerted = True

        # Alerta: aterrizaje inminente (ya descendiendo y cerca)
        if (descending and tracked.descent_alerted and not tracked.landing_alerted and
                self.config.alerts.notify_on_landing and
                self._should_alert(tracked)):

            in_radius, est_dist = will_land_in_radius(
                sonde, self.station, self.alert_radius_km, self.station.altitude_m
            )

            # Solo alertar aterrizaje si está muy cerca del suelo
            if in_radius and sonde.altitude_m < 2000:
                await self._fire_alert(tracked, "landing_soon", est_dist)
                tracked.landing_alerted = True

    async def _fire_alert(
        self,
        tracked: TrackedSonde,
        alert_type: str,
        distance_km: Optional[float]
    ) -> None:
        """Dispara callback de alerta."""
        tracked.last_alert = time.time()
        logger.info(
            f"ALERTA {alert_type}: {tracked.data.serial} "
            f"a ~{format_distance(distance_km) if distance_km else '?'}"
        )

        if self._alert_callback:
            try:
                await self._alert_callback(tracked, alert_type, distance_km)
            except Exception as e:
                logger.error(f"Error en callback de alerta: {e}")

    def _cleanup_old(self, max_age_sec: int = 1800) -> None:
        """Elimina sondas no actualizadas recientemente."""
        now = time.time()
        to_remove = [
            serial for serial, t in self._tracked.items()
            if now - t.data.altitude_m > max_age_sec  # Usamos altitud como proxy de tiempo
        ]
        for serial in to_remove:
            del self._tracked[serial]
            logger.debug(f"Sonda expirada eliminada: {serial}")

    def get_active_sondes(self) -> list[TrackedSonde]:
        """Retorna sondas actualmente trackeadas."""
        return list(self._tracked.values())

    def get_nearby_descending(self) -> list[TrackedSonde]:
        """Sondas descendientes dentro del radio de alerta."""
        result = []
        for t in self._tracked.values():
            if is_descending(t.data):
                in_radius, _ = will_land_in_radius(
                    t.data, self.station, self.alert_radius_km, self.station.altitude_m
                )
                if in_radius:
                    result.append(t)
        return result