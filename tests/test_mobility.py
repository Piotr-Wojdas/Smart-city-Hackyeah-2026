from __future__ import annotations

import numpy as np

from sztafeta.engine.graph import StreetGraph
from sztafeta.engine.mobility import Mobility


def _line_graph() -> StreetGraph:
    xy = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]])
    return StreetGraph(xy, np.array([[0, 1], [1, 2]]))


def test_agent_follows_polyline_at_its_speed() -> None:
    mob = Mobility(_line_graph(), np.array([[0.0, 0.0]]), np.array([2.0]))
    mob.start_trip(0, np.array([[10.0, 0.0], [10.0, 10.0]]))
    mob.step(1.0)
    assert np.allclose(mob.pos[0], [2.0, 0.0])
    for _ in range(5):
        mob.step(1.0)
    # po 6 s: 12 m drogi = 10 m w prawo i 2 m w górę (zakręt bez utraty dystansu)
    assert np.allclose(mob.pos[0], [10.0, 2.0])
    assert mob.moving[0]


def test_arrival_is_reported_once() -> None:
    mob = Mobility(_line_graph(), np.array([[0.0, 0.0], [5.0, 5.0]]), np.array([4.0, 1.0]))
    mob.start_trip(0, np.array([[10.0, 0.0]]))
    assert mob.step(1.0).size == 0
    assert mob.step(1.0).size == 0
    assert mob.step(1.0).tolist() == [0]
    assert np.allclose(mob.pos[0], [10.0, 0.0])
    assert not mob.moving[0]
    assert mob.step(1.0).size == 0
    assert np.allclose(mob.pos[1], [5.0, 5.0])  # agent bez trasy stoi


def test_route_via_graph_ends_at_destination() -> None:
    mob = Mobility(_line_graph(), np.array([[-1.0, 0.0]]), np.array([50.0]))
    mob.start_trip_to(0, np.array([11.0, 10.0]))
    for _ in range(3):
        mob.step(1.0)
    assert np.allclose(mob.pos[0], [11.0, 10.0])


def test_pool_grows_for_many_trips() -> None:
    n = 3000
    pos = np.zeros((n, 2))
    mob = Mobility(_line_graph(), pos, np.ones(n))
    for agent in range(n):
        mob.start_trip(agent, np.array([[10.0, 0.0], [10.0, 10.0], [0.0, 0.0]]))
    mob.step(1.0)
    assert np.allclose(mob.pos[:, 0], 1.0)
