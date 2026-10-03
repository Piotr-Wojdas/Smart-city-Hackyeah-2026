"""Pobranie mapy z OpenStreetMap (osmnx) i budowa `CityMap` w metrach (EPSG:2180).

Używane tylko przez `sztafeta fetch-osm`. Wynik trafia do `data/<miejsce>/` i jest commitowany,
żeby symulacja działała offline. Dane: © autorzy OpenStreetMap, licencja ODbL.
"""

from __future__ import annotations

import datetime
import itertools
from dataclasses import dataclass
from typing import Any

import numpy as np

from sztafeta.engine.geo import GeoRef, points_in_polygon
from sztafeta.engine.graph import StreetGraph, largest_component
from sztafeta.engine.model import CityMap, FloatArr

CRS = "EPSG:2180"
ATTRIBUTION = "© autorzy OpenStreetMap (ODbL)"

# budynki, w których na pewno nikt nie mieszka
_NOT_RESIDENTIAL = {
    "garage",
    "garages",
    "shed",
    "industrial",
    "commercial",
    "retail",
    "church",
    "chapel",
    "school",
    "kindergarten",
    "hospital",
    "roof",
    "service",
    "warehouse",
    "farm_auxiliary",
    "barn",
    "greenhouse",
    "kiosk",
    "hut",
    "cabin",
    "public",
    "office",
    "civic",
    "transformer_tower",
    "ruins",
    "construction",
    "carport",
    "sports_hall",
    "supermarket",
    "train_station",
    "fire_station",
    "government",
    "hotel",
}
_DEFAULT_LEVELS = {"apartments": 4.0, "residential": 3.0, "house": 1.5, "detached": 1.5}


@dataclass(slots=True)
class OsmRequest:
    """Co pobrać: środek obszaru, promień, szerokość strefy zagrożenia wokół rzek."""

    name: str
    lat: float
    lon: float
    dist_m: float = 1800.0
    network: str = "walk"
    zone_buffer_m: float = 120.0


