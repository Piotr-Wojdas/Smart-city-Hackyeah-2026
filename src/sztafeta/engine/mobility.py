"""Ruch agentów po grafie ulic: wektorowe podążanie za łamaną, spacery, ewakuacja, patrole kurierów."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from sztafeta.engine.graph import StreetGraph
from sztafeta.engine.model import BoolArr, FloatArr, IntArr

_EMPTY = np.empty(0, dtype=np.int64)


class Mobility:
    """Pozycje agentów i ruch po trasach.

    Trasy leżą w jednej wspólnej puli punktów; agent pamięta tylko zakres indeksów. Dzięki temu krok
    symulacji nie zawiera pętli Pythona po agentach – jedynie krótką pętlę po kolejnych punktach trasy
    dla tych agentów, którzy w danym kroku minęli punkt.
    """

    __slots__ = ("_end", "_pool", "_pool_n", "_ptr", "graph", "moving", "pos", "speed")

    def __init__(self, graph: StreetGraph, pos: FloatArr, speed: FloatArr) -> None:
        n = pos.shape[0]
        self.graph = graph
        self.pos: FloatArr = np.array(pos, dtype=np.float64)
        self.speed: FloatArr = np.array(speed, dtype=np.float64)
        self.moving: BoolArr = np.zeros(n, dtype=np.bool_)
        self._pool: FloatArr = np.empty((4096, 2), dtype=np.float64)
        self._pool_n = 0
        self._ptr: IntArr = np.zeros(n, dtype=np.int64)
        self._end: IntArr = np.zeros(n, dtype=np.int64)

    def start_trip(self, agent: int, waypoints: FloatArr) -> None:
        """Agent rusza z bieżącej pozycji przez kolejne punkty `waypoints` (K, 2)."""
        pts = np.asarray(waypoints, dtype=np.float64).reshape(-1, 2)
        k = pts.shape[0]
        if k == 0:
            return
        while self._pool_n + k > self._pool.shape[0]:
            grown = np.empty((self._pool.shape[0] * 2, 2), dtype=np.float64)
            grown[: self._pool_n] = self._pool[: self._pool_n]
            self._pool = grown
        self._pool[self._pool_n : self._pool_n + k] = pts
        self._ptr[agent] = self._pool_n
        self._end[agent] = self._pool_n + k
        self._pool_n += k
        self.moving[agent] = True

    def start_trip_to(self, agent: int, dst_xy: FloatArr) -> None:
        """Najkrótsza trasa ulicami z bieżącej pozycji do punktu `dst_xy`."""
        self.start_trip(agent, self.graph.route_xy(self.pos[agent], dst_xy))

    def stop(self, agent: int) -> None:
        self.moving[agent] = False

    def step(self, dt: float) -> IntArr:
        """Przesuwa agentów o `dt` sekund. Zwraca posortowane id agentów, którzy dotarli do celu."""
        idx = np.flatnonzero(self.moving)
        if idx.size == 0:
            return _EMPTY
        remaining = self.speed[idx] * dt
        finished: list[IntArr] = []
        while idx.size:
            target = self._pool[self._ptr[idx]]
            delta = target - self.pos[idx]
            dist = np.hypot(delta[:, 0], delta[:, 1])
            reach = dist <= remaining
            short = ~reach
            if short.any():
                frac = (remaining[short] / dist[short])[:, None]
                self.pos[idx[short]] += delta[short] * frac
            reached = idx[reach]
            if reached.size == 0:
                break
            self.pos[reached] = target[reach]
            self._ptr[reached] += 1
            left = remaining[reach] - dist[reach]
            done = self._ptr[reached] >= self._end[reached]
            if done.any():
                ended = reached[done]
                self.moving[ended] = False
                finished.append(ended)
            idx = reached[~done]
            remaining = left[~done]
        if not finished:
            return _EMPTY
        return np.sort(np.concatenate(finished))


@dataclass(slots=True)
class _Courier:
    agent: int
    sector: IntArr  # węzły grafu do patrolowania
    active: bool = False
    phase: int = 0  # 0 = w hubie, 1 = jedzie do punktu, 2 = postój w punkcie, 3 = wraca do huba
    wait_until: float = 0.0
    left_hub_t: float = 0.0
    visited_evac: bool = False
    cursor: int = 0


class CourierController:
    """Patrole kurierów: wyjazd z huba, objazd sektora strefy, punkt ewakuacji, powrót co N minut."""

    __slots__ = (
        "_couriers",
        "_evac_xy",
        "_graph",
        "_hub_dwell",
        "_hub_xy",
        "_mob",
        "_return_interval",
        "_rng",
        "_wp_dwell",
        "at_hub_events",
    )

    def __init__(
        self,
        mobility: Mobility,
        rng: np.random.Generator,
        courier_ids: IntArr,
        zone_nodes: IntArr,
        hub_xy: FloatArr,
        evac_xy: FloatArr,
        return_interval_s: float,
        hub_dwell_s: float,
        waypoint_dwell_s: float,
    ) -> None:
        self._mob = mobility
        self._graph = mobility.graph
        self._rng = rng
        self._hub_xy = hub_xy
        self._evac_xy = evac_xy
        self._return_interval = return_interval_s
        self._hub_dwell = hub_dwell_s
        self._wp_dwell = waypoint_dwell_s
        self.at_hub_events: list[int] = []
        self._couriers: list[_Courier] = []
        sectors = _split_sectors(self._graph.node_xy, zone_nodes, len(courier_ids))
        for agent, sector in zip(courier_ids.tolist(), sectors, strict=True):
            order = rng.permutation(sector.size)
            self._couriers.append(_Courier(agent=int(agent), sector=sector[order]))

    def dispatch(self, t: float) -> list[int]:
        """Uruchamia wszystkich nieaktywnych kurierów. Zwraca ich id."""
        started: list[int] = []
        for c in self._couriers:
            if not c.active:
                c.active = True
                c.phase = 0
                c.wait_until = t
                started.append(c.agent)
        return started

    def update(self, t: float, arrived: IntArr) -> None:
        """Automat stanów kurierów; wywoływany raz na krok po `Mobility.step`."""
        self.at_hub_events.clear()
        arrived_set = set(arrived.tolist()) if arrived.size else set()
        for c in self._couriers:
            if not c.active:
                continue
            if c.phase == 0:
                if t >= c.wait_until:
                    c.left_hub_t = t
                    c.visited_evac = False
                    self._go_next(c, t)
            elif c.phase == 1:
                if c.agent in arrived_set:
                    c.phase = 2
                    c.wait_until = t + self._wp_dwell
            elif c.phase == 2:
                if t >= c.wait_until:
                    self._go_next(c, t)
            elif c.phase == 3 and c.agent in arrived_set:
                c.phase = 0
                c.wait_until = t + self._hub_dwell
                self.at_hub_events.append(c.agent)

    def _go_next(self, c: _Courier, t: float) -> None:
        elapsed = t - c.left_hub_t
        if elapsed >= self._return_interval:
            if not c.visited_evac:
                c.visited_evac = True
                c.phase = 1
                self._mob.start_trip_to(c.agent, self._evac_xy)
                return
            c.phase = 3
            self._mob.start_trip_to(c.agent, self._hub_xy)
            return
        if c.sector.size == 0:
            c.visited_evac = True
            c.phase = 1
            self._mob.start_trip_to(c.agent, self._evac_xy)
            return
        node = int(c.sector[c.cursor % c.sector.size])
        c.cursor += 1
        c.phase = 1
        self._mob.start_trip_to(c.agent, self._graph.node_xy[node])


def _split_sectors(node_xy: FloatArr, zone_nodes: IntArr, k: int) -> list[IntArr]:
    """Dzieli węzły strefy na `k` sąsiadujących sektorów wzdłuż głównej osi strefy."""
    if k <= 0:
        return []
    if zone_nodes.size == 0:
        return [np.empty(0, dtype=np.int64) for _ in range(k)]
    pts = node_xy[zone_nodes]
    centered = pts - pts.mean(axis=0)
    # główna oś z rozkładu własnego macierzy kowariancji
    cov = centered.T @ centered
    _, vecs = np.linalg.eigh(cov)
    axis = vecs[:, -1]
    if axis[np.argmax(np.abs(axis))] < 0:  # ustalony zwrot osi = powtarzalny podział
        axis = -axis
    proj = centered @ axis
    order = np.argsort(proj, kind="stable")
    chunks: list[NDArray[np.int64]] = np.array_split(zone_nodes[order], k)
    return [np.asarray(ch, dtype=np.int64) for ch in chunks]
