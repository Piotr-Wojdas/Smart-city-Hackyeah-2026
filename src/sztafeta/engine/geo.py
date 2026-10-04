"""Pomocnicza geometria: geohash, punkt w wielokącie, przeliczenie metrów na stopnie."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def geohash_encode(lat: float, lon: float, precision: int = 7) -> str:
    """Standardowy geohash (base32). Precyzja 7 to komórka ok. 150 x 150 m."""
    lat_lo, lat_hi = -90.0, 90.0
    lon_lo, lon_hi = -180.0, 180.0
    chars: list[str] = []
    bit = 0
    value = 0
    even = True
    while len(chars) < precision:
        if even:
            mid = (lon_lo + lon_hi) / 2.0
            if lon >= mid:
                value = (value << 1) | 1
                lon_lo = mid
            else:
                value <<= 1
                lon_hi = mid
        else:
            mid = (lat_lo + lat_hi) / 2.0
            if lat >= mid:
                value = (value << 1) | 1
                lat_lo = mid
            else:
                value <<= 1
                lat_hi = mid
        even = not even
        bit += 1
        if bit == 5:
            chars.append(_BASE32[value])
            bit = 0
            value = 0
    return "".join(chars)


def points_in_polygon(points: NDArray[np.float64], polygon: NDArray[np.float64]) -> NDArray[np.bool_]:
    """Test „punkt w wielokącie” metodą promienia, wektorowo po punktach.

    `points` ma kształt (N, 2), `polygon` (K, 2) – wierzchołki bez powtórzonego domknięcia.
    """
    pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    poly = np.asarray(polygon, dtype=np.float64).reshape(-1, 2)
    inside = np.zeros(pts.shape[0], dtype=np.bool_)
    if poly.shape[0] < 3:
        return inside
    x = pts[:, 0]
    y = pts[:, 1]
    x1 = poly[:, 0]
    y1 = poly[:, 1]
    x2 = np.roll(x1, -1)
    y2 = np.roll(y1, -1)
    for k in range(poly.shape[0]):
        crosses = (y1[k] > y) != (y2[k] > y)
        dy = y2[k] - y1[k]
        if dy == 0.0:
            continue
        x_at = x1[k] + (y - y1[k]) * (x2[k] - x1[k]) / dy
        inside ^= crosses & (x < x_at)
    return inside


@dataclass(frozen=True, slots=True)
class GeoRef:
    """Afiniczne przeliczenie współrzędnych modelu (metry) na długość i szerokość geograficzną.

    lon = lon_c[0] + lon_c[1] * x + lon_c[2] * y, analogicznie lat. Dla danych OSM współczynniki są
    dopasowane do węzłów grafu; dla siatki proceduralnej wynikają z punktu zaczepienia.
    """

    lon_c: tuple[float, float, float]
    lat_c: tuple[float, float, float]

    @staticmethod
    def from_anchor(lon0: float, lat0: float, x0: float = 0.0, y0: float = 0.0) -> GeoRef:
        """Lokalne przybliżenie płaskie wokół punktu (lon0, lat0) odpowiadającego (x0, y0)."""
        m_per_deg_lat = 110_540.0
        m_per_deg_lon = 111_320.0 * float(np.cos(np.radians(lat0)))
        kx = 1.0 / m_per_deg_lon
        ky = 1.0 / m_per_deg_lat
        return GeoRef(lon_c=(lon0 - kx * x0, kx, 0.0), lat_c=(lat0 - ky * y0, 0.0, ky))

    def to_lonlat(self, x: float, y: float) -> tuple[float, float]:
        lon = self.lon_c[0] + self.lon_c[1] * x + self.lon_c[2] * y
        lat = self.lat_c[0] + self.lat_c[1] * x + self.lat_c[2] * y
        return lon, lat

    def geohash(self, x: float, y: float, precision: int = 7) -> str:
        lon, lat = self.to_lonlat(x, y)
        return geohash_encode(lat, lon, precision)