def fetch_city(req: OsmRequest) -> tuple[CityMap, dict[str, Any]]:
    """Pobiera dane i buduje mapę. Zwraca mapę i metadane do `meta.json`."""
    import osmnx as ox
    from shapely.geometry import MultiPolygon, Point, box
    from shapely.ops import unary_union

    center = (req.lat, req.lon)
    raw = ox.graph_from_point(center, dist=req.dist_m, network_type=req.network, simplify=True)
    projected = ox.project_graph(raw, to_crs=CRS)

    node_xy, edges = _densify(projected)
    node_xy, edges = largest_component(node_xy, edges)
    graph = StreetGraph(node_xy, edges)
    lo = node_xy.min(axis=0)
    hi = node_xy.max(axis=0)
    frame = box(lo[0] - 150.0, lo[1] - 150.0, hi[0] + 150.0, hi[1] + 150.0)

    # przeliczenie metry -> stopnie: dopasowanie afiniczne na węzłach grafu
    ids = list(projected.nodes)
    xy = np.array([[projected.nodes[i]["x"], projected.nodes[i]["y"]] for i in ids], dtype=np.float64)
    lonlat = np.array([[raw.nodes[i]["x"], raw.nodes[i]["y"]] for i in ids], dtype=np.float64)
    design = np.column_stack([np.ones(len(ids)), xy])
    lon_c, *_ = np.linalg.lstsq(design, lonlat[:, 0], rcond=None)
    lat_c, *_ = np.linalg.lstsq(design, lonlat[:, 1], rcond=None)
    georef = GeoRef(
        lon_c=(float(lon_c[0]), float(lon_c[1]), float(lon_c[2])),
        lat_c=(float(lat_c[0]), float(lat_c[1]), float(lat_c[2])),
    )

    # rzeki i strefa zagrożenia (bufor wokół rzek – to nie jest mapa zalewowa)
    water_gdf = _features(ox, center, {"waterway": ["river"]}, req.dist_m)
    water_lines: list[FloatArr] = []
    geoms = []
    for geom in water_gdf.geometry if water_gdf is not None else []:
        clipped = geom.intersection(frame)
        for part in getattr(clipped, "geoms", [clipped]):
            if part.geom_type == "LineString" and part.length > 20.0:
                water_lines.append(np.asarray(part.coords, dtype=np.float64)[:, :2])
                geoms.append(part)
    if not geoms:
        raise RuntimeError("W pobranym obszarze nie ma rzeki – nie da się wyznaczyć strefy zagrożenia")
    buffered = unary_union(geoms).buffer(req.zone_buffer_m).intersection(frame)
    if isinstance(buffered, MultiPolygon):
        buffered = max(buffered.geoms, key=lambda g: g.area)
    zone = np.asarray(buffered.simplify(6.0).exterior.coords, dtype=np.float64)[:-1, :2]

    # budynki mieszkalne: waga = powierzchnia x liczba kondygnacji
    b_gdf = _features(ox, center, {"building": True}, req.dist_m)
    if b_gdf is None or len(b_gdf) == 0:
        raise RuntimeError("W pobranym obszarze nie ma budynków")
    b_xy: list[tuple[float, float]] = []
    b_w: list[float] = []
    for _, row in b_gdf.iterrows():
        geom = row.geometry
        if geom.geom_type not in ("Polygon", "MultiPolygon") or geom.area < 40.0:
            continue
        kind = str(row.get("building", "yes"))
        if kind in _NOT_RESIDENTIAL:
            continue
        levels = _levels(row.get("building:levels"), kind, float(geom.area))
        centroid = geom.centroid
        if not frame.contains(centroid):
            continue
        b_xy.append((float(centroid.x), float(centroid.y)))
        b_w.append(float(geom.area) * levels)
    buildings = np.asarray(b_xy, dtype=np.float64)
    weights = np.asarray(b_w, dtype=np.float64)

    # hub (urząd) i punkt ewakuacji (szkoła) – oba muszą leżeć poza strefą zagrożenia
    town_center = np.array([float(np.mean(xy[:, 0])), float(np.mean(xy[:, 1]))])
    hub_raw = _first_site(_features(ox, center, {"amenity": ["townhall"]}, req.dist_m), town_center)
    hub_xy, hub_moved = _outside_zone(graph, zone, hub_raw, margin=40.0)
    schools = _features(ox, center, {"amenity": ["school"]}, req.dist_m)
    evac_xy, evac_note = _pick_evac(graph, zone, schools, hub_xy, Point)

    city = CityMap(
        name=req.name,
        crs=CRS,
        graph=graph,
        buildings_xy=buildings,
        building_weight=weights,
        hub_xy=hub_xy,
        evac_xy=evac_xy,
        hazard_zone=zone,
        georef=georef,
        water=water_lines,
        source=f"OpenStreetMap, {req.name} ({ATTRIBUTION})",
    )
    in_zone = points_in_polygon(buildings, zone)
    meta: dict[str, Any] = {
        "attribution": ATTRIBUTION,
        "license": "ODbL 1.0",
        "fetched": datetime.date.today().isoformat(),
        "center_lat_lon": [req.lat, req.lon],
        "dist_m": req.dist_m,
        "network": req.network,
        "zone_buffer_m": req.zone_buffer_m,
        "nodes": graph.n_nodes,
        "edges": int(graph.edges.shape[0]),
        "street_km": round(float(graph.edge_len.sum()) / 1000.0, 1),
        "residential_buildings": int(buildings.shape[0]),
        "buildings_in_zone": int(in_zone.sum()),
        "weight_share_in_zone": round(float(weights[in_zone].sum() / weights.sum()), 3),
        "hub_note": "urząd przesunięty poza strefę zagrożenia" if hub_moved else "położenie urzędu z OSM",
        "evac_note": evac_note,
        "disclaimer": (
            "Strefa zagrożenia to bufor wokół rzek, a nie mapa zalewowa. Położenie huba i punktu "
            "ewakuacji jest umowne: scenariusz jest inspirowany powodzią z 2024 r., "
            "nie jest jej rekonstrukcją."
        ),
    }
    return city, meta


def _features(ox: Any, center: tuple[float, float], tags: dict[str, Any], dist: float) -> Any:
    """Obiekty OSM o podanych tagach w układzie metrycznym; None, gdy nic nie znaleziono."""
    try:
        gdf = ox.features_from_point(center, tags=tags, dist=dist)
    except Exception as exc:
        if type(exc).__name__ == "InsufficientResponseError":
            return None
        raise
    if len(gdf) == 0:
        return None
    return gdf.to_crs(CRS)


