"""Szablony wielojęzyczne, widok telefonu (`inspect`) i wykresy do slajdów."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from helpers import make_world
from sztafeta.cli import app
from sztafeta.engine.model import Action, Hazard, Lang, MsgType, Role
from sztafeta.engine.sim import Simulation
from sztafeta.engine.templates import render_alert
from sztafeta.runner import run_once
from sztafeta.scenarios import load_preset

PLACES = {"EVAC-1": "Szkoła Podstawowa"}


def test_alert_is_rendered_in_every_phone_language() -> None:
    w = make_world([(0, 0)], [Role.HUB])
    alert = w.alert()
    texts = [render_alert(alert, lang, True, PLACES) for lang in Lang]
    assert len({t.body for t in texts}) == len(Lang)
    assert len({t.title for t in texts}) == len(Lang)
    assert all("Szkoła Podstawowa" in t.body for t in texts)  # nazwa miejsca nie jest tłumaczona
    assert texts[Lang.PL].title == "Powódź"
    assert texts[Lang.EN].body == "Evacuate immediately to: Szkoła Podstawowa."
    assert texts[Lang.UK].lang == "uk"
    assert all(t.pictograms == ("flood", "evacuate") for t in texts)


def test_every_hazard_action_and_message_type_has_a_template() -> None:
    w = make_world([(0, 0)], [Role.HUB])
    alert = w.alert()
    for lang in Lang:
        for hazard in Hazard:
            for action in Action:
                for msg_type in MsgType:
                    custom = type(alert)(
                        **{
                            **{f: getattr(alert, f) for f in alert.__slots__},
                            "hazard": hazard,
                            "action": action,
                            "msg_type": msg_type,
                        }
                    )
                    text = render_alert(custom, lang, True, PLACES)
                    assert text.title and text.body and "{" not in text.body


def test_unverified_alert_has_a_warning_header_in_phone_language() -> None:
    w = make_world([(0, 0)], [Role.TROLL])
    fake = w.fake_alert()
    genuine = render_alert(w.alert(), Lang.DE, True, PLACES)
    forged = render_alert(fake, Lang.DE, False, PLACES)
    assert genuine.header == "VERIFIZIERTE AMTLICHE WARNUNG"
    assert forged.header.startswith("NICHT VERIFIZIERT")
    assert render_alert(fake, Lang.PL, False, PLACES).header.startswith("NIEZWERYFIKOWANE")


@pytest.fixture(scope="module")
def sim() -> Simulation:
    params, scenario = load_preset("test-small")
    out = Simulation(params, scenario, 42)
    out.run(2400.0)
    return out


def test_phone_view_separates_verified_and_fake_alerts(sim: Simulation) -> None:
    log = sim.router.alert_log
    both = [
        a for a, rows in log.items() if {v for _, _, v in rows} >= {0} and any(v != 0 for _, _, v in rows)
    ]
    assert both, "w scenariuszu testowym ktoś powinien dostać i prawdziwy, i fałszywy alert"
    view = sim.phone_view(both[0])
    verified = [a for a in view["alerts"] if a["verified"]]
    fake = [a for a in view["alerts"] if not a["verified"]]
    assert verified and fake
    assert all(a["status"] == "rejected" and a["verdict"] == "bad_signature" for a in fake)
    assert all(a["verdict"] == "verified" for a in verified)
    assert verified[0]["text"]["lang"] == view["lang"]
    assert fake[0]["text"]["header"] != verified[0]["text"]["header"]
    # fałszywka nie leży w buforze przekazywania
    fake_ids = {a["id"] for a in fake}
    assert not fake_ids & {p["id"] for p in view["buffer"]["packets"]}
    assert json.loads(json.dumps(view)) == view


def test_phone_view_shows_own_report_status(sim: Simulation) -> None:
    acked = [tr for tr in sim.router.tracks if tr.acked_version >= tr.latest_version]
    waiting = [tr for tr in sim.router.tracks if np.isnan(tr.delivered_t)]
    assert acked
    done = sim.phone_view(acked[0].reporter)["own_reports"][0]
    assert done["phone_status"] == "acked" and done["truth"]["status"] == "acked"
    assert done["acked_t"] >= done["truth"]["delivered_t"] >= done["created_t"]
    if waiting:
        pending = sim.phone_view(waiting[0].reporter)["own_reports"][0]
        assert pending["phone_status"] == "sent" and pending["acked_t"] is None
    with pytest.raises(ValueError, match="Nie ma agenta"):
        sim.phone_view(10**6)


def test_phone_view_of_person_without_app_is_empty(sim: Simulation) -> None:
    agent = int(np.flatnonzero(~sim.agents.has_app)[0])
    view = sim.phone_view(agent)
    assert not view["has_app"]
    assert view["alerts"] == [] and view["own_reports"] == [] and view["buffer"]["count"] == 0


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    out = tmp_path_factory.mktemp("results")
    relay = run_once("test-small", seed=42, out_root=out, until=1800.0)
    base = run_once("test-small", seed=42, out_root=out, until=1800.0, baseline=True)
    assert relay.out_dir is not None and base.out_dir is not None
    return relay.out_dir, base.out_dir


def test_inspect_cli_replays_run_to_given_time(runs: tuple[Path, Path]) -> None:
    relay_dir, _ = runs
    runner = CliRunner()
    result = runner.invoke(app, ["inspect", str(relay_dir), "--agent", "5", "--t", "900"])
    assert result.exit_code == 0, result.output
    view = json.loads(result.output)
    assert view["schema"] == "sztafeta.phone/1"
    assert view["agent"] == 5 and view["t"] == 900.0
    # to samo co bezpośrednie przeliczenie symulacji (determinizm)
    params, scenario = load_preset("test-small")
    direct = Simulation(params, scenario, 42)
    direct.run(900.0)
    assert direct.phone_view(5) == view
    missing = runner.invoke(app, ["inspect", str(relay_dir), "--agent", "999999"])
    assert missing.exit_code == 2


def test_charts_are_rendered_with_and_without_baseline(runs: tuple[Path, Path], tmp_path: Path) -> None:
    from sztafeta.viz.charts import render_charts

    relay_dir, base_dir = runs
    with_base = render_charts(
        relay_dir, lang="pl", out_dir=tmp_path / "pl"
    )  # wariant bazowy wykryty po nazwie
    assert [p.name for p in with_base] == [
        "zasieg_alertu_pl.png",
        "zgloszenia_pl.png",
        "ewakuacja_pl.png",
        "karta_wynikow_pl.png",
    ]
    assert all(p.stat().st_size > 40_000 for p in with_base)
    alone = render_charts(base_dir, lang="en", out_dir=tmp_path / "en")
    assert all(p.exists() and p.name.endswith("_en.png") for p in alone)


def test_timeline_in_params_uses_action_values(runs: tuple[Path, Path]) -> None:
    import yaml

    meta = yaml.safe_load((runs[0] / "params.yaml").read_text(encoding="utf-8"))
    kinds = [act["kind"] for act in meta["scenario"]["timeline"]]
    assert "issue_alert" in kinds and "troll_broadcast" in kinds
    assert meta["scenario"]["timeline"][1]["hazard"] == "FLOOD"
