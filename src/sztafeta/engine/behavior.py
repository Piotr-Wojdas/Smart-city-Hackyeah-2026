"""Zachowania mieszkańców: spacery, reakcja na alert, ewakuacja, przekaz ustny."""

from __future__ import annotations

from enum import IntEnum

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

from sztafeta.engine.events import EventLog, EventType
from sztafeta.engine.mobility import Mobility
from sztafeta.engine.model import AgentArrays, AgentState, CityMap, FloatArr, IntArr, Params, Role


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
        "_city",
        "_events",
        "_mob",
        "_next_wom_t",
        "_p",
        "_rng",
        "_rng_walk",
        "_spread_m",
        "_wom_p",
        "activity",
        "evacuated_now",
        "need_help_now",
        "next_walk_t",
        "react_t",
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

    # ------------------------------------------------------------------ wejścia z innych podsystemów

    def inform(self, agent: int, t: float, via_app: bool) -> None:
        """Agent dowiedział się o ewakuacji: ze zweryfikowanego alertu (`via_app`) albo ustnie."""
        ag = self._agents
        first = np.isnan(ag.informed_t[agent]) and np.isnan(ag.wom_t[agent])
        if via_app:
            if np.isnan(ag.informed_t[agent]):
                ag.informed_t[agent] = t
        elif np.isnan(ag.wom_t[agent]):
            ag.wom_t[agent] = t
        if not first:
            return
        if ag.state[agent] in (AgentState.NO_APP, AgentState.UNINFORMED):
            ag.state[agent] = int(AgentState.INFORMED)
        if ag.role[agent] == Role.RESIDENT and ag.in_zone[agent]:
            delay = self._rng.lognormal(np.log(self._p.reaction_median_s), self._p.reaction_sigma)
            self.react_t[agent] = t + min(float(delay), self._p.reaction_max_s)

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
        self._handle_arrivals(t, arrived)
        self._handle_reactions(t)
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
                self.activity[agent] = int(Activity.STAYING)
                ag.state[agent] = int(AgentState.NEED_HELP)
                if self._mob.moving[agent]:
                    self._mob.start_trip_to(agent, ag.home_xy[agent])
                self.need_help_now.append(agent)
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
        """Osoba z aplikacją i zweryfikowanym alertem może ustnie poinformować sąsiada bez aplikacji."""
        ag = self._agents
        residents = ag.residents
        src = np.flatnonzero(residents & ag.has_app & ~np.isnan(ag.informed_t) & (ag.battery > 0))
        if src.size == 0:
            return
        dst = np.flatnonzero(residents & ~ag.has_app & np.isnan(ag.wom_t))
        if dst.size == 0:
            return
        tree = cKDTree(self._mob.pos[src])
        dist, _ = tree.query(self._mob.pos[dst], k=1, distance_upper_bound=self._p.wom_range_m)
        exposed = dst[np.isfinite(dist)]
        if exposed.size == 0:
            return
        told = exposed[self._rng.random(exposed.size) < self._wom_p]
        for agent in told.tolist():
            self.inform(agent, t, via_app=False)
            self._events.emit(t, EventType.WORD_OF_MOUTH, agent=agent)
