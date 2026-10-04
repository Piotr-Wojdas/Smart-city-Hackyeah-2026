from __future__ import annotations

import math

import numpy as np

from helpers import World, make_world
from sztafeta.engine.events import EventType
from sztafeta.engine.model import HelpCategory, PacketKind, Params, ReportKind, Role

R = Role.RESIDENT


def _pair(i: int, j: int) -> tuple[np.ndarray, np.ndarray]:
    return np.array([i], dtype=np.int64), np.array([j], dtype=np.int64)


def _report(
    w: World, agent: int, kind: ReportKind = ReportKind.SAFE, t: float = 0.0, urgency: int = 1
) -> int:
    p = w.router.create_report(agent, kind, HelpCategory.NONE, urgency, "u2uxyz1", t)
    assert p is not None
    return int(p)


# ----------------------------------------------------------------------------- alert: routing epidemiczny


def test_alert_spreads_hop_by_hop_and_counts_hops() -> None:
    w = make_world([(0, 0), (10, 0), (20, 0)], [Role.HUB, R, R])
    p = w.router.issue_alert(w.alert(), 0, 0.0)
    assert w.router.need_exchange(*_pair(0, 1))[0]
    assert not w.router.need_exchange(*_pair(1, 2))[0]  # nikt z tej pary jeszcze nic nie ma
    w.router.transfer(0, 1, p, 1.0)
    w.router.transfer(1, 2, p, 2.0)
    assert w.router.have[:, p].tolist() == [True, True, True]
    assert w.router.hops[:, p].tolist() == [0, 1, 2]
    assert not w.router.need_exchange(*_pair(1, 2))[0]  # obie strony już znają pakiet
    assert w.router.new_alerts == [(0, p, -1), (1, p, 0), (2, p, 1)]  # (odbiorca, pakiet, nadawca)


def test_ttl_limits_number_of_hops() -> None:
    w = make_world([(0, 0), (10, 0), (20, 0)], [Role.HUB, R, R])
    p = w.router.issue_alert(w.alert(ttl_hops=1), 0, 0.0)
    w.router.transfer(0, 1, p, 1.0)
    assert w.router.have[1, p]
    # urządzenie 1 ma pakiet po 1 skoku = wyczerpany TTL, więc go nie oferuje
    assert not w.router.need_exchange(*_pair(1, 2))[0]
    pk, _ = w.router.plan(1, 2)
    assert pk.size == 0


def test_expired_alert_is_removed_and_not_forwarded() -> None:
    w = make_world([(0, 0), (10, 0), (20, 0)], [Role.HUB, R, R])
    p = w.router.issue_alert(w.alert(lifetime=100.0), 0, 0.0)
    w.router.transfer(0, 1, p, 1.0)
    w.router.sweep(100.0)
    assert not w.router.have[:, p].any()
    assert not w.router.can_send(1, 2, p, 0.0)
    assert not w.router.need_exchange(*_pair(1, 2))[0]


def test_newer_seq_replaces_older_and_old_is_rejected_as_replay() -> None:
    w = make_world([(0, 0), (10, 0), (20, 0)], [Role.HUB, R, R])
    p1 = w.router.issue_alert(w.alert(seq=1), 0, 0.0)
    w.router.transfer(0, 1, p1, 1.0)
    p2 = w.router.issue_alert(w.alert(seq=2, t=5.0), 0, 5.0)
    assert not w.router.have[0, p1]  # hub sam zastąpił starszą wersję
    w.router.transfer(0, 1, p2, 6.0)
    assert w.router.have[1, p2] and not w.router.have[1, p1]
    assert w.router.alert_seq[1, 0] == 2
    # urządzenie 2 dostaje od razu seq 2; próba dosłania seq 1 (replay) jest odrzucana
    w.router.transfer(1, 2, p2, 7.0)
    assert not w.router.can_send(1, 2, p1, 0.0)
    w.events.drain()
    w.router.transfer(1, 2, p1, 8.0)  # wymuszone z pominięciem summary vector
    assert not w.router.have[2, p1]
    assert w.router.alert_seq[2, 0] == 2
    rejected = [e for e in w.events.drain() if e.type == EventType.ALERT_REJECTED]
    assert len(rejected) == 1 and rejected[0].data["reason"] == "stale_seq"


# ----------------------------------------------------------------------------- fałszywe alerty


def test_fake_alert_is_marked_unverified_and_not_forwarded() -> None:
    w = make_world([(0, 0), (10, 0), (20, 0)], [Role.TROLL, R, R])
    p = w.router.issue_alert(w.fake_alert(), 0, 0.0, forged=True)
    assert w.router.need_exchange(*_pair(0, 1))[0]  # troll oferuje fałszywkę sąsiadowi
    w.router.transfer(0, 1, p, 1.0)
    assert w.router.fake_seen[1]
    assert not w.router.have[1, p]  # nie trafia do bufora
    assert not w.router.need_exchange(*_pair(1, 2))[0]  # i nie jest przekazywana dalej
    assert not w.router.fake_accepted.any()
    assert w.router.new_alerts == []  # nie wywołuje reakcji (ewakuacji)
    assert w.router.alert_seq.sum() == 0
    reasons = [e.data["reason"] for e in w.events.drain() if e.type == EventType.ALERT_REJECTED]
    assert reasons == ["bad_signature"]


