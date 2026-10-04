"""Proceduralna siatka miejska – fallback, gdy nie ma danych OSM, i mapa używana w testach."""

from __future__ import annotations

import numpy as np

from sztafeta.engine.geo import GeoRef, points_in_polygon
from sztafeta.engine.graph import StreetGraph, largest_component
from sztafeta.engine.model import CityMap, FloatArr
from sztafeta.engine.rng import make_generator

# punkt zaczepienia geohashy siatki: okolice Stronia Śląskiego (siatka NIE odwzorowuje miasta)
_ANCHOR_LON = 16.8742
_ANCHOR_LAT = 50.2957


def make_grid_city(
    seed: int = 7,
    nx: int = 22,
    ny: int = 16,
    spacing: float = 90.0,
    zone_halfwidth: float = 130.0,
) -> CityMap:
    """Buduje nieregularną siatkę ulic z „rzeką” płynącą przez środek i strefą zagrożenia wzdłuż niej."""
    rng = make_generator(seed, "grid-city")
    width = (nx - 1) * spacing
    height = (ny - 1) * spacing

    gx, gy = np.meshgrid(np.arange(nx) * spacing, np.arange(ny) * spacing)
    node_xy = np.column_stack([gx.ravel(), gy.ravel()]).astype(np.float64)
    node_xy += rng.uniform(-0.13 * spacing, 0.13 * spacing, size=node_xy.shape)

    idx = np.arange(nx * ny).reshape(ny, nx)
    horiz = np.column_stack([idx[:, :-1].ravel(), idx[:, 1:].ravel()])
    vert = np.column_stack([idx[:-1, :].ravel(), idx[1:, :].ravel()])
    edges = np.vstack([horiz, vert]).astype(np.int64)
    edges = edges[rng.random(edges.shape[0]) > 0.12]
    node_xy, edges = largest_component(node_xy, edges)
    graph = StreetGraph(node_xy, edges)

    # rzeka: łagodna sinusoida przez środek mapy; strefa zagrożenia = pas wokół niej
    rx = np.linspace(-spacing, width + spacing, 40)
    ry = 0.5 * height + 0.12 * height * np.sin(rx / width * 2.2 * np.pi)
    river = np.column_stack([rx, ry])
    zone = np.vstack(
        [
            np.column_stack([rx, ry + zone_halfwidth]),
            np.column_stack([rx[::-1], ry[::-1] - zone_halfwidth]),
        ]
    )

    buildings, weights = _buildings_along_edges(graph, rng, spacing)

    hub_xy = _pick_site(graph, zone, np.array([0.22 * width, 0.9 * height]))
    evac_xy = _pick_site(graph, zone, np.array([0.8 * width, 0.92 * height]))

    return CityMap(
        name="siatka",
        crs="local-m",
        graph=graph,
        buildings_xy=buildings,
        building_weight=weights,
        hub_xy=hub_xy,
        evac_xy=evac_xy,
        hazard_zone=zone,
        georef=GeoRef.from_anchor(_ANCHOR_LON, _ANCHOR_LAT, 0.5 * width, 0.5 * height),
        water=[river],
        source="proceduralna siatka miejska (nie odwzorowuje rzeczywistego miasta)",
    )


def _buildings_along_edges(
    graph: StreetGraph, rng: np.random.Generator, spacing: float
) -> tuple[FloatArr, FloatArr]:
    """Budynki po obu stronach ulic; kilka skupisk „bloków” o większej wadze."""
    a = graph.node_xy[graph.edges[:, 0]]
    b = graph.node_xy[graph.edges[:, 1]]
    vec = b - a
    length = np.maximum(graph.edge_len, 1e-6)
    unit = vec / length[:, None]
    normal = np.column_stack([-unit[:, 1], unit[:, 0]])
    pts: list[FloatArr] = []
    for frac in (0.25, 0.5, 0.75):
        base = a + vec * frac
        for side in (1.0, -1.0):
            keep = np.asarray(rng.random(size=int(base.shape[0])) < 0.55)
            offset = rng.uniform(12.0, 20.0, size=int(keep.sum()))
            pts.append(base[keep] + normal[keep] * (side * offset)[:, None])
    buildings = np.vstack(pts)
    weights = np.ones(buildings.shape[0], dtype=np.float64)
    # bloki: budynki w promieniu 1,6 oczka od losowych centrów mieszczą wielokrotnie więcej osób
    lo = buildings.min(axis=0)
    hi = buildings.max(axis=0)
    for _ in range(4):
        centre = rng.uniform(lo + 0.15 * (hi - lo), hi - 0.15 * (hi - lo))
        near = np.hypot(buildings[:, 0] - centre[0], buildings[:, 1] - centre[1]) < 1.6 * spacing
        weights[near] = rng.uniform(6.0, 12.0)
    return buildings, weights


def _pick_site(graph: StreetGraph, zone: FloatArr, wanted: FloatArr) -> FloatArr:
    """Węzeł grafu najbliższy punktowi `wanted`, leżący poza strefą zagrożenia."""
    outside = ~points_in_polygon(graph.node_xy, zone)
    cand = np.flatnonzero(outside)
    d = np.hypot(graph.node_xy[cand, 0] - wanted[0], graph.node_xy[cand, 1] - wanted[1])
    return np.array(graph.node_xy[cand[int(np.argmin(d))]], dtype=np.float64)
