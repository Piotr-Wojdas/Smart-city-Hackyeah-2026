"""Testy całego scenariusza na małej siatce: sztafeta alertu, fałszywki, wariant bazowy."""

from __future__ import annotations

import numpy as np

from sztafeta.engine.events import EventType
from sztafeta.engine.model import ActionKind, Params, Scenario
from sztafeta.engine.sim import FLAG_ALERT, FLAG_FAKE_SEEN, Simulation
from sztafeta.scenarios import load_preset


def test_signed_alert_spreads_phone_to_phone(small: tuple[Params, Scenario]) -> None:
    params, scenario = small
    sim = Simulation(params, scenario, 42)
    sim.run(2400.0)
    events = sim.drain_events()
    received = [e for e in events if e.type == EventType.ALERT_RECEIVED]
    summary = sim.metrics.summary(sim.alert_issued_t)
    assert summary["alert_reach_app"] > 80.0
    assert summary["t50_app_s"] is not None
    # sztafeta, a nie zasięg huba: większość odebrała alert po więcej niż jednym skoku
    hops = np.array([e.data["hops"] for e in received])
    assert (hops > 1).mean() > 0.5
    # nikt nie dostał alertu przed jego wydaniem
    assert min(e.t for e in received) >= 120.0
    assert not any(e.type == EventType.EVACUATION_START and e.t < 120.0 for e in events)
    assert summary["evac_started_zone"] > 30.0


def test_fake_alert_alone_never_triggers_anything(small: tuple[Params, Scenario]) -> None:
    params, scenario = small
    scenario.timeline = [a for a in scenario.timeline if a.kind != ActionKind.ISSUE_ALERT]
    sim = Simulation(params, scenario, 42)
    sim.run(2400.0)
    events = sim.drain_events()
    summary = sim.metrics.summary(sim.alert_issued_t)
    assert summary["fake_received_devices"] > 0
    assert summary["fake_verified_devices"] == 0
    assert summary["alert_reach_app"] == 0.0
    assert summary["evac_started_zone"] == 0.0
    assert not any(e.type in (EventType.ALERT_RECEIVED, EventType.EVACUATION_START) for e in events)
    rejected = [e for e in events if e.type == EventType.ALERT_REJECTED]
    assert len(rejected) == summary["fake_received_devices"]
    assert {e.data["reason"] for e in rejected} == {"bad_signature"}
    flags = sim.flags()
    assert int(((flags & FLAG_FAKE_SEEN) > 0).sum()) == summary["fake_received_devices"]
    assert not (flags & FLAG_ALERT).any()
    # fałszywka nie rozchodzi się sztafetą: ma ją w buforze tylko troll
    fake = next(a for a in sim.alerts_view() if not a["verified"])
    assert fake["holders"] == len(sim.troll_ids)


def test_baseline_reaches_fewer_people_than_relay() -> None:
    params, scenario = load_preset("test-small")
    relay = Simulation(params, scenario, 7)
    relay.run(1800.0)
    base_params, base_scenario = load_preset("test-small", overrides=["routing.relay_enabled=false"])
    base = Simulation(base_params, base_scenario, 7)
    base.run(1800.0)
    # ten sam seed = ta sama populacja
    assert np.array_equal(relay.agents.home_xy, base.agents.home_xy)
    assert np.array_equal(relay.agents.has_app, base.agents.has_app)
    r = relay.metrics.summary(relay.alert_issued_t)
    b = base.metrics.summary(base.alert_issued_t)
    assert b["alert_reach_app"] < r["alert_reach_app"]
    assert b["alert_reach_app"] < 40.0
    assert b["fake_received_devices"] == 0  # bez kanału P2P troll nie ma jak rozsyłać


def test_metrics_are_sampled_on_schedule(small: tuple[Params, Scenario]) -> None:
    params, scenario = small
    sim = Simulation(params, scenario, 3)
    sim.run(300.0)
    times = [row.t for row in sim.metrics.rows]
    assert times[0] == 0.0 and times[-1] == 300.0
    assert times == sorted(set(times))
    assert len(times) == 31
    reach = [row.alert_reach_app for row in sim.metrics.rows]
    assert reach == sorted(reach)  # zasięg nie maleje
