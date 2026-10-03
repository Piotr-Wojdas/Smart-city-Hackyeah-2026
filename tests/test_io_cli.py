"""Zapis wyników, odczyt, CLI i wizualizacja na małym scenariuszu."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from sztafeta.cli import app
from sztafeta.io import load_run
from sztafeta.runner import make_run_id, run_once

FILES = (
    "params.yaml",
    "metrics.csv",
    "events.jsonl",
    "snapshots.npz",
    "static.json",
    "pczk.json",
    "summary.json",
)


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("results")
    result = run_once("test-small", seed=42, out_root=out, until=1500.0)
    assert result.out_dir is not None
    return result.out_dir


def test_run_writes_all_files(run_dir: Path) -> None:
    for name in FILES:
        assert (run_dir / name).stat().st_size > 0, name
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["run_id"] == "test-small_s42"
    assert summary["fake_verified_devices"] == 0
    assert summary["alert_reach_app"] > 0


def test_loaded_run_is_consistent(run_dir: Path) -> None:
    run = load_run(run_dir)
    n = run.static["agents"]["n"]
    frames = run.t.size
    assert run.x.shape == (frames, n) and run.state.shape == (frames, n)
    assert run.t[0] == 0.0 and run.t[-1] == 1500.0
    assert np.all(np.diff(run.t) > 0)
    assert run.links_ptr.size == frames + 1 and run.links_ptr[-1] == run.links.shape[0]
    assert len(run.metrics) == 151
    assert next(iter(run.metrics.columns)) == "t"
    types = {e["type"] for e in run.events}
    assert {"network_down", "alert_issued", "alert_received", "contact", "transfer"} <= types
    # zdarzenia są uporządkowane w czasie
    times = [e["t"] for e in run.events]
    assert times == sorted(times)
    # połączenia ze snapshotu odnoszą się do istniejących agentów i są w zasięgu radia
    links = run.links_at(int(np.argmax(np.diff(run.links_ptr))))
    assert links.size > 0
    frame = int(np.argmax(np.diff(run.links_ptr)))
    a, b = links[:, 0], links[:, 1]
    dist = np.hypot(run.x[frame, a] - run.x[frame, b], run.y[frame, a] - run.y[frame, b])
    assert (dist <= run.static["map"]["radio_range_m"] + 1e-3).all()


def test_same_seed_gives_identical_metrics_file(run_dir: Path, tmp_path: Path) -> None:
    again = run_once("test-small", seed=42, out_root=tmp_path, until=1500.0)
    assert again.out_dir is not None
    for name in ("metrics.csv", "events.jsonl", "summary.json", "pczk.json"):
        assert (again.out_dir / name).read_bytes() == (run_dir / name).read_bytes(), name


def test_run_id_is_deterministic_and_distinguishes_variants() -> None:
    assert make_run_id("flood-stronie", 42, False, []) == "flood-stronie_s42"
    assert make_run_id("flood-stronie", 42, True, []) == "flood-stronie_s42_baseline"
    a = make_run_id("flood-stronie", 42, False, ["radio.range_m=80"])
    b = make_run_id("flood-stronie", 42, False, ["radio.range_m=20"])
    assert a != b and a.startswith("flood-stronie_s42_")


def test_cli_run_and_unknown_preset(tmp_path: Path) -> None:
    runner = CliRunner()
    ok = runner.invoke(
        app,
        [
            "run",
            "--preset",
            "test-small",
            "--seed",
            "3",
            "--until",
            "600",
            "--out",
            str(tmp_path),
            "--baseline",
        ],
    )
    assert ok.exit_code == 0, ok.output
    assert "wynik modelu" in ok.output
    assert (tmp_path / "test-small_s3_baseline" / "summary.json").exists()
    bad = runner.invoke(app, ["run", "--preset", "nie-ma-takiego", "--out", str(tmp_path)])
    assert bad.exit_code == 2
    wrong = runner.invoke(
        app, ["run", "--preset", "test-small", "--set", "radio.zasieg=1", "--out", str(tmp_path)]
    )
    assert wrong.exit_code == 2


def test_frame_and_animation_render(run_dir: Path, tmp_path: Path) -> None:
    from sztafeta.viz.animate import render_animation, render_frame

    png = render_frame(run_dir, tmp_path / "klatka.png", t=900.0, lang="en", dpi=50)
    assert png.stat().st_size > 10_000
    movie = render_animation(run_dir, tmp_path / "anim", every=30, dpi=50, fps=10, hold_s=0.2)
    assert movie.suffix in (".mp4", ".gif")
    assert movie.stat().st_size > 5_000


def test_story_is_ordered_and_ends_with_summary(run_dir: Path) -> None:
    from sztafeta.io.reader import load_run
    from sztafeta.viz.animate import _STORY_EVENTS, build_story

    run = load_run(run_dir, _STORY_EVENTS)
    story = build_story(run, "pl")
    times = [t for t, _ in story]
    texts = [text for _, text in story]
    assert times == sorted(times)
    assert texts[0] == "Awaria sieci komórkowej"
    assert texts[-1].startswith("Bilans:") and times[-1] == run.t[-1]
    assert len(texts) == len(set(texts))  # każdy moment pojawia się raz
    # kurier nie może „zbierać zgłoszeń”, zanim wyruszył
    assert texts.index("Kurierzy wyruszają w teren") < texts.index("Kurier zbiera zgłoszenia")
    # „alert idzie od telefonu do telefonu” dopiero wtedy, gdy widać go w liczniku zasięgu
    relay_t = times[texts.index("Alert idzie od telefonu do telefonu")]
    row = run.metrics[run.metrics["t"] == relay_t].iloc[0]
    assert row["alert_reach_app"] >= 5.0


def test_frame_plan_is_dense_early_and_holds_on_key_moments() -> None:
    import numpy as np

    from sztafeta.viz.animate import frame_plan

    times = np.arange(0.0, 21601.0, 10.0)
    plan = frame_plan(times, [600.0, 7200.0], 0.0, None, None, None, hold_frames=5)
    assert plan == sorted(plan)  # czas nigdy się nie cofa
    assert plan[0] == 0 and plan[-1] == times.size - 1
    unique = sorted(set(plan))
    early = [k for k in unique if times[k] < 5400.0]
    late = [k for k in unique if times[k] >= 5400.0]
    assert np.diff(early).max() == 2 and np.diff(late[:-1]).max() == 6
    assert plan.count(60) == 6 and plan.count(720) == 6  # zatrzymanie: klatka + 5 powtórzeń
    uniform = frame_plan(times, [], 0.0, 3, 600.0, 1200.0, hold_frames=5)
    assert [float(times[k]) for k in uniform] == [600.0 + 30.0 * k for k in range(21)]
    assert frame_plan(times, [], 0.0, None, 50000.0, 60000.0, hold_frames=0) == []
