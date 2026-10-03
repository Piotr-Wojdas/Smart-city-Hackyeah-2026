"""Wykresy z przeglądu parametrów: mediana między seedami i pas rozrzutu (minimum–maksimum).

Serie różnią się kolorem, znacznikiem i stylem linii jednocześnie, więc wykres da się odczytać także
w skali szarości. Wartość odniesienia (domyślne ustawienie modelu) jest zawsze niebieska.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from matplotlib.axes import Axes
from matplotlib.ticker import FuncFormatter, MultipleLocator

from sztafeta.viz import style
from sztafeta.viz.charts import (
    LineStyle,
    Series,
    _declutter,
    _end_label,
    _figure,
    _frame,
    _legend,
    _pct,
    _save,
)
from sztafeta.viz.labels import tr

if TYPE_CHECKING:
    from sztafeta.batch import BatchSpec

# (kolor, znacznik, styl linii): pierwsza pozycja dla wartości odniesienia
_STYLES: tuple[tuple[str, str, LineStyle], ...] = (
    (style.BLUE, "o", "-"),
    (style.ORANGE, "s", "--"),
    (style.VIOLET, "^", ":"),
)


def _pick(values: list[float], preferred: float) -> float:
    return preferred if preferred in values else values[len(values) // 2]


def _relay(summary: pd.DataFrame, **fixed: float) -> pd.DataFrame:
    """Wiersze wariantu „Sztafeta” dla ustalonych wartości wybranych parametrów."""
    rows = summary[summary["variant"] == "full"]
    for key, value in fixed.items():
        rows = rows[rows[key] == value]
    return rows.sort_values(["adoption", "range_m", "couriers"])


def _band(ax: Axes, x: Any, rows: pd.DataFrame, metric: str, look: Series, scale: float = 1.0) -> None:
    med = rows[f"{metric}_med"].to_numpy(dtype=float) * scale
    lo = rows[f"{metric}_min"].to_numpy(dtype=float) * scale
    hi = rows[f"{metric}_max"].to_numpy(dtype=float) * scale
    ax.fill_between(x, lo, hi, color=look.color, alpha=0.16, linewidth=0, zorder=2)
    ax.plot(
        x,
        med,
        color=look.color,
        linewidth=look.lw,
        linestyle=look.linestyle,
        marker=look.marker,
        markersize=9,
        markeredgecolor=style.SURFACE,
        markeredgewidth=2,
        zorder=4,
    )


def _adoption_axis(ax: Axes, lang: str, adoption: list[float]) -> None:
    ax.set_xticks([100.0 * a for a in adoption])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_xlabel(tr(lang, "axis_adoption"), fontsize=15, labelpad=8)
    ax.set_xlim(0, 100.0 * max(adoption) * 1.06)


def _batch_note(lang: str, spec: BatchSpec, fixed: str) -> str:
    return tr(lang, "batch_note", preset=Path(spec.preset).stem, seeds=len(spec.seeds), fixed=fixed)


def _percent_axis(ax: Axes) -> None:
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_locator(MultipleLocator(25))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))


def plot_time_vs_adoption(summary: pd.DataFrame, spec: BatchSpec, out: Path, lang: str = "pl") -> Path:
    """Czas, po którym połowa telefonów z aplikacją ma alert, w funkcji adopcji."""
    range_m = _pick(spec.ranges, 40.0)
    couriers = _pick([float(c) for c in spec.couriers], 5.0)
    rows = _relay(summary, range_m=range_m, couriers=couriers)
    fig, ax = _figure()
    x = rows["adoption"].to_numpy(dtype=float) * 100.0
    n_seeds = len(spec.seeds)
    look = Series(tr(lang, "series_t50"), style.BLUE, marker="o")
    _band(ax, x, rows, "t50_app_s", look, scale=1.0 / 60.0)
    for xi, reached, med in zip(x, rows["t50_app_s_reached"], rows["t50_app_s_med"], strict=True):
        if 0 < reached < n_seeds:
            ax.annotate(
                tr(lang, "reached_in", k=int(reached), n=n_seeds),
                (xi, float(med) / 60.0),
                xytext=(0, 13),
                textcoords="offset points",
                ha="center",
                fontsize=12,
                color=style.INK2,
            )
    worst = float(rows["t50_app_s_max"].max()) / 60.0 if rows["t50_app_s_max"].notna().any() else 0.0
    ax.set_ylim(0, max(240.0, 60.0 * math.ceil(worst / 60.0)))
    ax.yaxis.set_major_locator(MultipleLocator(60))
    ax.set_ylabel(tr(lang, "axis_minutes"), fontsize=15, labelpad=10)
    _adoption_axis(ax, lang, spec.adoption)
    _legend(ax, [look])

    within_hour = rows[rows["t50_app_s_med"] <= 3600.0]
    if len(within_hour):
        first = 100.0 * float(within_hour["adoption"].iloc[0])
        title = tr(lang, "time_title_hour", adoption=first, seeds=n_seeds)
    else:
        title = tr(lang, "time_title_slow")
    full = rows[rows["t90_app_s_reached"] == n_seeds]
    if len(full):
        subtitle = tr(lang, "time_sub_90", adoption=100.0 * float(full["adoption"].iloc[0]))
    else:
        best = rows.sort_values("t90_app_s_reached").iloc[-1]
        subtitle = tr(
            lang,
            "time_sub_90_never",
            k=int(best["t90_app_s_reached"]),
            n=n_seeds,
            adoption=100.0 * float(best["adoption"]),
        )
    fixed = tr(lang, "fixed_range_couriers", range_m=range_m, couriers=int(couriers))
    _frame(fig, lang, title, subtitle, _batch_note(lang, spec, fixed))
    return _save(fig, out)


def plot_reach_vs_adoption(summary: pd.DataFrame, spec: BatchSpec, out: Path, lang: str = "pl") -> Path:
    """Zasięg alertu na koniec symulacji w funkcji adopcji, osobna linia dla każdego zasięgu radia."""
    couriers = _pick([float(c) for c in spec.couriers], 5.0)
    reference = _pick(spec.ranges, 40.0)
    fig, ax = _figure()
    _percent_axis(ax)
    ranges = sorted(spec.ranges)[:3]
    # wartość odniesienia dostaje pierwszy styl (niebieski, linia ciągła), pozostałe kolejne
    ordered = [reference, *[r for r in ranges if r != reference]]
    looks = {
        r: Series(tr(lang, "range_label", range_m=r), color, marker=marker, linestyle=line)
        for r, (color, marker, line) in zip(ordered, _STYLES, strict=False)
    }
    ends: list[tuple[float, float, str, Series]] = []
    for range_m in ranges:
        rows = _relay(summary, range_m=range_m, couriers=couriers)
        x = rows["adoption"].to_numpy(dtype=float) * 100.0
        _band(ax, x, rows, "alert_reach_app", looks[range_m])
        last = float(rows["alert_reach_app_med"].iloc[-1])
        ends.append((float(x[-1]), last, f"{_pct(last)} ({range_m:.0f} m)", looks[range_m]))
    label_y = _declutter([end[1] for end in ends], 6.5)
    for (end_x, end_y, text, look), text_y in zip(ends, label_y, strict=True):
        _end_label(ax, end_x, end_y, text, look.color, label_y=text_y, marker=look.marker)
    ax.set_ylabel(tr(lang, "reach_axis"), fontsize=15, labelpad=10)
    _adoption_axis(ax, lang, spec.adoption)
    ax.set_xlim(0, 100.0 * max(spec.adoption) * 1.16)
    _legend(ax, [looks[r] for r in ranges])
    low = _pick(spec.adoption, 0.10)
    at_low = _relay(summary, adoption=low, couriers=couriers).set_index("range_m")["alert_reach_app_med"]
    title = tr(
        lang,
        "reach_batch_title",
        adoption=100.0 * low,
        short=ranges[0],
        short_pct=_pct(float(at_low[ranges[0]])),
        long=ranges[-1],
        long_pct=_pct(float(at_low[ranges[-1]])),
    )
    hours = (spec.duration_s or 21600.0) / 3600.0
    fixed = tr(lang, "fixed_couriers", couriers=int(couriers))
    _frame(fig, lang, title, tr(lang, "reach_batch_sub", hours=hours), _batch_note(lang, spec, fixed))
    return _save(fig, out)


def plot_reports_vs_couriers(summary: pd.DataFrame, spec: BatchSpec, out: Path, lang: str = "pl") -> Path:
    """Odsetek zgłoszeń dostarczonych do PCZK w funkcji liczby kurierów."""
    range_m = _pick(spec.ranges, 40.0)
    adoption = _pick(spec.adoption, 0.30)
    rows = _relay(summary, range_m=range_m, adoption=adoption)
    fig, ax = _figure()
    _percent_axis(ax)
    x = rows["couriers"].to_numpy(dtype=float)
    candidates = (
        ("reports_delivered_pct_1h", "series_rep_1h"),
        ("reports_delivered_pct_3h", "series_rep_3h"),
        ("reports_delivered_pct", "series_rep_end"),
    )
    present = [(metric, key) for metric, key in candidates if rows[f"{metric}_med"].notna().all()]
    entries: list[Series] = []
    ends: list[tuple[float, str, Series]] = []
    for (metric, key), (color, marker, line) in zip(present, _STYLES, strict=False):
        look = Series(tr(lang, key), color, marker=marker, linestyle=line)
        _band(ax, x, rows, metric, look)
        entries.append(look)
        last = float(rows[f"{metric}_med"].iloc[-1])
        ends.append((last, f"{_pct(last)} ({tr(lang, key)})", look))
    label_y = _declutter([end[0] for end in ends], 6.5)
    for (end_y, text, look), text_y in zip(ends, label_y, strict=True):
        _end_label(ax, float(x[-1]), end_y, text, look.color, label_y=text_y, marker=look.marker)
    ax.set_xticks(x)
    ax.set_xlim(0, float(x.max()) * 1.04)
    ax.set_xlabel(tr(lang, "axis_couriers"), fontsize=15, labelpad=8)
    ax.set_ylabel(tr(lang, "axis_reports_pct"), fontsize=15, labelpad=10)
    _legend(ax, entries)

    def cell(metric: str, k: int) -> str:
        row = rows.iloc[k]
        return tr(
            lang,
            "with_range",
            med=_pct(float(row[f"{metric}_med"])),
            lo=float(row[f"{metric}_min"]),
            hi=float(row[f"{metric}_max"]),
        )

    metric = present[0][0]
    key = "couriers_title_1h" if metric.endswith("_1h") else "couriers_title"
    title = tr(lang, key, few=int(x[0]), few_pct=cell(metric, 0), many=int(x[-1]), many_pct=cell(metric, -1))
    end_first = _pct(float(rows["reports_delivered_pct_med"].iloc[0]))
    end_last = _pct(float(rows["reports_delivered_pct_med"].iloc[-1]))
    subtitle = tr(lang, "couriers_sub", few_pct=end_first, many_pct=end_last)
    fixed = tr(lang, "fixed_adoption_range", adoption=100.0 * adoption, range_m=range_m)
    _frame(fig, lang, title, subtitle, _batch_note(lang, spec, fixed))
    return _save(fig, out)


def render_batch_charts(
    summary: pd.DataFrame, spec: BatchSpec, out_dir: Path, lang: str = "pl"
) -> list[Path]:
    paths = [plot_time_vs_adoption(summary, spec, out_dir / f"adopcja_czas_{lang}.png", lang)]
    if len(spec.adoption) > 1 and len(spec.ranges) > 1:
        paths.append(plot_reach_vs_adoption(summary, spec, out_dir / f"adopcja_zasieg_{lang}.png", lang))
    if len(spec.couriers) > 1:
        paths.append(
            plot_reports_vs_couriers(summary, spec, out_dir / f"kurierzy_zgloszenia_{lang}.png", lang)
        )
    return paths
