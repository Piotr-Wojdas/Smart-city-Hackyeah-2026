"""Scenariusz bez strefy zagrożenia: alert, ewakuacja i patrole kurierów obejmują całe miasto."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml
from scipy.spatial import cKDTree
from typer.testing import CliRunner

from sztafeta.batch import BatchSpec, run_batch, write_outputs
from sztafeta.cli import app
from sztafeta.engine.geo import points_in_polygon
from sztafeta.engine.model import Params, PopulationParams, Role, Scenario
from sztafeta.engine.population import settled_buildings
from sztafeta.engine.sim import Simulation
from sztafeta.runner import run_once
from sztafeta.scenarios import load_preset, read_preset


@pytest.fixture(scope="module")
def city_preset(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Kopia presetu testowego z `scenario.area: city` (ścieżka do pliku YAML)."""
    raw = read_preset("test-small")
    raw["name"] = "test-city"
    raw["scenario"]["area"] = "city"
    path = tmp_path_factory.mktemp("presets") / "test-city.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    return str(path)


@pytest.fixture(scope="module")
def city_run(city_preset: str, tmp_path_factory: pytest.TempPathFactory) -> Path:
    result = run_once(city_preset, seed=42, out_root=tmp_path_factory.mktemp("results"), until=1500.0)
    assert result.out_dir is not None
    return result.out_dir


def _couriers_only(area_city: bool) -> tuple[Simulation, Params, Scenario]:
    """Wariant „sami kurierzy”: alert roznoszą tylko kurierzy, więc widać, dokąd docierają."""
    params, scenario = load_preset("test-small", overrides=["routing.phone_relay=false"])
    if area_city:
        scenario.city.hazard_zone = np.empty((0, 2))
    return Simulation(params, scenario, 7), params, scenario


def test_preset_area_selects_zone_or_whole_city(city_preset: str, tmp_path: Path) -> None:
    _, zoned = load_preset("test-small")
    assert zoned.city.has_zone
    _, whole = load_preset(city_preset)
    assert not whole.city.has_zone and whole.city.hazard_zone.shape == (0, 2)
    # bez strefy każdy punkt leży w obszarze alertu; ze strefą tylko jej wnętrze
    points = whole.city.buildings_xy
    assert whole.city.in_area(points).all()
    inside = zoned.city.in_area(points)
    assert inside.any() and not inside.all()
    # presety demo (mapa OSM i jej proceduralny zamiennik) są scenariuszem dla całego miasta
    assert not load_preset("flood-grid")[1].city.has_zone
    assert not load_preset("flood-stronie", data_dir=tmp_path)[1].city.has_zone

    raw = read_preset("test-small")
    raw["scenario"]["area"] = "powiat"
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="obszar alertu"):
        load_preset(str(bad))


def test_without_zone_every_resident_is_addressed_and_evacuates(city_preset: str) -> None:
    params, scenario = load_preset(city_preset)
    old_zone = load_preset("test-small")[1].city.hazard_zone
    sim = Simulation(params, scenario, 42)
    ag = sim.agents
    residents = ag.residents
    assert ag.in_zone[residents].all()
    # obszar alertu (komórki geohash) obejmuje wszystkie budynki, a certyfikat PCZK cały ten obszar
    city = scenario.city
    cells = {city.georef.geohash(float(x), float(y), 6) for x, y in city.buildings_xy}
    assert cells <= set(sim.area)
    sim.run(1500.0)
    started = ~np.isnan(ag.evac_start_t)
    outside_old_zone = residents & ~points_in_polygon(ag.home_xy, old_zone)
    assert (started & outside_old_zone).sum() > 20  # ruszają także ci, których dawna strefa nie obejmowała
    summary = sim.metrics.summary(sim.alert_issued_t)
    assert summary["zone_residents"] == summary["residents"]
    assert summary["alert_reach_zone_app"] == summary["alert_reach_app"]
    row = sim.sample_metrics()
    assert row.reports_outside_created == 0 and row.reports_zone_created == row.reports_created
    assert sim.describe()["map"]["hazard_zone"] == []
    assert sim.metrics.rows[-1].fake_verified_devices == 0


