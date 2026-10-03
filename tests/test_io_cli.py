"""Zapis wyników, odczyt, CLI i wizualizacja na małym scenariuszu."""

from __future__ import annotations

import itertools
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
    movie = render_animation(run_dir, tmp_path / "anim", step_s=120.0, dpi=50, fps=10, closeup=False)
    assert movie.suffix in (".mp4", ".gif")
    assert movie.stat().st_size > 5_000
    zoom = render_frame(run_dir, tmp_path / "zblizenie.png", lang="pl", dpi=50, closeup=True)
    assert zoom.stat().st_size > 5_000


def test_story_tells_outage_couriers_relay_and_evacuation(run_dir: Path) -> None:
    from sztafeta.io.reader import load_run
    from sztafeta.viz.animate import _EVENTS, build_story, story_end

    run = load_run(run_dir, _EVENTS)
    end = story_end(run)
    story = build_story(run, "pl", end)
    times = [t for t, _ in story]
    texts = [text for _, text in story]
    assert times == sorted(times) and 0.0 <= times[-1] < end <= run.t[-1]
    assert texts[0] == "Awaria sieci komórkowej"
    assert texts[-1].startswith("Ewakuowano")
    assert len(texts) == len(set(texts))  # każdy moment pojawia się raz
    order = [
        "Awaria sieci komórkowej",
        "PCZK wydaje podpisany alert",
        "Kurierzy wyruszają w teren",
        "Telefony przekazują sobie alert",
        "Strefa zaczyna się ewakuować",
    ]
    assert [text for text in texts if text in order] == order
    # animacja nie opowiada o fałszywym alercie ani o zgłoszeniach do PCZK
    banned = ("fałszyw", "troll", "zgłosze", "potwierdz")
    assert not any(word in text.lower() for text in texts for word in banned)
    # film kończy się, gdy do punktu ewakuacji dotarła większość tych, którzy tam dotrą
    evacuated = run.metrics["evacuated_zone"].to_numpy()
    at_end = evacuated[int(np.searchsorted(run.metrics["t"].to_numpy(), end, side="right")) - 1]
    assert at_end >= 0.9 * evacuated[-1] > 0


def test_storyboard_runs_smoothly_and_inserts_closeup() -> None:
    from sztafeta.viz.animate import Closeup, Shot, storyboard

    close = Closeup(0.0, 0.0, 75.0, 1500.0, 1600.0, (0, 1, 2))
    shots = storyboard(7200.0, close, fps=10, step_s=12.0)
    times = [s.t for s in shots]
    assert times == sorted(times)  # czas nigdy się nie cofa
    assert shots[0] == Shot(0.0) and shots[-1] == Shot(7200.0)
    # poza zbliżeniem czas płynie równo i żadna klatka się nie powtarza (brak zatrzymań obrazu)
    city = [s.t for s in shots if s.zoom == 0.0]
    assert len(city) == len(set(city))
    before = [t for t in city if t < 1500.0]
    assert {round(b - a, 6) for a, b in itertools.pairwise(before)} == {12.0}
    # zbliżenie: najazd, zwolnione tempo (0,5 s na klatkę), odjazd
    zoomed = [s for s in shots if s.zoom == 1.0]
    assert zoomed[0].t == 1500.0 and zoomed[-1].t == 1600.0 and len(zoomed) == 201
    assert {round(b.t - a.t, 3) for a, b in itertools.pairwise(zoomed)} == {0.5}
    ramp_in = [s.zoom for s in shots if s.t == 1500.0 and 0.0 < s.zoom < 1.0]
    ramp_out = [s.zoom for s in shots if s.t == 1600.0 and 0.0 < s.zoom < 1.0]
    assert ramp_in == sorted(ramp_in) and ramp_out == sorted(ramp_out, reverse=True) and len(ramp_in) == 9
    assert not any(1500.0 < t < 1600.0 for t in city)  # czas zbliżenia nie jest pokazywany drugi raz

    plain = storyboard(7200.0, None, fps=10, step_s=12.0)
    assert all(s.zoom == 0.0 for s in plain) and len(plain) == 601
    part = storyboard(1200.0, close, 10, 30.0, t_from=600.0)
    assert [s.t for s in part] == [600.0 + 30.0 * k for k in range(21)]  # zbliżenie poza zakresem
    assert storyboard(100.0, None, 10, 12.0, t_from=500.0) == []


def test_closeup_shows_a_chain_of_three_phone_to_phone_handovers() -> None:
    from sztafeta.viz.animate import pick_chain

    # telefony 0..6; przekazania (nadawca -> odbiorca, czas):
    # wczesny łańcuch 0->1->2->3 trwa 300 s (za długi), późniejszy 3->4->5->6 trwa 40 s
    peer = np.array([0, 1, 2, 3, 4, 5, 9])
    agent = np.array([1, 2, 3, 4, 5, 6, 8])
    t = np.array([100.0, 250.0, 400.0, 1000.0, 1020.0, 1040.0, 50.0])
    visible = np.ones(t.size, dtype=bool)
    chain = pick_chain(t, agent, peer, visible)
    assert chain == (3, 4, 5)  # najwcześniejszy łańcuch mieszczący się w limicie czasu
    assert [int(agent[k]) for k in chain[:-1]] == [int(peer[k]) for k in chain[1:]]  # odbiorca podaje dalej
    assert pick_chain(t, agent, peer, visible, max_duration=20.0) == (3, 4, 5)  # nic w limicie: najkrótszy
    visible[4] = False  # np. przekazanie w obrębie jednego budynku albo przez kuriera
    assert pick_chain(t, agent, peer, visible) == (0, 1, 2)
    visible[1] = False
    assert pick_chain(t, agent, peer, visible) is None  # nie ma już żadnego łańcucha trzech przekazań


def test_closeup_of_real_run_draws_exactly_three_handovers(run_dir: Path) -> None:
    from sztafeta.io.reader import load_run
    from sztafeta.viz.animate import _EVENTS, MapAnimation

    anim = MapAnimation(load_run(run_dir, _EVENTS), dpi=40)
    close = anim.closeup
    assert close is not None and len(close.ids) == 3
    assert int(anim._in_close.sum()) == 3
    times = anim._got_t[list(close.ids)]
    assert list(times) == sorted(times)
    assert close.t0 < times[0] and times[-1] < close.t1 <= times[-1] + 6.0
    # każde z trzech przekazań mieści się w kadrze i ma długość najwyżej zasięgu radia
    x0, x1, y0, y1 = anim._close
    seg = anim._hand_seg[list(close.ids)]
    assert (seg[..., 0] > x0).all() and (seg[..., 0] < x1).all()
    assert (seg[..., 1] > y0).all() and (seg[..., 1] < y1).all()
    assert (np.hypot(*(seg[:, 1] - seg[:, 0]).T) <= 40.0 + 1e-6).all()