def _densify(graph: Any) -> tuple[FloatArr, np.ndarray[Any, np.dtype[np.int64]]]:
    """Rozbija geometrię ulic na odcinki proste: każdy punkt załamania staje się węzłem."""
    index: dict[tuple[int, int], int] = {}
    coords: list[tuple[float, float]] = []
    edges: set[tuple[int, int]] = set()

    def node_id(x: float, y: float) -> int:
        key = (round(x * 10.0), round(y * 10.0))
        found = index.get(key)
        if found is None:
            found = len(coords)
            index[key] = found
            coords.append((float(x), float(y)))
        return found

    for u, v, data in graph.edges(data=True):
        if "geometry" in data:
            line = [(float(x), float(y)) for x, y in data["geometry"].coords]
        else:
            line = [
                (float(graph.nodes[u]["x"]), float(graph.nodes[u]["y"])),
                (float(graph.nodes[v]["x"]), float(graph.nodes[v]["y"])),
            ]
        ids = [node_id(x, y) for x, y in line]
        for a, b in itertools.pairwise(ids):
            if a != b:
                edges.add((min(a, b), max(a, b)))
    return np.asarray(coords, dtype=np.float64), np.asarray(sorted(edges), dtype=np.int64)


def _levels(raw: Any, kind: str, area: float) -> float:
    try:
        value = float(str(raw).replace(",", "."))
        if 0.5 <= value <= 20.0:
            return value
    except (TypeError, ValueError):
        pass
    if kind in _DEFAULT_LEVELS:
        return _DEFAULT_LEVELS[kind]
    return 3.0 if area > 400.0 else 1.5


def _first_site(gdf: Any, fallback: FloatArr) -> FloatArr:
    if gdf is None or len(gdf) == 0:
        return fallback
    centroid = gdf.geometry.iloc[0].centroid
    return np.array([float(centroid.x), float(centroid.y)])


def _outside_zone(graph: StreetGraph, zone: FloatArr, xy: FloatArr, margin: float) -> tuple[FloatArr, bool]:
    """Zwraca `xy`, jeśli leży poza strefą; inaczej najbliższy węzeł grafu poza strefą (z zapasem)."""
    if not points_in_polygon(xy.reshape(1, 2), zone)[0]:
        return xy, False
    outside = np.flatnonzero(~_near_zone(graph.node_xy, zone, margin))
    d = np.hypot(graph.node_xy[outside, 0] - xy[0], graph.node_xy[outside, 1] - xy[1])
    return np.array(graph.node_xy[outside[int(np.argmin(d))]], dtype=np.float64), True


def _near_zone(points: FloatArr, zone: FloatArr, margin: float) -> np.ndarray[Any, np.dtype[np.bool_]]:
    """Punkty w strefie albo bliżej niż `margin` od jej wierzchołków."""
    inside = points_in_polygon(points, zone)
    d = np.hypot(points[:, None, 0] - zone[None, :, 0], points[:, None, 1] - zone[None, :, 1]).min(axis=1)
    return inside | (d < margin)


def _pick_evac(
    graph: StreetGraph, zone: FloatArr, schools: Any, hub_xy: FloatArr, point_cls: Any
) -> tuple[FloatArr, str]:
    """Punkt ewakuacji: szkoła poza strefą, możliwie blisko zabudowy; w ostateczności węzeł grafu."""
    candidates: list[FloatArr] = []
    if schools is not None:
        for geom in schools.geometry:
            c = geom.centroid
            candidates.append(np.array([float(c.x), float(c.y)]))
    safe = [c for c in candidates if not _near_zone(c.reshape(1, 2), zone, 60.0)[0]]
    if safe:
        centre = graph.node_xy.mean(axis=0)
        best = min(safe, key=lambda c: float(np.hypot(c[0] - centre[0], c[1] - centre[1])))
        return best, "szkoła z OSM położona poza strefą zagrożenia"
    outside = np.flatnonzero(~_near_zone(graph.node_xy, zone, 150.0))
    d = np.hypot(graph.node_xy[outside, 0] - hub_xy[0], graph.node_xy[outside, 1] - hub_xy[1])
    far = outside[d > 400.0] if (d > 400.0).any() else outside
    centre = graph.node_xy.mean(axis=0)
    dc = np.hypot(graph.node_xy[far, 0] - centre[0], graph.node_xy[far, 1] - centre[1])
    _ = point_cls
    return np.array(
        graph.node_xy[far[int(np.argmin(dc))]], dtype=np.float64
    ), "węzeł poza strefą (brak szkoły poza strefą w OSM)"
