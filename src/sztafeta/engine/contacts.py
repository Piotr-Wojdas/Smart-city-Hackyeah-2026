"""Kontakty między urządzeniami: duty cycle, wykrywanie (cKDTree), zestawianie połączenia, transfer.

Pętla Pythona biegnie tylko po aktywnych połączeniach i po parach, które faktycznie mają sobie coś
do przekazania – nigdy po wszystkich agentach.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

from sztafeta.engine.events import EventLog, EventType
from sztafeta.engine.model import AgentArrays, BoolArr, FloatArr, IntArr, Params, Role
from sztafeta.engine.routing import Router

_NO_PLAN_P = np.empty(0, dtype=np.int64)
_NO_PLAN_R = np.empty(0, dtype=np.bool_)


@dataclass(slots=True)
class Link:
    """Jedno połączenie między urządzeniami `a` < `b`."""

    a: int
    b: int
    t_start: float
    ready_t: float  # koniec zestawiania połączenia i wymiany summary vector
    planned: bool = False
    plan_p: IntArr = field(default_factory=lambda: _NO_PLAN_P)
    plan_rev: BoolArr = field(default_factory=lambda: _NO_PLAN_R)
    cursor: int = 0
    budget: float = 0.0
    sent_ab: int = 0
    sent_ba: int = 0
    bytes_ab: int = 0
    bytes_ba: int = 0


class ContactEngine:
    """Radio wszystkich urządzeń: kto skanuje, kto z kim jest połączony, co i jak szybko przesyła."""

    def __init__(
        self,
        params: Params,
        agents: AgentArrays,
        router: Router,
        rng: np.random.Generator,
        events: EventLog,
        hub_id: int,
    ) -> None:
        self._p = params.radio
        self._bat = params.battery
        self._relay = params.routing.relay_enabled
        self._agents = agents
        self._router = router
        self._rng = rng
        self._events = events
        self._hub = hub_id
        n = agents.n
        role = agents.role
        self._n = n
        self.always_on: BoolArr = (
            (role == int(Role.COURIER)) | (role == int(Role.HUB)) | (role == int(Role.TROLL))
        )
        self._duty_idx: IntArr = np.flatnonzero(agents.has_app & ~self.always_on)
        self._win_start: FloatArr = np.full(n, np.inf)
        self._cycle_end = 0.0
        self.awake: BoolArr = np.zeros(n, dtype=np.bool_)
        self.on: BoolArr = agents.has_app & (agents.battery > 0.0)
        self.max_links: IntArr = np.full(n, self._p.max_links_resident, dtype=np.int64)
        self.max_links[role == int(Role.COURIER)] = self._p.max_links_courier
        self.max_links[role == int(Role.HUB)] = self._p.max_links_hub
        self.n_links: IntArr = np.zeros(n, dtype=np.int64)
        self.links: dict[int, Link] = {}
        # bateria: rozładowują się tylko telefony mieszkańców (kurier ma powerbank, hub agregat)
        self._drain_idx: IntArr = np.flatnonzero(agents.has_app & agents.residents)
        duty = np.full(n, self._p.scan_window_s / self._p.scan_period_s)
        duty[self.always_on] = 1.0
        self._base_drain: FloatArr = (self._bat.idle_pct_per_h + self._bat.scan_pct_per_h * duty) / 3600.0
        # liczniki
        self.n_contacts = 0
        self.n_interrupted = 0

    # ------------------------------------------------------------------ krok

    def step(self, t: float, dt: float, pos: FloatArr) -> None:
        self._drain(t, dt)
        self._update_windows(t)
        self._progress_links(t, dt, pos)
        self._open_links(t, pos)

    def _drain(self, t: float, dt: float) -> None:
        idx = self._drain_idx[self.on[self._drain_idx]]
        if idx.size == 0:
            return
        bat = self._agents.battery
        linked = self.n_links[idx] > 0
        bat[idx] -= (self._base_drain[idx] + linked * (self._bat.link_pct_per_h / 3600.0)) * dt
        dead = idx[bat[idx] <= 0.0]
        if dead.size:
            bat[dead] = 0.0
            self.on[dead] = False
            for agent in dead.tolist():
                self._events.emit(t, EventType.BATTERY_DEAD, agent=agent)

    def _update_windows(self, t: float) -> None:
        """Okno skanowania: `scan_window_s` w każdym cyklu `scan_period_s`, początek losowany co cykl."""
        if t >= self._cycle_end:
            slack = max(self._p.scan_period_s - self._p.scan_window_s, 0.0)
            self._win_start[self._duty_idx] = t + self._rng.uniform(0.0, slack, size=self._duty_idx.size)
            self._cycle_end = t + self._p.scan_period_s
        self.awake = self.on & (
            self.always_on | ((self._win_start <= t) & (t < self._win_start + self._p.scan_window_s))
        )

    def _progress_links(self, t: float, dt: float, pos: FloatArr) -> None:
        if not self.links:
            return
        links = list(self.links.items())
        a = np.fromiter((link.a for _, link in links), dtype=np.int64, count=len(links))
        b = np.fromiter((link.b for _, link in links), dtype=np.int64, count=len(links))
        delta = pos[a] - pos[b]
        in_range = (np.hypot(delta[:, 0], delta[:, 1]) <= self._p.range_m).tolist()
        powered = (self.on[a] & self.on[b]).tolist()
        router = self._router
        size = router.size
        for (key, link), near, power in zip(links, in_range, powered, strict=True):
            if not power:
                self._close(key, link, t, "device_off")
                continue
            if not near:
                self._close(key, link, t, "out_of_range")
                continue
            if t < link.ready_t:
                continue
            if not link.planned:
                link.plan_p, link.plan_rev = router.plan(link.a, link.b)
                link.planned = True
            link.budget += self._p.throughput_bps * dt
            plan_p = link.plan_p
            while link.cursor < plan_p.size:
                p = int(plan_p[link.cursor])
                rev = bool(link.plan_rev[link.cursor])
                src, dst = (link.b, link.a) if rev else (link.a, link.b)
                if not router.can_send(src, dst, p):
                    link.cursor += 1
                    continue
                nbytes = int(size[p])
                if nbytes > link.budget:
                    break
                link.budget -= nbytes
                router.transfer(src, dst, p, t)
                if rev:
                    link.sent_ba += 1
                    link.bytes_ba += nbytes
                else:
                    link.sent_ab += 1
                    link.bytes_ab += nbytes
                link.cursor += 1
            if link.cursor >= plan_p.size:
                self._close(key, link, t, "done")
            elif t - link.t_start >= self._p.max_session_s:
                self._close(key, link, t, "timeout")

    def _close(self, key: int, link: Link, t: float, reason: str) -> None:
        del self.links[key]
        self.n_links[link.a] -= 1
        self.n_links[link.b] -= 1
        pending = link.planned and link.cursor < link.plan_p.size
        if reason != "done" and (pending or not link.planned):
            self.n_interrupted += 1
        if link.sent_ab:
            self._events.emit(
                t, EventType.TRANSFER, agent=link.a, peer=link.b, packets=link.sent_ab, bytes=link.bytes_ab
            )
        if link.sent_ba:
            self._events.emit(
                t, EventType.TRANSFER, agent=link.b, peer=link.a, packets=link.sent_ba, bytes=link.bytes_ba
            )
        self._events.emit(
            t,
            EventType.CONTACT,
            agent=link.a,
            peer=link.b,
            start=round(link.t_start, 3),
            duration=round(t - link.t_start, 3),
            reason=reason,
            packets=link.sent_ab + link.sent_ba,
        )

    def _open_links(self, t: float, pos: FloatArr) -> None:
        free = np.flatnonzero(self.awake & (self.n_links < self.max_links))
        if free.size < 2:
            return
        tree = cKDTree(pos[free])
        pairs: NDArray[np.int64] = tree.query_pairs(self._p.range_m, output_type="ndarray")
        if pairs.shape[0] == 0:
            return
        ii = free[pairs[:, 0]]
        jj = free[pairs[:, 1]]
        if not self._relay:
            # wariant bazowy: telefony nie rozmawiają między sobą, tylko z hubem
            with_hub = (ii == self._hub) | (jj == self._hub)
            ii = ii[with_hub]
            jj = jj[with_hub]
            if ii.size == 0:
                return
        if ii.size > self._p.max_candidate_pairs:
            pick = np.sort(self._rng.choice(ii.size, size=self._p.max_candidate_pairs, replace=False))
            ii = ii[pick]
            jj = jj[pick]
        useful = self._router.need_exchange(ii, jj)
        if not useful.any():
            return
        ii = ii[useful]
        jj = jj[useful]
        keys = ii * self._n + jj
        # kolejność par losowa (żeby niskie id nie miały pierwszeństwa), ale powtarzalna dla seeda
        order = np.lexsort((jj, ii))
        order = order[self._rng.permutation(order.size)]
        setups = self._rng.uniform(self._p.setup_min_s, self._p.setup_max_s, size=order.size)
        n_links = self.n_links
        max_links = self.max_links
        for k, setup in zip(order.tolist(), setups.tolist(), strict=True):
            a = int(ii[k])
            b = int(jj[k])
            key = int(keys[k])
            if key in self.links or n_links[a] >= max_links[a] or n_links[b] >= max_links[b]:
                continue
            self.links[key] = Link(a=a, b=b, t_start=t, ready_t=t + setup + self._p.summary_vector_s)
            n_links[a] += 1
            n_links[b] += 1
            self.n_contacts += 1

    # ------------------------------------------------------------------ odczyty

    def link_list(self, t: float) -> list[list[int]]:
        """Aktywne połączenia jako [a, b, faza]; faza 0 = zestawianie, 1 = transfer."""
        return [[link.a, link.b, 0 if t < link.ready_t else 1] for link in self.links.values()]