def test_forwarding_unverified_content_is_possible_but_never_verified() -> None:
    params = Params()
    params.routing.unverified_forward_hops = 1
    w = make_world([(0, 0), (10, 0), (20, 0), (30, 0)], [Role.TROLL, R, R, R], params=params)
    p = w.router.issue_alert(w.fake_alert(), 0, 0.0, forged=True)
    w.router.transfer(0, 1, p, 1.0)
    assert w.router.have[1, p]  # wariant wrażliwości: niesione dalej o 1 skok
    assert w.router.need_exchange(*_pair(1, 2))[0]
    w.router.transfer(1, 2, p, 2.0)
    assert not w.router.have[2, p]
    assert not w.router.need_exchange(*_pair(2, 3))[0]
    assert w.router.fake_seen.tolist() == [False, True, True, False]
    assert not w.router.fake_accepted.any()
    assert w.router.new_alerts == []


def test_fake_alert_has_lowest_priority_in_transfer_plan() -> None:
    w = make_world([(0, 0), (10, 0)], [Role.TROLL, R])
    fake = w.router.issue_alert(w.fake_alert(), 0, 0.0, forged=True)
    real = w.router.issue_alert(w.alert(t=1.0), 0, 1.0)
    pk, rev = w.router.plan(0, 1)
    assert pk.tolist() == [real, fake]
    assert not rev.any()


# ----------------------------------------------------------------------------- zgłoszenia: Spray-and-Wait


def test_spray_and_wait_halves_copies_and_stops_at_one() -> None:
    params = Params()
    params.routing.spray_copies = 4
    w = make_world([(0, 0)] * 5, [R, R, R, R, R], params=params)
    p = _report(w, 0)
    assert w.router.copies[0, p] == 4
    w.router.transfer(0, 1, p, 1.0)
    assert (w.router.copies[0, p], w.router.copies[1, p]) == (2, 2)
    w.router.transfer(0, 2, p, 2.0)
    assert (w.router.copies[0, p], w.router.copies[2, p]) == (1, 1)
    # faza „wait”: z jedną kopią nie rozdajemy dalej zwykłym urządzeniom
    assert not w.router.can_send(0, 3, p, 0.0)
    assert not w.router.need_exchange(*_pair(2, 3))[0]
    w.router.transfer(1, 3, p, 3.0)
    assert w.router.copies[:, p].sum() == 4  # liczba kopii jest zachowana
    assert not w.router.need_exchange(*_pair(3, 4))[0]


def test_courier_always_accepts_and_hub_delivery_is_recorded_once() -> None:
    params = Params()
    params.routing.spray_copies = 1
    w = make_world([(0, 0)] * 4, [R, R, Role.COURIER, Role.HUB], params=params)
    p = _report(w, 0, ReportKind.NEED_HELP, urgency=3)
    assert not w.router.need_exchange(*_pair(0, 1))[0]  # jedna kopia: nie dla sąsiada
    assert w.router.need_exchange(*_pair(0, 2))[0]  # ale dla kuriera zawsze (custody)
    w.router.transfer(0, 2, p, 10.0)
    assert w.router.have[2, p] and w.router.have[0, p]
    assert not w.router.need_exchange(*_pair(1, 2))[0]  # kurier nie rozdaje zgłoszeń mieszkańcom
    w.router.transfer(2, 3, p, 50.0)
    track = w.router.tracks[0]
    assert track.picked_up_t == 10.0 and track.delivered_t == 50.0
    assert len(w.router.deliveries) == 1 and w.router.deliveries[0].carrier == 2
    assert not w.router.have[3, p]  # hub jest celem, nie przekaźnikiem
    # autor przy hubie nie dostarcza drugi raz tej samej wersji
    assert not w.router.can_send(0, 3, p, 0.0)


def test_newer_report_version_replaces_older() -> None:
    w = make_world([(0, 0)] * 3, [R, R, Role.HUB])
    p1 = _report(w, 0, ReportKind.NEED_HELP, t=0.0, urgency=3)
    w.router.transfer(0, 1, p1, 1.0)
    p2 = _report(w, 0, ReportKind.SAFE, t=10.0)
    track = w.router.tracks[0]
    assert track.latest_version == 2 and track.packets == [p1, p2]
    assert not w.router.have[0, p1]
    w.router.transfer(0, 1, p2, 11.0)
    assert w.router.have[1, p2] and not w.router.have[1, p1]
    w.router.transfer(1, 2, p2, 20.0)
    assert track.delivered_version == 2 and track.kind == ReportKind.SAFE
    assert not w.router.can_send(0, 2, p1, 0.0)  # hub zna już nowszą wersję