def test_couriers_patrol_streets_next_to_buildings_of_the_whole_city() -> None:
    whole, _, scenario = _couriers_only(area_city=True)
    zoned, _, zoned_scenario = _couriers_only(area_city=False)
    city = scenario.city
    nodes = whole._patrol_nodes()
    assert set(nodes.tolist()) == set(city.graph.nearest_nodes(city.buildings_xy).tolist())
    old_zone = zoned_scenario.city.hazard_zone
    assert not points_in_polygon(city.graph.node_xy[nodes], old_zone).all()
    assert points_in_polygon(city.graph.node_xy[zoned._patrol_nodes()], old_zone).all()

    # ile domów poza dawną strefą znalazło się w zasięgu radia kuriera i ile telefonów dostało tam alert
    def outside_zone(sim: Simulation) -> tuple[float, float]:
        ag = sim.agents
        outside = (ag.role == int(Role.RESIDENT)) & ~points_in_polygon(ag.home_xy, old_zone)
        homes = np.flatnonzero(outside)
        tree = cKDTree(ag.home_xy[homes])
        passed = np.zeros(homes.size, dtype=np.bool_)
        while sim.t < 3000.0:
            sim.step()
            for courier in sim.courier_ids.tolist():
                passed[tree.query_ball_point(sim.mobility.pos[courier], sim.params.radio.range_m)] = True
        phones = outside & ag.has_app
        return float(passed.mean()), float((~np.isnan(ag.informed_t[phones])).mean())

    passed_city, reach_city = outside_zone(whole)
    passed_zone, reach_zone = outside_zone(zoned)
    assert passed_city > 0.7 and passed_city > passed_zone + 0.1
    assert reach_city > reach_zone  # sami kurierzy: więcej telefonów z alertem tam, dokąd teraz docierają


def test_run_files_mark_whole_city_and_cli_says_so(city_preset: str, city_run: Path, tmp_path: Path) -> None:
    import json

    summary = json.loads((city_run / "summary.json").read_text(encoding="utf-8"))
    params = yaml.safe_load((city_run / "params.yaml").read_text(encoding="utf-8"))
    static = json.loads((city_run / "static.json").read_text(encoding="utf-8"))
    assert summary["area"] == "city" and params["area"] == "city"
    assert static["map"]["hazard_zone"] == [] and all(static["agents"]["in_zone"][:400])
    out = CliRunner().invoke(
        app, ["run", "--preset", city_preset, "--seed", "3", "--until", "300", "--out", str(tmp_path)]
    )
    assert out.exit_code == 0, out.output
    assert "alert dla całego miasta" in out.output and "strefie zagrożenia" not in out.output
    zoned = CliRunner().invoke(
        app, ["run", "--preset", "test-small", "--seed", "3", "--until", "300", "--out", str(tmp_path)]
    )
    assert "w strefie zagrożenia:" in zoned.output


def test_animation_without_zone_tells_the_story_of_the_whole_city(city_run: Path, tmp_path: Path) -> None:
    from sztafeta.io.reader import load_run
    from sztafeta.viz.animate import _EVENTS, MapAnimation, Shot
    from sztafeta.viz.charts import render_charts

    anim = MapAnimation(load_run(city_run, _EVENTS), dpi=40)
    texts = [text for _, text in anim.story]
    assert "Kurierzy roznoszą alert po mieście" in texts
    assert "Miasto zaczyna się ewakuować" in texts
    assert texts[-1].startswith("Ewakuowano") and texts[-1].endswith("mieszkańców")
    assert texts.index("Kurierzy roznoszą alert po mieście") < texts.index("Miasto zaczyna się ewakuować")
    anim.draw(Shot(900.0))
    drawn = [t.get_text() for t in anim.ax.texts] + [t.get_text() for t in anim.panel.texts]
    assert not any(
        "stref" in text.lower() for text in [*texts, *drawn]
    )  # strefy nie ma ani na mapie, ani w opisach
    assert len(anim.ax.patches) == 0  # żadnego wielokąta strefy
    assert any(text.endswith("mieszkańców miasta") for text in drawn)
    # w lewym górnym rogu jest nazwa aplikacji, a podtytuł zaczyna się za nią
    title, subtitle = anim.fig.texts[0], anim.fig.texts[1]
    assert title.get_text() == "Netless"
    assert subtitle.get_window_extent().x0 > title.get_window_extent().x1

    charts = render_charts(city_run, lang="pl", out_dir=tmp_path / "wykresy")
    assert len(charts) == 4 and all(p.stat().st_size > 40_000 for p in charts)


