"""Tests para tracker."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.tracker import SondeTracker, TrackedSonde
from src.utils import SondeData, Coordinates


@pytest.fixture
def tracker():
    t = SondeTracker()
    t.config = MagicMock()
    t.config.location = MagicMock(latitude=40.0, longitude=-3.0, altitude_m=650)
    t.config.alert_radius_km = 30
    t.config.filters = MagicMock(
        frequency_mhz_min=None,
        frequency_mhz_max=None,
        sonde_type=None,
        min_altitude_m=None,
    )
    t.config.alerts = MagicMock(
        notify_on_descent_start=True,
        notify_on_landing=True,
        min_alert_interval_sec=0,
    )
    t.station = Coordinates(40.0, -3.0, 650)
    t.alert_radius_km = 30
    return t


@pytest.fixture
def sample_sonde():
    return SondeData(
        serial="TEST123",
        latitude=40.1,
        longitude=-3.1,
        altitude_m=5000,
        velocity_ms=10,
        heading_deg=225,  # Hacia la estación
        ascent_rate_ms=-5.0,
        frequency_mhz=403.5,
        sonde_type="RS41",
        datetime="2024-01-15T10:00:00Z",
    )


class TestSondeTracker:
    @pytest.mark.asyncio
    async def test_new_sonde_tracked(self, tracker, sample_sonde):
        await tracker.process_sonde(sample_sonde)
        assert "TEST123" in tracker._tracked

    @pytest.mark.asyncio
    async def test_filter_frequency(self, tracker, sample_sonde):
        tracker.config.filters.frequency_mhz_min = 405
        await tracker.process_sonde(sample_sonde)
        assert "TEST123" not in tracker._tracked

    @pytest.mark.asyncio
    async def test_filter_sonde_type(self, tracker, sample_sonde):
        tracker.config.filters.sonde_type = "RS92"
        await tracker.process_sonde(sample_sonde)
        assert "TEST123" not in tracker._tracked

    @pytest.mark.asyncio
    async def test_descent_alert_triggered(self, tracker, sample_sonde):
        alerts = []

        async def callback(t, alert_type, dist):
            alerts.append((t.data.serial, alert_type, dist))

        tracker.set_alert_callback(callback)

        # Primera vez: subiendo
        sample_sonde.ascent_rate_ms = 5.0
        await tracker.process_sonde(sample_sonde)

        # Segunda vez: descendiendo
        sample_sonde.ascent_rate_ms = -5.0
        await tracker.process_sonde(sample_sonde)

        assert len(alerts) == 1
        assert alerts[0][1] == "descent_start"

    @pytest.mark.asyncio
    async def test_no_alert_outside_radius(self, tracker):
        far_sonde = SondeData(
            serial="FAR",
            latitude=50.0,  # Muy lejos
            longitude=10.0,
            altitude_m=5000,
            velocity_ms=10,
            heading_deg=0,
            ascent_rate_ms=-5.0,
            frequency_mhz=403.5,
            sonde_type="RS41",
            datetime="2024-01-15T10:00:00Z",
        )
        alerts = []
        tracker.set_alert_callback(lambda *a: alerts.append(a))
        await tracker.process_sonde(far_sonde)
        assert len(alerts) == 0