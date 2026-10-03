"""Graf ulic jako tablice numpy + najkrótsze ścieżki (scipy.sparse.csgraph)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

_NO_PRED = -9999


class StreetGraph:
    """Nieskierowany graf ulic. Krawędzie to odcinki proste między węzłami (współrzędne w metrach)."""

    __slots__ = ("_csr", "_dist", "_pred", "_tree", "edge_len", "edges", "node_xy")

    def __init__(self, node_xy: NDArray[np.float64], edges: NDArray[np.int64]) -> None:
        self.node_xy: NDArray[np.float64] = np.ascontiguousarray(node_xy, dtype=np.float64)
        self.edges: NDArray[np.int64] = np.ascontiguousarray(edges, dtype=np.int64).reshape(-1, 2)
        delta = self.node_xy[self.edges[:, 0]] - self.node_xy[self.edges[:, 1]]
        self.edge_len: NDArray[np.float64] = np.hypot(delta[:, 0], delta[:, 1])
        n = self.node_xy.shape[0]
        # zerowa długość oznaczałaby „brak krawędzi” w macierzy rzadkiej
        weights = np.maximum(self.edge_len, 1e-3)
        self._csr = csr_matrix((weights, (self.edges[:, 0], self.edges[:, 1])), shape=(n, n))
        self._tree = cKDTree(self.node_xy)
        self._pred: dict[int, NDArray[np.int32]] = {}
        self._dist: dict[int, NDArray[np.float64]] = {}

    @property
    def n_nodes(self) -> int:
        return int(self.node_xy.shape[0])

    def nearest_node(self, xy: NDArray[np.float64]) -> int:
        """Indeks węzła najbliższego punktowi (x, y)."""
        _, idx = self._tree.query(np.asarray(xy, dtype=np.float64))
        return int(idx)

    def nearest_nodes(self, xy: NDArray[np.float64]) -> NDArray[np.int64]:
        """Indeksy węzłów najbliższych wielu punktom, kształt (N,)."""
        _, idx = self._tree.query(np.asarray(xy, dtype=np.float64).reshape(-1, 2))
        return np.asarray(idx, dtype=np.int64)

    def nodes_within(self, xy: NDArray[np.float64], radius: float) -> NDArray[np.int64]:
        """Posortowane indeksy węzłów w promieniu `radius` od punktu."""
        found = self._tree.query_ball_point(np.asarray(xy, dtype=np.float64), radius)
        return np.sort(np.asarray(found, dtype=np.int64))

    def _solve(self, target: int) -> None:
        dist, pred = dijkstra(self._csr, directed=False, indices=target, return_predecessors=True)
        self._dist[target] = np.asarray(dist, dtype=np.float64)
        self._pred[target] = np.asarray(pred, dtype=np.int32)

    def distances_to(self, target: int) -> NDArray[np.float64]:
        """Długości najkrótszych ścieżek ze wszystkich węzłów do `target` (inf, gdy brak połączenia)."""
        if target not in self._dist:
            self._solve(target)
        return self._dist[target]

    def route_nodes(self, src: int, dst: int) -> NDArray[np.int64]:
        """Najkrótsza ścieżka src -> dst jako ciąg węzłów (łącznie z końcami)."""
        if src == dst:
            return np.array([src], dtype=np.int64)
        if dst not in self._pred:
            self._solve(dst)
        pred = self._pred[dst]
        path = [src]
        cur = src
        for _ in range(self.n_nodes):
            nxt = int(pred[cur])
            if nxt == _NO_PRED:
                break
            path.append(nxt)
            cur = nxt
            if cur == dst:
                break
        if path[-1] != dst:
            # brak połączenia w grafie: idziemy „na przełaj” (nie powinno się zdarzyć po largest_component)
            path.append(dst)
        return np.asarray(path, dtype=np.int64)

    def route_xy(self, src_xy: NDArray[np.float64], dst_xy: NDArray[np.float64]) -> NDArray[np.float64]:
        """Trasa między dwoma punktami: dojście do ulicy, ulicami, dojście do celu. Kształt (K, 2)."""
        src = self.nearest_node(src_xy)
        dst = self.nearest_node(dst_xy)
        nodes = self.route_nodes(src, dst)
        return np.vstack([self.node_xy[nodes], np.asarray(dst_xy, dtype=np.float64).reshape(1, 2)])


def largest_component(
    node_xy: NDArray[np.float64], edges: NDArray[np.int64]
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Zostawia największą spójną składową grafu i przenumerowuje węzły."""
    n = node_xy.shape[0]
    edges = np.asarray(edges, dtype=np.int64).reshape(-1, 2)
    adj = csr_matrix((np.ones(edges.shape[0]), (edges[:, 0], edges[:, 1])), shape=(n, n))
    _, labels = connected_components(adj, directed=False)
    counts = np.bincount(labels)
    keep = labels == int(np.argmax(counts))
    remap = np.full(n, -1, dtype=np.int64)
    remap[keep] = np.arange(int(keep.sum()), dtype=np.int64)
    edge_keep = keep[edges[:, 0]] & keep[edges[:, 1]]
    return node_xy[keep], remap[edges[edge_keep]]
