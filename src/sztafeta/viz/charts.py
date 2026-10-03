"""Wykresy do slajdów (PNG 16:9, 200 dpi) i karta wyników jednego uruchomienia.

Zasady: tytuł jest wnioskiem, jedna oś Y, cienkie linie, etykiety bezpośrednio przy liniach,
seria „Sztafeta” wyróżniona kolorem, wariant bazowy szary. Każdy wykres ma adnotację „wynik modelu”.
"""

from __future__ import annotations

import itertools
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

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
_TITLE_MAX_WIDTH = 0.91  # największa szerokość tytułu jako ułamek szerokości figury

LineStyle = Literal["-", "--", ":", "-."]


@dataclass(slots=True)
class Light:
    """Lekki odczyt uruchomienia: bez snapshotów i zdarzeń."""

    params: dict[str, Any]
    summary: dict[str, Any]
    metrics: pd.DataFrame


@dataclass(frozen=True, slots=True)
class Series:
    """Wygląd jednej serii: kolor oraz – żeby nie polegać na samym kolorze – znacznik i styl linii."""

    label: str
    color: str
    lw: float = 3.0
    marker: str = ""
    linestyle: LineStyle = "-"


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


def _text_width(fig: Figure, text: str, fontsize: float) -> float:
    """Szerokość napisu jako ułamek szerokości figury (mierzona rendererem, nie liczbą znaków)."""
    probe = fig.text(0.0, 0.0, text, fontsize=fontsize, fontweight="bold")
    width = probe.get_window_extent().width
    probe.remove()
    return float(width) / (fig.get_figwidth() * fig.dpi)