def test_results_document_without_zone_has_no_zone_columns(city_preset: str, tmp_path: Path) -> None:
    spec = BatchSpec(
        preset=city_preset, adoption=[0.2, 0.5], ranges=[40.0], couriers=[2], seeds=[1], duration_s=1500.0
    )
    spec.baseline_adoption, spec.baseline_range, spec.baseline_couriers = 0.5, 40.0, 2
    runs = run_batch(spec, workers=1)
    assert (runs["area"] == "city").all()
    docs = tmp_path / "docs" / "WYNIKI.md"
    write_outputs(runs, spec, tmp_path / "batch", docs)
    text = docs.read_text(encoding="utf-8")
    assert "alert i ewakuacja dotyczą **całego miasta**" in text
    for phrase in ("w strefie", "W strefie", "Ze strefy", "Spoza strefy", "ze strefy", "poza strefą"):
        assert phrase not in text, phrase
    assert "mieszkańców miasta" in text and "Mieszkańcy w punkcie ewakuacji" in text
    assert "co najmniej 90% telefonów z aplikacją**" in text


def test_compact_settlement_puts_residents_in_the_densest_quarter_of_buildings() -> None:
    params, scenario = load_preset("test-small", overrides=["population.settled_share=0.25"])
    scenario.city.hazard_zone = np.empty((0, 2))
    city = scenario.city
    n = city.buildings_xy.shape[0]
    everywhere = settled_buildings(city, PopulationParams())
    assert everywhere.all() and everywhere.shape == (n,)  # domyślnie ludzie mieszkają we wszystkich budynkach
    lived_in = settled_buildings(city, params.population)
    assert int(lived_in.sum()) == round(0.25 * n)
    assert np.array_equal(lived_in, settled_buildings(city, params.population))  # wybór jest powtarzalny
    # zostają budynki o najgęstszym otoczeniu (suma wag budynków w promieniu settled_radius_m)
    tree = cKDTree(city.buildings_xy)
    local = np.array(
        [
            city.building_weight[idx].sum()
            for idx in tree.query_ball_point(city.buildings_xy, params.population.settled_radius_m)
        ]
    )
    assert local[lived_in].min() >= local[~lived_in].max()

    sim = Simulation(params, scenario, 42)
    ag = sim.agents
    homes = ag.home_xy[ag.residents]
    to_lived_in, _ = cKDTree(city.buildings_xy[lived_in]).query(homes)
    assert to_lived_in.max() < 20.0  # każdy dom leży przy zamieszkanym budynku (rozrzut wokół budynku: 3 m)
    # kurierzy objeżdżają tylko ulice przy zamieszkanych budynkach
    nodes = sim._patrol_nodes()
    assert set(nodes.tolist()) == set(city.graph.nearest_nodes(city.buildings_xy[lived_in]).tolist())
    assert nodes.size < np.unique(city.graph.nearest_nodes(city.buildings_xy)).size


def test_demo_preset_is_a_densely_populated_town_with_unchanged_radio_rules(tmp_path: Path) -> None:
    dense, _ = load_preset("flood-stronie", data_dir=tmp_path)
    plain = Params()
    assert dense.population.n_residents == 4956 and dense.population.settled_share == 0.25
    assert dense.behavior.p_comply == 0.92 and plain.behavior.p_comply == 0.85
    assert plain.population.n_residents == 3000 and plain.population.settled_share == 1.0
    # zagęszczenie nie zmienia zasad rozchodzenia się sygnału: radio, routing, bateria i adopcja są domyślne
    assert dense.radio == plain.radio and dense.routing == plain.routing and dense.battery == plain.battery
    assert dense.behavior.adoption == plain.behavior.adoption
    for name in ("wom_enabled", "wom_prob_per_min", "wom_range_m", "wom_household_only", "p_need_help_zone"):
        assert getattr(dense.behavior, name) == getattr(plain.behavior, name), name
