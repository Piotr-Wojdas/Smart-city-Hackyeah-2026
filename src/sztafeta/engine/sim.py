"""Klasa `Simulation` – publiczne API silnika.

Kontrakt z przyszłym backendem: `step()`, `run()`, `snapshot()`, `describe()`, `drain_events()` oraz
akcje scenariusza jako metody (`issue_alert`, `dispatch_couriers`, `troll_broadcast`, ...).
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
from numpy.typing import NDArray

from sztafeta.engine.behavior import Behavior
from sztafeta.engine.contacts import ContactEngine
from sztafeta.engine.crypto import (
    KeyRing,
    Verifier,
    common_prefix,
    make_certificate,
    public_bytes,
    sign_alert,
)
from sztafeta.engine.events import Event, EventLog, EventType
from sztafeta.engine.geo import points_in_polygon
from sztafeta.engine.metrics import MetricsCollector, MetricsRow
from sztafeta.engine.mobility import CourierController, Mobility
from sztafeta.engine.model import (
    Action,
    ActionKind,
    AgentState,
    Alert,
    Forgery,
    Hazard,
    Lang,
    MsgType,
    Params,
    Role,
    Scenario,
    ScheduledAction,
    Verdict,
)
from sztafeta.engine.population import build_population
from sztafeta.engine.rng import make_streams
from sztafeta.engine.routing import Router

SNAPSHOT_SCHEMA = "sztafeta.snapshot/1"
STATIC_SCHEMA = "sztafeta.static/1"

# bity pola `flags` w snapshocie
FLAG_ALERT = 1  # ma zweryfikowany alert w aplikacji
FLAG_WOM = 2  # poinformowany ustnie
FLAG_FAKE_SEEN = 4  # dostał fałszywy alert (i go odrzucił)
FLAG_REPORT_DELIVERED = 8  # własne zgłoszenie dotarło do PCZK
FLAG_REPORT_ACKED = 16  # dostał potwierdzenie własnego zgłoszenia
FLAG_DEVICE_OFF = 32  # telefon rozładowany
FLAG_RADIO_AWAKE = 64  # radio w fazie skanowania
FLAG_MOVING = 128

_CERT_VALIDITY_S = 30 * 86400.0
_SWEEP_INTERVAL_S = 10.0


class Simulation:
    """Jedno uruchomienie symulacji. Ten sam `seed` i parametry dają identyczny przebieg."""

    def __init__(self, params: Params, scenario: Scenario, seed: int) -> None:
        self.params = params
        self.scenario = scenario
        self.seed = seed
        self.t = 0.0
        self.step_count = 0
        self.network_down_t: float | None = None
        self.alert_issued_t: float | None = None
        self.events = EventLog()
        self.rng = make_streams(seed)

        city = scenario.city
        self.agents, speed = build_population(params, city, self.rng.population)
        self.mobility = Mobility(city.graph, self.agents.home_xy, speed)
        self.behavior = Behavior(
            params, city, self.agents, self.mobility, self.rng.behavior, self.rng.mobility, self.events
        )
        zone_nodes = np.flatnonzero(points_in_polygon(city.graph.node_xy, city.hazard_zone))
        pop = params.population
        self.courier_ids = np.flatnonzero(self.agents.role == int(Role.COURIER))
        self.hub_id = int(np.flatnonzero(self.agents.role == int(Role.HUB))[0])
        self.troll_ids = np.flatnonzero(self.agents.role == int(Role.TROLL))
        self.couriers = CourierController(
            self.mobility,
            self.rng.mobility,
            self.courier_ids,
            zone_nodes,
            city.hub_xy,
            city.evac_xy,
            pop.courier_return_interval_s,
            pop.courier_hub_dwell_s,
            pop.courier_waypoint_dwell_s,
        )

        # zaufanie: klucz główny -> certyfikat PCZK z zakresem obszaru
        self.keys = KeyRing.generate(self.rng.crypto)
        self.verifier = Verifier(self.keys.trust_store())
        self.area = self._zone_cells()
        self._scope = common_prefix(self.area, 4)
        self.cert = make_certificate(
            self.keys.root,
            "PCZK",
            public_bytes(self.keys.issuer),
            self._scope,
            -_CERT_VALIDITY_S,
            _CERT_VALIDITY_S,
        )
        self._alert_seq = 0

        self.router = Router(params, self.agents, self.verifier, self.events, self.rng.crypto, self.hub_id)
        self.radio = ContactEngine(params, self.agents, self.router, self.rng.radio, self.events, self.hub_id)
        self.metrics = MetricsCollector(self.agents, self.router, self.radio)

        self._timeline: list[ScheduledAction] = sorted(scenario.timeline, key=lambda a: a.t)
        self._timeline_i = 0
        self._next_metrics_t = 0.0
        self._next_sweep_t = 0.0

    def _zone_cells(self) -> tuple[str, ...]:
        """Obszar alertu: komórki geohash (precyzja 6) pokrywające strefę zagrożenia."""
        city = self.scenario.city
        inside = points_in_polygon(city.buildings_xy, city.hazard_zone)
        pts = np.vstack([city.hazard_zone, city.buildings_xy[inside]])
        cells = {city.georef.geohash(float(x), float(y), 6) for x, y in pts}
        return tuple(sorted(cells))

    # ------------------------------------------------------------------ czas

    def step(self, dt: float | None = None) -> None:
        """Przesuwa symulację o `dt` sekund czasu modelu (domyślnie `params.dt`)."""
        step = self.params.dt if dt is None else dt
        t = self.t
        if t >= self._next_metrics_t:
            self.metrics.sample(t)
            self._next_metrics_t = t + self.params.output.metrics_interval_s
        self._run_timeline()
        arrived = self.mobility.step(step)
        self.couriers.update(t, arrived)
        for agent in self.couriers.at_hub_events:
            self.events.emit(t, EventType.COURIER_AT_HUB, agent=agent)
        self.behavior.step(t, arrived)
        self.radio.step(t, step, self.mobility.pos)
        self._after_radio()
        if t >= self._next_sweep_t:
            self.router.sweep(t)
            self._next_sweep_t = t + _SWEEP_INTERVAL_S
        self.t = t + step
        self.step_count += 1

    def run(self, until: float | None = None) -> None:
        """Liczy kroki do chwili `until` (domyślnie do końca scenariusza) i domyka metryki."""
        end = self.params.duration_s if until is None else until
        while self.t < end - 1e-9:
            self.step()
        self.sample_metrics()

    def sample_metrics(self) -> MetricsRow:
        """Próbka metryk dla bieżącej chwili (bez dublowania, gdy już ją zapisano)."""
        rows = self.metrics.rows
        if rows and rows[-1].t == self.t:
            return rows[-1]
        return self.metrics.sample(self.t)

    def _run_timeline(self) -> None:
        while self._timeline_i < len(self._timeline) and self._timeline[self._timeline_i].t <= self.t:
            self._apply(self._timeline[self._timeline_i])
            self._timeline_i += 1

    def _apply(self, act: ScheduledAction) -> None:
        if act.kind == ActionKind.NETWORK_DOWN:
            self.network_down(act.label)
        elif act.kind == ActionKind.ISSUE_ALERT:
            self.issue_alert(act.hazard, act.action, act.msg_type)
        elif act.kind == ActionKind.DISPATCH_COURIERS:
            self.dispatch_couriers()
        elif act.kind == ActionKind.TROLL_BROADCAST:
            self.troll_broadcast(act.forgery)
        elif act.kind == ActionKind.NOTE:
            self.note(act.label)

    def _after_radio(self) -> None:
        """Skutki odebranych pakietów: pierwszy zweryfikowany alert uruchamia reakcję mieszkańca."""
        router = self.router
        if not router.new_alerts:
            return
        ag = self.agents
        for agent, p in router.new_alerts:
            alert = router.packets[p]
            assert isinstance(alert, Alert)
            first = bool(np.isnan(ag.informed_t[agent]))
            evacuate = alert.action == Action.EVACUATE and alert.msg_type != MsgType.CANCEL
            if evacuate:
                self.behavior.inform(agent, self.t, via_app=True)
            elif first:
                ag.informed_t[agent] = self.t
                if ag.state[agent] == AgentState.UNINFORMED:
                    ag.state[agent] = int(AgentState.INFORMED)
            if agent != int(router.origin[p]):
                self.events.emit(
                    self.t,
                    EventType.ALERT_RECEIVED,
                    agent=agent,
                    packet=alert.pid,
                    seq=alert.seq,
                    hops=int(router.hops[agent, p]),
                    first=first,
                )
        router.new_alerts.clear()

    # ------------------------------------------------------------------ akcje scenariusza

    def network_down(self, label: str = "") -> None:
        """Awaria sieci komórkowej – od tej chwili działa tylko kanał telefon–telefon."""
        self.network_down_t = self.t
        self.events.emit(self.t, EventType.NETWORK_DOWN, label=label)

    def note(self, label: str) -> None:
        """Wpis narracyjny do strumienia zdarzeń (np. napis w animacji)."""
        self.events.emit(self.t, EventType.NOTE, label=label)

    def dispatch_couriers(self) -> list[int]:
        """Wysyła wszystkich oczekujących kurierów na patrol. Zwraca ich id."""
        started = self.couriers.dispatch(self.t)
        for agent in started:
            self.events.emit(self.t, EventType.COURIER_DISPATCHED, agent=agent)
        return started

    def issue_alert(
        self,
        hazard: Hazard = Hazard.FLOOD,
        action: Action = Action.EVACUATE,
        msg_type: MsgType = MsgType.ALERT,
    ) -> str:
        """PCZK podpisuje alert i nadaje go z huba. Kolejny alert zastępuje poprzedni (wyższy seq)."""
        self._alert_seq += 1
        alert = sign_alert(
            self.keys.issuer,
            self.cert,
            incident=self.scenario.incident,
            seq=self._alert_seq,
            msg_type=msg_type,
            hazard=hazard,
            action=action,
            area=self.area,
            place="EVAC-1",
            issued_at=self.t,
            expires_at=self.t + self.params.routing.alert_lifetime_s,
            priority=0,
            ttl_hops=self.params.routing.alert_ttl_hops,
        )
        self.router.issue_alert(alert, self.hub_id, self.t)
        if self.alert_issued_t is None:
            self.alert_issued_t = self.t
        self.events.emit(
            self.t,
            EventType.ALERT_ISSUED,
            agent=self.hub_id,
            packet=alert.pid,
            seq=alert.seq,
            hazard=hazard.name,
            action=action.name,
            msg_type=msg_type.name,
            bytes=alert.size,
        )
        return alert.pid

    def cancel_alert(self) -> str:
        """Odwołanie alertu („anuluj”): nowy numer sekwencyjny, działanie ALL_CLEAR."""
        return self.issue_alert(Hazard.FLOOD, Action.ALL_CLEAR, MsgType.CANCEL)

    def troll_broadcast(self, forgery: Forgery = Forgery.BAD_SIGNATURE) -> list[str]:
        """Każdy troll rozsyła fałszywy alert „odwołanie ewakuacji” i rusza z nim w miasto."""
        pids: list[str] = []
        routing = self.params.routing
        for troll in self.troll_ids.tolist():
            if forgery == Forgery.BAD_SIGNATURE:
                cert = self.cert  # prawdziwy certyfikat PCZK skopiowany z cudzego alertu
            else:
                cert = make_certificate(
                    self.keys.troll_root,
                    "PCZK",
                    public_bytes(self.keys.troll),
                    self._scope,
                    -_CERT_VALIDITY_S,
                    _CERT_VALIDITY_S,
                )
            fake = sign_alert(
                self.keys.troll,
                cert,
                incident=self.scenario.incident,
                seq=self._alert_seq + 50,
                msg_type=MsgType.CANCEL,
                hazard=Hazard.FLOOD,
                action=Action.ALL_CLEAR,
                area=self.area,
                place="EVAC-1",
                issued_at=self.t,
                expires_at=self.t + routing.alert_lifetime_s,
                priority=0,
                ttl_hops=routing.alert_ttl_hops,
            )
            p = self.router.issue_alert(fake, troll, self.t, forged=True)
            self.behavior.send_to(troll, self.scenario.city.evac_xy)
            self.events.emit(
                self.t,
                EventType.TROLL_BROADCAST,
                agent=troll,
                packet=fake.pid,
                forgery=forgery.name,
                verdict=Verdict(int(self.router.verdict[p])).name.lower(),
            )
            pids.append(fake.pid)
        return pids

    # ------------------------------------------------------------------ wyjścia

    def drain_events(self) -> list[Event]:
        """Zwraca zdarzenia od poprzedniego wywołania i czyści bufor."""
        return self.events.drain()

    def flags(self) -> NDArray[np.uint8]:
        """Maska bitowa stanu urządzenia każdego agenta (patrz stałe FLAG_*)."""
        ag = self.agents
        out = np.zeros(ag.n, dtype=np.uint8)
        out[~np.isnan(ag.informed_t)] |= FLAG_ALERT
        out[~np.isnan(ag.wom_t)] |= FLAG_WOM
        out[self.router.fake_seen] |= FLAG_FAKE_SEEN
        for track in self.router.tracks:
            if track.delivered_version > 0:
                out[track.reporter] |= FLAG_REPORT_DELIVERED
            if track.acked_version > 0:
                out[track.reporter] |= FLAG_REPORT_ACKED
        out[ag.has_app & ~self.radio.on] |= FLAG_DEVICE_OFF
        out[self.radio.awake] |= FLAG_RADIO_AWAKE
        out[self.mobility.moving] |= FLAG_MOVING
        return out

    def alerts_view(self) -> list[dict[str, Any]]:
        """Wszystkie alerty w obiegu (prawdziwe i fałszywe) z liczbą urządzeń, które je mają."""
        router = self.router
        out: list[dict[str, Any]] = []
        for p, packet in enumerate(router.packets):
            if not isinstance(packet, Alert):
                continue
            verified = router.verdict[p] == Verdict.VERIFIED
            if not router.live[p]:
                status = "expired"
            elif not verified:
                status = "rejected"
            elif packet.seq < self._alert_seq:
                status = "superseded"
            else:
                status = "active"
            out.append(
                {
                    "id": packet.pid,
                    "seq": packet.seq,
                    "msg_type": packet.msg_type.name,
                    "hazard": packet.hazard.name,
                    "action": packet.action.name,
                    "issued_at": packet.issued_at,
                    "verified": bool(verified),
                    "verdict": Verdict(int(router.verdict[p])).name.lower(),
                    "status": status,
                    "holders": router.holders(p),
                }
            )
        return out

    def describe(self) -> dict[str, Any]:
        """Statyczna część stanu: mapa, cechy agentów, słowniki wyliczeń. Wysyłana raz."""
        city = self.scenario.city
        g = city.graph
        segs = np.hstack([g.node_xy[g.edges[:, 0]], g.node_xy[g.edges[:, 1]]])
        ag = self.agents
        lo = g.node_xy.min(axis=0)
        hi = g.node_xy.max(axis=0)
        return {
            "schema": STATIC_SCHEMA,
            "run": {
                "scenario": self.scenario.name,
                "seed": self.seed,
                "baseline": not self.params.routing.relay_enabled,
                "dt": self.params.dt,
                "duration_s": self.params.duration_s,
                "start": self.scenario.start_iso,
            },
            "map": {
                "name": city.name,
                "source": city.source,
                "crs": city.crs,
                "bbox": [round(float(v), 1) for v in (lo[0], lo[1], hi[0], hi[1])],
                "streets": np.round(segs, 1).tolist(),
                "water": [np.round(line, 1).tolist() for line in city.water],
                "hub": {"x": round(float(city.hub_xy[0]), 1), "y": round(float(city.hub_xy[1]), 1)},
                "evac_point": {"x": round(float(city.evac_xy[0]), 1), "y": round(float(city.evac_xy[1]), 1)},
                "hazard_zone": np.round(city.hazard_zone, 1).tolist(),
                "hub_name": self.scenario.hub_name,
                "evac_name": self.scenario.evac_name,
                "radio_range_m": self.params.radio.range_m,
            },
            "agents": {
                "n": ag.n,
                "role": ag.role.tolist(),
                "has_app": ag.has_app.astype(np.uint8).tolist(),
                "lang": ag.lang.tolist(),
                "home_x": np.round(ag.home_xy[:, 0], 1).tolist(),
                "home_y": np.round(ag.home_xy[:, 1], 1).tolist(),
                "in_zone": ag.in_zone.astype(np.uint8).tolist(),
                "is_vehicle": ag.is_vehicle.astype(np.uint8).tolist(),
            },
            "enums": {
                "role": [r.name.lower() for r in Role],
                "state": [s.name.lower() for s in AgentState],
                "lang": [la.name.lower() for la in Lang],
                "link_phase": ["setup", "transfer"],
                "flags": {
                    "alert": FLAG_ALERT,
                    "word_of_mouth": FLAG_WOM,
                    "fake_seen": FLAG_FAKE_SEEN,
                    "report_delivered": FLAG_REPORT_DELIVERED,
                    "report_acked": FLAG_REPORT_ACKED,
                    "device_off": FLAG_DEVICE_OFF,
                    "radio_awake": FLAG_RADIO_AWAKE,
                    "moving": FLAG_MOVING,
                },
            },
        }

    def snapshot(self) -> dict[str, Any]:
        """Dynamiczny stan w chwili `t` (serializowalny do JSON). Format: docs/FORMAT.md."""
        ag = self.agents
        pos = self.mobility.pos
        row = self.sample_metrics()
        return {
            "schema": SNAPSHOT_SCHEMA,
            "t": self.t,
            "agents": {
                "x": np.round(pos[:, 0], 1).tolist(),
                "y": np.round(pos[:, 1], 1).tolist(),
                "state": ag.state.tolist(),
                "battery": np.round(ag.battery).astype(np.int64).tolist(),
                "flags": self.flags().tolist(),
            },
            "links": self.radio.link_list(self.t),
            "alerts": self.alerts_view(),
            "pczk": {},
            "metrics": dataclasses.asdict(row),
        }
