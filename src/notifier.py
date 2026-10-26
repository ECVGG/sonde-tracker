"""Notificador Telegram para alertas de sondas."""

import logging
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError
from telegram.constants import ParseMode

from .config import get_config
from .tracker import TrackedSonde
from .utils import format_distance, format_altitude

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Envía notificaciones por Telegram Bot."""

    def __init__(self):
        self.config = get_config()
        self.bot = Bot(token=self.config.telegram.bot_token)
        self.chat_id = self.config.telegram.chat_id
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    async def send_alert(
        self,
        tracked: TrackedSonde,
        alert_type: str,
        distance_km: Optional[float]
    ) -> bool:
        """
        Envía alerta formateada.

        alert_type: "descent_start" | "landing_soon"
        """
        if not self._enabled:
            return False

        sonde = tracked.data

        if alert_type == "descent_start":
            return await self._send_descent_alert(sonde, distance_km)
        elif alert_type == "landing_soon":
            return await self._send_landing_alert(sonde, distance_km)

        return False

    async def _send_descent_alert(
        self,
        sonde,
        distance_km: Optional[float]
    ) -> bool:
        """Alerta: sonda ha empezado a descender y caerá cerca."""
        emoji = "📡"
        title = "DESCENSO DETECTADO"
        color = "🟡"

        msg = (
            f"{emoji} <b>{title}</b> {color}\n\n"
            f"📍 <b>Sonda:</b> <code>{sonde.serial}</code> ({sonde.sonde_type})\n"
            f"📡 <b>Frecuencia:</b> {sonde.frequency_mhz:.3f} MHz\n"
            f"📍 <b>Posición actual:</b> {sonde.latitude:.5f}, {sonde.longitude:.5f}\n"
            f"📏 <b>Altitud:</b> {format_altitude(sonde.altitude_m)}\n"
            f"⬇️ <b>Tasa descenso:</b> {abs(sonde.ascent_rate_ms):.1f} m/s\n"
            f"🧭 <b>Rumbo:</b> {sonde.heading_deg:.0f}°\n"
            f"💨 <b>Vel. horizontal:</b> {sonde.velocity_ms:.1f} m/s\n"
        )

        if distance_km is not None:
            msg += f"🎯 <b>Dist. estimada aterrizaje:</b> {format_distance(distance_km)}\n"

        if self.config.alerts.include_map_link and sonde.predictor:
            msg += f"\n🔗 <a href='{sonde.predictor}'>Ver en sondehub.org</a>"

        return await self._send_message(msg)

    async def _send_landing_alert(
        self,
        sonde,
        distance_km: Optional[float]
    ) -> bool:
        """Alerta: aterrizaje inminente."""
        emoji = "🎯"
        title = "ATERRIZAJE INMINENTE"
        color = "🔴"

        msg = (
            f"{emoji} <b>{title}</b> {color}\n\n"
            f"📍 <b>Sonda:</b> <code>{sonde.serial}</code> ({sonde.sonde_type})\n"
            f"📍 <b>Posición:</b> {sonde.latitude:.5f}, {sonde.longitude:.5f}\n"
            f"📏 <b>Altitud:</b> {format_altitude(sonde.altitude_m)}\n"
        )

        if distance_km is not None:
            msg += f"🎯 <b>Dist. estimada:</b> {format_distance(distance_km)}\n"

        if self.config.alerts.include_map_link and sonde.predictor:
            msg += f"\n🔗 <a href='{sonde.predictor}'>Ver en sondehub.org</a>"

        return await self._send_message(msg)

    async def send_startup_message(self) -> bool:
        """Mensaje de inicio del servicio."""
        cfg = self.config
        msg = (
            f"🚀 <b>Sonde Tracker iniciado</b>\n\n"
            f"📍 Estación: {cfg.location.latitude:.5f}, {cfg.location.longitude:.5f}\n"
            f"📏 Altitud: {cfg.location.altitude_m:.0f} m\n"
            f"🎯 Radio alerta: {cfg.alert_radius_km} km\n"
            f"🔍 Filtros: {self._format_filters()}"
        )
        return await self._send_message(msg)

    async def send_shutdown_message(self) -> bool:
        """Mensaje de parada del servicio."""
        msg = "🛑 <b>Sonde Tracker detenido</b>"
        return await self._send_message(msg)

    async def send_test_message(self) -> bool:
        """Mensaje de prueba."""
        msg = "✅ <b>Test de notificación</b> - Bot funcionando correctamente"
        return await self._send_message(msg)

    def _format_filters(self) -> str:
        f = self.config.filters
        parts = []
        if f.frequency_mhz_min or f.frequency_mhz_max:
            parts.append(f"Frecuencia: {f.frequency_mhz_min or 0}-{f.frequency_mhz_max or '∞'} MHz")
        if f.sonde_type:
            parts.append(f"Tipo: {f.sonde_type}")
        if f.min_altitude_m:
            parts.append(f"Alt. mín: {f.min_altitude_m} m")
        return ", ".join(parts) if parts else "Sin filtros"

    async def _send_message(self, text: str) -> bool:
        """Envía mensaje con reintentos y manejo de errores."""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            logger.debug("Notificación Telegram enviada")
            return True
        except TelegramError as e:
            logger.error(f"Error enviando Telegram: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado notificando: {e}")
            return False