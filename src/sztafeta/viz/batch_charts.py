"""Wykresy z przeglądu parametrów: mediana między seedami i pas rozrzutu (minimum–maksimum)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from matplotlib.axes import Axes
from matplotlib.ticker import FuncFormatter, MultipleLocator

from sztafeta.viz import style
from sztafeta.viz.charts import _declutter, _end_label, _figure, _frame, _legend, _pct, _save
from sztafeta.viz.labels import tr

if TYPE_CHECKING:
    from sztafeta.batch import BatchSpec

_SERIES = (style.BLUE, style.ORANGE, style.AQUA)


def _pick(values: list[float], preferred: float) -> float:
    return preferred if preferred in values else values[len(values) // 2]


def _relay(summary: pd.DataFrame, **fixed: float) -> pd.DataFrame:
    """Wiersze wariantu „Sztafeta” dla ustalonych wartości wybranych parametrów."""
    rows = summary[~summary["baseline"].astype(bool)]
    for key, value in fixed.items():
        rows = rows[rows[key] == value]
    return rows.sort_values(["adoption", "range_m", "couriers"])


def _band(ax: Axes, x: Any, rows: pd.DataFrame, metric: str, color: str, scale: float = 1.0) -> None:
    med = rows[f"{metric}_med"].to_numpy(dtype=float) * scale
    lo = rows[f"{metric}_min"].to_numpy(dtype=float) * scale
    hi = rows[f"{metric}_max"].to_numpy(dtype=float) * scale
    ax.fill_between(x, lo, hi, color=color, alpha=0.16, linewidth=0, zorder=2)
    ax.plot(
        x,
        med,
        color=color,
        linewidth=3.0,
        marker="o",
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


def plot_time_vs_adoption(summary: pd.DataFrame, spec: BatchSpec, out: Path, lang: str = "pl") -> Path:
    """Czas do zasięgu 50% i 90% telefonów z aplikacją w funkcji adopcji."""
    range_m = _pick(spec.ranges, 40.0)
    couriers = _pick([float(c) for c in spec.couriers], 5.0)
    rows = _relay(summary, range_m=range_m, couriers=couriers)
    fig, ax = _figure()
    x = rows["adoption"].to_numpy(dtype=float) * 100.0
    n_seeds = len(spec.seeds)
    entries = []
    full_90: float | None = None
    for metric, color, key in (
        ("t50_app_s", style.BLUE, "series_t50"),
        ("t90_app_s", style.ORANGE, "series_t90"),
    ):
        _band(ax, x, rows, metric, color, scale=1.0 / 60.0)
        entries.append((tr(lang, key), color, 3.0))
        for xi, reached, med in zip(x, rows[f"{metric}_reached"], rows[f"{metric}_med"], strict=True):
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
            if metric == "t90_app_s" and reached == n_seeds and full_90 is None:
                full_90 = float(xi)
    duration_min = (spec.duration_s or 21600.0) / 60.0
    ax.set_ylim(0, duration_min)
    ax.yaxis.set_major_locator(MultipleLocator(60))
    ax.set_ylabel(tr(lang, "axis_minutes"), fontsize=15, labelpad=10)
    _adoption_axis(ax, lang, spec.adoption)
    _legend(ax, entries)
    within_hour = rows[rows["t50_app_s_med"] <= 3600.0]
    if len(within_hour):
        title = tr(lang, "time_title_hour", adoption=100.0 * float(within_hour["adoption"].iloc[0]))
    else:
        title = tr(lang, "time_title_slow")
    if full_90 is not None:
        subtitle = tr(lang, "time_sub_90", adoption=full_90)
    else:
        subtitle = tr(lang, "time_sub_90_never")
    fixed = tr(lang, "fixed_range_couriers", range_m=range_m, couriers=int(couriers))
    _frame(fig, lang, title, subtitle, _batch_note(lang, spec, fixed))
    return _save(fig, out)


def plot_reach_vs_adoption(summary: pd.DataFrame, spec: BatchSpec, out: Path, lang: str = "pl") -> Path:
    """Zasięg alertu na koniec symulacji w funkcji adopcji, osobna linia dla każdego zasięgu radia."""
    couriers = _pick([float(c) for c in spec.couriers], 5.0)
    fig, ax = _figure()
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_locator(MultipleLocator(25))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ranges = sorted(spec.ranges)[:3]
    entries = []
    ends: list[tuple[float, float, str, str]] = []
    for range_m, color in zip(ranges, _SERIES, strict=False):
        rows = _relay(summary, range_m=range_m, couriers=couriers)
        x = rows["adoption"].to_numpy(dtype=float) * 100.0
        _band(ax, x, rows, "alert_reach_app", color)
        last = float(rows["alert_reach_app_med"].iloc[-1])
        ends.append((float(x[-1]), last, f"{_pct(last)} ({range_m:.0f} m)", color))
        entries.append((tr(lang, "range_label", range_m=range_m), color, 3.0))
    label_y = _declutter([end[1] for end in ends], 6.5)
    for (end_x, end_y, text, color), text_y in zip(ends, label_y, strict=True):
        _end_label(ax, end_x, end_y, text, color, label_y=text_y)
    ax.set_ylabel(tr(lang, "reach_axis"), fontsize=15, labelpad=10)
    _adoption_axis(ax, lang, spec.adoption)
    ax.set_xlim(0, 100.0 * max(spec.adoption) * 1.16)
    _legend(ax, entries)
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
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_locator(MultipleLocator(25))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    x = rows["couriers"].to_numpy(dtype=float)
    entries = []
    series = (
        ("reports_delivered_pct", style.BLUE, "series_rep_end"),
        ("reports_delivered_pct_3h", style.ORANGE, "series_rep_3h"),
        ("reports_delivered_pct_1h", style.AQUA, "series_rep_1h"),
    )
    for metric, color, key in series:
        if rows[f"{metric}_med"].isna().all():
            continue
        _band(ax, x, rows, metric, color)
        entries.append((tr(lang, key), color, 3.0))
    ax.set_xticks(x)
    ax.set_xlim(0, float(x.max()) * 1.08)
    ax.set_xlabel(tr(lang, "axis_couriers"), fontsize=15, labelpad=8)
    ax.set_ylabel(tr(lang, "axis_reports_pct"), fontsize=15, labelpad=10)
    _legend(ax, entries)
    first = float(rows["reports_delivered_pct_med"].iloc[0])
    last = float(rows["reports_delivered_pct_med"].iloc[-1])
    early = rows["reports_delivered_pct_1h_med"]
    if early.notna().all():
        title = tr(
            lang,
            "couriers_title_1h",
            few=int(x[0]),
            few_pct=_pct(float(early.iloc[0])),
            many=int(x[-1]),
            many_pct=_pct(float(early.iloc[-1])),
        )
        subtitle = tr(lang, "couriers_sub_1h", few_pct=_pct(first), many_pct=_pct(last))
    else:
        title = tr(
            lang, "couriers_title", few=int(x[0]), few_pct=_pct(first), many=int(x[-1]), many_pct=_pct(last)
        )
        subtitle = tr(lang, "couriers_sub")
    fixed = tr(lang, "fixed_adoption_range", adoption=100.0 * adoption, range_m=range_m)
    _frame(fig, lang, title, subtitle, _batch_note(lang, spec, fixed))
    return _save(fig, out)


def render_batch_charts(
    summary: pd.DataFrame, spec: BatchSpec, out_dir: Path, lang: str = "pl"
) -> list[Path]:
    paths = [plot_time_vs_adoption(summary, spec, out_dir / f"adopcja_czas_{lang}.png", lang)]
    if len(spec.adoption) > 1:
        paths.append(plot_reach_vs_adoption(summary, spec, out_dir / f"adopcja_zasieg_{lang}.png", lang))
    if len(spec.couriers) > 1:
        paths.append(
            plot_reports_vs_couriers(summary, spec, out_dir / f"kurierzy_zgloszenia_{lang}.png", lang)
        )
    return paths
