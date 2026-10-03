"""Testy poprawek po recenzji modelu: co uruchamia ewakuację, warianty przekazywania, wygasanie."""

from __future__ import annotations

import hashlib
import json

import numpy as np

from helpers import make_world
from sztafeta.engine.events import EventType
from sztafeta.engine.model import (
    Action,
    AgentState,
    BoolArr,
    Hazard,
    HelpCategory,
    IntArr,
    MsgType,
    Params,
    ReportKind,
    Role,
    Scenario,
)
from sztafeta.engine.sim import Simulation
from sztafeta.scenarios import load_preset

R = Role.RESIDENT


def _quiet(overrides: list[str] | None = None) -> tuple[Params, Scenario]:
    """Scenariusz testowy bez osi czasu: alerty wydajemy ręcznie."""
    params, scenario = load_preset("test-small", overrides=overrides or [])
    scenario.timeline.clear()
    return params, scenario


def _evacuations(sim: Simulation) -> tuple[int, int]:
    """(z aplikacją, bez aplikacji) – ilu mieszkańców ruszyło do punktu ewakuacji."""
    started = ~np.isnan(sim.agents.evac_start_t)
    return int((started & sim.agents.has_app).sum()), int((started & ~sim.agents.has_app).sum())


# ----------------------------------------------------------------------------- co uruchamia ewakuację


def test_alert_other_than_evacuate_triggers_no_evacuation() -> None:
    params, scenario = _quiet()
    sim = Simulation(params, scenario, 3)
    sim.issue_alert(Hazard.FLOOD, Action.SHELTER)
    sim.run(2400.0)
    summary = sim.metrics.summary(sim.alert_issued_t)
    assert summary["alert_reach_app"] > 50.0  # alert się rozszedł...
    assert _evacuations(sim) == (0, 0)  # ...ale nikt się nie ewakuuje, także „ze słyszenia”
    assert np.isnan(sim.agents.wom_t).all()
    assert np.isnan(sim.agents.evac_order_t).all()


def test_evacuate_alert_after_shelter_alert_still_evacuates() -> None:
    params, scenario = _quiet()
    sim = Simulation(params, scenario, 3)
    sim.issue_alert(Hazard.FLOOD, Action.SHELTER)
    sim.run(900.0)
    assert _evacuations(sim) == (0, 0)
    sim.issue_alert(Hazard.DAM_FAILURE, Action.EVACUATE, MsgType.UPDATE)
    sim.run(3600.0)
    with_app, without_app = _evacuations(sim)
    zone_app = int((sim.agents.in_zone & sim.agents.has_app & (sim.agents.role == int(R))).sum())
    assert with_app > 0.5 * zone_app  # wcześniejszy alert nie blokuje reakcji na „ewakuuj”
    assert without_app > 0


def test_cancel_stops_word_of_mouth_and_pending_reactions() -> None:
    params, scenario = _quiet(["behavior.reaction_median_s=3000", "behavior.reaction_sigma=0.01"])
    sim = Simulation(params, scenario, 3)
    sim.issue_alert(Hazard.FLOOD, Action.EVACUATE)
    sim.run(600.0)
    assert (~np.isnan(sim.agents.evac_order_t)).sum() > 20
    assert _evacuations(sim) == (0, 0)  # wszyscy jeszcze „się zbierają” (reakcja po ok. 50 min)
    sim.cancel_alert()
    sim.run(6000.0)
    ordered = ~np.isnan(sim.agents.evac_order_t)
    got_cancel = sim.router.alert_seq[:, 0] == 2
    assert not (ordered & got_cancel).any()  # kto dostał odwołanie, nie ma już „rozkazu ewakuacji”
    with_app, _ = _evacuations(sim)
    late = int((ordered & ~got_cancel & sim.agents.in_zone).sum())
    assert with_app <= late + 1  # ewakuują się najwyżej ci, do których odwołanie nie dotarło
    # po odwołaniu przekaz ustny od tych telefonów ustaje
    told_after = [e for e in sim.drain_events() if e.type == EventType.WORD_OF_MOUTH and e.t > 4000.0]
    assert len(told_after) <= late


# ----------------------------------------------------------------------------- przekaz ustny


def test_word_of_mouth_household_tier_and_neighbour_tier() -> None:
    params, scenario = _quiet(["behavior.wom_household_only=true"])
    house = Simulation(params, scenario, 5)
    house.issue_alert(Hazard.FLOOD, Action.EVACUATE)
    house.run(1800.0)
    ag = house.agents
    told = np.flatnonzero(~np.isnan(ag.wom_t))
    assert told.size > 0
    with_alert = set(ag.household[ag.has_app & ~np.isnan(ag.evac_order_t)].tolist())
    assert all(int(ag.household[a]) in with_alert for a in told)  # tylko domownicy osoby z alertem

    params2, scenario2 = _quiet()
    both = Simulation(params2, scenario2, 5)
    both.issue_alert(Hazard.FLOOD, Action.EVACUATE)
    both.run(1800.0)
    assert (~np.isnan(both.agents.wom_t)).sum() > told.size  # z sąsiadami dowiaduje się więcej osób


