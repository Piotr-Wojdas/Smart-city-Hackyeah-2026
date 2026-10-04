"""Mapy: zapis i odczyt, fallback na siatkę, pomocnicze funkcje importu OSM (bez sieci)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from sztafeta.data.grid import make_grid_city
from sztafeta.data.store import city_exists, load_city, save_city
from sztafeta.engine.geo import geohash_encode, points_in_polygon
from sztafeta.scenarios import build_city, load_preset


def test_city_roundtrip_through_data_dir(tmp_path: Path) -> None:
    city = make_grid_city(seed=3, nx=8, ny=6)
    place = tmp_path / "miasto"
    assert not city_exists(place)
    save_city(city, place, {"fetched": "2026-10-03", "attribution": "test"})
    assert city_exists(place)
    back = load_city(place)
    assert back.name == city.name and back.crs == city.crs and back.source == city.source
    assert np.array_equal(back.graph.node_xy, city.graph.node_xy)
    assert np.array_equal(back.graph.edges, city.graph.edges)
    assert np.array_equal(back.buildings_xy, city.buildings_xy)
    assert np.allclose(back.hazard_zone, city.hazard_zone)
    assert len(back.water) == len(city.water) and np.allclose(back.water[0], city.water[0])
    assert back.georef == city.georef
    # ta sama mapa po odczycie daje te same trasy
    assert back.graph.route_nodes(0, 20).tolist() == city.graph.route_nodes(0, 20).tolist()


def test_osm_preset_falls_back_to_grid_without_data(tmp_path: Path) -> None:
    cfg = {"kind": "osm", "dir": "nie-ma", "grid": {"seed": 3, "nx": 8, "ny": 6}}
    city = build_city(cfg, tmp_path)
    assert "FALLBACK" in city.source
    assert city.graph.n_nodes > 20
    params, scenario = load_preset("flood-stronie", data_dir=tmp_path)
    assert "FALLBACK" in scenario.city.source
    assert params.duration_s == 21600.0


def test_committed_stronie_map_is_valid() -> None:
    place = Path(__file__).resolve().parents[1] / "data" / "stronie-slaskie"
    if not city_exists(place):
        pytest.skip("brak danych OSM w data/stronie-slaskie (uruchom: sztafeta fetch-osm)")
    city = load_city(place)
    assert city.crs == "EPSG:2180"
    assert "OpenStreetMap" in city.source
    assert np.isfinite(city.graph.distances_to(0)).all()  # graf spójny
    sites = np.vstack([city.hub_xy, city.evac_xy])
    assert not points_in_polygon(sites, city.hazard_zone).any()
    in_zone = points_in_polygon(city.buildings_xy, city.hazard_zone)
    assert 0.05 < in_zone.mean() < 0.7
    # dopasowanie metry -> stopnie trafia w okolice Stronia Śląskiego
    lon, lat = city.georef.to_lonlat(float(city.hub_xy[0]), float(city.hub_xy[1]))
    assert 16.8 < lon < 16.95 and 50.25 < lat < 50.35
    cell = city.georef.geohash(float(city.hub_xy[0]), float(city.hub_xy[1]), 6)
    assert cell == geohash_encode(lat, lon, 6) and cell.startswith("u2g")


def test_densify_turns_street_geometry_into_straight_segments() -> None:
    nx = pytest.importorskip("networkx")
    geometry = pytest.importorskip("shapely.geometry")
    from sztafeta.data.osm import _densify, _levels

    g = nx.MultiDiGraph()
    g.add_node(1, x=0.0, y=0.0)
    g.add_node(2, x=100.0, y=0.0)
    g.add_node(3, x=100.0, y=50.0)
    bend = geometry.LineString([(0.0, 0.0), (50.0, 20.0), (100.0, 0.0)])
    g.add_edge(1, 2, geometry=bend)
    g.add_edge(2, 1, geometry=geometry.LineString(list(bend.coords)[::-1]))  # ten sam odcinek w drugą stronę
    g.add_edge(2, 3)
    node_xy, edges = _densify(g)
    assert node_xy.shape == (4, 2)  # punkt załamania stał się węzłem
    assert edges.shape == (3, 2)  # bez duplikatów mimo dwóch kierunków
    assert [50.0, 20.0] in node_xy.tolist()
    assert _levels("4", "yes", 100.0) == 4.0
    assert _levels(None, "apartments", 100.0) == 4.0
    assert _levels("abc", "yes", 500.0) == 3.0
