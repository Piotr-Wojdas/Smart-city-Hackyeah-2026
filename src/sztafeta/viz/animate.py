"""Animacja mapy: sztafeta alertu między telefonami, ewakuacja, kurierzy, liczniki i narracja.

Obraz pokazuje tylko to, co niesie historię: telefony z aplikacją (szare = bez alertu, niebieskie =
z alertem), przekazania alertu jako linie, ewakuujących się, zgłoszenia „potrzebuję pomocy”
i kurierów. Osoby bez aplikacji i wątek fałszywego alertu nie są rysowane (są w liczbach i na
wykresach). W trakcie animacji kamera raz zbliża się na jedno osiedle i w zwolnionym tempie pokazuje,
jak telefony zestawiają połączenia i przekazują sobie alert.

Eksport MP4 przez ffmpeg (systemowy albo z pakietu imageio-ffmpeg); gdy go nie ma – GIF przez pillow.
"""

from __future__ import annotations

import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib as mpl
import numpy as np
from matplotlib.animation import AbstractMovieWriter, FFMpegWriter, PillowWriter
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.collections import LineCollection, PathCollection
from matplotlib.colors import to_rgba
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon, Rectangle
from matplotlib.text import Annotation, Text
from numpy.typing import NDArray

from sztafeta.io.reader import RunData, load_run
from sztafeta.viz import style
from sztafeta.viz.labels import elapsed, people, tr

_EVENTS = {
    "network_down",
    "alert_issued",
    "alert_received",
    "courier_dispatched",
    "report_created",
    "report_picked_up",
    "contact",
}
_STATE_EVACUATING = 3
_STATE_SAFE = 4
_STATE_NEED_HELP = 5
_ROLE_COURIER = 1
_ROLE_HUB = 2
_MAP_BOX = (0.012, 0.150, 0.672, 0.780)
_LEGEND_BOX = (0.012, 0.058, 0.672, 0.082)
_PANEL_BOX = (0.698, 0.0, 0.302, 1.0)
_DENSE_S = 5400.0  # pierwsze 90 min po awarii pokazujemy gęściej niż resztę
_STORY_LINES = 6
_CLOSE_HALF_WIDTH_M = 130.0
_CLOSE_WINDOW_S = 100.0
_CLOSE_STEP_S = 0.5
_PACKET_TRAVEL_S = 3.0  # przez tyle sekund przed odbiorem widać „pakiet” lecący do odbiorcy
_CLOSE_MIN_LINK_M = 12.0  # krótszych przekazań (ten sam budynek) nie byłoby widać jako linii
_SIZE_GAIN = 3.8  # o tyle rosną znaczniki w zbliżeniu


@dataclass(frozen=True, slots=True)
class Shot:
    """Jedna klatka filmu: chwila czasu modelu i stopień zbliżenia (0 = całe miasto, 1 = osiedle)."""

    t: float
    zoom: float = 0.0


@dataclass(frozen=True, slots=True)
class Closeup:
    """Miejsce i czas zbliżenia: tam, gdzie w krótkim czasie najwięcej telefonów przekazało sobie alert."""

    cx: float
    cy: float
    t0: float
    t1: float
    handovers: int


def build_story(run: RunData, lang: str) -> list[tuple[float, str]]:
    """Kluczowe momenty przebiegu jako (czas, napis), w kolejności, w jakiej widać je na mapie."""
    story: list[tuple[float, str]] = []
    seen: set[str] = set()

    def once(key: str, t: float, **fmt: object) -> None:
        if key not in seen:
            seen.add(key)
            story.append((t, tr(lang, key, **fmt)))

    dispatched = False
    for ev in run.events:
        kind = ev["type"]
        t = float(ev["t"])
        data = ev.get("data", {})
        if kind == "network_down":
            once("ev_network_down", t)
        elif kind == "alert_issued":
            once("ev_alert_issued" if data.get("seq", 1) == 1 else "ev_alert_update", t)
        elif kind == "courier_dispatched":
            dispatched = True
            once("ev_couriers", t)
        elif kind == "report_created":
            once("ev_report", t)
        elif kind == "report_picked_up" and dispatched:
            once("ev_pickup", t)

    m = run.metrics
    times = m["t"].to_numpy(dtype=float)
    reach = m["alert_reach_app"].to_numpy(dtype=float)
    for level, key in ((5.0, "ev_alert_relay"), (50.0, "ev_reach_50"), (90.0, "ev_reach_90")):
        hit = np.flatnonzero(reach >= level)
        if hit.size:
            story.append((float(times[hit[0]]), tr(lang, key)))
    # kurier oddaje paczkę zgłoszeń: skok licznika o co najmniej 10 w ciągu 2 minut
    delivered = m["reports_delivered"].to_numpy(dtype=float)
    span = max(round(120.0 / max(float(times[1] - times[0]), 1.0)), 1) if times.size > 1 else 1
    if delivered.size > span:
        jump = delivered[span:] - delivered[:-span]
        burst = np.flatnonzero(jump >= 10)
        if burst.size:
            k = int(burst[0])
            end = min(k + 2 * span, delivered.size - 1)
            n = int(delivered[end] - delivered[k])
            story.append((float(times[k + span]), tr(lang, "ev_delivered", n=n)))
        elif delivered[-1] > 0:
            first = int(np.flatnonzero(delivered > 0)[0])
            story.append((float(times[first]), tr(lang, "ev_delivered_first")))
    acks = m["acks_received"].to_numpy(dtype=float)
    level = 10.0 if acks.size and acks[-1] >= 10 else 1.0
    got = np.flatnonzero(acks >= level)
    if got.size:
        story.append((float(times[got[0]]), tr(lang, "ev_ack")))
    if times.size:
        last = m.iloc[-1]
        story.append(
            (
                float(times[-1]),
                tr(
                    lang,
                    "ev_summary",
                    reach=float(last["alert_reach_app"]),
                    delivered=int(last["reports_delivered"]),
                    created=int(last["reports_created"]),
                ),
            )
        )
    story.sort(key=lambda item: item[0])
    return story


