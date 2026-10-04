from __future__ import annotations

from helpers import World, make_world
from sztafeta.engine.events import EventType
from sztafeta.engine.model import HelpCategory, Params, ReportKind, Role

R = Role.RESIDENT


def test_no_contact_out_of_range() -> None:
    w = make_world([(0, 0), (41, 0)], [Role.HUB, R])
    w.router.issue_alert(w.alert(), 0, 0.0)
    w.steps(60)
    assert w.radio.n_contacts == 0
    assert not w.router.have[1].any()


def test_alert_needs_setup_time_before_it_arrives() -> None:
    w = make_world([(0, 0), (39, 0)], [Role.HUB, R])
    p = w.router.issue_alert(w.alert(), 0, 0.0)
    radio = w.params.radio
    # przed upływem najkrótszego czasu zestawienia i wymiany summary vector nic nie przechodzi
    w.steps(int(radio.setup_min_s + radio.summary_vector_s))
    assert w.radio.n_contacts == 1
    assert not w.router.have[1, p]
    w.steps(int(radio.setup_max_s) + 3)
    assert w.router.have[1, p]
    assert not w.radio.links  # po wymianie połączenie jest zamykane
    ends = [e for e in w.events.drain() if e.type == EventType.CONTACT]
    assert [e.data["reason"] for e in ends] == ["done"]


def test_contact_broken_during_setup_delivers_nothing() -> None:
    w = make_world([(0, 0), (30, 0)], [Role.HUB, R])
    p = w.router.issue_alert(w.alert(), 0, 0.0)
    w.steps(2)
    assert len(w.radio.links) == 1
    w.pos[1] = (500.0, 0.0)  # urządzenie wychodzi z zasięgu w trakcie zestawiania
    w.steps(20)
    assert not w.router.have[1, p]
    assert w.radio.n_interrupted == 1
    ends = [e for e in w.events.drain() if e.type == EventType.CONTACT]
    assert [e.data["reason"] for e in ends] == ["out_of_range"]


def _courier_with_reports(n_reports: int) -> tuple[World, int]:
    """Kurier (przy hubie) niosący po jednym zgłoszeniu od `n_reports` odległych mieszkańców."""
    params = Params()
    params.radio.setup_min_s = params.radio.setup_max_s = 1.0
    params.radio.summary_vector_s = 0.0
    far = [(1000.0 + 100.0 * k, 0.0) for k in range(n_reports)]
    courier = n_reports
    w = make_world([*far, (0.0, 0.0), (10.0, 0.0)], [R] * n_reports + [Role.COURIER, Role.HUB], params=params)
    for agent in range(n_reports):
        p = w.router.create_report(agent, ReportKind.SAFE, HelpCategory.NONE, 1, "u2uxyz1", 0.0)
        assert p is not None
        w.router.transfer(agent, courier, p, 0.0)
    size = int(w.router.size[0])
    assert size > 100  # zgłoszenie ma realny rozmiar: klucz 32 B + podpis 64 B + pola
    params.radio.throughput_bps = float(size)  # dokładnie jedno zgłoszenie na sekundę
    return w, courier


def test_throughput_limits_packets_per_second() -> None:
    w, _ = _courier_with_reports(6)
    w.steps(1)  # t=0: początek zestawiania połączenia
    assert len(w.router.deliveries) == 0
    w.steps(1)  # t=1: połączenie gotowe, budżet wystarcza na jeden pakiet
    assert len(w.router.deliveries) == 1
    w.steps(3)
    assert len(w.router.deliveries) == 4
    w.steps(5)
    assert len(w.router.deliveries) == 6
    assert not w.radio.links


def test_transfer_is_cut_when_contact_breaks() -> None:
    w, courier = _courier_with_reports(6)
    w.steps(3)
    assert len(w.router.deliveries) == 2
    w.pos[courier] = (900.0, 900.0)  # kurier odjeżdża w połowie przekazywania
    w.steps(10)
    assert len(w.router.deliveries) == 2  # reszta nie dotarła
    assert w.radio.n_interrupted == 1
    ends = [e for e in w.events.drain() if e.type == EventType.CONTACT]
    assert ends[-1].data["reason"] == "out_of_range" and ends[-1].data["packets"] == 2


