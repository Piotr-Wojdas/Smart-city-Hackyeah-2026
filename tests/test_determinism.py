from __future__ import annotations

import hashlib
import json
import subprocess
import sys

import numpy as np

from sztafeta.engine.model import Params, Scenario
from sztafeta.engine.sim import Simulation
from sztafeta.scenarios import load_preset


def _digest(sim: Simulation) -> str:
    payload = json.dumps(sim.snapshot(), sort_keys=True).encode()
    events = json.dumps([e.to_dict() for e in sim.drain_events()], sort_keys=True).encode()
    return hashlib.sha256(payload + events).hexdigest()


def _run(seed: int, until: float) -> Simulation:
    params, scenario = load_preset("test-small")
    sim = Simulation(params, scenario, seed)
    sim.run(until)
    return sim


def test_same_seed_gives_identical_run() -> None:
    assert _digest(_run(11, 1500.0)) == _digest(_run(11, 1500.0))


def test_different_seed_gives_different_run() -> None:
    assert _digest(_run(11, 1500.0)) != _digest(_run(12, 1500.0))


def test_population_matches_parameters(small: tuple[Params, Scenario]) -> None:
    params, scenario = small
    sim = Simulation(params, scenario, 1)
    ag = sim.agents
    pop = params.population
    assert ag.n == pop.n_residents + pop.n_couriers + 1
    assert int(ag.residents.sum()) == pop.n_residents
    share = ag.has_app[: pop.n_residents].mean()
    assert abs(share - params.behavior.adoption) < 0.08
    assert ag.in_zone.any() and not ag.in_zone.all()
    # każda osoba jest liczona w zgłoszeniach najwyżej raz
    app_res = ag.has_app[: pop.n_residents]
    assert int(ag.report_persons[: pop.n_residents][app_res].sum()) <= pop.n_residents


def test_residents_walk_and_come_back(small: tuple[Params, Scenario]) -> None:
    params, scenario = small
    scenario.timeline.clear()
    sim = Simulation(params, scenario, 5)
    moved = np.zeros(sim.agents.n, dtype=bool)
    for _ in range(1800):
        sim.step()
        moved |= sim.mobility.moving
    assert moved.sum() > 10
    idle = ~sim.mobility.moving & sim.agents.residents
    assert np.allclose(sim.mobility.pos[idle], sim.agents.home_xy[idle])


def test_snapshot_is_json_serializable(small: tuple[Params, Scenario]) -> None:
    params, scenario = small
    sim = Simulation(params, scenario, 2)
    sim.run(60.0)
    snap = json.loads(json.dumps(sim.snapshot()))
    static = json.loads(json.dumps(sim.describe()))
    assert snap["schema"] == "sztafeta.snapshot/1"
    assert len(snap["agents"]["x"]) == static["agents"]["n"]


def test_engine_does_not_import_presentation_layers() -> None:
    code = (
        "import sys, sztafeta.engine.sim\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in ('matplotlib', 'pandas', 'typer')"
        " or m.startswith(('sztafeta.viz', 'sztafeta.io', 'sztafeta.cli'))]\n"
        "print(','.join(bad))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == ""
