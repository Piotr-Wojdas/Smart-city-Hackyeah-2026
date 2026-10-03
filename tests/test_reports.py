"""Kurier Danych do Sztabu: zgłoszenia, kurierzy, hub, PCZK, potwierdzenia."""

from __future__ import annotations

import math

import numpy as np
import pytest

from helpers import make_world
from sztafeta.engine.events import Event, EventType
from sztafeta.engine.model import AgentState, HelpCategory, Params, ReportKind, Role, Scenario
from sztafeta.engine.pczk import Pczk
from sztafeta.engine.sim import FLAG_REPORT_ACKED, FLAG_REPORT_DELIVERED, Simulation
from sztafeta.scenarios import load_preset

R = Role.RESIDENT


@pytest.fixture(scope="module")
def finished() -> tuple[Simulation, list[Event]]:
    params, scenario = load_preset("test-small")
    sim = Simulation(params, scenario, 42)
    sim.run()
    return sim, sim.drain_events()


def test_reports_travel_to_pczk_via_couriers(finished: tuple[Simulation, list[Event]]) -> None:
    sim, events = finished
    tracks = sim.router.tracks
    delivered = [tr for tr in tracks if not math.isnan(tr.delivered_t)]
    assert len(tracks) > 20
    assert len(delivered) > 0.5 * len(tracks)
    assert {tr.kind for tr in tracks} == {ReportKind.SAFE, ReportKind.NEED_HELP}
    for tr in delivered:
        assert tr.delivered_t >= tr.created_t
        if not math.isnan(tr.picked_up_t):
            # kurier mógł zabrać kopię także po tym, jak autor sam oddał zgłoszenie w hubie
            assert tr.created_t <= tr.picked_up_t
    carriers = [sim.agents.role[e.peer] for e in events if e.type == EventType.REPORT_DELIVERED]
    assert sum(1 for role in carriers if role == Role.COURIER) > 0.8 * len(carriers)


def test_pczk_dashboard_is_deduplicated_and_sorted(finished: tuple[Simulation, list[Event]]) -> None:
    sim, _ = finished
    board = sim.pczk_dashboard()
    ids = [r["report_id"] for r in board["reports"]]
    assert len(ids) == len(set(ids))
    delivered = sum(1 for tr in sim.router.tracks if not math.isnan(tr.delivered_t))
    assert board["counters"]["reports"] == delivered == len(ids)
    # najpierw „potrzebuję pomocy” od najpilniejszych, potem „bezpieczni”
    keys = [(r["kind"] != "NEED_HELP", -r["urgency"]) for r in board["reports"]]
    assert keys == sorted(keys)
    counters = board["counters"]
    assert counters["safe_reports"] + counters["need_help_reports"] == counters["reports"]
    assert counters["safe_persons"] + counters["need_help_persons"] <= sim.params.population.n_residents
    assert all(r["delay_s"] >= 0 for r in board["reports"])


def test_acks_return_to_reporters_after_delivery(finished: tuple[Simulation, list[Event]]) -> None:
    sim, events = finished
    acked = [tr for tr in sim.router.tracks if not math.isnan(tr.acked_t)]
    assert len(acked) > 5
    for tr in acked:
        assert not math.isnan(tr.delivered_t)
        assert tr.acked_t > tr.delivered_t  # potwierdzenie musi fizycznie wrócić z huba
    issued = [e for e in events if e.type == EventType.ACK_ISSUED]
    assert sum(int(e.data["reports"]) for e in issued) >= len(acked)
    assert all(int(e.data["reports"]) <= sim.params.routing.ack_batch_size for e in issued)
    assert min(e.t for e in events if e.type == EventType.ACK_RECEIVED) > issued[0].t
    flags = sim.flags()
    assert int(((flags & FLAG_REPORT_ACKED) > 0).sum()) == len(acked)
    assert ((flags & FLAG_REPORT_ACKED) <= (flags & FLAG_REPORT_DELIVERED) * 2).all()
    summary = sim.metrics.summary(sim.alert_issued_t)
    assert summary["acks_received"] == len(acked)


def test_need_help_people_stay_home_and_safe_people_are_at_evac_point(
    finished: tuple[Simulation, list[Event]],
) -> None:
    sim, _ = finished
    ag = sim.agents
    need = np.flatnonzero((ag.state == int(AgentState.NEED_HELP)) & ~sim.mobility.moving)
    assert need.size > 0
    assert np.allclose(sim.mobility.pos[need], ag.home_xy[need])
    safe = np.flatnonzero(ag.state == int(AgentState.SAFE))
    evac = sim.scenario.city.evac_xy
    dist = np.hypot(sim.mobility.pos[safe, 0] - evac[0], sim.mobility.pos[safe, 1] - evac[1])
    assert safe.size > 0 and (dist <= sim.params.population.evac_spread_m + 1e-6).all()
    assert ag.in_zone[safe].all()  # ewakuują się tylko mieszkańcy strefy


