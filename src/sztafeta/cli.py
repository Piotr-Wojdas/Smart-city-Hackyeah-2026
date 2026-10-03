"""Interfejs wiersza poleceń: `sztafeta fetch-osm | run | batch | animate | frame | charts | inspect`."""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from sztafeta.runner import build, run_once
from sztafeta.scenarios import list_presets, read_preset

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Sztafeta – symulacja offline'owego kanału kryzysowego telefon–telefon (wynik modelu, nie pomiar).",
)


@app.callback()
def _main() -> None:
    # polskie znaki w konsoli Windows
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]


def _fmt_time(seconds: object) -> str:
    if not isinstance(seconds, int | float):
        return "nie osiągnięto"
    minutes = float(seconds) / 60.0
    return f"{minutes:.0f} min" if minutes >= 1 else f"{float(seconds):.0f} s"


@app.command()
def run(
    preset: Annotated[str, typer.Option(help="Nazwa presetu albo ścieżka do pliku YAML.")] = "flood-stronie",
    seed: Annotated[int, typer.Option(help="Seed losowości – ten sam seed daje ten sam wynik.")] = 42,
    set_: Annotated[
        list[str] | None,
        typer.Option("--set", help="Nadpisanie parametru, np. --set radio.range_m=80 (można powtarzać)."),
    ] = None,
    baseline: Annotated[bool, typer.Option("--baseline", help="Wariant bazowy „bez Sztafety”.")] = False,
    out: Annotated[Path, typer.Option(help="Katalog na wyniki.")] = Path("results"),
    until: Annotated[float | None, typer.Option(help="Skróć symulację do tylu sekund czasu modelu.")] = None,
) -> None:
    """Jedno uruchomienie symulacji -> results/<run_id>/."""
    typer.echo(
        f"Preset: {preset} · seed: {seed} · wariant: {'bazowy (bez Sztafety)' if baseline else 'Sztafeta'}"
    )

    def progress(t: float, end: float) -> None:
        typer.echo(f"  czas modelu {t / 3600.0:4.1f} h z {end / 3600.0:.1f} h")

    try:
        result = run_once(preset, seed, set_ or [], baseline, out, until, progress)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"Błąd: {exc}", err=True)
        typer.echo(f"Dostępne presety: {', '.join(list_presets())}", err=True)
        raise typer.Exit(code=2) from exc
    s = result.summary
    typer.echo("")
    typer.echo(f"Mapa: {result.map_source}")
    typer.echo(
        f"Mieszkańcy: {s['residents']} (z aplikacją: {s['residents_with_app']}, "
        f"w strefie zagrożenia: {s['zone_residents']})"
    )
    typer.echo(
        f"Zasięg alertu wśród telefonów z aplikacją: {s['alert_reach_app']:.1f}% "
        f"(50% po {_fmt_time(s['t50_app_s'])}, 90% po {_fmt_time(s['t90_app_s'])})"
    )
    typer.echo(
        f"Zasięg wśród wszystkich mieszkańców: aplikacja {s['alert_reach_all']:.1f}% "
        f"+ przekaz ustny {s['wom_reach_all']:.1f}% (liczony osobno)"
    )
    typer.echo(f"Ewakuowani ze strefy zagrożenia: {s['evacuated_zone']:.1f}%")
    typer.echo(
        f"Zgłoszenia: {s['reports_delivered']} z {s['reports_created']} w PCZK "
        f"(„potrzebuję pomocy”: {s['need_help_delivered']} z {s['need_help_created']}), "
        f"potwierdzenia u zgłaszających: {s['acks_received']}"
    )
    typer.echo(
        f"Fałszywy alert: dostało {s['fake_received_devices']} urządzeń, "
        f"uznało za prawdziwy: {s['fake_verified_devices']}"
    )
    megabytes = s["bytes_total"] / 1e6
    typer.echo(f"Kontakty: {s['contacts_total']} · transfery: {s['transfers_total']} · {megabytes:.2f} MB")
    typer.echo(f"Czas obliczeń: {result.wall_s:.1f} s · wyniki: {result.out_dir}")
    typer.echo("To wynik modelu (symulacja), nie pomiar z terenu.")


