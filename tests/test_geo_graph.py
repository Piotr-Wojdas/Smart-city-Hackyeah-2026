from __future__ import annotations

import numpy as np

from sztafeta.data.grid import make_grid_city
from sztafeta.engine.geo import GeoRef, geohash_encode, points_in_polygon
from sztafeta.engine.graph import StreetGraph


def test_geohash_known_value() -> None:
    # wartość referencyjna z opisu algorytmu geohash (Jutlandia)
    assert geohash_encode(57.64911, 10.40744, 11) == "u4pruydqqvj"


def test_geohash_prefix_property() -> None:
    full = geohash_encode(50.2957, 16.8742, 8)
    assert geohash_encode(50.2957, 16.8742, 5) == full[:5]


def test_points_in_polygon_square() -> None:
    square = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]])
    pts = np.array([[5.0, 5.0], [15.0, 5.0], [-1.0, 5.0], [9.9, 0.1]])
    assert points_in_polygon(pts, square).tolist() == [True, False, False, True]


def test_georef_anchor_roundtrip() -> None:
    ref = GeoRef.from_anchor(16.8742, 50.2957, 100.0, 200.0)
    lon, lat = ref.to_lonlat(100.0, 200.0)
    assert abs(lon - 16.8742) < 1e-9
    assert abs(lat - 50.2957) < 1e-9


def test_route_follows_shortest_path() -> None:
    # 0 - 1 - 2 w linii oraz długi objazd 0 - 3 - 2
    xy = np.array([[0.0, 0.0], [10.0, 0.0], [20.0, 0.0], [10.0, 50.0]])
    edges = np.array([[0, 1], [1, 2], [0, 3], [3, 2]])
    g = StreetGraph(xy, edges)
    assert g.route_nodes(0, 2).tolist() == [0, 1, 2]
    assert g.route_nodes(2, 0).tolist() == [2, 1, 0]
    assert abs(g.distances_to(2)[0] - 20.0) < 1e-6


def test_grid_city_is_connected_and_sites_outside_zone() -> None:
    city = make_grid_city(seed=3, nx=9, ny=7, spacing=80.0, zone_halfwidth=90.0)
    g = city.graph
    assert np.isfinite(g.distances_to(0)).all()
    sites = np.vstack([city.hub_xy, city.evac_xy])
    assert not points_in_polygon(sites, city.hazard_zone).any()
    assert points_in_polygon(city.buildings_xy, city.hazard_zone).any()


def test_grid_city_is_deterministic() -> None:
    a = make_grid_city(seed=5, nx=8, ny=6)
    b = make_grid_city(seed=5, nx=8, ny=6)
    assert np.array_equal(a.graph.node_xy, b.graph.node_xy)
    assert np.array_equal(a.buildings_xy, b.buildings_xy)