def test_baseline_reports_arrive_only_in_person() -> None:
    params, scenario = load_preset("test-small", overrides=["routing.relay_enabled=false"])
    sim = Simulation(params, scenario, 42)
    sim.run()
    events = sim.drain_events()
    assert not any(e.type == EventType.REPORT_PICKED_UP for e in events)
    delivered = [e for e in events if e.type == EventType.REPORT_DELIVERED]
    for e in delivered:
        track = sim.router.tracks[sim.router.track_of_agent[e.peer]]
        assert track.reporter == e.peer  # zgłoszenie oddał osobiście jego autor
    relay_params, relay_scenario = load_preset("test-small")
    relay = Simulation(relay_params, relay_scenario, 42)
    relay.run()
    base_n = sim.metrics.rows[-1].reports_delivered
    assert base_n < relay.metrics.rows[-1].reports_delivered


def test_report_needs_app_and_working_phone(small: tuple[Params, Scenario]) -> None:
    params, scenario = small
    sim = Simulation(params, scenario, 1)
    ag = sim.agents
    no_app = int(np.flatnonzero(~ag.has_app)[0])
    with_app = int(np.flatnonzero(ag.has_app & (ag.role == int(Role.RESIDENT)))[0])
    assert sim.submit_report(no_app, ReportKind.SAFE) is None
    pid = sim.submit_report(with_app, ReportKind.NEED_HELP, HelpCategory.MEDICAL, 3, sensitive_len=64)
    assert pid is not None
    track = sim.router.tracks[sim.router.track_of_agent[with_app]]
    assert track.urgency == 3 and track.category == HelpCategory.MEDICAL
    sim.radio.on[with_app] = False
    assert sim.submit_report(with_app, ReportKind.SAFE) is None


# ----------------------------------------------------------------------------- PCZK w izolacji


def _pczk(batch: int = 32) -> tuple[Pczk, object]:
    params = Params()
    params.routing.ack_batch_size = batch
    params.routing.max_own_reports_per_hour = 1000
    n = 80
    w = make_world([(0.0, 0.0)] * n + [(5.0, 0.0)], [R] * n + [Role.HUB], params=params)
    return Pczk(params.routing, w.keys.issuer, w.cert, w.router, w.events, w.hub), w


def test_pczk_keeps_newest_version_only() -> None:
    pczk, w = _pczk()
    router = w.router  # type: ignore[attr-defined]
    p1 = router.create_report(0, ReportKind.NEED_HELP, HelpCategory.MEDICAL, 2, "u2uxyz1", 0.0)
    p2 = router.create_report(0, ReportKind.NEED_HELP, HelpCategory.MEDICAL, 3, "u2uxyz1", 60.0)
    v1, v2 = router.packets[p1], router.packets[p2]
    pczk.receive(v1, 0, 100.0)
    pczk.receive(v2, 0, 200.0)
    pczk.receive(v1, 0, 300.0)  # spóźniona starsza wersja jest ignorowana
    board = pczk.dashboard(400.0)
    assert len(board["reports"]) == 1
    entry = board["reports"][0]
    assert entry["version"] == 2 and entry["urgency"] == 3
    assert entry["received_t"] == 100.0 and entry["updated_t"] == 200.0
    assert board["counters"]["need_help_critical"] == 1


def test_pczk_acks_in_batches_on_its_service_cycle() -> None:
    pczk, w = _pczk(batch=32)
    router = w.router  # type: ignore[attr-defined]
    events = w.events  # type: ignore[attr-defined]
    for agent in range(70):
        p = router.create_report(agent, ReportKind.SAFE, HelpCategory.NONE, 1, "u2uxyz1", 0.0)
        pczk.receive(router.packets[p], agent, 10.0)
    events.drain()
    pczk.step(60.0)  # przed końcem cyklu obsługi nic nie wychodzi
    assert pczk.acks_issued == 0
    pczk.step(120.0)
    issued = [e for e in events.drain() if e.type == EventType.ACK_ISSUED]
    assert [e.data["reports"] for e in issued] == [32, 32, 6]
    assert pczk.acks_issued == 3
    assert all(entry.acked for entry in pczk.entries.values())
    assert int(router.have[w.hub].sum()) == 3  # type: ignore[attr-defined]
    pczk.step(240.0)
    assert pczk.acks_issued == 3  # brak nowych zgłoszeń = brak nowych potwierdzeń
