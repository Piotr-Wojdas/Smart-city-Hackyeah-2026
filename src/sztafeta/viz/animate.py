"""Animacja mapy: ulice, agenci (kolor i kształt = stan), transmisje, panel liczników i narracja.

Eksport MP4 przez ffmpeg (systemowy albo z pakietu imageio-ffmpeg); gdy go nie ma – GIF przez pillow.
"""

from __future__ import annotations

import textwrap
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib as mpl
import numpy as np
from matplotlib.animation import AbstractMovieWriter, FFMpegWriter, PillowWriter
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.collections import LineCollection, PathCollection
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon, Rectangle
from matplotlib.text import Annotation, Text
from numpy.typing import NDArray

from sztafeta.io.reader import RunData, load_run
from sztafeta.viz import style
from sztafeta.viz.labels import elapsed, tr

_STORY_EVENTS = {
    "network_down",
    "alert_issued",
    "alert_received",
    "alert_rejected",
    "troll_broadcast",
    "courier_dispatched",
    "report_created",
    "report_picked_up",
    "report_delivered",
    "ack_received",
}
_STATE_SAFE = 4
_ROLE_COURIER = 1
_ROLE_HUB = 2
_ROLE_TROLL = 3
_MAP_BOX = (0.012, 0.055, 0.672, 0.875)
_PANEL_BOX = (0.698, 0.0, 0.302, 1.0)


def build_story(run: RunData, lang: str) -> list[tuple[float, str]]:
    """Kluczowe momenty przebiegu (czas, napis) – pierwsze wystąpienie każdego rodzaju zdarzenia."""
    story: list[tuple[float, str]] = []
    seen: set[str] = set()

    def once(key: str, t: float) -> None:
        if key not in seen:
            seen.add(key)
            story.append((t, tr(lang, key)))

    for ev in run.events:
        kind = ev["type"]
        t = float(ev["t"])
        data = ev.get("data", {})
        if kind == "network_down":
            once("ev_network_down", t)
        elif kind == "alert_issued":
            once("ev_alert_issued" if data.get("seq", 1) == 1 else "ev_alert_update", t)
        elif kind == "alert_received" and data.get("hops", 0) >= 2:
            once("ev_alert_relay", t)
        elif kind == "courier_dispatched":
            once("ev_couriers", t)
        elif kind == "troll_broadcast":
            once("ev_troll", t)
        elif kind == "alert_rejected" and data.get("reason") != "stale_seq":
            once("ev_rejected", t)
        elif kind == "report_created":
            once("ev_report", t)
        elif kind == "report_picked_up":
            once("ev_pickup", t)
        elif kind == "report_delivered":
            once("ev_delivered", t)
        elif kind == "ack_received":
            once("ev_ack", t)
    reach = run.metrics["alert_reach_app"].to_numpy()
    times = run.metrics["t"].to_numpy()
    for level, key in ((50.0, "ev_reach_50"), (90.0, "ev_reach_90")):
        hit = np.flatnonzero(reach >= level)
        if hit.size:
            story.append((float(times[hit[0]]), tr(lang, key)))
    story.sort(key=lambda item: item[0])
    return story


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