def test_ack_reaches_reporter_and_acts_as_antipacket() -> None:
    w = make_world([(0, 0)] * 3, [R, R, Role.HUB])
    p = _report(w, 0)
    w.router.transfer(0, 1, p, 1.0)
    w.router.transfer(1, 2, p, 2.0)
    track = w.router.tracks[0]
    ack = w.router.issue_ack(w.ack(((track.report_id, 1),), t=5.0), 2, 5.0)
    assert w.router.kind[ack] == PacketKind.ACK
    w.router.transfer(2, 1, ack, 6.0)
    assert not w.router.have[1, p]  # przekaźnik zwalnia bufor
    assert math.isnan(track.acked_t)
    w.router.transfer(1, 0, ack, 7.0)
    assert track.acked_t == 7.0 and track.acked_version == 1
    assert not w.router.have[0, p]
    got = [e for e in w.events.drain() if e.type == EventType.ACK_RECEIVED]
    assert len(got) == 1 and got[0].agent == 0


def test_own_report_rate_limit() -> None:
    params = Params()
    params.routing.max_own_reports_per_hour = 2
    w = make_world([(0, 0)], [R], params=params)
    assert w.router.create_report(0, ReportKind.SAFE, HelpCategory.NONE, 1, "u2uxyz1", 0.0) is not None
    assert w.router.create_report(0, ReportKind.SAFE, HelpCategory.NONE, 1, "u2uxyz1", 60.0) is not None
    assert w.router.create_report(0, ReportKind.SAFE, HelpCategory.NONE, 1, "u2uxyz1", 120.0) is None
    assert w.router.create_report(0, ReportKind.SAFE, HelpCategory.NONE, 1, "u2uxyz1", 3700.0) is not None


# ----------------------------------------------------------------------------- bufor i priorytety


def test_transfer_plan_follows_priority_order() -> None:
    w = make_world([(0, 0)] * 4, [R, R, Role.COURIER, Role.HUB])
    safe = _report(w, 0, ReportKind.SAFE, t=1.0)
    need = _report(w, 1, ReportKind.NEED_HELP, t=2.0, urgency=3)
    w.router.transfer(1, 0, need, 3.0)
    track = w.router.tracks[1]
    alert = w.router.issue_alert(w.alert(t=4.0), 3, 4.0)
    w.router.transfer(3, 0, alert, 5.0)
    other = w.router.issue_ack(w.ack((("ffffffffffffffff", 1),), t=6.0), 3, 6.0)
    w.router.transfer(3, 0, other, 7.0)
    assert track.reporter == 1
    pk, _ = w.router.plan(0, 2)  # mieszkaniec -> kurier: wszystko, w kolejności priorytetu
    assert pk.tolist() == [alert, other, need, safe]


def test_buffer_evicts_expired_then_lowest_priority_then_oldest() -> None:
    params = Params()
    params.routing.buffer_resident = 3
    w = make_world([(0, 0)] * 6, [R, R, R, R, R, Role.HUB], params=params)
    old_safe = _report(w, 1, ReportKind.SAFE, t=1.0)
    new_safe = _report(w, 2, ReportKind.SAFE, t=2.0)
    need = _report(w, 3, ReportKind.NEED_HELP, t=3.0, urgency=2)
    for src, p in ((1, old_safe), (2, new_safe), (3, need)):
        w.router.transfer(src, 0, p, 4.0)
    assert w.router.count[0] == 3
    alert = w.router.issue_alert(w.alert(t=5.0), 5, 5.0)
    w.router.transfer(5, 0, alert, 6.0)
    # przepełnienie: wypada najstarsze zgłoszenie o najniższym priorytecie (SAFE z t=1)
    assert w.router.count[0] == 3
    assert not w.router.have[0, old_safe]
    assert w.router.have[0, [new_safe, need, alert]].all()
    # pakiet wygasły wypada przed wszystkimi innymi, nawet jeśli ma wysoki priorytet
    w.router.expires[alert] = 6.5
    extra = _report(w, 4, ReportKind.SAFE, t=7.0)
    w.router.transfer(4, 0, extra, 7.0)
    assert not w.router.have[0, alert]
    assert w.router.have[0, [new_safe, need, extra]].all()
    assert w.router.n_evicted == 2


def test_own_unacked_report_is_never_evicted() -> None:
    params = Params()
    params.routing.buffer_resident = 1
    w = make_world([(0, 0)] * 2, [R, Role.HUB], params=params)
    own = _report(w, 0, ReportKind.SAFE, t=0.0)
    alert = w.router.issue_alert(w.alert(t=1.0), 1, 1.0)
    w.router.transfer(1, 0, alert, 2.0)
    assert w.router.have[0, own]


def test_registry_grows_beyond_initial_capacity() -> None:
    w = make_world([(0, 0)] * 2, [R, Role.HUB])
    w.params.routing.max_own_reports_per_hour = 10_000
    first = _report(w, 0, t=0.0)
    for k in range(600):
        _report(w, 0, t=float(k + 1))
    assert w.router.n == 601 and w.router.cap >= 1024
    assert w.router.have[0, : w.router.n].sum() == 1  # zostaje tylko najnowsza wersja
    assert w.router.known[0, first]
    assert w.router.need_exchange(*_pair(0, 1))[0]