def pick_closeup(
    got_t: NDArray[np.float64],
    receiver_xy: NDArray[np.float64],
    visible: NDArray[np.bool_],
    radius: float = 110.0,
    window: float = _CLOSE_WINDOW_S,
) -> Closeup | None:
    """Wybiera osiedle i chwilę, w której telefony w krótkim czasie przekazały sobie alert wiele razy.

    `visible` wskazuje przekazania między telefonami mieszkańców na odległość, którą widać na mapie
    (bez huba, kurierów i par z jednego budynku). Bierzemy najwcześniejszą serię co najmniej w 60%
    tak gęstą jak najgęstsza, żeby zbliżenie pojawiło się na początku filmu. Zwraca None, gdy
    przekazań było za mało, żeby było co pokazać.
    """
    idx = np.flatnonzero(visible)
    if idx.size < 4:
        return None
    t = got_t[idx]
    xy = receiver_xy[idx]
    dt = t[None, :] - t[:, None]
    dist = np.hypot(xy[None, :, 0] - xy[:, None, 0], xy[None, :, 1] - xy[:, None, 1])
    members = (dt >= 0.0) & (dt <= window - 20.0) & (dist <= radius)
    counts = members.sum(axis=1)
    top = int(np.max(counts))
    if top < 4:
        return None
    enough = np.flatnonzero(counts >= max(4, int(0.6 * top)))
    best = int(enough[np.argmin(t[enough])])
    centre = xy[members[best]].mean(axis=0)
    t0 = float(t[best]) - 12.0
    return Closeup(float(centre[0]), float(centre[1]), t0, t0 + window, int(counts[best]))


def storyboard(
    t_end: float,
    snapshot_dt: float,
    outage_t: float,
    alert_t: float,
    story_times: list[float],
    closeup: Closeup | None,
    fps: int,
    hold_s: float,
    every: int | None = None,
    t_from: float | None = None,
    t_to: float | None = None,
) -> list[Shot]:
    """Plan filmu: kolejne klatki jako (czas modelu, stopień zbliżenia).

    Bez podanego `every`: przed alertem 60 s czasu modelu na klatkę, przez pierwsze 90 min po awarii
    20 s, potem 120 s. Przy każdym kluczowym momencie narracji obraz zatrzymuje się na `hold_s`.
    Zbliżenie biegnie w zwolnionym tempie (2 s na klatkę) z sekundowym najazdem i odjazdem kamery.
    """
    lo = 0.0 if t_from is None else t_from
    hi = t_end if t_to is None else min(t_to, t_end)
    if hi < lo:
        return []
    hold = round(hold_s * fps)
    ramp = max(fps, 2)
    use_close = closeup is not None and closeup.t0 >= lo and closeup.t1 <= hi
    pending = sorted(tm for tm in story_times if lo <= tm <= hi)
    shots: list[Shot] = []

    def emit(t: float) -> None:
        shots.append(Shot(t))
        hit = False
        while pending and pending[0] <= t:
            pending.pop(0)
            hit = True
        if hit:
            shots.extend([Shot(t)] * hold)

    t = lo
    zoomed = False
    while t <= hi + 1e-9:
        if use_close and not zoomed and closeup is not None and t >= closeup.t0:
            zoomed = True
            shots.extend(Shot(closeup.t0, (k + 1) / ramp) for k in range(ramp))
            n_close = round((closeup.t1 - closeup.t0) / _CLOSE_STEP_S)
            shots.extend(Shot(closeup.t0 + k * _CLOSE_STEP_S, 1.0) for k in range(n_close + 1))
            shots.extend(Shot(closeup.t1, 1.0 - (k + 1) / ramp) for k in range(ramp))
            t = closeup.t1
            continue
        emit(t)
        if every is not None:
            step = max(every, 1) * snapshot_dt
        elif t < alert_t:
            step = 60.0
        elif t < outage_t + _DENSE_S:
            step = 20.0
        else:
            step = 120.0
        if t < hi < t + step:
            t = hi  # zawsze kończymy dokładnie na ostatniej chwili zakresu (bilans)
        else:
            t += step
    return shots