def _split_title(title: str) -> str:
    """Dzieli tytuł na dwa wiersze przy spacji najbliższej środka."""
    spaces = [k for k, ch in enumerate(title) if ch == " "]
    if not spaces:
        return title
    cut = min(spaces, key=lambda k: abs(k - len(title) // 2))
    return title[:cut] + "\n" + title[cut + 1 :]


def _frame(fig: Figure, lang: str, title: str, subtitle: str, note: str) -> None:
    """Wspólna rama: tytuł-wniosek, podtytuł, stopka z opisem uruchomienia, plakietka „wynik modelu”."""
    if _text_width(fig, title, 25) <= _TITLE_MAX_WIDTH:
        fig.text(0.045, 0.945, title, fontsize=25, fontweight="bold", va="top")
        fig.text(0.045, 0.868, subtitle, fontsize=15.5, color=style.INK2, va="top")
    else:
        wrapped = _split_title(title)
        size = 22.0
        while (
            size > 17.0
            and max(_text_width(fig, line, size) for line in wrapped.split("\n")) > _TITLE_MAX_WIDTH
        ):
            size -= 1.0
        fig.text(0.045, 0.962, wrapped, fontsize=size, fontweight="bold", va="top", linespacing=1.15)
        fig.text(0.045, 0.853, subtitle, fontsize=14.5, color=style.INK2, va="top")
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
    fig.text(0.045, 0.036, note, fontsize=11, color=style.MUTED, va="center")


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


def _events(ax: Axes, lang: str, run: Light, kinds: tuple[str, ...] = ("alert", "troll", "update")) -> None:
    """Pionowe kreski w chwilach akcji scenariusza; napisy leżą pod liniami danych."""
    top = ax.get_ylim()[1]
    seen_alert = False
    for act in run.params["scenario"]["timeline"]:
        if act["kind"] == "issue_alert":
            name = "update" if seen_alert else "alert"
            seen_alert = True
        elif act["kind"] == "troll_broadcast":
            name = "troll"
        else:
            continue
        if name not in kinds:
            continue
        x = float(act["t"]) / 3600.0
        ax.axvline(x, color=style.AXIS, linewidth=1.0, zorder=1)
        ax.text(
            x + 0.03,
            top * 0.985,
            tr(lang, f"mark_{name}"),
            fontsize=11.5,
            color=style.INK2,
            va="top",
            rotation=90,
            zorder=1.5,
        )


def _end_label(
    ax: Axes,
    x: float,
    y: float,
    text: str,
    color: str,
    dy: float = 0.0,
    label_y: float | None = None,
    marker: str = "o",
) -> None:
    """Punkt na końcu linii i etykieta obok; `label_y` pozwala odsunąć sam napis od sąsiednich."""
    ax.plot(
        [x], [y], marker=marker, markersize=9, color=color, markeredgecolor=style.SURFACE, markeredgewidth=2
    )
    ax.annotate(
        text,
        (x, y if label_y is None else label_y),
        xytext=(10, dy),
        textcoords="offset points",
        fontsize=15,
        fontweight="bold",
        color=style.INK,
        va="center",
        annotation_clip=False,
    )


def _declutter(values: list[float], gap: float) -> list[float]:
    """Pozycje etykiet (w jednostkach osi) rozsunięte tak, by sąsiednie dzieliło co najmniej `gap`."""
    order = sorted(range(len(values)), key=lambda k: values[k])
    placed = list(values)
    for prev, cur in itertools.pairwise(order):
        if placed[cur] - placed[prev] < gap:
            placed[cur] = placed[prev] + gap
    return placed


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


def _legend(ax: Axes, entries: list[Series]) -> None:
    handles = [
        Line2D(
            [],
            [],
            color=s.color,
            linewidth=s.lw,
            linestyle=s.linestyle,
            marker=s.marker or None,
            markersize=9,
            markeredgecolor=style.SURFACE,
            label=s.label,
        )
        for s in entries
    ]
    ax.legend(
        handles=handles,
        loc="lower left",
        bbox_to_anchor=(0.0, 1.035),
        ncol=len(handles),
        fontsize=14,
        handlelength=2.4,
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
    entries = [Series(tr(lang, "series_relay"), style.BLUE)]
    dy_run, dy_base = 0.0, 0.0
    if base is not None:
        bx, by = _series(base, column)
        ax.plot(bx, by, color=style.MUTED, linewidth=2.4, linestyle="--", zorder=3)
        dy_run, dy_base = _spread(float(y[-1]), float(by[-1]), 7.0)
        _end_label(ax, float(bx[-1]), float(by[-1]), _pct(float(by[-1])), style.MUTED, dy_base)
        entries.append(Series(tr(lang, "series_base"), style.MUTED, 2.4, linestyle="--"))
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
    _frame(fig, lang, title, subtitle, _run_note(lang, run))
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
    title = tr(lang, "evac_title", relay=_pct(float(run.summary["evacuated_zone"])))
    subtitle = tr(lang, "evac_sub_vs" if base is not None else "evac_sub")
    return _percent_chart(
        run, base, "evacuated_zone", lang, title, subtitle, tr(lang, "evac_axis"), out, False
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
    _events(ax, lang, run, kinds=("alert",))
    ax.fill_between(x, 0, created, color=style.GRID, zorder=2, linewidth=0)
    ax.plot(x, created, color=style.AXIS, linewidth=1.6, zorder=2.5)
    entries = [
        Series(tr(lang, "series_created"), style.AXIS, 6.0),
        Series(tr(lang, "series_delivered"), style.BLUE),
    ]
    dy_run, dy_base = 0.0, 0.0
    if base is not None:
        bx, bdel = _series(base, "reports_delivered")
        ax.plot(bx, bdel, color=style.MUTED, linewidth=2.4, linestyle="--", zorder=3)
        dy_run, dy_base = _spread(float(delivered[-1]), float(bdel[-1]), 0.07 * top)
        _end_label(ax, float(bx[-1]), float(bdel[-1]), f"{int(bdel[-1])}", style.MUTED, dy_base)
        entries.append(Series(tr(lang, "series_delivered_base"), style.MUTED, 2.4, linestyle="--"))
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
            base_created=base.summary["reports_created"],
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
    _frame(fig, lang, title, subtitle, _run_note(lang, run))
    return _save(fig, out)


def _tile(
    fig: Figure,
    box: tuple[float, float, float, float],
    value: str,
    label: str,
    notes: list[str],
    color: str,
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
            (x, y + h - 0.007),
            w,
            0.007,
            boxstyle="square,pad=0.0",
            facecolor=color,
            edgecolor="none",
            transform=fig.transFigure,
        )
    )
    size = 33 if len(value) <= 8 else 27
    fig.text(x + 0.016, y + h - 0.075, value, fontsize=size, fontweight="bold", va="center")
    fig.text(x + 0.016, y + h - 0.128, textwrap.fill(label, 28), fontsize=13, color=style.INK2, va="top")
    # każdy dopisek zawijany osobno, żeby wariant bazowy zawsze zaczynał się od nowego wiersza
    lines = "\n".join(textwrap.fill(note, 34) for note in notes if note)
    fig.text(x + 0.016, y + 0.02, lines, fontsize=11.5, color=style.INK2, va="bottom", linespacing=1.3)


def plot_scorecard(run: Light, base: Light | None, out: Path, lang: str = "pl") -> Path:
    """Karta wyników: najważniejsze liczby jednego uruchomienia, w układzie dwóch modułów."""
    style.apply_style()
    fig = Figure(figsize=_FIGSIZE, dpi=_DPI)
    FigureCanvasAgg(fig)
    s = run.summary
    b = base.summary if base is not None else None

    def versus(text: str) -> str:
        return "" if b is None else tr(lang, "card_base", value=text)

    def when(key: str) -> str:
        value = s.get(key)
        return tr(lang, "card_never") if value is None else elapsed(lang, float(value))

    alerts = [
        (
            _pct(float(s["alert_reach_app"])),
            tr(lang, "card_reach"),
            [
                tr(lang, "card_reach_note", t50=when("t50_app_s")),
                tr(lang, "card_zone_note", zone=_pct(float(s["alert_reach_zone_app"]))),
                versus(_pct(float(b["alert_reach_app"]))) if b is not None else "",
            ],
        ),
        (
            f"{s['alert_reach_all']:.0f}% + {s['wom_reach_all']:.0f}%",
            tr(lang, "card_all"),
            [tr(lang, "card_all_note")],
        ),
        (
            _pct(float(s["evacuated_zone"])),
            tr(lang, "card_evac"),
            [versus(_pct(float(b["evacuated_zone"]))) if b is not None else "", tr(lang, "card_evac_note")],
        ),
        (
            f"{s['fake_verified_devices']}",
            tr(lang, "card_fake"),
            [tr(lang, "card_fake_note", received=s["fake_received_devices"])],
        ),
    ]
    reports = [
        (
            f"{s['reports_delivered']} / {s['reports_created']}",
            tr(lang, "card_reports"),
            [
                versus(tr(lang, "card_of", a=b["reports_delivered"], b=b["reports_created"]))
                if b is not None
                else ""
            ],
        ),
        (
            f"{s['need_help_delivered']} / {s['need_help_created']}",
            tr(lang, "card_need"),
            [tr(lang, "card_need_note")],
        ),
        (
            f"{s['acks_received']}",
            tr(lang, "card_acks"),
            [tr(lang, "card_acks_note", pct=float(s["acks_received_pct"]))],
        ),
        (
            elapsed(lang, float(s["delay_median_s"])),
            tr(lang, "card_delay"),
            [tr(lang, "card_delay_note", p90=elapsed(lang, float(s["delay_p90_s"])))],
        ),
    ]
    left, right = 0.045, 0.955
    gap_x = 0.018
    cols = 4
    width = (right - left - gap_x * (cols - 1)) / cols
    height = 0.312
    rows = (
        (0.772, tr(lang, "card_row_alerts"), alerts, style.BLUE),
        (0.418, tr(lang, "card_row_reports"), reports, style.VIOLET),
    )
    for top, header, tiles, color in rows:
        fig.text(left, top + 0.012, header, fontsize=13, fontweight="bold", color=style.INK2, va="bottom")
        for col, (value, label, notes) in enumerate(tiles):
            box = (left + col * (width + gap_x), top - height, width, height)
            _tile(fig, box, value, label, notes, color)
    hours = float(run.metrics["t"].iloc[-1]) / 3600.0
    title = tr(
        lang,
        "card_title",
        hours=hours,
        reach=_pct(float(s["alert_reach_app"])),
        delivered=s["reports_delivered"],
        fake=s["fake_verified_devices"],
    )
    subtitle = tr(
        lang,
        "card_sub",
        contacts=s["contacts_total"],
        megabytes=float(s["bytes_total"]) / 1e6,
        battery=float(s["battery_mean"]),
    )
    _frame(fig, lang, title, subtitle, _run_note(lang, run))
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
