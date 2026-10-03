"""Przegląd parametrów: adopcja x zasięg x kurierzy x seedy, równolegle przez multiprocessing.

Wynik: `results/batch/runs.csv` (wiersz na uruchomienie), `summary.csv` (mediana i rozrzut między
seedami), wykresy w `plots/` oraz `docs/WYNIKI.md`. Wszystkie liczby to wyniki modelu.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from sztafeta.io.writer import code_version
from sztafeta.runner import run_once

RUNS_FILE = "runs.csv"
SUMMARY_FILE = "summary.csv"
KEYS = ["baseline", "adoption", "range_m", "couriers"]

# metryki agregowane między seedami (mediana, minimum, maksimum)
METRICS = [
    "t50_app_s",
    "t90_app_s",
    "t90_zone_app_s",
    "alert_reach_app",
    "alert_reach_app_1h",
    "alert_reach_zone_app",
    "alert_reach_all",
    "wom_reach_all",
    "evacuated_zone",
    "reports_created",
    "reports_delivered_pct",
    "reports_delivered_pct_1h",
    "reports_delivered_pct_3h",
    "need_help_delivered_pct",
    "delay_median_s",
    "acks_received_pct",
    "fake_received_devices",
    "fake_verified_devices",
    "battery_mean",
    "bytes_total",
    "wall_s",
]


@dataclass(slots=True)
class BatchSpec:
    """Siatka przeglądu. Adopcja w ułamkach (0.3 = 30%), zasięg w metrach."""

    preset: str = "flood-stronie"
    adoption: list[float] = field(default_factory=lambda: [0.05, 0.10, 0.20, 0.30, 0.50])
    ranges: list[float] = field(default_factory=lambda: [25.0, 40.0, 80.0])
    couriers: list[int] = field(default_factory=lambda: [2, 5, 10])
    seeds: list[int] = field(default_factory=lambda: [1, 2, 3, 4, 5])
    duration_s: float | None = None
    baseline_adoption: float = 0.30
    baseline_range: float = 40.0
    baseline_couriers: int = 5

    def jobs(self) -> list[tuple[str, int, tuple[str, ...], bool, float | None, float, float, int]]:
        out = []
        for adoption in self.adoption:
            for range_m in self.ranges:
                for couriers in self.couriers:
                    for seed in self.seeds:
                        out.append(self._job(seed, adoption, range_m, couriers, False))
        # wariant bazowy „bez Sztafety” dla punktu odniesienia, te same seedy
        for seed in self.seeds:
            out.append(
                self._job(seed, self.baseline_adoption, self.baseline_range, self.baseline_couriers, True)
            )
        return out

    def _job(
        self, seed: int, adoption: float, range_m: float, couriers: int, baseline: bool
    ) -> tuple[str, int, tuple[str, ...], bool, float | None, float, float, int]:
        overrides = (
            f"behavior.adoption={adoption}",
            f"radio.range_m={range_m}",
            f"population.n_couriers={couriers}",
        )
        return (self.preset, seed, overrides, baseline, self.duration_s, adoption, range_m, couriers)


def _run_job(job: tuple[str, int, tuple[str, ...], bool, float | None, float, float, int]) -> dict[str, Any]:
    """Jedno uruchomienie w procesie roboczym (bez zapisu snapshotów)."""
    preset, seed, overrides, baseline, duration, adoption, range_m, couriers = job
    result = run_once(preset, seed, overrides, baseline, out_root=None, until=duration)
    row = dict(result.summary)
    row.update(
        {"adoption": adoption, "range_m": range_m, "couriers": couriers, "wall_s": round(result.wall_s, 2)}
    )
    row["map_source"] = result.map_source
    return row


def run_batch(
    spec: BatchSpec,
    workers: int | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    """Uruchamia wszystkie kombinacje i zwraca tabelę z jednym wierszem na uruchomienie."""
    jobs = spec.jobs()
    n_workers = workers or max((os.cpu_count() or 2) - 1, 1)
    rows: list[dict[str, Any]] = []
    if n_workers == 1:
        for k, job in enumerate(jobs):
            rows.append(_run_job(job))
            if progress is not None:
                progress(k + 1, len(jobs))
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futures = [pool.submit(_run_job, job) for job in jobs]
            for k, future in enumerate(as_completed(futures)):
                rows.append(future.result())
                if progress is not None:
                    progress(k + 1, len(jobs))
    runs = pd.DataFrame(rows)
    # kolejność wyników z puli jest przypadkowa – sortujemy, żeby pliki były powtarzalne
    return runs.sort_values([*KEYS, "seed"]).reset_index(drop=True)


def aggregate(runs: pd.DataFrame) -> pd.DataFrame:
    """Mediana, minimum i maksimum między seedami dla każdej kombinacji parametrów."""
    rows: list[dict[str, Any]] = []
    for key, group in runs.groupby(KEYS, sort=True):
        row: dict[str, Any] = dict(zip(KEYS, key, strict=True))
        row["seeds"] = len(group)
        for metric in METRICS:
            values = pd.to_numeric(group[metric], errors="coerce")
            reached = values.dropna()
            if metric.startswith("t"):
                row[f"{metric}_reached"] = len(reached)
            row[f"{metric}_med"] = float(reached.median()) if len(reached) else None
            row[f"{metric}_min"] = float(reached.min()) if len(reached) else None
            row[f"{metric}_max"] = float(reached.max()) if len(reached) else None
        rows.append(row)
    return pd.DataFrame(rows)


def write_outputs(
    runs: pd.DataFrame,
    spec: BatchSpec,
    out_dir: Path,
    docs_path: Path | None,
    lang: str = "pl",
) -> list[Path]:
    """Zapisuje CSV, wykresy i (opcjonalnie) `docs/WYNIKI.md`. Zwraca listę utworzonych plików."""
    from sztafeta.viz.batch_charts import render_batch_charts
    from sztafeta.wyniki import write_wyniki

    out_dir.mkdir(parents=True, exist_ok=True)
    summary = aggregate(runs)
    runs.to_csv(out_dir / RUNS_FILE, index=False, lineterminator="\n")
    summary.to_csv(out_dir / SUMMARY_FILE, index=False, lineterminator="\n")
    paths = [out_dir / RUNS_FILE, out_dir / SUMMARY_FILE]
    paths += render_batch_charts(summary, spec, out_dir / "plots", lang)
    if docs_path is not None:
        paths.append(write_wyniki(runs, summary, spec, docs_path, out_dir, code_version()))
    return paths


def parse_list(text: str, cast: Callable[[str], Any]) -> list[Any]:
    """„5,10,20” -> [5, 10, 20]."""
    return [cast(part.strip()) for part in text.split(",") if part.strip()]


def percent_list(values: Sequence[float]) -> list[float]:
    """Adopcja podana w procentach (5, 10, 30) -> ułamki (0.05, 0.1, 0.3)."""
    return [v / 100.0 for v in values]