def _map_limits(bbox: list[float], box_ratio: float) -> tuple[float, float, float, float]:
    """Granice osi tak, by skala w obu kierunkach była równa i mapa wypełniała pole."""
    x0, y0, x1, y1 = bbox
    width = (x1 - x0) * 1.06
    height = (y1 - y0) * 1.06
    cx = 0.5 * (x0 + x1)
    cy = 0.5 * (y0 + y1)
    if width / height < box_ratio:
        width = height * box_ratio
    else:
        height = width / box_ratio
    return cx - width / 2, cx + width / 2, cy - height / 2, cy + height / 2


def _ease(z: float) -> float:
    """Łagodny start i koniec ruchu kamery."""
    return z * z * (3.0 - 2.0 * z)


class MapAnimation:
    """Figura 16:9 z mapą, legendą i panelem bocznym; `draw(shot)` ustawia stan dla jednej klatki."""

    def __init__(self, run: RunData, lang: str = "pl", dpi: int = 120) -> None:
        style.apply_style()
        self.run = run
        self.lang = lang
        self.fig = Figure(figsize=(16, 9), dpi=dpi)
        FigureCanvasAgg(self.fig)
        self.ax: Axes = self.fig.add_axes(_MAP_BOX)
        self.legend_ax: Axes = self.fig.add_axes(_LEGEND_BOX)
        self.panel: Axes = self.fig.add_axes(_PANEL_BOX)
        static = run.static
        role = np.asarray(static["agents"]["role"], dtype=np.int64)
        n = role.size
        # troll jest w animacji zwykłym telefonem: wątek fałszywego alertu pokazują wykresy i karta wyników
        self._person = (role != _ROLE_COURIER) & (role != _ROLE_HUB)
        self._phone = self._person & (np.asarray(static["agents"]["has_app"], dtype=np.int64) > 0)
        self._courier = np.flatnonzero(role == _ROLE_COURIER)
        self._start = datetime.fromisoformat(static["run"]["start"])
        self._metric_t = run.metrics["t"].to_numpy()
        self._range_m = float(static["map"].get("radio_range_m", 40.0))
        self.story = build_story(run, lang)
        self.outage_t = next((float(e["t"]) for e in run.events if e["type"] == "network_down"), 0.0)
        self.alert_t = next((float(e["t"]) for e in run.events if e["type"] == "alert_issued"), 0.0)

        # przekazania alertu: kto, komu i kiedy (pierwszy zweryfikowany alert na telefonie)
        got = [e for e in run.events if e["type"] == "alert_received" and e.get("data", {}).get("first")]
        self._got_t = np.array([float(e["t"]) for e in got], dtype=np.float64)
        self._got_agent = np.array([int(e["agent"]) for e in got], dtype=np.int64)
        self._got_peer = np.array([int(e.get("peer", -1)) for e in got], dtype=np.int64)
        self._alert_at = np.full(n, np.inf)
        self._alert_at[self._got_agent] = self._got_t
        picks = [e for e in run.events if e["type"] == "report_picked_up" and "peer" in e]
        self._pick_t = np.array([float(e["t"]) for e in picks], dtype=np.float64)
        self._pick_courier = np.array([int(e["agent"]) for e in picks], dtype=np.int64)
        self._pick_from = np.array([int(e["peer"]) for e in picks], dtype=np.int64)

        home = np.column_stack(
            [
                np.asarray(static["agents"]["home_x"], dtype=np.float64),
                np.asarray(static["agents"]["home_y"], dtype=np.float64),
            ]
        )
        has_peer = self._got_peer >= 0
        between_phones = has_peer & self._phone[self._got_agent]
        between_phones[has_peer] &= self._phone[self._got_peer[has_peer]]
        # długość łącza liczona z rzeczywistych pozycji w chwili odbioru (telefony bywają w ruchu)
        peer = np.where(has_peer, self._got_peer, self._got_agent)
        recv_xy = self._positions_at(self._got_t, self._got_agent)
        send_xy = self._positions_at(self._got_t, peer)
        link_m = np.hypot(recv_xy[:, 0] - send_xy[:, 0], recv_xy[:, 1] - send_xy[:, 1])
        # linia przekazania łączy miejsca z chwili przekazania: nadawca w ruchu nie „ciągnie” jej za sobą
        self._hand_seg: NDArray[np.float64] = np.stack([send_xy, recv_xy], axis=1)
        self.closeup = pick_closeup(self._got_t, recv_xy, between_phones & (link_m >= _CLOSE_MIN_LINK_M))

        box_ratio = (_MAP_BOX[2] * 16.0) / (_MAP_BOX[3] * 9.0)
        self._city = _map_limits(self._view_bbox(home), box_ratio)
        self._close = self._city
        # początek połączenia, którym przyszedł alert (nan = nieznany);
        # w zbliżeniu rysujemy je przerywaną linią
        self._got_start = np.full(self._got_t.size, np.nan)
        if self.closeup is not None:
            c = self.closeup
            w = _CLOSE_HALF_WIDTH_M
            h = w / box_ratio
            self._close = (c.cx - w, c.cx + w, c.cy - h, c.cy + h)
            starts: dict[tuple[int, int], list[tuple[float, float]]] = {}
            for e in run.events:
                if e["type"] != "contact" or float(e["t"]) < c.t0 - 5.0 or float(e["data"]["start"]) > c.t1:
                    continue
                pair = (min(int(e["agent"]), int(e["peer"])), max(int(e["agent"]), int(e["peer"])))
                starts.setdefault(pair, []).append((float(e["data"]["start"]), float(e["t"])))
            for k in np.flatnonzero(has_peer & (self._got_t >= c.t0) & (self._got_t <= c.t1 + 5.0)):
                pair = (
                    min(int(self._got_agent[k]), int(self._got_peer[k])),
                    max(int(self._got_agent[k]), int(self._got_peer[k])),
                )
                for begin, end in starts.get(pair, []):
                    if begin <= self._got_t[k] <= end + 1.0:
                        self._got_start[k] = begin
                        break

        self._build_map()
        self._build_legend()
        self._build_panel()

    def _positions_at(self, times: NDArray[np.float64], agents: NDArray[np.int64]) -> NDArray[np.float64]:
        """Pozycje agentów w podanych chwilach, interpolowane liniowo między snapshotami."""
        run = self.run
        lo = np.clip(np.searchsorted(run.t, times, side="right") - 1, 0, run.t.size - 1)
        hi = np.minimum(lo + 1, run.t.size - 1)
        span = np.maximum(run.t[hi] - run.t[lo], 1e-9)
        part = np.clip((times - run.t[lo]) / span, 0.0, 1.0)[:, None]
        start = np.column_stack([run.x[lo, agents], run.y[lo, agents]]).astype(np.float64)
        end = np.column_stack([run.x[hi, agents], run.y[hi, agents]]).astype(np.float64)
        out: NDArray[np.float64] = start + (end - start) * part
        return out

    # ------------------------------------------------------------------ mapa

    def _view_bbox(self, home: NDArray[np.float64]) -> list[float]:
        """Kadr miasta: zasięg domów mieszkańców (bez pojedynczych odległych) z hubem i punktem ewakuacji."""
        m = self.run.static["map"]
        hx = home[self._person, 0]
        hy = home[self._person, 1]
        xs = np.concatenate([np.quantile(hx, [0.005, 0.995]), [m["hub"]["x"], m["evac_point"]["x"]]])
        ys = np.concatenate([np.quantile(hy, [0.005, 0.995]), [m["hub"]["y"], m["evac_point"]["y"]]])
        pad = 60.0
        return [float(xs.min()) - pad, float(ys.min()) - pad, float(xs.max()) + pad, float(ys.max()) + pad]

    def _build_map(self) -> None:
        ax = self.ax
        m = self.run.static["map"]
        ax.set_axis_off()
        x0, x1, y0, y1 = self._city
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect("equal")

        zone = np.asarray(m["hazard_zone"], dtype=np.float64)
        ax.add_patch(
            Polygon(
                zone,
                closed=True,
                facecolor=style.HAZARD_FILL,
                edgecolor=style.HAZARD_EDGE,
                linewidth=1.0,
                alpha=0.55,
                zorder=1,
            )
        )
        for line in m["water"]:
            pts = np.asarray(line, dtype=np.float64)
            ax.plot(
                pts[:, 0], pts[:, 1], color=style.WATER, linewidth=4.0, zorder=1.5, solid_capstyle="round"
            )
        streets = np.asarray(m["streets"], dtype=np.float64).reshape(-1, 2, 2)
        ax.add_collection(LineCollection(list(streets), colors=style.STREET_LIGHT, linewidths=1.0, zorder=2))

        anchor = self._zone_anchor(zone, self._city)
        self._site_labels: list[Annotation] = [
            self._label(float(anchor[0]), float(anchor[1]), tr(self.lang, "zone"), style.HAZARD_EDGE, (0, 10))
        ]

        self._idle_sc = self._scatter(style.PHONE_IDLE, 3)
        self._alert_sc = self._scatter(style.PHONE_ALERT, 4)
        self._evac_sc = self._scatter(style.EVACUEE, 5)
        self._need_sc = self._scatter(style.NEED_HELP, 6)
        self._contact_lines = LineCollection(
            [], colors=style.INK, linewidths=2.2, linestyles=(0, (3, 2.5)), zorder=7
        )
        ax.add_collection(self._contact_lines)
        self._hand_lines = LineCollection([], linewidths=2.4, zorder=8, capstyle="round")
        ax.add_collection(self._hand_lines)
        self._pick_lines = LineCollection([], colors=style.VIOLET, linewidths=2.0, alpha=0.85, zorder=8)
        ax.add_collection(self._pick_lines)
        self._ring_sc = self._scatter(style.RING, 9)
        self._packet_sc = self._scatter(style.PACKET, 10)

        hub = m["hub"]
        evac = m["evac_point"]
        self._evac_name = str(m["evac_name"])
        self._evac_label = self._site(evac["x"], evac["y"], style.EVAC, self._evac_name, 2.5, (-70, 30))
        hub_label = self._site(hub["x"], hub["y"], style.HUB, str(m["hub_name"]), 12, (70, -34))
        self._site_labels += [self._evac_label, hub_label]
        self._courier_sc = self._scatter(style.COURIER, 13)

        self._bar = ax.plot([], [], color=style.INK2, linewidth=2.5, zorder=20, solid_capstyle="butt")[0]
        self._bar_text = ax.text(0.0, 0.0, "", ha="center", va="bottom", fontsize=13, zorder=20)
        self._caption = ax.text(
            0.5,
            0.965,
            tr(self.lang, "closeup_caption"),
            transform=ax.transAxes,
            ha="center",
            va="top",
            fontsize=15,
            fontweight="bold",
            zorder=30,
            bbox={"boxstyle": "round,pad=0.45", "facecolor": style.SURFACE, "edgecolor": style.AXIS},
        )

        self.fig.text(_MAP_BOX[0] + 0.004, 0.948, tr(self.lang, "title"), fontsize=30, fontweight="bold")
        self.fig.text(_MAP_BOX[0] + 0.118, 0.954, tr(self.lang, "subtitle"), fontsize=17, color=style.INK2)
        self.fig.text(_MAP_BOX[0] + 0.004, 0.030, tr(self.lang, "model_note"), fontsize=13, color=style.INK2)
        source = textwrap.shorten(tr(self.lang, "map_note", source=m["source"]), width=150, placeholder="…")
        self.fig.text(_MAP_BOX[0] + 0.004, 0.008, source, fontsize=11, color=style.MUTED)

    def _zone_anchor(
        self, zone: NDArray[np.float64], view: tuple[float, float, float, float]
    ) -> NDArray[np.float64]:
        """Wierzchołek strefy na podpis: w kadrze, z dala od krawędzi oraz od huba i punktu ewakuacji."""
        x0, x1, y0, y1 = view
        m = self.run.static["map"]
        mx = 0.12 * (x1 - x0)
        my = 0.12 * (y1 - y0)
        ok = (zone[:, 0] > x0 + mx) & (zone[:, 0] < x1 - mx) & (zone[:, 1] > y0 + my) & (zone[:, 1] < y1 - my)
        cand = zone[ok] if ok.any() else zone
        sites = np.array([[m["hub"]["x"], m["hub"]["y"]], [m["evac_point"]["x"], m["evac_point"]["y"]]])
        dist = np.hypot(cand[:, None, 0] - sites[None, :, 0], cand[:, None, 1] - sites[None, :, 1]).min(
            axis=1
        )
        best: NDArray[np.float64] = cand[int(np.argmax(dist))]
        return best

    def _scatter(self, marker: style.Marker, zorder: float) -> PathCollection:
        return self.ax.scatter(
            [],
            [],
            s=marker.size,
            marker=marker.marker,
            facecolors=marker.face,
            edgecolors=marker.edge,
            linewidths=marker.lw,
            zorder=zorder,
        )

    def _site(
        self, x: float, y: float, marker: style.Marker, name: str, zorder: float, offset: tuple[float, float]
    ) -> Annotation:
        self.ax.scatter(
            [x],
            [y],
            s=marker.size,
            marker=marker.marker,
            facecolors=marker.face,
            edgecolors=marker.edge,
            linewidths=marker.lw,
            zorder=zorder,
        )
        return self._label(x, y, name, style.INK, offset, leader=True)

    def _label(
        self, x: float, y: float, text: str, color: str, offset: tuple[float, float], leader: bool = False
    ) -> Annotation:
        """Podpis miejsca; `leader` dodaje cienką linię odniesienia, żeby napis nie zasłaniał znaczników."""
        return self.ax.annotate(
            text,
            (x, y),
            xytext=offset,
            textcoords="offset points",
            ha="center",
            fontsize=14,
            fontweight="bold",
            color=color,
            zorder=21,
            bbox={
                "boxstyle": "round,pad=0.25",
                "facecolor": style.SURFACE,
                "edgecolor": "none",
                "alpha": 0.9,
            },
            arrowprops={"arrowstyle": "-", "color": style.INK2, "linewidth": 1.0} if leader else None,
        )

    # ------------------------------------------------------------------ legenda pod mapą

    def _build_legend(self) -> None:
        ax = self.legend_ax
        ax.set_axis_off()
        lang = self.lang
        handles = [
            self._handle(style.PHONE_IDLE, tr(lang, "leg_idle"), 7.0),
            self._handle(style.PHONE_ALERT, tr(lang, "leg_alert"), 8.0),
            Line2D([], [], color=style.BLUE, linewidth=2.4, label=tr(lang, "leg_handover")),
            self._handle(style.RING, tr(lang, "leg_ring"), 11.0),
            self._handle(style.EVACUEE, tr(lang, "leg_evac"), 8.0),
            self._handle(style.NEED_HELP, tr(lang, "leg_need"), 10.0),
            self._handle(style.COURIER, tr(lang, "leg_courier"), 10.0),
            Line2D([], [], color=style.VIOLET, linewidth=2.0, label=tr(lang, "leg_pickup")),
        ]
        ax.legend(
            handles=handles,
            loc="upper left",
            bbox_to_anchor=(0.0, 1.0),
            ncol=4,
            fontsize=13.5,
            labelspacing=0.5,
            columnspacing=2.2,
            handlelength=1.5,
            handletextpad=0.5,
            borderaxespad=0.0,
        )

    @staticmethod
    def _handle(marker: style.Marker, label: str, size: float) -> Line2D:
        return Line2D(
            [],
            [],
            linestyle="none",
            marker=marker.marker,
            markersize=size,
            markerfacecolor=marker.face,
            markeredgecolor=marker.edge if marker.edge != "none" else marker.face,
            markeredgewidth=max(marker.lw, 0.0),
            label=label,
        )

    # ------------------------------------------------------------------ panel

    def _build_panel(self) -> None:
        p = self.panel
        p.set_axis_off()
        p.set_xlim(0, 1)
        p.set_ylim(0, 1)
        p.add_patch(Rectangle((0, 0), 1, 1, facecolor=style.PANEL, edgecolor="none", zorder=0))
        lang = self.lang
        left = 0.07

        p.text(
            0.93,
            0.966,
            tr(lang, "model_tag").upper(),
            fontsize=11.5,
            fontweight="bold",
            color=style.INK2,
            ha="right",
            va="center",
            bbox={"boxstyle": "round,pad=0.4", "facecolor": style.SURFACE, "edgecolor": style.AXIS},
        )
        self._clock = p.text(left, 0.898, "", fontsize=40, fontweight="bold")
        self._date = p.text(left + 0.42, 0.905, "", fontsize=15, color=style.INK2)
        self._since = p.text(left, 0.862, "", fontsize=14.5, color=style.INK2)

        self._bars: dict[str, Rectangle] = {}
        self._values: dict[str, Text] = {}
        y = 0.795
        for key, color in (("alert", style.BLUE), ("evac", style.AQUA)):
            p.text(left, y, tr(lang, f"tile_{key}"), fontsize=14.5, color=style.INK2)
            self._values[key] = p.text(left, y - 0.040, "", fontsize=23, fontweight="bold")
            p.add_patch(Rectangle((left, y - 0.060), 0.86, 0.010, facecolor=style.GRID, edgecolor="none"))
            bar = Rectangle((left, y - 0.060), 0.0, 0.010, facecolor=color, edgecolor="none")
            p.add_patch(bar)
            self._bars[key] = bar
            y -= 0.112
        p.text(left, y, tr(lang, "tile_reports"), fontsize=14.5, color=style.INK2)
        self._values["reports"] = p.text(left, y - 0.040, "", fontsize=23, fontweight="bold")
        self._values["reports_sub"] = p.text(left, y - 0.070, "", fontsize=14, color=style.INK2)
        self._values["acks"] = p.text(left, y - 0.097, "", fontsize=14, color=style.INK2)

        p.text(left, 0.372, tr(lang, "story"), fontsize=14.5, color=style.INK2)
        self._story_txt = [p.text(left, 0.326 - 0.050 * k, "", fontsize=15) for k in range(_STORY_LINES)]

    # ------------------------------------------------------------------ klatka

    def draw(self, shot: Shot) -> None:
        run = self.run
        t = shot.t
        z = _ease(min(max(shot.zoom, 0.0), 1.0))
        frame = int(np.clip(np.searchsorted(run.t, t, side="right") - 1, 0, run.t.size - 1))
        xy: NDArray[np.float64] = np.column_stack([run.x[frame], run.y[frame]]).astype(np.float64)
        if frame + 1 < run.t.size:
            # płynny ruch między snapshotami (ważne w zbliżeniu, gdzie klatka to pół sekundy)
            part = float((t - run.t[frame]) / (run.t[frame + 1] - run.t[frame]))
            nxt = np.column_stack([run.x[frame + 1], run.y[frame + 1]]).astype(np.float64)
            xy += (nxt - xy) * min(max(part, 0.0), 1.0)
        state = run.state[frame]

        x0, x1, y0, y1 = (a + (b - a) * z for a, b in zip(self._city, self._close, strict=True))
        self.ax.set_xlim(x0, x1)
        self.ax.set_ylim(y0, y1)
        gain = 1.0 + (_SIZE_GAIN - 1.0) * z

        moving_out = state == _STATE_EVACUATING
        safe = state == _STATE_SAFE
        need = (state == _STATE_NEED_HELP) & self._phone
        at_home = self._phone & ~moving_out & ~safe & ~need
        has_alert = self._alert_at <= t
        self._place(self._idle_sc, xy[at_home & ~has_alert], style.PHONE_IDLE, gain)
        self._place(self._alert_sc, xy[at_home & has_alert], style.PHONE_ALERT, gain)
        self._place(self._evac_sc, xy[self._person & moving_out], style.EVACUEE, gain)
        self._place(self._need_sc, xy[need], style.NEED_HELP, gain)
        self._place(self._courier_sc, xy[self._courier], style.COURIER, 1.0 + 0.6 * z)
        n_safe = int((self._person & safe).sum())
        crowd = people(self.lang, n_safe)
        self._evac_label.set_text(f"{self._evac_name} · {crowd}" if n_safe else self._evac_name)

        # przekazania alertu: linia nadawca -> odbiorca i pierścień u odbiorcy
        close = z > 0.5 and self.closeup is not None
        age = t - self._got_t
        if close and self.closeup is not None:
            # w zbliżeniu linie zostają do końca: widać rosnący łańcuch telefonów
            recent = (age >= 0.0) & (self._got_t >= self.closeup.t0 - 60.0)
            fresh = (age >= 0.0) & (age < 8.0)
            fade = np.ones(int((recent & (self._got_peer >= 0)).sum()))
        else:
            keep = 90.0
            recent = (age >= 0.0) & (age < keep)
            fresh = (age >= 0.0) & (age < 45.0)
            fade = 1.0 - 0.75 * (age[recent & (self._got_peer >= 0)] / keep)
        self._place(self._ring_sc, xy[self._got_agent[fresh]], style.RING, gain)
        shown = recent & (self._got_peer >= 0)
        self._hand_lines.set_segments(list(self._hand_seg[shown]))
        base = to_rgba(style.BLUE)
        self._hand_lines.set_color([(base[0], base[1], base[2], float(a)) for a in fade])
        self._hand_lines.set_linewidth(3.0 + 1.5 * z)

        picked = (t - self._pick_t >= 0.0) & (t - self._pick_t < 60.0)
        self._pick_lines.set_segments(
            [xy[[a, b]] for a, b in zip(self._pick_from[picked], self._pick_courier[picked], strict=True)]
        )

        # tylko w zbliżeniu: połączenie w trakcie zestawiania i „pakiet” lecący do odbiorcy tuż przed odbiorem
        if close:
            ahead = self._got_t - t
            linking = (self._got_start <= t) & (ahead > 0.0)
            self._contact_lines.set_segments(list(self._hand_seg[linking]))
            flying = linking & (ahead <= _PACKET_TRAVEL_S)
            src = self._hand_seg[flying, 0]
            dst = self._hand_seg[flying, 1]
            done = (1.0 - ahead[flying] / _PACKET_TRAVEL_S)[:, None]
            self._place(self._packet_sc, src + (dst - src) * done, style.PACKET, 1.0)
        else:
            self._contact_lines.set_segments([])
            self._packet_sc.set_offsets(np.empty((0, 2)))
        for label in self._site_labels:
            label.set_visible(z < 0.5)
        self._caption.set_alpha(z)
        bbox = self._caption.get_bbox_patch()
        if bbox is not None:
            bbox.set_alpha(z)

        self._draw_scale((x0, x1, y0, y1), z)
        self._draw_panel(t)

    @staticmethod
    def _place(sc: PathCollection, points: NDArray[np.float64], marker: style.Marker, gain: float) -> None:
        sc.set_offsets(points.reshape(-1, 2))
        sc.set_sizes([marker.size * gain])

    def _draw_scale(self, view: tuple[float, float, float, float], z: float) -> None:
        """Podziałka dopasowana do kadru; w zbliżeniu ma długość zasięgu radia."""
        x0, x1, y0, y1 = view
        width = x1 - x0
        bx = x0 + 0.03 * width
        by = y0 + 0.05 * (y1 - y0)
        if z > 0.5:
            length = self._range_m
            self._bar_text.set_text(tr(self.lang, "scale_range", m=int(length)))
            self._bar_text.set_horizontalalignment("left")
            self._bar_text.set_position((bx, by + 0.012 * (y1 - y0)))
        else:
            fitting = [m for m in (50.0, 100.0, 200.0, 500.0, 1000.0) if m <= 0.12 * width]
            length = max(fitting) if fitting else 20.0
            self._bar_text.set_text(tr(self.lang, "scale", m=int(length)))
            self._bar_text.set_horizontalalignment("center")
            self._bar_text.set_position((bx + length / 2.0, by + 0.012 * (y1 - y0)))
        self._bar.set_data([bx, bx + length], [by, by])

    def _draw_panel(self, t: float) -> None:
        run = self.run
        lang = self.lang
        now = self._start + timedelta(seconds=t)
        self._clock.set_text(now.strftime("%H:%M"))
        self._date.set_text(now.strftime("%d.%m.%Y"))
        if t >= self.outage_t:
            self._since.set_text(tr(lang, "since_outage", elapsed=elapsed(lang, t - self.outage_t)))
        else:
            self._since.set_text(tr(lang, "before_outage"))

        row = run.metrics.iloc[max(int(np.searchsorted(self._metric_t, t, side="right")) - 1, 0)]
        reach = float(row["alert_reach_app"])
        evac = float(row["evacuated_zone"])
        self._values["alert"].set_text(tr(lang, "tile_alert_value", pct=reach))
        self._values["evac"].set_text(tr(lang, "tile_evac_value", pct=evac))
        self._bars["alert"].set_width(0.86 * reach / 100.0)
        self._bars["evac"].set_width(0.86 * evac / 100.0)
        self._values["reports"].set_text(
            tr(
                lang,
                "tile_reports_value",
                delivered=int(row["reports_delivered"]),
                created=int(row["reports_created"]),
            )
        )
        self._values["reports_sub"].set_text(
            tr(
                lang,
                "tile_reports_sub",
                need_delivered=int(row["need_help_delivered"]),
                need_created=int(row["need_help_created"]),
            )
        )
        self._values["acks"].set_text(tr(lang, "tile_acks_value", n=int(row["acks_received"])))

        past = [item for item in self.story if item[0] <= t][-_STORY_LINES:]
        for k, txt in enumerate(self._story_txt):
            if k < len(past):
                when = (self._start + timedelta(seconds=past[k][0])).strftime("%H:%M")
                txt.set_text(f"{when}  {past[k][1]}")
                newest = k == len(past) - 1
                txt.set_fontweight("bold" if newest else "normal")
                txt.set_color(style.INK if newest else style.INK2)
            else:
                txt.set_text("")

    def shots(
        self,
        fps: int,
        hold_s: float,
        every: int | None = None,
        t_from: float | None = None,
        t_to: float | None = None,
        closeup: bool = True,
    ) -> list[Shot]:
        """Plan filmu dla tego uruchomienia."""
        times = self.run.t
        dt = float(times[1] - times[0]) if times.size > 1 else 10.0
        return storyboard(
            float(times[-1]),
            dt,
            self.outage_t,
            self.alert_t,
            [t for t, _ in self.story],
            self.closeup if closeup else None,
            fps,
            hold_s,
            every,
            t_from,
            t_to,
        )


