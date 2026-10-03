"""Wykresy do slajdów (PNG 16:9, 200 dpi) i karta wyników jednego uruchomienia.

Zasady: tytuł jest wnioskiem, jedna oś Y, cienkie linie, etykiety bezpośrednio przy liniach,
seria „Sztafeta” wyróżniona kolorem, wariant bazowy szary. Każdy wykres ma adnotację „wynik modelu”.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import FuncFormatter, MultipleLocator

from sztafeta.io.reader import load_light
from sztafeta.viz import style
from sztafeta.viz.labels import elapsed, tr

_FIGSIZE = (12.8, 7.2)
_DPI = 200


@dataclass(slots=True)
class Light:
    """Lekki odczyt uruchomienia: bez snapshotów i zdarzeń."""

    params: dict[str, Any]
    summary: dict[str, Any]
    metrics: pd.DataFrame


def _load(run_dir: Path) -> Light:
    params, summary, metrics = load_light(run_dir)
    return Light(params, summary, metrics)


def _figure() -> tuple[Figure, Axes]:
    style.apply_style()
    fig = Figure(figsize=_FIGSIZE, dpi=_DPI)
    FigureCanvasAgg(fig)
    ax = fig.add_axes((0.085, 0.185, 0.80, 0.515))
    ax.tick_params(labelsize=15, length=0)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", visible=False)
    return fig, ax


def _frame(fig: Figure, lang: str, title: str, subtitle: str, run: Light) -> None:
    fig.text(0.045, 0.945, title, fontsize=25, fontweight="bold", va="top")
    fig.text(0.045, 0.868, subtitle, fontsize=15.5, color=style.INK2, va="top")
    fig.text(
        0.955,
        0.052,
        tr(lang, "model_tag").upper(),
        fontsize=12,
        fontweight="bold",
        color=style.INK2,
        ha="right",
        va="center",
        bbox={"boxstyle": "round,pad=0.45", "facecolor": style.PANEL, "edgecolor": style.AXIS},
    )
    fig.text(0.045, 0.068, tr(lang, "model_note"), fontsize=12, color=style.INK2, va="center")
    fig.text(0.045, 0.036, _run_note(lang, run), fontsize=11, color=style.MUTED, va="center")


def _run_note(lang: str, run: Light) -> str:
    p = run.params["params"]
    s = run.summary
    return tr(
        lang,
        "run_note",
        scenario=run.params["scenario"]["name"],
        seed=run.params["seed"],
        residents=s["residents"],
        adoption=round(100 * p["behavior"]["adoption"]),
        range_m=round(p["radio"]["range_m"]),
        couriers=p["population"]["n_couriers"],
    )


def _hours_axis(ax: Axes, lang: str, end_s: float) -> None:
    ax.set_xlim(0, end_s / 3600.0)
    ax.xaxis.set_major_locator(MultipleLocator(1.0))
    ax.set_xlabel(tr(lang, "axis_hours"), fontsize=15, labelpad=8)


def _percent_axis(ax: Axes) -> None:
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_locator(MultipleLocator(25))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))


def _events(ax: Axes, lang: str, run: Light) -> None:
    """Pionowe kreski w chwilach akcji scenariusza (alert, fałszywka, aktualizacja)."""
    top = ax.get_ylim()[1]
    seen_alert = False
    for act in run.params["scenario"]["timeline"]:
        kind = act["kind"]
        if kind == "issue_alert":
            key = "mark_update" if seen_alert else "mark_alert"
            seen_alert = True
        elif kind == "troll_broadcast":
            key = "mark_troll"
        else:
            continue
        x = float(act["t"]) / 3600.0
        ax.axvline(x, color=style.AXIS, linewidth=1.0, zorder=1)
        ax.text(
            x + 0.03,
            top * 0.985,
            tr(lang, key),
            fontsize=11.5,
            color=style.INK2,
            va="top",
            rotation=90,
            zorder=6,
            bbox={
                "boxstyle": "square,pad=0.15",
                "facecolor": style.SURFACE,
                "edgecolor": "none",
                "alpha": 0.8,
            },
        )


def _end_label(ax: Axes, x: float, y: float, text: str, color: str, dy: float = 0.0) -> None:
    ax.plot([x], [y], marker="o", markersize=9, color=color, markeredgecolor=style.SURFACE, markeredgewidth=2)
    ax.annotate(
        text,
        (x, y),
        xytext=(10, dy),
        textcoords="offset points",
        fontsize=15,
        fontweight="bold",
        color=style.INK,
        va="center",
        annotation_clip=False,
    )


def _pct(value: float) -> str:
    """Procent do napisu: wartości między 0 a 1 jako „<1%”, żeby nie udawać zera."""
    if 0.0 < value < 1.0:
        return "<1%"
    return f"{value:.0f}%"


def _spread(y_a: float, y_b: float, min_gap: float) -> tuple[float, float]:
    """Przesunięcia etykiet (w punktach), żeby dwie etykiety końcowe na siebie nie nachodziły."""
    if abs(y_a - y_b) >= min_gap:
        return 0.0, 0.0
    return (9.0, -9.0) if y_a >= y_b else (-9.0, 9.0)


def _legend(ax: Axes, entries: list[tuple[str, str, float]]) -> None:
    handles = [Line2D([], [], color=color, linewidth=lw, label=label) for label, color, lw in entries]
    ax.legend(
        handles=handles,
        loc="lower left",
        bbox_to_anchor=(0.0, 1.035),
        ncol=len(handles),
        fontsize=14,
        handlelength=1.8,
        columnspacing=1.8,
        borderaxespad=0.0,
    )


def _save(fig: Figure, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=_DPI)
    return out


def _series(run: Light, column: str) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    return run.metrics["t"].to_numpy() / 3600.0, run.metrics[column].to_numpy()


def _percent_chart(
    run: Light,
    base: Light | None,
    column: str,
    lang: str,
    title: str,
    subtitle: str,
    ylabel: str,
    out: Path,
    milestones: bool,
) -> Path:
    fig, ax = _figure()
    _percent_axis(ax)
    _hours_axis(ax, lang, float(run.metrics["t"].iloc[-1]))
    _events(ax, lang, run)
    x, y = _series(run, column)
    entries = [(tr(lang, "series_relay"), style.BLUE, 3.0)]
    dy_run, dy_base = 0.0, 0.0
    if base is not None:
        bx, by = _series(base, column)
        ax.plot(bx, by, color=style.MUTED, linewidth=2.4, zorder=3)
        dy_run, dy_base = _spread(float(y[-1]), float(by[-1]), 7.0)
        _end_label(ax, float(bx[-1]), float(by[-1]), _pct(float(by[-1])), style.MUTED, dy_base)
        entries.append((tr(lang, "series_base"), style.MUTED, 2.4))
    ax.plot(x, y, color=style.BLUE, linewidth=3.0, zorder=4)
    _end_label(ax, float(x[-1]), float(y[-1]), _pct(float(y[-1])), style.BLUE, dy_run)
    if milestones:
        t0 = run.summary.get("alert_issued_t") or 0.0
        for share, key in ((50.0, "t50_app_s"), (90.0, "t90_app_s")):
            after = run.summary.get(key)
            if after is None:
                continue
            mx = (t0 + after) / 3600.0
            ax.plot([mx], [share], marker="o", markersize=8, color=style.BLUE, markeredgecolor=style.SURFACE)
            ax.annotate(
                tr(lang, "milestone", share=int(share), elapsed=elapsed(lang, after)),
                (mx, share),
                xytext=(12, -16),
                textcoords="offset points",
                fontsize=13,
                color=style.INK2,
            )
    ax.set_ylabel(ylabel, fontsize=15, labelpad=10)
    _legend(ax, entries)
    _frame(fig, lang, title, subtitle, run)
    return _save(fig, out)


def plot_reach(run: Light, base: Light | None, out: Path, lang: str = "pl") -> Path:
    """Zasięg zweryfikowanego alertu w czasie: Sztafeta kontra wariant bazowy."""
    reach = float(run.summary["alert_reach_app"])
    if base is not None:
        title = tr(
            lang, "reach_title_vs", relay=_pct(reach), base=_pct(float(base.summary["alert_reach_app"]))
        )
    else:
        hours = float(run.metrics["t"].iloc[-1]) / 3600.0
        title = tr(lang, "reach_title", relay=_pct(reach), hours=hours)
    return _percent_chart(
        run, base, "alert_reach_app", lang, title, tr(lang, "reach_sub"), tr(lang, "reach_axis"), out, True
    )


def plot_evacuation(run: Light, base: Light | None, out: Path, lang: str = "pl") -> Path:
    """Odsetek mieszkańców strefy zagrożenia, którzy dotarli do punktu ewakuacji."""
    evac = float(run.summary["evacuated_zone"])
    if base is not None:
        title = tr(lang, "evac_title_vs", relay=_pct(evac), base=_pct(float(base.summary["evacuated_zone"])))
    else:
        title = tr(lang, "evac_title", relay=_pct(evac))
    return _percent_chart(
        run, base, "evacuated_zone", lang, title, tr(lang, "evac_sub"), tr(lang, "evac_axis"), out, False
    )


def plot_reports(run: Light, base: Light | None, out: Path, lang: str = "pl") -> Path:
    """Zgłoszenia mieszkańców wysłane i dostarczone do PCZK w czasie."""
    fig, ax = _figure()
    end_s = float(run.metrics["t"].iloc[-1])
    _hours_axis(ax, lang, end_s)
    x, created = _series(run, "reports_created")
    _, delivered = _series(run, "reports_delivered")
    top = max(float(created[-1]), 1.0) * 1.12
    ax.set_ylim(0, top)
    _events(ax, lang, run)
    ax.fill_between(x, 0, created, color=style.GRID, zorder=2, linewidth=0)
    ax.plot(x, created, color=style.AXIS, linewidth=1.6, zorder=2.5)
    entries = [
        (tr(lang, "series_created"), style.AXIS, 6.0),
        (tr(lang, "series_delivered"), style.BLUE, 3.0),
    ]
    dy_run, dy_base = 0.0, 0.0
    if base is not None:
        bx, bdel = _series(base, "reports_delivered")
        ax.plot(bx, bdel, color=style.MUTED, linewidth=2.4, zorder=3)
        dy_run, dy_base = _spread(float(delivered[-1]), float(bdel[-1]), 0.07 * top)
        _end_label(ax, float(bx[-1]), float(bdel[-1]), f"{int(bdel[-1])}", style.MUTED, dy_base)
        entries.append((tr(lang, "series_delivered_base"), style.MUTED, 2.4))
    ax.plot(x, delivered, color=style.BLUE, linewidth=3.0, zorder=4)
    dy_created, _ = _spread(float(created[-1]), float(delivered[-1]), 0.07 * top)
    _end_label(ax, float(x[-1]), float(created[-1]), f"{int(created[-1])}", style.AXIS, dy_created)
    _end_label(ax, float(x[-1]), float(delivered[-1]), f"{int(delivered[-1])}", style.BLUE, dy_run)
    ax.set_ylabel(tr(lang, "reports_axis"), fontsize=15, labelpad=10)
    _legend(ax, entries)
    s = run.summary
    if base is not None:
        title = tr(
            lang,
            "reports_title_vs",
            delivered=s["reports_delivered"],
            created=s["reports_created"],
            base=base.summary["reports_delivered"],
        )
    else:
        title = tr(lang, "reports_title", delivered=s["reports_delivered"], created=s["reports_created"])
    subtitle = tr(
        lang,
        "reports_sub",
        delay=elapsed(lang, float(s["delay_median_s"])),
        need_delivered=s["need_help_delivered"],
        need_created=s["need_help_created"],
        acks=s["acks_received"],
    )
    _frame(fig, lang, title, subtitle, run)
    return _save(fig, out)


def _tile(
    fig: Figure, box: tuple[float, float, float, float], value: str, label: str, note: str, color: str
) -> None:
    x, y, w, h = box
    fig.add_artist(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.0,rounding_size=0.012",
            facecolor=style.PANEL,
            edgecolor="none",
            transform=fig.transFigure,
        )
    )
    fig.add_artist(
        FancyBboxPatch(
            (x, y + h - 0.008),
            w,
            0.008,
            boxstyle="square,pad=0.0",
            facecolor=color,
            edgecolor="none",
            transform=fig.transFigure,
        )
    )
    fig.text(x + 0.016, y + h - 0.035, textwrap.fill(label, 27), fontsize=13.5, color=style.INK2, va="top")
    size = 34 if len(value) <= 8 else 29
    fig.text(x + 0.016, y + h * 0.44, value, fontsize=size, fontweight="bold", va="center")
    fig.text(x + 0.016, y + 0.022, textwrap.fill(note, 34), fontsize=11.5, color=style.INK2, va="bottom")


def plot_scorecard(run: Light, base: Light | None, out: Path, lang: str = "pl") -> Path:
    """Karta wyników: najważniejsze liczby jednego uruchomienia na jednym slajdzie."""
    style.apply_style()
    fig = Figure(figsize=_FIGSIZE, dpi=_DPI)
    FigureCanvasAgg(fig)
    s = run.summary
    b = base.summary if base is not None else None

    def versus(key: str, fmt: str) -> str:
        if b is None:
            return ""
        value = b[key]
        text = _pct(float(value)) if "%" in fmt else fmt.format(value)
        return tr(lang, "card_base", value=text)

    def when(key: str) -> str:
        value = s.get(key)
        return tr(lang, "card_never") if value is None else elapsed(lang, float(value))

    tiles = [
        (
            _pct(float(s["alert_reach_app"])),
            tr(lang, "card_reach"),
            tr(lang, "card_reach_note", t50=when("t50_app_s"), base=versus("alert_reach_app", "{:.0f}%")),
            style.BLUE,
        ),
        (
            f"{s['alert_reach_zone_app']:.0f}%",
            tr(lang, "card_zone"),
            tr(lang, "card_zone_note", t90=when("t90_zone_app_s")),
            style.BLUE,
        ),
        (
            f"{s['alert_reach_all']:.0f}% + {s['wom_reach_all']:.0f}%",
            tr(lang, "card_all"),
            tr(lang, "card_all_note"),
            style.BLUE,
        ),
        (
            _pct(float(s["evacuated_zone"])),
            tr(lang, "card_evac"),
            versus("evacuated_zone", "{:.0f}%"),
            style.AQUA,
        ),
        (
            f"{s['reports_delivered']} / {s['reports_created']}",
            tr(lang, "card_reports"),
            tr(lang, "card_reports_note", delay=elapsed(lang, float(s["delay_median_s"])))
            + (" " + versus("reports_delivered", "{}") if b is not None else ""),
            style.VIOLET,
        ),
        (
            f"{s['need_help_delivered']} / {s['need_help_created']}",
            tr(lang, "card_need"),
            versus("need_help_delivered", "{}"),
            style.RED,
        ),
        (
            f"{s['acks_received']}",
            tr(lang, "card_acks"),
            tr(lang, "card_acks_note", pct=float(s["acks_received_pct"])),
            style.VIOLET,
        ),
        (
            f"{s['fake_verified_devices']}",
            tr(lang, "card_fake"),
            tr(lang, "card_fake_note", received=s["fake_received_devices"]),
            style.INK,
        ),
    ]
    cols, rows = 4, 2
    left, right, top, bottom = 0.045, 0.955, 0.790, 0.120
    gap_x, gap_y = 0.018, 0.035
    width = (right - left - gap_x * (cols - 1)) / cols
    height = (top - bottom - gap_y * (rows - 1)) / rows
    for k, (value, label, note, color) in enumerate(tiles):
        col, row = k % cols, k // cols
        box = (left + col * (width + gap_x), top - (row + 1) * height - row * gap_y, width, height)
        _tile(fig, box, value, label, note, color)
    hours = float(run.metrics["t"].iloc[-1]) / 3600.0
    subtitle = tr(
        lang,
        "card_sub",
        hours=hours,
        megabytes=float(s["bytes_total"]) / 1e6,
        battery=float(s["battery_mean"]),
        contacts=s["contacts_total"],
    )
    _frame(fig, lang, tr(lang, "card_title"), subtitle, run)
    return _save(fig, out)


def render_charts(
    run_dir: Path, baseline_dir: Path | None = None, lang: str = "pl", out_dir: Path | None = None
) -> list[Path]:
    """Komplet wykresów i karta wyników dla uruchomienia (z wariantem bazowym, jeśli istnieje)."""
    run = _load(run_dir)
    if baseline_dir is None:
        guess = run_dir.with_name(run_dir.name + "_baseline")
        baseline_dir = guess if (guess / "summary.json").exists() else None
    base = _load(baseline_dir) if baseline_dir is not None else None
    target = out_dir if out_dir is not None else run_dir / "wykresy"
    suffix = f"_{lang}.png"
    return [
        plot_reach(run, base, target / f"zasieg_alertu{suffix}", lang),
        plot_reports(run, base, target / f"zgloszenia{suffix}", lang),
        plot_evacuation(run, base, target / f"ewakuacja{suffix}", lang),
        plot_scorecard(run, base, target / f"karta_wynikow{suffix}", lang),
    ]
