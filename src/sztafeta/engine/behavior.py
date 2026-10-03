"""Zachowania mieszkańców: spacery, reakcja na alert, ewakuacja, przekaz ustny."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

from sztafeta.engine.events import EventLog, EventType
from sztafeta.engine.mobility import Mobility
from sztafeta.engine.model import (
    AgentArrays,
    AgentState,
    CityMap,
    FloatArr,
    HelpCategory,
    IntArr,
    Params,
    ReportKind,
    Role,
)

NeedTable = tuple[tuple[HelpCategory, ...], tuple[float, ...], tuple[float, ...]]

# powody i pilność zgłoszeń „potrzebuję pomocy”: (kategorie, wagi kategorii, wagi pilności 1..3)
_ZONE_NEEDS: NeedTable = (
    (HelpCategory.EVACUATION, HelpCategory.MEDICAL, HelpCategory.MEDICINE, HelpCategory.WATER),
    (0.45, 0.25, 0.20, 0.10),
    (0.25, 0.45, 0.30),
)
_BLACKOUT_NEEDS: NeedTable = (
    (HelpCategory.POWER, HelpCategory.MEDICINE, HelpCategory.MEDICAL, HelpCategory.WATER),
    (0.40, 0.30, 0.15, 0.15),
    (0.50, 0.40, 0.10),
)
_DUE_NONE = 0
_DUE_SAFE = 1
_DUE_BLACKOUT_NEED = 2
_DUE_UPDATE = 3


@dataclass(slots=True)
class ReportRequest:
    """Mieszkaniec chce wysłać zgłoszenie (Simulation zamienia to na podpisany pakiet)."""

    agent: int
    kind: ReportKind
    category: HelpCategory
    urgency: int
    sensitive_len: int = 0


class Activity(IntEnum):
    HOME = 0
    WALK = 1
    EVACUATING = 2
    AT_EVAC = 3
    STAYING = 4  # zostaje w domu: potrzebuje pomocy albo nie posłuchał alertu


class Behavior:
    """Decyzje mieszkańców. Losowość: spacery ze strumienia `mobility`, decyzje ze strumienia `behavior`."""

    __slots__ = (
        "_agents",
        "_category",
        "_city",
        "_due_kind",
        "_due_t",
        "_events",
        "_mob",
        "_next_wom_t",
        "_p",
        "_rng",
        "_rng_walk",
        "_spread_m",
        "_urgency",
        "_wom_p",
        "activity",
        "evacuated_now",
        "need_help_now",
        "next_walk_t",
        "react_t",
        "requests",
    )

    def __init__(
        self,
        params: Params,
        city: CityMap,
        agents: AgentArrays,
        mobility: Mobility,
        rng_behavior: np.random.Generator,
        rng_walk: np.random.Generator,
        events: EventLog,
    ) -> None:
        self._p = params.behavior
        self._spread_m = params.population.evac_spread_m
        self._city = city
        self._agents = agents
        self._mob = mobility
        self._rng = rng_behavior
        self._rng_walk = rng_walk
        self._events = events
        n = agents.n
        self.activity: NDArray[np.uint8] = np.full(n, int(Activity.HOME), dtype=np.uint8)
        self.next_walk_t: FloatArr = np.full(n, np.inf)
        self.react_t: FloatArr = np.full(n, np.inf)
        res = np.flatnonzero(agents.role == Role.RESIDENT)
        if self._p.walk_rate_per_h > 0:
            self.next_walk_t[res] = rng_walk.exponential(3600.0 / self._p.walk_rate_per_h, size=res.size)
        self._next_wom_t = 0.0
        self._wom_p = 1.0 - (1.0 - self._p.wom_prob_per_min) ** (self._p.wom_interval_s / 60.0)
        # agenci, którzy w bieżącym kroku dotarli do punktu ewakuacji / zgłosili potrzebę pomocy
        self.evacuated_now: list[int] = []
        self.need_help_now: list[int] = []
        # zgłoszenia do wysłania w bieżącym kroku oraz zaplanowane na później
        self.requests: list[ReportRequest] = []
        self._due_t: FloatArr = np.full(n, np.inf)
        self._due_kind: NDArray[np.uint8] = np.zeros(n, dtype=np.uint8)
        self._urgency: NDArray[np.uint8] = np.zeros(n, dtype=np.uint8)
        self._category: NDArray[np.uint8] = np.zeros(n, dtype=np.uint8)

    # ------------------------------------------------------------------ wejścia z innych podsystemów

    def inform(self, agent: int, t: float, via_app: bool) -> None:
        """Agent dowiedział się o ewakuacji: ze zweryfikowanego alertu „ewakuuj” (`via_app`) albo ustnie.

        O reakcji decyduje wyłącznie to, czy agent wiedział już o ewakuacji. Wcześniejszy alert
        z innym działaniem (np. „zostań w budynku”) niczego tu nie blokuje ani nie uruchamia.
        """
        ag = self._agents
        first = np.isnan(ag.evac_order_t[agent]) and np.isnan(ag.wom_t[agent])
        if via_app:
            if np.isnan(ag.informed_t[agent]):
                ag.informed_t[agent] = t
            if np.isnan(ag.evac_order_t[agent]):
                ag.evac_order_t[agent] = t
        elif np.isnan(ag.wom_t[agent]):
            ag.wom_t[agent] = t
        if not first:
            return
        if ag.state[agent] == AgentState.NEED_HELP:
            return  # już zgłosił potrzebę pomocy i zostaje na miejscu
        if ag.state[agent] in (AgentState.NO_APP, AgentState.UNINFORMED):
            ag.state[agent] = int(AgentState.INFORMED)
        if ag.role[agent] != Role.RESIDENT:
            return
        if ag.in_zone[agent]:
            delay = self._rng.lognormal(np.log(self._p.reaction_median_s), self._p.reaction_sigma)
            self.react_t[agent] = t + min(float(delay), self._p.reaction_max_s)
        elif (
            via_app
            and self._due_kind[agent] == _DUE_NONE
            and self._rng.random() < self._p.p_safe_report_outside
        ):
            self._schedule(agent, t + float(self._rng.exponential(self._p.safe_report_delay_s)), _DUE_SAFE)

    def cancel(self, agent: int) -> None:
        """Telefon agenta dostał zweryfikowane odwołanie alertu: przestaje on namawiać innych do ewakuacji.

        Kto jeszcze nie ruszył, zostaje; kto już idzie albo dotarł do punktu ewakuacji, nie zawraca.
        """
        self._agents.evac_order_t[agent] = np.nan
        self.react_t[agent] = np.inf

    def schedule_blackout_needs(self, t: float) -> None:
        """Po awarii sieci część mieszkańców będzie potrzebować pomocy niezależnie od powodzi."""
        res = np.flatnonzero(self._agents.role == int(Role.RESIDENT))
        hit = res[self._rng.random(res.size) < self._p.p_need_help_blackout]
        when = t + self._rng.uniform(0.0, self._p.need_help_blackout_window_s, size=hit.size)
        self._due_t[hit] = when
        self._due_kind[hit] = _DUE_BLACKOUT_NEED

    def _schedule(self, agent: int, when: float, kind: int) -> None:
        self._due_t[agent] = when
        self._due_kind[agent] = kind

    def _need_help(self, agent: int, t: float, table: NeedTable) -> None:
        """Agent zostaje na miejscu i (jeśli ma aplikację) zgłasza „potrzebuję pomocy”."""
        ag = self._agents
        self.activity[agent] = int(Activity.STAYING)
        ag.state[agent] = int(AgentState.NEED_HELP)
        self.next_walk_t[agent] = np.inf
        self.react_t[agent] = np.inf
        if self._mob.moving[agent]:
            self._mob.start_trip_to(agent, ag.home_xy[agent])
        self.need_help_now.append(agent)
        categories, cat_w, urg_w = table
        category = categories[int(self._rng.choice(len(categories), p=cat_w))]
        urgency = 1 + int(self._rng.choice(3, p=urg_w))
        sensitive = int(self._rng.integers(48, 161)) if self._rng.random() < self._p.p_sensitive else 0
        update = self._rng.random() < self._p.p_report_update
        if not ag.has_app[agent]:
            return
        self._urgency[agent] = urgency
        self._category[agent] = int(category)
        self.requests.append(ReportRequest(agent, ReportKind.NEED_HELP, category, urgency, sensitive))
        if update:
            self._schedule(
                agent, t + float(self._rng.exponential(self._p.report_update_delay_s)), _DUE_UPDATE
            )

    def send_to(self, agent: int, dst_xy: FloatArr) -> None:
        """Wysyła agenta w obie strony do `dst_xy` (używane przez trolla)."""
        fwd = self._mob.graph.route_xy(self._mob.pos[agent], dst_xy)
        back = np.vstack([fwd[::-1][1:], self._agents.home_xy[agent][None, :]])
        self._mob.start_trip(agent, np.vstack([fwd, back]))
        self.activity[agent] = int(Activity.WALK)

    # ------------------------------------------------------------------ krok

    def step(self, t: float, arrived: IntArr) -> None:
        self.evacuated_now.clear()
        self.need_help_now.clear()
        self.requests.clear()
        self._handle_arrivals(t, arrived)
        self._handle_reactions(t)
        self._handle_due(t)
        self._start_walks(t)
        if self._p.wom_enabled and t >= self._next_wom_t:
            self._word_of_mouth(t)
            self._next_wom_t = t + self._p.wom_interval_s

    def _handle_arrivals(self, t: float, arrived: IntArr) -> None:
        ag = self._agents
        for agent in arrived.tolist():
            act = self.activity[agent]
            if act == Activity.WALK:
                self.activity[agent] = int(Activity.HOME)
                if ag.role[agent] == Role.RESIDENT and self._p.walk_rate_per_h > 0:
                    gap = self._rng_walk.exponential(3600.0 / self._p.walk_rate_per_h)
                    self.next_walk_t[agent] = t + float(gap)
            elif act == Activity.EVACUATING:
                self.activity[agent] = int(Activity.AT_EVAC)
                ag.state[agent] = int(AgentState.SAFE)
                ag.evac_done_t[agent] = t
                self.evacuated_now.append(agent)
                self._events.emit(t, EventType.EVACUATION_DONE, agent=agent)
                wants = self._rng.random() < self._p.p_safe_report_evacuated
                if ag.has_app[agent] and wants:
                    self.requests.append(ReportRequest(agent, ReportKind.SAFE, HelpCategory.NONE, 1))

    def _handle_reactions(self, t: float) -> None:
        due = np.flatnonzero(self.react_t <= t)
        if due.size == 0:
            return
        ag = self._agents
        p = self._p
        draws = self._rng.random(due.size)
        for agent, u in zip(due.tolist(), draws.tolist(), strict=True):
            self.react_t[agent] = np.inf
            self.next_walk_t[agent] = np.inf
            if u < p.p_need_help_zone:
                self._need_help(agent, t, _ZONE_NEEDS)
            elif u < p.p_need_help_zone + (1.0 - p.p_need_help_zone) * p.p_comply:
                self._mob.start_trip_to(agent, self._city.evac_xy + self._evac_offset())
                self.activity[agent] = int(Activity.EVACUATING)
                ag.state[agent] = int(AgentState.EVACUATING)
                ag.evac_start_t[agent] = t
                self._events.emit(t, EventType.EVACUATION_START, agent=agent)
            else:
                self.activity[agent] = int(Activity.STAYING)
                if self._mob.moving[agent]:
                    self._mob.start_trip_to(agent, ag.home_xy[agent])

    def _handle_due(self, t: float) -> None:
        """Zaplanowane zgłoszenia: „bezpieczny” spoza strefy, potrzeby po awarii, aktualizacje."""
        due = np.flatnonzero(self._due_t <= t)
        if due.size == 0:
            return
        ag = self._agents
        for agent in due.tolist():
            kind = int(self._due_kind[agent])
            self._due_t[agent] = np.inf
            self._due_kind[agent] = _DUE_NONE
            at_home = self.activity[agent] in (Activity.HOME, Activity.WALK)
            if kind == _DUE_SAFE and at_home:
                self.requests.append(ReportRequest(agent, ReportKind.SAFE, HelpCategory.NONE, 1))
            elif kind == _DUE_BLACKOUT_NEED and at_home:
                self._need_help(agent, t, _BLACKOUT_NEEDS)
            elif kind == _DUE_UPDATE and ag.state[agent] == AgentState.NEED_HELP:
                # sytuacja się pogarsza: nowa wersja zgłoszenia z wyższą pilnością
                urgency = min(int(self._urgency[agent]) + 1, 3)
                self._urgency[agent] = urgency
                category = HelpCategory(int(self._category[agent]))
                self.requests.append(ReportRequest(agent, ReportKind.NEED_HELP, category, urgency))

    def _evac_offset(self) -> FloatArr:
        """Losowe miejsce w obrębie punktu ewakuacji, żeby ludzie nie stali w jednym punkcie."""
        radius = self._spread_m * float(np.sqrt(self._rng.random()))
        angle = float(self._rng.random()) * 2.0 * np.pi
        return np.array([radius * np.cos(angle), radius * np.sin(angle)])

    def _start_walks(self, t: float) -> None:
        due = np.flatnonzero((self.next_walk_t <= t) & (self.activity == Activity.HOME))
        if due.size == 0:
            return
        graph = self._mob.graph
        ag = self._agents
        for agent in due.tolist():
            near = graph.nodes_within(ag.home_xy[agent], self._p.walk_radius_m)
            if near.size == 0:
                self.next_walk_t[agent] = np.inf
                continue
            dst = int(near[int(self._rng_walk.integers(near.size))])
            fwd = graph.route_xy(self._mob.pos[agent], graph.node_xy[dst])
            back = np.vstack([fwd[::-1][1:], ag.home_xy[agent][None, :]])
            self._mob.start_trip(agent, np.vstack([fwd, back]))
            self.activity[agent] = int(Activity.WALK)
            self.next_walk_t[agent] = np.inf

    def _word_of_mouth(self, t: float) -> None:
        """Przekaz ustny: osoba z aplikacją i alertem „ewakuuj” informuje osoby bez aplikacji.

        Domownik będący w zasięgu dowiaduje się od razu (rozmowa w mieszkaniu). Sąsiad z innego
        gospodarstwa – z prawdopodobieństwem `wom_prob_per_min`, o ile nie włączono trybu
        `wom_household_only`. Osoby poinformowane ustnie nie przekazują informacji dalej.
        """
        ag = self._agents
        residents = ag.residents
        src = np.flatnonzero(residents & ag.has_app & ~np.isnan(ag.evac_order_t) & (ag.battery > 0))
        if src.size == 0:
            return
        dst = np.flatnonzero(residents & ~ag.has_app & np.isnan(ag.wom_t))
        if dst.size == 0:
            return
        pos = self._mob.pos
        # domownicy: jeden informujący na gospodarstwo wystarcza
        teller = np.full(int(np.max(ag.household)) + 2, -1, dtype=np.int64)
        teller[ag.household[src]] = src
        mate = teller[ag.household[dst]]
        has_mate = mate >= 0
        near = np.zeros(dst.size, dtype=np.bool_)
        delta = pos[dst[has_mate]] - pos[mate[has_mate]]
        near[has_mate] = np.hypot(delta[:, 0], delta[:, 1]) <= self._p.wom_range_m
        told = [dst[near]]
        rest = dst[~near]
        if not self._p.wom_household_only and rest.size:
            tree = cKDTree(pos[src])
            dist, _ = tree.query(pos[rest], k=1, distance_upper_bound=self._p.wom_range_m)
            exposed = rest[np.isfinite(dist)]
            told.append(exposed[self._rng.random(exposed.size) < self._wom_p])
        for agent in np.sort(np.concatenate(told)).tolist():
            self.inform(agent, t, via_app=False)
            self._events.emit(t, EventType.WORD_OF_MOUTH, agent=agent)