def _make_writer(fps: int, fmt: str) -> tuple[AbstractMovieWriter, str]:
    """MP4 przez ffmpeg, jeśli jest dostępny; inaczej GIF przez pillow."""
    if fmt in ("auto", "mp4"):
        try:
            import imageio_ffmpeg

            mpl.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
        except (ImportError, RuntimeError):
            pass
        if FFMpegWriter.isAvailable():
            writer = FFMpegWriter(fps=fps, codec="libx264", extra_args=["-pix_fmt", "yuv420p", "-crf", "20"])
            return writer, ".mp4"
        if fmt == "mp4":
            raise RuntimeError("Brak ffmpeg: zainstaluj pakiet imageio-ffmpeg albo użyj --format gif")
    return PillowWriter(fps=min(fps, 12)), ".gif"


def render_animation(
    run_dir: Path,
    out: Path | None = None,
    lang: str = "pl",
    fps: int = 15,
    every: int | None = None,
    dpi: int = 120,
    t_from: float | None = None,
    t_to: float | None = None,
    fmt: str = "auto",
    progress: Callable[[int, int], None] | None = None,
    hold_s: float = 1.2,
    closeup: bool = True,
) -> Path:
    """Renderuje animację uruchomienia z `run_dir`. Zwraca ścieżkę pliku wynikowego."""
    run = load_run(run_dir, _EVENTS)
    writer, ext = _make_writer(fps, fmt)
    if ext == ".gif":
        dpi = min(dpi, 60)
    anim = MapAnimation(run, lang=lang, dpi=dpi)
    plan = anim.shots(fps, hold_s, every, t_from, t_to, closeup)
    if not plan:
        raise ValueError("Brak klatek w wybranym zakresie czasu")
    target = out if out is not None else run_dir / f"animacja_{lang}{ext}"
    if target.suffix.lower() != ext:
        target = target.with_suffix(ext)
    previous: Shot | None = None
    with writer.saving(anim.fig, str(target), dpi):
        for k, shot in enumerate(plan):
            if shot != previous:
                anim.draw(shot)
                previous = shot
            writer.grab_frame()
            if progress is not None:
                progress(k + 1, len(plan))
    return target


def render_frame(
    run_dir: Path, out: Path, t: float | None = None, lang: str = "pl", dpi: int = 120, closeup: bool = False
) -> Path:
    """Pojedyncza klatka jako PNG: widok miasta w chwili `t` albo zbliżenie (domyślnie w jego połowie)."""
    run = load_run(run_dir, _EVENTS)
    anim = MapAnimation(run, lang=lang, dpi=dpi)
    if closeup:
        if anim.closeup is None:
            raise ValueError("W tym uruchomieniu nie ma czego pokazać w zbliżeniu (za mało przekazań alertu)")
        when = 0.5 * (anim.closeup.t0 + anim.closeup.t1) if t is None else t
        anim.draw(Shot(when, 1.0))
    else:
        anim.draw(Shot(3600.0 if t is None else t, 0.0))
    anim.fig.savefig(out, dpi=dpi)
    return out
