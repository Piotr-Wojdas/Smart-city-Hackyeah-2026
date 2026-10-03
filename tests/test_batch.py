"""Przegląd parametrów: siatka zadań, agregacja między seedami, pliki wynikowe i WYNIKI.md."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sztafeta.batch import BatchSpec, aggregate, parse_list, percent_list, run_batch, write_outputs
from sztafeta.wyniki import adoption_threshold


def _spec() -> BatchSpec:
    spec = BatchSpec(
        preset="test-small",
        adoption=[0.2, 0.5],
        ranges=[40.0],
        couriers=[1, 2],
        seeds=[1, 2],
        duration_s=1500.0,
    )
    spec.baseline_adoption, spec.baseline_range, spec.baseline_couriers = 0.5, 40.0, 2
    return spec


@pytest.fixture(scope="module")
def runs() -> pd.DataFrame:
    return run_batch(_spec(), workers=1)


def test_batch_runs_every_combination_and_baseline(runs: pd.DataFrame) -> None:
    assert len(runs) == 2 * 1 * 2 * 2 + 2
    relay = runs[~runs["baseline"]]
    assert sorted(relay["adoption"].unique()) == [0.2, 0.5]
    assert sorted(relay["couriers"].unique()) == [1, 2]
    assert set(runs[runs["baseline"]]["seed"]) == {1, 2}
    assert (runs["fake_verified_devices"] == 0).all()
    # większa adopcja = więcej telefonów z aplikacją w tej samej populacji
    by_adoption = relay.groupby("adoption")["residents_with_app"].mean()
    assert by_adoption[0.5] > by_adoption[0.2]
    # wariant bazowy nie dorównuje Sztafecie przy tych samych ustawieniach
    ref = relay[(relay["adoption"] == 0.5) & (relay["couriers"] == 2)]["alert_reach_app"].mean()
    assert runs[runs["baseline"]]["alert_reach_app"].mean() < ref


def test_aggregate_reports_median_and_spread(runs: pd.DataFrame) -> None:
    summary = aggregate(runs)
    assert len(summary) == 5
    assert (summary["seeds"] == 2).all()
    row = summary[(~summary["baseline"]) & (summary["adoption"] == 0.5) & (summary["couriers"] == 2)].iloc[0]
    assert row["alert_reach_app_min"] <= row["alert_reach_app_med"] <= row["alert_reach_app_max"]
    assert 0 <= row["t50_app_s_reached"] <= 2
    assert row["fake_verified_devices_max"] == 0


def test_batch_is_deterministic(runs: pd.DataFrame) -> None:
    spec = _spec()
    spec.adoption, spec.couriers = [0.5], [2]
    again = run_batch(spec, workers=2)  # przez pulę procesów
    cols = [
        "seed",
        "alert_reach_app",
        "reports_created",
        "reports_delivered",
        "contacts_total",
        "bytes_total",
    ]
    first = runs[(runs["adoption"] == 0.5) & (runs["couriers"] == 2)].sort_values(["baseline", "seed"])
    assert (
        first[cols]
        .reset_index(drop=True)
        .equals(again.sort_values(["baseline", "seed"])[cols].reset_index(drop=True))
    )


def test_outputs_and_results_document(runs: pd.DataFrame, tmp_path: Path) -> None:
    spec = _spec()
    docs = tmp_path / "docs" / "WYNIKI.md"
    paths = write_outputs(runs, spec, tmp_path / "batch", docs)
    names = {p.name for p in paths}
    assert {"runs.csv", "summary.csv", "adopcja_czas_pl.png", "WYNIKI.md"} <= names
    assert len(pd.read_csv(tmp_path / "batch" / "runs.csv")) == len(runs)
    text = docs.read_text(encoding="utf-8")
    assert "wyniki modelu, nie pomiary" in text
    assert "## Liczby na slajd" in text and "## Od jakiej adopcji system ma sens" in text
    assert "uznało za zweryfikowany **0 urządzeń**" in text
    assert (docs.parent / "wykresy" / "adopcja_czas_pl.png").exists()
    # każde zdanie „na slajd” podaje parametry, przy których zachodzi
    slide = text.split("## Liczby na slajd")[1].split("##")[0]
    assert slide.count("adopcja 50%, zasięg 40 m, 2 kurierów") >= 3


def test_adoption_threshold_follows_stated_criterion() -> None:
    spec = BatchSpec(adoption=[0.1, 0.3, 0.5], ranges=[40.0, 80.0], couriers=[5], seeds=[1])
    rows = []
    # (adopcja, czas do 50% w sekundach, zasięg w strefie)
    for adoption, t50, zone in ((0.1, 9000.0, 95.0), (0.3, 3000.0, 85.0), (0.5, 2000.0, 95.0)):
        rows.append(
            {
                "baseline": False,
                "adoption": adoption,
                "range_m": 40.0,
                "couriers": 5,
                "t50_app_s_med": t50,
                "alert_reach_zone_app_med": zone,
            }
        )
    rows.append(
        {
            "baseline": False,
            "adoption": 0.1,
            "range_m": 80.0,
            "couriers": 5,
            "t50_app_s_med": 1200.0,
            "alert_reach_zone_app_med": 99.0,
        }
    )
    summary = pd.DataFrame(rows)
    # 10%: za wolno; 30%: szybko, ale za mały zasięg w strefie; 50%: spełnia oba warunki
    assert adoption_threshold(summary, spec) == 0.5
    assert adoption_threshold(summary, spec, 80.0) == 0.1
    summary.loc[(summary["adoption"] == 0.5), "t50_app_s_med"] = None  # progu 50% nie osiągnięto
    assert adoption_threshold(summary, spec) is None


def test_list_parsing() -> None:
    assert parse_list("5, 10,30", float) == [5.0, 10.0, 30.0]
    assert parse_list("2,5", int) == [2, 5]
    assert percent_list([5.0, 30.0]) == [0.05, 0.3]
    with pytest.raises(ValueError, match="could not convert"):
        parse_list("5,x", float)