class MapAnimation:
    """Figura 16:9 z mapą i panelem bocznym; `draw(frame)` ustawia stan dla jednej klatki."""

    def __init__(self, run: RunData, lang: str = "pl", dpi: int = 120) -> None:
        style.apply_style()
        self.run = run
        self.lang = lang
        self.fig = Figure(figsize=(16, 9), dpi=dpi)
        FigureCanvasAgg(self.fig)
        self.ax: Axes = self.fig.add_axes(_MAP_BOX)
        self.panel: Axes = self.fig.add_axes(_PANEL_BOX)
        static = run.static
        self._role = np.asarray(static["agents"]["role"], dtype=np.int64)
        self._resident = (self._role == 0) | (self._role == _ROLE_TROLL)
        self._courier = np.flatnonzero(self._role == _ROLE_COURIER)
        self._troll = np.flatnonzero(self._role == _ROLE_TROLL)
        self._start = datetime.fromisoformat(static["run"]["start"])
        self._metric_t = run.metrics["t"].to_numpy()
        self._story = build_story(run, lang)
        outage = [float(e["t"]) for e in run.events if e["type"] == "network_down"]
        self._outage_t = outage[0] if outage else 0.0
        self._state_sc: list[PathCollection] = []
        self._build_map()
        self._build_panel()

    # ------------------------------------------------------------------ mapa

    def _build_map(self) -> None:
        ax = self.ax
        m = self.run.static["map"]
        ax.set_axis_off()
        box_ratio = (_MAP_BOX[2] * 16.0) / (_MAP_BOX[3] * 9.0)
        x0, x1, y0, y1 = _map_limits(self._view_bbox(), box_ratio)
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect("equal")

        zone = np.asarray(m["hazard_zone"], dtype=np.float64)
        ax.add_patch(
            Polygon(zone, closed=True, facecolor=style.HAZARD_FILL, edgecolor="none", alpha=0.75, zorder=1)
        )
        ax.add_patch(
            Polygon(
                zone,
                closed=True,
                facecolor="none",
                edgecolor=style.HAZARD_EDGE,
                linewidth=1.4,
                hatch="//",
                alpha=0.45,
                zorder=1.1,
            )
        )
        for line in m["water"]:
            pts = np.asarray(line, dtype=np.float64)
            ax.plot(
                pts[:, 0], pts[:, 1], color=style.WATER, linewidth=5.0, zorder=1.5, solid_capstyle="round"
            )
        streets = np.asarray(m["streets"], dtype=np.float64).reshape(-1, 2, 2)
        ax.add_collection(LineCollection(list(streets), colors=style.STREET, linewidths=1.3, zorder=2))

        anchor = self._zone_anchor(zone, (x0, x1, y0, y1))
        self._label(float(anchor[0]), float(anchor[1]), tr(self.lang, "zone"), style.HAZARD_EDGE, dy=10)

        for marker in style.STATE_MARKERS:
            sc = ax.scatter(
                [],
                [],
                s=marker.size,
                marker=marker.marker,
                facecolors=marker.face,
                edgecolors=marker.edge,
                linewidths=marker.lw,
                zorder=3 + len(self._state_sc),
            )
            self._state_sc.append(sc)
        self._links = LineCollection([], colors=style.INK, linewidths=1.1, alpha=0.75, zorder=10)
        ax.add_collection(self._links)

        hub = m["hub"]
        evac = m["evac_point"]
        self._evac_name = str(m["evac_name"])
        self._evac_label = self._site(evac["x"], evac["y"], style.EVAC, self._evac_name)
        self._site(hub["x"], hub["y"], style.HUB, m["hub_name"])
        self._courier_sc = self._role_scatter(style.COURIER, 13)
        self._troll_sc = self._role_scatter(style.TROLL, 14)

        # podziałka
        span = x1 - x0
        bar = 500.0 if span > 2500 else 200.0
        bx = x0 + 0.03 * span
        by = y0 + 0.035 * (y1 - y0)
        ax.plot([bx, bx + bar], [by, by], color=style.INK2, linewidth=2.5, zorder=20, solid_capstyle="butt")
        ax.text(
            bx + bar / 2, by + 0.012 * (y1 - y0), tr(self.lang, "scale", m=int(bar)), ha="center", fontsize=11
        )

        self.fig.text(_MAP_BOX[0] + 0.004, 0.945, tr(self.lang, "title"), fontsize=30, fontweight="bold")
        self.fig.text(_MAP_BOX[0] + 0.118, 0.951, tr(self.lang, "subtitle"), fontsize=17, color=style.INK2)
        self.fig.text(_MAP_BOX[0] + 0.004, 0.030, tr(self.lang, "model_note"), fontsize=12, color=style.INK2)
        source = textwrap.shorten(tr(self.lang, "map_note", source=m["source"]), width=150, placeholder="…")
        self.fig.text(_MAP_BOX[0] + 0.004, 0.009, source, fontsize=10, color=style.MUTED)

    def _view_bbox(self) -> list[float]:
        """Kadr mapy: zasięg domów mieszkańców (bez pojedynczych odległych) z hubem i punktem ewakuacji."""
        static = self.run.static
        m = static["map"]
        hx = np.asarray(static["agents"]["home_x"], dtype=np.float64)[self._resident]
        hy = np.asarray(static["agents"]["home_y"], dtype=np.float64)[self._resident]
        xs = np.concatenate([np.quantile(hx, [0.005, 0.995]), [m["hub"]["x"], m["evac_point"]["x"]]])
        ys = np.concatenate([np.quantile(hy, [0.005, 0.995]), [m["hub"]["y"], m["evac_point"]["y"]]])
        pad = 60.0
        return [float(xs.min()) - pad, float(ys.min()) - pad, float(xs.max()) + pad, float(ys.max()) + pad]

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

    def _role_scatter(self, marker: style.Marker, zorder: float) -> PathCollection:
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

    def _site(self, x: float, y: float, marker: style.Marker, name: str) -> Annotation:
        self.ax.scatter(
            [x],
            [y],
            s=marker.size,
            marker=marker.marker,
            facecolors=marker.face,
            edgecolors=marker.edge,
            linewidths=marker.lw,
            zorder=2.5,
        )
        return self._label(x, y, name, style.INK, dy=17)

    def _label(self, x: float, y: float, text: str, color: str, dy: float) -> Annotation:
        return self.ax.annotate(
            text,
            (x, y),
            xytext=(0, dy),
            textcoords="offset points",
            ha="center",
            fontsize=13,
            fontweight="bold",
            color=color,
            zorder=21,
            bbox={
                "boxstyle": "round,pad=0.25",
                "facecolor": style.SURFACE,
                "edgecolor": "none",
                "alpha": 0.85,
            },
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

        self._clock = p.text(left, 0.932, "", fontsize=38, fontweight="bold")
        self._date = p.text(left + 0.40, 0.938, "", fontsize=15, color=style.INK2)
        self._since = p.text(left, 0.900, "", fontsize=14, color=style.INK2)

        self._bars: dict[str, Rectangle] = {}
        self._values: dict[str, Text] = {}
        y = 0.852
        for key, color in (("alert", style.BLUE), ("evac", style.AQUA)):
            p.text(left, y, tr(lang, f"tile_{key}"), fontsize=13, color=style.INK2)
            self._values[key] = p.text(left, y - 0.033, "", fontsize=20, fontweight="bold")
            p.add_patch(Rectangle((left, y - 0.050), 0.86, 0.009, facecolor=style.GRID, edgecolor="none"))
            bar = Rectangle((left, y - 0.050), 0.0, 0.009, facecolor=color, edgecolor="none")
            p.add_patch(bar)
            self._bars[key] = bar
            y -= 0.086
        p.text(left, y, tr(lang, "tile_reports"), fontsize=13, color=style.INK2)
        self._values["reports"] = p.text(left, y - 0.033, "", fontsize=20, fontweight="bold")
        self._values["reports_sub"] = p.text(left, y - 0.057, "", fontsize=12, color=style.INK2)
        self._values["acks"] = p.text(left, y - 0.079, "", fontsize=12, color=style.INK2)
        y -= 0.118
        p.text(left, y, tr(lang, "tile_fake"), fontsize=13, color=style.INK2)
        self._values["fake"] = p.text(left, y - 0.028, "", fontsize=14, fontweight="bold")

        handles: list[Line2D] = []
        for k, marker in enumerate(style.STATE_MARKERS):
            handles.append(self._handle(marker, tr(lang, f"state_{k}")))
        handles.append(self._handle(style.COURIER, tr(lang, "courier")))
        handles.append(self._handle(style.TROLL, tr(lang, "troll")))
        handles.append(self._handle(style.HUB, tr(lang, "hub")))
        handles.append(self._handle(style.EVAC, tr(lang, "evac")))
        handles.append(Line2D([], [], color=style.INK, linewidth=1.4, label=tr(lang, "link")))
        legend = p.legend(
            handles=handles,
            loc="upper left",
            bbox_to_anchor=(left - 0.035, 0.505),
            fontsize=11.5,
            title=tr(lang, "legend_states"),
            title_fontsize=12,
            labelspacing=0.30,
            handlelength=1.6,
            borderaxespad=0.0,
            alignment="left",
        )
        legend.get_title().set_color(style.INK2)

        p.text(left, 0.178, tr(lang, "story"), fontsize=13, color=style.INK2)
        self._story_txt = [p.text(left, 0.149 - 0.029 * k, "", fontsize=12) for k in range(5)]

    @staticmethod
    def _handle(marker: style.Marker, label: str) -> Line2D:
        return Line2D(
            [],
            [],
            linestyle="none",
            marker=marker.marker,
            markersize=float(np.clip(np.sqrt(marker.size) * 0.95, 5.0, 14.0)),
            markerfacecolor=marker.face,
            markeredgecolor=marker.edge if marker.edge != "none" else marker.face,
            markeredgewidth=max(marker.lw, 0.0),
            label=label,
        )

    # ------------------------------------------------------------------ klatka

    def draw(self, frame: int) -> None:
        run = self.run
        t = float(run.t[frame])
        xy: NDArray[np.float32] = np.column_stack([run.x[frame], run.y[frame]])
        state = run.state[frame]
        for k, sc in enumerate(self._state_sc):
            sc.set_offsets(xy[self._resident & (state == k)])
        self._courier_sc.set_offsets(xy[self._courier])
        n_safe = int((self._resident & (state == _STATE_SAFE)).sum())
        people = tr(self.lang, "people", n=n_safe)
        self._evac_label.set_text(f"{self._evac_name} · {people}" if n_safe else self._evac_name)
        self._troll_sc.set_offsets(xy[self._troll])
        links = run.links_at(frame)
        active = links[links[:, 2] == 1] if links.size else links
        self._links.set_segments([xy[[a, b]] for a, b in active[:, :2]] if active.size else [])

        now = self._start + timedelta(seconds=t)
        self._clock.set_text(now.strftime("%H:%M"))
        self._date.set_text(now.strftime("%d.%m.%Y"))
        if t >= self._outage_t:
            self._since.set_text(
                tr(self.lang, "since_outage", elapsed=elapsed(self.lang, t - self._outage_t))
            )
        else:
            self._since.set_text(tr(self.lang, "before_outage"))

        row = run.metrics.iloc[int(np.searchsorted(self._metric_t, t, side="right")) - 1]
        lang = self.lang
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
        self._values["fake"].set_text(
            tr(
                lang,
                "tile_fake_value",
                received=int(row["fake_received_devices"]),
                verified=int(row["fake_verified_devices"]),
            )
        )

        past = [item for item in self._story if item[0] <= t][-5:]
        for k, txt in enumerate(self._story_txt):
            if k < len(past):
                when = (self._start + timedelta(seconds=past[k][0])).strftime("%H:%M")
                txt.set_text(f"{when}  {past[k][1]}")
                newest = k == len(past) - 1
                txt.set_fontweight("bold" if newest else "normal")
                txt.set_color(style.INK if newest else style.INK2)
            else:
                txt.set_text("")


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
    fps: int = 24,
    every: int = 3,
    dpi: int = 120,
    t_from: float | None = None,
    t_to: float | None = None,
    fmt: str = "auto",
    progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Renderuje animację uruchomienia z `run_dir`. Zwraca ścieżkę pliku wynikowego."""
    run = load_run(run_dir, _STORY_EVENTS)
    writer, ext = _make_writer(fps, fmt)
    if ext == ".gif":
        dpi = min(dpi, 60)
    frames = np.arange(0, run.t.size, max(every, 1))
    lo = run.t[0] if t_from is None else t_from
    hi = run.t[-1] if t_to is None else t_to
    frames = frames[(run.t[frames] >= lo) & (run.t[frames] <= hi)]
    if frames.size == 0:
        raise ValueError("Brak klatek w wybranym zakresie czasu")
    target = out if out is not None else run_dir / f"animacja_{lang}{ext}"
    if target.suffix.lower() != ext:
        target = target.with_suffix(ext)
    anim = MapAnimation(run, lang=lang, dpi=dpi)
    with writer.saving(anim.fig, str(target), dpi):
        for k, frame in enumerate(frames.tolist()):
            anim.draw(frame)
            writer.grab_frame()
            if progress is not None:
                progress(k + 1, int(frames.size))
    return target


def render_frame(run_dir: Path, out: Path, t: float, lang: str = "pl", dpi: int = 120) -> Path:
    """Pojedyncza klatka animacji jako PNG (do slajdów i do szybkiego podglądu)."""
    run = load_run(run_dir, _STORY_EVENTS)
    anim = MapAnimation(run, lang=lang, dpi=dpi)
    anim.draw(int(np.argmin(np.abs(run.t - t))))
    anim.fig.savefig(out, dpi=dpi)
    return out
