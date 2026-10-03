"""Interfejs wiersza poleceń: `sztafeta run | animate | frame`."""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from typing import Annotated

import typer

from sztafeta.runner import run_once
from sztafeta.scenarios import list_presets

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
