"""Klasa `Simulation` – publiczne API silnika.

Kontrakt z przyszłym backendem: `step()`, `run()`, `snapshot()`, `describe()`, `drain_events()` oraz
akcje scenariusza jako metody (`issue_alert`, `dispatch_couriers`, `troll_broadcast`, ...).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from sztafeta.engine.behavior import Behavior
from sztafeta.engine.events import Event, EventLog, EventType
from sztafeta.engine.geo import points_in_polygon
from sztafeta.engine.mobility import CourierController, Mobility
from sztafeta.engine.model import (
    ActionKind,
    AgentState,
    Lang,
    Params,
    Role,
    Scenario,
    ScheduledAction,
)
from sztafeta.engine.population import build_population
from sztafeta.engine.rng import make_streams

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


class Simulation:
    """Jedno uruchomienie symulacji. Ten sam `seed` i parametry dają identyczny przebieg."""

    def __init__(self, params: Params, scenario: Scenario, seed: int) -> None:
        self.params = params
        self.scenario = scenario
        self.seed = seed
        self.t = 0.0
        self.step_count = 0
        self.network_down_t: float | None = None
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
        self.courier_ids = np.flatnonzero(self.agents.role == Role.COURIER)
        self.hub_id = int(np.flatnonzero(self.agents.role == Role.HUB)[0])
        self.troll_ids = np.flatnonzero(self.agents.role == Role.TROLL)
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
        self._timeline: list[ScheduledAction] = sorted(scenario.timeline, key=lambda a: a.t)
        self._timeline_i = 0

    # ------------------------------------------------------------------ czas

    def step(self, dt: float | None = None) -> None:
        """Przesuwa symulację o `dt` sekund czasu modelu (domyślnie `params.dt`)."""
        step = self.params.dt if dt is None else dt
        self._run_timeline()
        arrived = self.mobility.step(step)
        self.couriers.update(self.t, arrived)
        for agent in self.couriers.at_hub_events:
            self.events.emit(self.t, EventType.COURIER_AT_HUB, agent=agent)
        self.behavior.step(self.t, arrived)
        self.t += step
        self.step_count += 1

    def run(self, until: float | None = None) -> None:
        """Liczy kroki do chwili `until` (domyślnie do końca scenariusza)."""
        end = self.params.duration_s if until is None else until
        while self.t < end - 1e-9:
            self.step()

    def _run_timeline(self) -> None:
        while self._timeline_i < len(self._timeline) and self._timeline[self._timeline_i].t <= self.t:
            self._apply(self._timeline[self._timeline_i])
            self._timeline_i += 1

    def _apply(self, act: ScheduledAction) -> None:
        if act.kind == ActionKind.NETWORK_DOWN:
            self.network_down(act.label)
        elif act.kind == ActionKind.DISPATCH_COURIERS:
            self.dispatch_couriers()
        elif act.kind == ActionKind.NOTE:
            self.note(act.label)

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

    # ------------------------------------------------------------------ wyjścia

    def drain_events(self) -> list[Event]:
        """Zwraca zdarzenia od poprzedniego wywołania i czyści bufor."""
        return self.events.drain()

    def flags(self) -> np.ndarray[Any, np.dtype[np.uint8]]:
        """Maska bitowa stanu urządzenia każdego agenta (patrz stałe FLAG_*)."""
        ag = self.agents
        out = np.zeros(ag.n, dtype=np.uint8)
        out[~np.isnan(ag.informed_t)] |= FLAG_ALERT
        out[~np.isnan(ag.wom_t)] |= FLAG_WOM
        out[ag.has_app & (ag.battery <= 0.0)] |= FLAG_DEVICE_OFF
        out[self.mobility.moving] |= FLAG_MOVING
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
            "links": [],
            "alerts": [],
            "pczk": {},
            "metrics": {},
        }