def test_evacuation_metric_splits_into_app_and_word_of_mouth() -> None:
    params, scenario = load_preset("test-small")
    sim = Simulation(params, scenario, 42)
    sim.run(3000.0)
    row = sim.metrics.rows[-1]
    assert row.evacuated_zone > 0
    assert abs(row.evacuated_zone - row.evacuated_zone_app - row.evacuated_zone_wom) < 0.01
    assert row.reports_zone_created + row.reports_outside_created == row.reports_created
    assert row.reports_zone_delivered + row.reports_outside_delivered == row.reports_delivered


# ----------------------------------------------------------------------------- warianty przekazywania


def test_couriers_only_mode_blocks_phone_to_phone_relay() -> None:
    params = Params()
    params.routing.phone_relay = False
    w = make_world([(0, 0), (30, 0), (60, 0), (90, 0)], [Role.HUB, R, R, Role.COURIER], params=params)
    p = w.router.issue_alert(w.alert(), 0, 0.0)
    w.steps(60)
    assert w.router.have[1, p]  # sąsiad huba dostaje alert od huba
    assert not w.router.have[2, p]  # ale nie podaje go dalej drugiemu mieszkańcowi
    assert not w.router.have[3, p]
    w.pos[3] = (45.0, 0.0)  # kurier podchodzi: w zasięgu obu mieszkańców
    w.steps(60)
    assert w.router.have[3, p] and w.router.have[2, p]  # kurier odbiera i przekazuje


def test_simulation_runs_without_couriers() -> None:
    params, scenario = load_preset("test-small", overrides=["population.n_couriers=0"])
    sim = Simulation(params, scenario, 2)
    sim.run(1500.0)
    assert sim.courier_ids.size == 0
    assert sim.metrics.summary(sim.alert_issued_t)["alert_reach_app"] > 0


# ----------------------------------------------------------------------------- wygasanie i determinizm


def test_expired_report_and_ack_are_not_sent_even_before_cleanup() -> None:
    w = make_world([(0, 0)] * 3, [R, Role.COURIER, Role.HUB])
    rep = w.router.create_report(0, ReportKind.SAFE, HelpCategory.NONE, 1, "u2uxyz1", 0.0)
    assert rep is not None
    expires = float(w.router.expires[rep])
    assert w.router.can_send(0, 1, rep, expires - 1.0)
    assert not w.router.can_send(0, 1, rep, expires)  # jeszcze przed `sweep`, a już nie wolno
    track = w.router.tracks[0]
    ack = w.router.issue_ack(w.ack(((track.report_id, 1),), t=0.0), 2, 0.0)
    assert w.router.can_send(2, 1, ack, 3599.0)
    assert not w.router.can_send(2, 1, ack, 3600.0)


def test_run_is_deterministic_when_candidate_pair_limit_is_active() -> None:
    def digest() -> tuple[str, int]:
        params, scenario = load_preset("test-small", overrides=["radio.max_candidate_pairs=4"])
        sim = Simulation(params, scenario, 9)
        capped = 0
        original = sim.radio._router.need_exchange

        def counting(ii: IntArr, jj: IntArr) -> BoolArr:
            nonlocal capped
            capped += int(ii.size == 4)
            return original(ii, jj)

        sim.radio._router.need_exchange = counting
        sim.run(1500.0)
        events = json.dumps([e.to_dict() for e in sim.drain_events()], sort_keys=True).encode()
        return hashlib.sha256(events).hexdigest(), capped

    first, capped = digest()
    second, _ = digest()
    assert capped > 20  # limit par rzeczywiście działał
    assert first == second


def test_need_help_state_is_not_overridden_by_later_alert() -> None:
    params, scenario = _quiet(["behavior.p_need_help_blackout=0.3"])
    sim = Simulation(params, scenario, 4)
    sim.network_down()
    sim.run(7300.0)
    needing = np.flatnonzero(sim.agents.state == int(AgentState.NEED_HELP))
    assert needing.size > 10
    sim.issue_alert(Hazard.FLOOD, Action.EVACUATE)
    sim.run(10800.0)
    assert (sim.agents.state[needing] == int(AgentState.NEED_HELP)).all()
    assert np.isnan(sim.agents.evac_start_t[needing]).all()
