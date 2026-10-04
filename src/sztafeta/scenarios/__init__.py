"""Presety scenariuszy (YAML) i ich ładowanie do typów silnika."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from sztafeta.data.grid import make_grid_city
from sztafeta.engine.model import (
    Action,
    ActionKind,
    CityMap,
    Forgery,
    Hazard,
    MsgType,
    Params,
    Scenario,
    ScheduledAction,
)

PRESET_DIR = Path(__file__).parent / "presets"
DEFAULT_DATA_DIR = Path("data")


def list_presets() -> list[str]:
    return sorted(p.stem for p in PRESET_DIR.glob("*.yaml"))


def read_preset(name: str) -> dict[str, Any]:
    """Surowa zawartość presetu. `name` to nazwa wbudowanego presetu albo ścieżka do pliku YAML."""
    path = Path(name)
    if not path.suffix:
        path = PRESET_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Nie ma presetu „{name}”. Dostępne: {', '.join(list_presets())}")
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ValueError(f"Preset {path} musi być słownikiem YAML")
    return raw


def load_preset(
    name: str,
    overrides: Sequence[str] = (),
    data_dir: Path | None = None,
) -> tuple[Params, Scenario]:
    """Buduje parametry i scenariusz z presetu; `overrides` to napisy „sekcja.pole=wartość”."""
    raw = read_preset(name)
    params = params_from_dict(raw.get("params", {}))
    apply_overrides(params, overrides)
    city = build_city(raw.get("map", {"kind": "grid"}), data_dir or DEFAULT_DATA_DIR)
    sc = raw.get("scenario", {})
    scenario = Scenario(
        name=str(raw.get("name", Path(name).stem)),
        city=city,
        timeline=[_parse_action(item) for item in sc.get("timeline", [])],
        start_iso=str(sc.get("start", "2024-09-15T06:00:00+02:00")),
        hub_name=str(sc.get("hub_name", "Urząd / PCZK")),
        evac_name=str(sc.get("evac_name", "Punkt ewakuacji")),
        incident=str(sc.get("incident", "INC-1")),
    )
    return params, scenario


def build_city(cfg: Mapping[str, Any], data_dir: Path) -> CityMap:
    """Mapa z presetu: dane OSM z `data/`, a gdy ich nie ma – proceduralna siatka (fallback)."""
    kind = str(cfg.get("kind", "grid"))
    grid_args = dict(cfg.get("grid", {}))
    if kind == "osm":
        from sztafeta.data.store import city_exists, load_city

        place_dir = data_dir / str(cfg["dir"])
        if city_exists(place_dir):
            return load_city(place_dir)
        city = make_grid_city(**grid_args)
        city.source = f"{city.source}; FALLBACK – brak danych OSM w {place_dir.as_posix()}"
        return city
    if kind == "grid":
        return make_grid_city(**grid_args)
    raise ValueError(f"Nieznany rodzaj mapy: {kind}")


def _parse_action(item: Mapping[str, Any]) -> ScheduledAction:
    t = float(item["t_min"]) * 60.0 if "t_min" in item else float(item["t"])
    act = ScheduledAction(t=t, kind=ActionKind(str(item["kind"])), label=str(item.get("label", "")))
    if "hazard" in item:
        act.hazard = Hazard[str(item["hazard"])]
    if "action" in item:
        act.action = Action[str(item["action"])]
    if "msg_type" in item:
        act.msg_type = MsgType[str(item["msg_type"])]
    if "forgery" in item:
        act.forgery = Forgery[str(item["forgery"])]
    return act


# --------------------------------------------------------------------------- parametry <-> słownik


def params_from_dict(data: Mapping[str, Any]) -> Params:
    params = Params()
    _fill(params, data, "")
    return params


def params_to_dict(params: Params) -> dict[str, Any]:
    out: dict[str, Any] = _plain(dataclasses.asdict(params))
    return out


def apply_overrides(params: Params, overrides: Sequence[str]) -> None:
    """Nadpisuje pola parametrów, np. „radio.range_m=80” albo „behavior.adoption=0.5”."""
    for item in overrides:
        if "=" not in item:
            raise ValueError(f"Nadpisanie musi mieć postać sekcja.pole=wartość, a jest: {item}")
        key, text = item.split("=", 1)
        nested: dict[str, Any] = {}
        cur = nested
        parts = key.strip().split(".")
        for part in parts[:-1]:
            cur[part] = {}
            cur = cur[part]
        cur[parts[-1]] = yaml.safe_load(text)
        _fill(params, nested, "")


def _fill(obj: Any, data: Mapping[str, Any], path: str) -> None:
    names = {f.name for f in dataclasses.fields(obj)}
    for key, value in data.items():
        if key not in names:
            raise ValueError(f"Nieznany parametr: {path}{key}")
        current = getattr(obj, key)
        if dataclasses.is_dataclass(current):
            if not isinstance(value, Mapping):
                raise ValueError(f"Parametr {path}{key} jest sekcją, a podano wartość")
            _fill(current, value, f"{path}{key}.")
        else:
            setattr(obj, key, _coerce(value, current, f"{path}{key}"))


def _coerce(value: Any, current: Any, name: str) -> Any:
    try:
        if isinstance(current, bool):
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "tak", "yes")
            return bool(value)
        if isinstance(current, int):
            return int(value)
        if isinstance(current, float):
            return float(value)
        if isinstance(current, tuple):
            return tuple(float(v) for v in value)
        return str(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Zła wartość parametru {name}: {value!r}") from exc


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_plain(v) for v in value]
    return value
