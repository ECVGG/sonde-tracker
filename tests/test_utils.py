"""Tests para utilidades geográficas."""

import pytest
from src.utils import (
    haversine_km,
    bearing_deg,
    distance_to_station,
    is_descending,
    estimate_landing_point,
    will_land_in_radius,
    Coordinates,
    SondeData,
)


class TestHaversine:
    def test_same_point(self):
        assert haversine_km(40.0, -3.0, 40.0, -3.0) == 0.0

    def test_known_distance(self):
        # Madrid a Barcelona ~504 km
        dist = haversine_km(40.4168, -3.7038, 41.3851, 2.1734)
        assert 500 < dist < 510

    def test_antipodes(self):
        # Polo norte a polo sur ~20015 km
        dist = haversine_km(90, 0, -90, 0)
        assert abs(dist - 20015) < 10


class TestBearing:
    def test_north(self):
        # Mismo meridiano, lat2 > lat1
        assert abs(bearing_deg(40, -3, 41, -3) - 0) < 1

    def test_east(self):
        # Misma latitud, lon2 > lon1
        assert abs(bearing_deg(40, -3, 40, -2) - 90) < 1

    def test_south(self):
        assert abs(bearing_deg(41, -3, 40, -3) - 180) < 1

    def test_west(self):
        assert abs(bearing_deg(40, -2, 40, -3) - 270) < 1


class TestIsDescending:
    def test_descending(self):
        sonde = SondeData(
            serial="TEST", latitude=40, longitude=-3, altitude_m=10000,
            velocity_ms=10, heading_deg=0, ascent_rate_ms=-5.0,
            frequency_mhz=403, sonde_type="RS41", datetime="2024-01-01T00:00:00Z"
        )
        assert is_descending(sonde) is True

    def test_ascending(self):
        sonde = SondeData(
            serial="TEST", latitude=40, longitude=-3, altitude_m=1000,
            velocity_ms=10, heading_deg=0, ascent_rate_ms=5.0,
            frequency_mhz=403, sonde_type="RS41", datetime="2024-01-01T00:00:00Z"
        )
        assert is_descending(sonde) is False

    def test_near_zero(self):
        sonde = SondeData(
            serial="TEST", latitude=40, longitude=-3, altitude_m=1000,
            velocity_ms=10, heading_deg=0, ascent_rate_ms=-0.1,
            frequency_mhz=403, sonde_type="RS41", datetime="2024-01-01T00:00:00Z"
        )
        assert is_descending(sonde, threshold_ms=-0.5) is False


class TestLandingEstimation:
    def setup_method(self):
        self.station = Coordinates(40.0, -3.0, 650)

    def test_descending_sonde(self):
        sonde = SondeData(
            serial="TEST", latitude=40.1, longitude=-3.1, altitude_m=5000,
            velocity_ms=10, heading_deg=90, ascent_rate_ms=-5.0,  # Este, bajando
            frequency_mhz=403, sonde_type="RS41", datetime="2024-01-01T00:00:00Z"
        )
        landing = estimate_landing_point(sonde, self.station)
        assert landing is not None
        assert landing.altitude_m == 650
        # Debería estar al este de la posición actual
        assert landing.longitude > sonde.longitude

    def test_ascending_sonde(self):
        sonde = SondeData(
            serial="TEST", latitude=40.1, longitude=-3.1, altitude_m=1000,
            velocity_ms=10, heading_deg=90, ascent_rate_ms=5.0,  # Subiendo
            frequency_mhz=403, sonde_type="RS41", datetime="2024-01-01T00:00:00Z"
        )
        landing = estimate_landing_point(sonde, self.station)
        assert landing is None

    def test_already_on_ground(self):
        sonde = SondeData(
            serial="TEST", latitude=40.1, longitude=-3.1, altitude_m=600,
            velocity_ms=0, heading_deg=0, ascent_rate_ms=0,
            frequency_mhz=403, sonde_type="RS41", datetime="2024-01-01T00:00:00Z"
        )
        landing = estimate_landing_point(sonde, self.station)
        assert landing is None


class TestWillLandInRadius:
    def setup_method(self):
        self.station = Coordinates(40.0, -3.0, 650)

    def test_inside_radius(self):
        sonde = SondeData(
            serial="TEST", latitude=40.05, longitude=-3.05, altitude_m=3000,
            velocity_ms=5, heading_deg=225, ascent_rate_ms=-3.0,  # Hacia SW (hacia estación)
            frequency_mhz=403, sonde_type="RS41", datetime="2024-01-01T00:00:00Z"
        )
        in_radius, dist = will_land_in_radius(sonde, self.station, 30)
        assert in_radius is True
        assert dist is not None
        assert dist < 30

    def test_outside_radius(self):
        sonde = SondeData(
            serial="TEST", latitude=41.0, longitude=-2.0, altitude_m=3000,
            velocity_ms=5, heading_deg=45, ascent_rate_ms=-3.0,  # Lejos, dirección NE
            frequency_mhz=403, sonde_type="RS41", datetime="2024-01-01T00:00:00Z"
        )
        in_radius, dist = will_land_in_radius(sonde, self.station, 30)
        assert in_radius is False