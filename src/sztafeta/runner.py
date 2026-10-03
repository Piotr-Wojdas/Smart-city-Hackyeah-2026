"""Uruchomienie symulacji z presetu i zapis wyników (warstwa między CLI a silnikiem)."""

from __future__ import annotations

import dataclasses
import hashlib
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Any

from sztafeta.engine.model import Params, Scenario
from sztafeta.engine.sim import Simulation
from sztafeta.io.writer import RunWriter, code_version
from sztafeta.scenarios import AREA_CITY, AREA_ZONE, load_preset, params_to_dict

BASELINE_OVERRIDE = "routing.relay_enabled=false"


@dataclass(slots=True)
class RunResult:
    run_id: str
    out_dir: Path | None
    summary: dict[str, Any]
    wall_s: float
    map_source: str


def _plain_enum(value: Any) -> Any:
    """Wyliczenia do YAML: StrEnum jako wartość (np. „issue_alert”), IntEnum jako nazwa (np. „FLOOD”)."""
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, IntEnum):
        return value.name
    return value


def make_run_id(preset: str, seed: int, baseline: bool, overrides: Sequence[str]) -> str:
    """Deterministyczny identyfikator: te same ustawienia zawsze trafiają do tego samego katalogu."""
    run_id = f"{Path(preset).stem}_s{seed}"
    if baseline:
        run_id += "_baseline"
    if overrides:
        digest = hashlib.sha256("|".join(sorted(overrides)).encode()).hexdigest()[:6]
        run_id += f"_{digest}"
    return run_id


def build(
    preset: str, seed: int, overrides: Sequence[str] = (), baseline: bool = False
) -> tuple[Simulation, Params, Scenario]:
    """Tworzy symulację z presetu. `baseline` wyłącza przekazywanie między telefonami."""
    all_overrides = [*overrides, BASELINE_OVERRIDE] if baseline else list(overrides)
    params, scenario = load_preset(preset, all_overrides)
    return Simulation(params, scenario, seed), params, scenario


def run_once(
    preset: str,
    seed: int = 42,
    overrides: Sequence[str] = (),
    baseline: bool = False,
    out_root: Path | None = Path("results"),
    until: float | None = None,
    progress: Callable[[float, float], None] | None = None,
) -> RunResult:
    """Jedno uruchomienie. Gdy `out_root` jest None, niczego nie zapisuje (tryb przeglądu parametrów)."""
    sim, params, scenario = build(preset, seed, overrides, baseline)
    run_id = make_run_id(preset, seed, baseline, overrides)
    end = params.duration_s if until is None else min(until, params.duration_s)
    info: dict[str, Any] = {
        "run_id": run_id,
        "preset": Path(preset).stem,
        "preset_source": preset,
        "seed": seed,
        "baseline": baseline,
        "duration_s": end,
        # kogo dotyczy alert: mieszkańców strefy zagrożenia albo – gdy jej nie ma – całego miasta
        "area": AREA_ZONE if scenario.city.has_zone else AREA_CITY,
    }
    started = time.perf_counter()

    if out_root is None:
        sim.run(end)
        summary = {**info, **sim.metrics.summary(sim.alert_issued_t)}
        return RunResult(run_id, None, summary, time.perf_counter() - started, scenario.city.source)

    writer = RunWriter(out_root / run_id)
    writer.write_params(
        {
            **info,
            "overrides": list(overrides),
            "code_version": code_version(),
            "scenario": {
                "name": scenario.name,
                "map": scenario.city.name,
                "map_source": scenario.city.source,
                "crs": scenario.city.crs,
                "start": scenario.start_iso,
                "incident": scenario.incident,
                "timeline": [
                    {k: _plain_enum(v) for k, v in dataclasses.asdict(act).items()}
                    for act in scenario.timeline
                ],
            },
            "params": params_to_dict(params),
        }
    )
    snap_dt = params.output.snapshot_interval_s
    next_snap = 0.0
    next_report = 0.0
    while sim.t < end - 1e-9:
        if sim.t >= next_snap:
            writer.add_snapshot(sim)
            next_snap = sim.t + snap_dt
        sim.step()
        if len(sim.events) >= 20_000:
            writer.write_events(sim.drain_events())
        if progress is not None and sim.t >= next_report:
            progress(sim.t, end)
            next_report = sim.t + end / 20.0
    sim.sample_metrics()
    writer.add_snapshot(sim)
    summary = writer.finish(sim, info)
    return RunResult(run_id, writer.out_dir, summary, time.perf_counter() - started, scenario.city.source)
