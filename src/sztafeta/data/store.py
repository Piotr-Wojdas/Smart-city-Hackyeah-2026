"""Zapis i odczyt mapy z katalogu `data/<miejsce>/` (city.npz + meta.json).

Format jest celowo prosty: wczytanie nie wymaga osmnx ani geopandas, więc symulacja działa offline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from sztafeta.engine.geo import GeoRef
from sztafeta.engine.graph import StreetGraph
from sztafeta.engine.model import CityMap

_NPZ = "city.npz"
_META = "meta.json"


def city_exists(place_dir: Path) -> bool:
    return (place_dir / _NPZ).exists() and (place_dir / _META).exists()


def save_city(city: CityMap, place_dir: Path, meta: dict[str, Any]) -> None:
    """Zapisuje mapę. `meta` trafia do meta.json (źródło, licencja, data pobrania, parametry)."""
    place_dir.mkdir(parents=True, exist_ok=True)
    if city.water:
        water_xy = np.vstack(city.water)
        water_ptr = np.cumsum([0, *[line.shape[0] for line in city.water]])
    else:
        water_xy = np.empty((0, 2), dtype=np.float64)
        water_ptr = np.zeros(1, dtype=np.int64)
    np.savez_compressed(
        place_dir / _NPZ,
        node_xy=city.graph.node_xy.astype(np.float64),
        edges=city.graph.edges.astype(np.int32),
        buildings_xy=city.buildings_xy.astype(np.float64),
        building_weight=city.building_weight.astype(np.float64),
        hub_xy=city.hub_xy.astype(np.float64),
        evac_xy=city.evac_xy.astype(np.float64),
        hazard_zone=city.hazard_zone.astype(np.float64),
        water_xy=water_xy,
        water_ptr=np.asarray(water_ptr, dtype=np.int64),
        lon_c=np.asarray(city.georef.lon_c, dtype=np.float64),
        lat_c=np.asarray(city.georef.lat_c, dtype=np.float64),
    )
    full = {"name": city.name, "crs": city.crs, "source": city.source, **meta}
    (place_dir / _META).write_text(json.dumps(full, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_city(place_dir: Path) -> CityMap:
    meta = json.loads((place_dir / _META).read_text(encoding="utf-8"))
    with np.load(place_dir / _NPZ) as z:
        ptr = z["water_ptr"]
        water = [np.array(z["water_xy"][ptr[i] : ptr[i + 1]]) for i in range(len(ptr) - 1)]
        lon_c = z["lon_c"].tolist()
        lat_c = z["lat_c"].tolist()
        return CityMap(
            name=str(meta["name"]),
            crs=str(meta["crs"]),
            graph=StreetGraph(z["node_xy"], z["edges"].astype(np.int64)),
            buildings_xy=np.array(z["buildings_xy"]),
            building_weight=np.array(z["building_weight"]),
            hub_xy=np.array(z["hub_xy"]),
            evac_xy=np.array(z["evac_xy"]),
            hazard_zone=np.array(z["hazard_zone"]),
            georef=GeoRef(
                lon_c=(float(lon_c[0]), float(lon_c[1]), float(lon_c[2])),
                lat_c=(float(lat_c[0]), float(lat_c[1]), float(lat_c[2])),
            ),
            water=water,
            source=str(meta["source"]),
        )
