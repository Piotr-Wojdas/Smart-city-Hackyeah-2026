"""Przegląd parametrów: siatka zadań, warianty odniesienia, agregacja, pliki wynikowe i WYNIKI.md."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sztafeta.batch import (
    REFERENCE_VARIANTS,
    BatchSpec,
    aggregate,
    parse_list,
    percent_list,
    run_batch,
    write_outputs,
)
from sztafeta.wyniki import _number, adoption_threshold

N_VARIANTS = len(REFERENCE_VARIANTS)


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


def _ref(runs: pd.DataFrame, variant: str) -> pd.DataFrame:
    return runs[(runs["variant"] == variant) & (runs["adoption"] == 0.5) & (runs["couriers"] == 2)]


def test_batch_runs_every_combination_and_reference_variants(runs: pd.DataFrame) -> None:
    assert len(runs) == 2 * 1 * 2 * 2 + N_VARIANTS * 2
    full = runs[runs["variant"] == "full"]
    assert sorted(full["adoption"].unique()) == [0.2, 0.5]
    assert sorted(full["couriers"].unique()) == [1, 2]
    assert set(runs["variant"]) == {"full", *[name for name, _, _ in REFERENCE_VARIANTS]}
    assert (runs["fake_verified_devices"] == 0).all()
    # większa adopcja = więcej telefonów z aplikacją w tej samej populacji
    by_adoption = full.groupby("adoption")["residents_with_app"].mean()
    assert by_adoption[0.5] > by_adoption[0.2]


def test_reference_variants_isolate_each_mechanism(runs: pd.DataFrame) -> None:
    full = _ref(runs, "full")
    baseline = _ref(runs, "baseline")
    phones = _ref(runs, "phones_only")
    couriers = _ref(runs, "couriers_only")
    no_wom = _ref(runs, "no_wom")
    household = _ref(runs, "wom_household")
    reach = "alert_reach_app"
    # wariant bazowy jest najsłabszy
    assert baseline[reach].mean() < min(phones[reach].mean(), couriers[reach].mean())
    # sami kurierzy: telefony nie podają dalej, więc zasięg jest mniejszy niż w pełnej Sztafecie
    assert couriers[reach].mean() < full[reach].mean()
    # bez kurierów nikt nie zbiera zgłoszeń po drodze
    assert phones["reports_delivered"].mean() < full["reports_delivered"].mean()
    # przekaz ustny: wyłączony = nikt bez aplikacji się nie ewakuuje; tylko domownicy = mniej niż z sąsiadami
    assert (no_wom["evacuated_zone_wom"] == 0).all()
    assert (no_wom["wom_reach_all"] == 0).all()
    assert household["wom_reach_all"].mean() < full["wom_reach_all"].mean()


def test_aggregate_reports_median_and_spread(runs: pd.DataFrame) -> None:
    summary = aggregate(runs)
    assert len(summary) == 4 + N_VARIANTS
    assert (summary["seeds"] == 2).all()
    pick = (summary["variant"] == "full") & (summary["adoption"] == 0.5) & (summary["couriers"] == 2)
    row = summary[pick].iloc[0]
    assert row["alert_reach_app_min"] <= row["alert_reach_app_med"] <= row["alert_reach_app_max"]
    assert 0 <= row["t50_app_s_reached"] <= 2
    assert row["fake_verified_devices_max"] == 0


def test_batch_is_deterministic(runs: pd.DataFrame) -> None:
    spec = _spec()
    spec.adoption, spec.couriers = [0.5], [2]
    spec.reference_variants = False
    again = run_batch(spec, workers=2)  # przez pulę procesów
    cols = [
        "seed",
        "alert_reach_app",
        "reports_created",
        "reports_delivered",
        "contacts_total",
        "bytes_total",
    ]
    first = _ref(runs, "full").sort_values("seed")[cols].reset_index(drop=True)
    assert first.equals(again.sort_values("seed")[cols].reset_index(drop=True))


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
    assert "## 5. Co daje który mechanizm" in text and "## 6. Wrażliwość na założenia" in text
    assert "Sami kurierzy, bez przekazywania telefon–telefon" in text
    assert "uznało za zweryfikowany **0 urządzeń**" in text
    assert (docs.parent / "wykresy" / "adopcja_czas_pl.png").exists()
    # każde zdanie „na slajd” o wynikach podaje parametry, przy których zachodzi
    slide = text.split("## Liczby na slajd")[1].split("##")[0]
    assert slide.count("adopcja 50%, zasięg 40 m, 2 kurierów") >= 4
    # ewakuacja jest rozbita na osoby z aplikacją i poinformowane ustnie
    assert "osoby bez aplikacji poinformowane ustnie" in slide


def test_adoption_threshold_follows_stated_criterion() -> None:
    spec = BatchSpec(adoption=[0.1, 0.3, 0.5], ranges=[40.0, 80.0], couriers=[5], seeds=[1])
    rows = []
    # (adopcja, czas do 50% w sekundach, zasięg w strefie)
    for adoption, t50, zone in ((0.1, 9000.0, 95.0), (0.3, 3000.0, 85.0), (0.5, 2000.0, 95.0)):
        rows.append(
            {
                "variant": "full",
                "adoption": adoption,
                "range_m": 40.0,
                "couriers": 5,
                "t50_app_s_med": t50,
                "alert_reach_zone_app_med": zone,
            }
        )
    rows.append(
        {
            "variant": "full",
            "adoption": 0.1,
            "range_m": 80.0,
            "couriers": 5,
            "t50_app_s_med": 1200.0,
            "alert_reach_zone_app_med": 99.0,
        }
    )
    # wiersz wariantu wrażliwości nie może wpływać na próg
    rows.append(
        {
            "variant": "scan_5_120",
            "adoption": 0.1,
            "range_m": 40.0,
            "couriers": 5,
            "t50_app_s_med": 100.0,
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


def test_results_never_round_a_value_below_100_up_to_100() -> None:
    assert _number(83.7) == "84" and _number(2.46, 1) == "2.5"
    assert _number(100.0) == "100"
    assert _number(99.7) == "99.7" and _number(99.97) == "99.9" and _number(99.96, 1) == "99.9"
    assert _number(99.4) == "99"