def test_duty_cycle_blocks_contact_while_asleep() -> None:
    params = Params()
    w = make_world([(0, 0), (10, 0)], [Role.HUB, R], params=params, always_awake=False)
    w.router.issue_alert(w.alert(), 0, 0.0)
    w.radio._update_windows(0.0)
    start = float(w.radio._win_start[1])
    assert 0.0 <= start <= params.radio.scan_period_s - params.radio.scan_window_s
    asleep = int(start)  # całe sekundy przed początkiem okna
    w.steps(asleep)
    assert w.radio.n_contacts == 0
    w.steps(int(start) + 2 - asleep)
    assert w.radio.n_contacts == 1
    # po zestawieniu połączenie trwa mimo końca okna skanowania
    w.steps(int(params.radio.scan_window_s + params.radio.setup_max_s) + 3)
    assert w.router.have[1].any()


def test_duty_cycle_window_is_redrawn_every_cycle() -> None:
    w = make_world([(0, 0), (10, 0)], [R, R], always_awake=False)
    starts = []
    for cycle in range(6):
        t = cycle * w.params.radio.scan_period_s
        w.radio._update_windows(t)
        starts.append(float(w.radio._win_start[0]) - t)
    assert len({round(s, 6) for s in starts}) > 1
    assert all(0.0 <= s <= 50.0 for s in starts)


def test_device_without_app_or_battery_never_connects() -> None:
    w = make_world([(0, 0), (10, 0), (15, 0)], [Role.HUB, R, R], has_app=[True, False, True])
    w.agents.battery[2] = 0.0
    w.radio.on[2] = False
    w.router.issue_alert(w.alert(), 0, 0.0)
    w.steps(40)
    assert w.radio.n_contacts == 0


def test_link_limit_per_device() -> None:
    params = Params()
    params.radio.max_links_resident = 1
    params.radio.max_links_hub = 2
    w = make_world([(0, 0), (5, 0), (5, 5), (0, 5)], [Role.HUB, R, R, R], params=params)
    w.router.issue_alert(w.alert(), 0, 0.0)
    w.steps(1)
    assert len(w.radio.links) == 2  # hub ma tylko dwa wolne połączenia
    assert w.radio.n_links[0] == 2
    assert (w.radio.n_links <= w.radio.max_links).all()
    w.steps(40)
    assert w.router.have[1:, 0].all()  # ostatecznie alert dociera do wszystkich


def test_baseline_only_talks_to_hub() -> None:
    params = Params()
    params.routing.relay_enabled = False
    w = make_world([(0, 0), (30, 0), (60, 0)], [Role.HUB, R, R], params=params)
    p = w.router.issue_alert(w.alert(), 0, 0.0)
    w.steps(60)
    assert w.router.have[1, p]  # w zasięgu huba
    assert not w.router.have[2, p]  # 60 m od huba: bez sztafety alert nie dociera
    relay = make_world([(0, 0), (30, 0), (60, 0)], [Role.HUB, R, R])
    p2 = relay.router.issue_alert(relay.alert(), 0, 0.0)
    relay.steps(60)
    assert relay.router.have[2, p2]  # ze sztafetą dociera przez sąsiada


def test_battery_drains_and_dead_phone_leaves_network() -> None:
    params = Params()
    w = make_world([(0, 0), (10, 0)], [Role.HUB, R], params=params)
    w.agents.battery[1] = 0.002
    w.steps(3)
    assert w.agents.battery[1] == 0.0
    assert not w.radio.on[1]
    assert w.agents.battery[0] == 100.0  # hub ma zasilanie
    dead = [e for e in w.events.drain() if e.type == EventType.BATTERY_DEAD]
    assert [e.agent for e in dead] == [1]