@app.command()
def animate(
    run_dir: Annotated[Path, typer.Argument(help="Katalog z wynikami uruchomienia (results/<run_id>).")],
    out: Annotated[
        Path | None, typer.Option(help="Plik wynikowy (domyślnie w katalogu uruchomienia).")
    ] = None,
    lang: Annotated[str, typer.Option(help="Język napisów: pl albo en.")] = "pl",
    fps: Annotated[int, typer.Option(help="Klatki na sekundę.")] = 24,
    every: Annotated[int, typer.Option(help="Co który snapshot staje się klatką (1 = wszystkie).")] = 3,
    dpi: Annotated[int, typer.Option(help="120 = 1920x1080.")] = 120,
    t_from: Annotated[float | None, typer.Option(help="Początek fragmentu (sekundy czasu modelu).")] = None,
    t_to: Annotated[float | None, typer.Option(help="Koniec fragmentu (sekundy czasu modelu).")] = None,
    fmt: Annotated[str, typer.Option("--format", help="auto, mp4 albo gif.")] = "auto",
) -> None:
    """Animacja mapy (MP4; gdy brak ffmpeg – GIF)."""
    from sztafeta.viz.animate import render_animation

    def progress(done: int, total: int) -> None:
        if done == total or done % max(total // 10, 1) == 0:
            typer.echo(f"  klatka {done} z {total}")

    try:
        path = render_animation(run_dir, out, lang, fps, every, dpi, t_from, t_to, fmt, progress)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        typer.echo(f"Błąd: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"Animacja: {path}")


@app.command()
def frame(
    run_dir: Annotated[Path, typer.Argument(help="Katalog z wynikami uruchomienia.")],
    t: Annotated[float, typer.Option(help="Chwila (sekundy czasu modelu).")] = 3600.0,
    out: Annotated[Path | None, typer.Option(help="Plik PNG (domyślnie w katalogu uruchomienia).")] = None,
    lang: Annotated[str, typer.Option(help="Język napisów: pl albo en.")] = "pl",
) -> None:
    """Pojedyncza klatka animacji jako PNG 1920x1080."""
    from sztafeta.viz.animate import render_frame

    target = out if out is not None else run_dir / f"klatka_{int(t)}_{lang}.png"
    try:
        path = render_frame(run_dir, target, t, lang)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"Błąd: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"Klatka: {path}")


@app.command()
def charts(
    run_dir: Annotated[Path, typer.Argument(help="Katalog z wynikami uruchomienia.")],
    baseline: Annotated[
        Path | None,
        typer.Option(help="Katalog wariantu bazowego (domyślnie <run_dir>_baseline, jeśli istnieje)."),
    ] = None,
    lang: Annotated[str, typer.Option(help="Język napisów: pl albo en.")] = "pl",
    out: Annotated[
        Path | None, typer.Option(help="Katalog na pliki PNG (domyślnie <run_dir>/wykresy).")
    ] = None,
) -> None:
    """Wykresy do slajdów i karta wyników (PNG 16:9, 200 dpi)."""
    from sztafeta.viz.charts import render_charts

    try:
        paths = render_charts(run_dir, baseline, lang, out)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        typer.echo(f"Błąd: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    for path in paths:
        typer.echo(f"Wykres: {path}")


@app.command()
def inspect(
    run_dir: Annotated[Path, typer.Argument(help="Katalog z wynikami uruchomienia.")],
    agent: Annotated[int, typer.Option(help="Id agenta.")],
    t: Annotated[float | None, typer.Option(help="Chwila (sekundy czasu modelu); domyślnie koniec.")] = None,
) -> None:
    """Stan telefonu agenta w chwili t (JSON). Odtwarzany przez ponowne przeliczenie symulacji."""
    import yaml

    params_file = run_dir / "params.yaml"
    if not params_file.exists():
        typer.echo(f"Błąd: w katalogu {run_dir} nie ma params.yaml", err=True)
        raise typer.Exit(code=2)
    meta = yaml.safe_load(params_file.read_text(encoding="utf-8"))
    source = str(meta.get("preset_source", meta["preset"]))
    try:
        sim, params, _ = build(source, int(meta["seed"]), list(meta["overrides"]), bool(meta["baseline"]))
        end = float(meta["duration_s"]) if t is None else min(float(t), params.duration_s)
        sim.run(end)
        view = sim.phone_view(agent)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"Błąd: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(json.dumps(view, ensure_ascii=False, indent=2))


@app.command("fetch-osm")
def fetch_osm(
    preset: Annotated[str, typer.Option(help="Preset z sekcją map.osm.")] = "flood-stronie",
    data_dir: Annotated[Path, typer.Option(help="Katalog na dane map.")] = Path("data"),
) -> None:
    """Pobiera ulice, budynki i rzeki z OpenStreetMap i zapisuje mapę do data/<miejsce>/ (wymaga sieci)."""
    from sztafeta.data.osm import OsmRequest, fetch_city
    from sztafeta.data.store import save_city

    try:
        cfg = read_preset(preset).get("map", {})
        osm = cfg["osm"]
        request = OsmRequest(
            name=str(osm["name"]),
            lat=float(osm["center"][0]),
            lon=float(osm["center"][1]),
            dist_m=float(osm.get("dist_m", 1800.0)),
            network=str(osm.get("network", "walk")),
            zone_buffer_m=float(osm.get("zone_buffer_m", 120.0)),
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        typer.echo(f"Błąd: preset „{preset}” nie ma poprawnej sekcji map.osm ({exc})", err=True)
        raise typer.Exit(code=2) from exc
    target = data_dir / str(cfg["dir"])
    typer.echo(f"Pobieram {request.name} z OpenStreetMap (promień {request.dist_m:.0f} m)...")
    try:
        city, meta = fetch_city(request)
    except ImportError as exc:
        typer.echo("Błąd: brak pakietu osmnx. Zainstaluj grupę zależności: uv sync --group osm", err=True)
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        typer.echo(f"Błąd pobierania danych OSM: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    save_city(city, target, meta)
    typer.echo(
        f"Zapisano {target}: {meta['nodes']} węzłów, {meta['street_km']} km ulic, "
        f"{meta['residential_buildings']} budynków mieszkalnych "
        f"({meta['buildings_in_zone']} w strefie zagrożenia)."
    )
    typer.echo(f"Hub: {meta['hub_note']}. Punkt ewakuacji: {meta['evac_note']}.")
    typer.echo("Dane: © autorzy OpenStreetMap, licencja ODbL.")


@app.command()
def batch(
    preset: Annotated[str, typer.Option(help="Preset bazowy przeglądu.")] = "flood-stronie",
    adoption: Annotated[str, typer.Option(help="Adopcja w procentach, po przecinku.")] = "5,10,20,30,50",
    range_m: Annotated[
        str, typer.Option("--range", help="Zasięg radia w metrach, po przecinku.")
    ] = "25,40,80",
    couriers: Annotated[str, typer.Option(help="Liczba kurierów, po przecinku.")] = "2,5,10",
    seeds: Annotated[int, typer.Option(help="Liczba seedów na kombinację (seedy 1..N).")] = 5,
    workers: Annotated[int | None, typer.Option(help="Liczba procesów (domyślnie: rdzenie - 1).")] = None,
    out: Annotated[Path, typer.Option(help="Katalog na wyniki przeglądu.")] = Path("results/batch"),
    docs: Annotated[Path, typer.Option(help="Plik z opisem wyników.")] = Path("docs/WYNIKI.md"),
    until: Annotated[float | None, typer.Option(help="Skróć każde uruchomienie do tylu sekund.")] = None,
    quick: Annotated[
        bool, typer.Option("--quick", help="Mała siatka do sprawdzenia, czy wszystko działa.")
    ] = False,
) -> None:
    """Przegląd parametrów -> results/batch/*.csv, wykresy i docs/WYNIKI.md."""
    from sztafeta.batch import BatchSpec, parse_list, percent_list, run_batch, write_outputs

    try:
        spec = BatchSpec(
            preset=preset,
            adoption=percent_list(parse_list(adoption, float)),
            ranges=parse_list(range_m, float),
            couriers=parse_list(couriers, int),
            seeds=list(range(1, seeds + 1)),
            duration_s=until,
        )
    except ValueError as exc:
        typer.echo(f"Błąd: zła lista wartości ({exc})", err=True)
        raise typer.Exit(code=2) from exc
    if quick:
        spec.adoption, spec.ranges, spec.couriers, spec.seeds = [0.10, 0.30], [40.0], [5], [1, 2]
        spec.duration_s = until or 5400.0
    if not (spec.adoption and spec.ranges and spec.couriers and spec.seeds):
        typer.echo(
            "Błąd: każda lista (adopcja, zasięg, kurierzy, seedy) musi mieć co najmniej jedną wartość",
            err=True,
        )
        raise typer.Exit(code=2)
    spec.baseline_adoption = 0.30 if 0.30 in spec.adoption else spec.adoption[-1]
    spec.baseline_range = 40.0 if 40.0 in spec.ranges else spec.ranges[0]
    spec.baseline_couriers = 5 if 5 in spec.couriers else spec.couriers[0]
    total = len(spec.jobs())
    typer.echo(f"Przegląd: {total} uruchomień (preset {preset}).")

    def progress(done: int, count: int) -> None:
        if done == count or done % max(count // 20, 1) == 0:
            typer.echo(f"  {done} z {count}")

    try:
        runs = run_batch(spec, workers, progress)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"Błąd: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    paths = write_outputs(runs, spec, out, None if quick else docs)
    for path in paths:
        typer.echo(f"Zapisano: {path}")
    worst = int(runs["fake_verified_devices"].max())
    typer.echo(f"Fałszywe alerty uznane za zweryfikowane (maksimum ze wszystkich uruchomień): {worst}")
    if worst > 0:
        typer.echo("UWAGA: to błąd modelu albo kryptografii – zgłoś go.", err=True)
        raise typer.Exit(code=1)
