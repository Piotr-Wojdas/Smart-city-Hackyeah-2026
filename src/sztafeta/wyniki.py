"""Generator `docs/WYNIKI.md` z przeglądu parametrów. Liczby nie są zaokrąglane na korzyść projektu."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from sztafeta.batch import BatchSpec

FULL = "full"
THRESHOLD_T50_S = 3600.0
THRESHOLD_ZONE_PCT = 90.0

# warianty „co daje który mechanizm” i warianty wrażliwości: (nazwa w danych, opis w tabeli)
MECHANISMS = (
    ("baseline", "Bez Sztafety: tylko zasięg huba, zgłoszenia osobiście"),
    ("phones_only", "Same telefony, bez kurierów"),
    ("couriers_only", "Sami kurierzy, bez przekazywania telefon–telefon"),
    (FULL, "Pełna Sztafeta: telefony i kurierzy"),
)
SENSITIVITY = (
    (FULL, "Ustawienia odniesienia"),
    ("no_wom", "Bez przekazu ustnego"),
    ("wom_household", "Przekaz ustny tylko między domownikami"),
    ("scan_5_60", "Okno skanowania 5 s co 60 s (zamiast 10 s)"),
    ("scan_5_120", "Okno skanowania 5 s co 120 s"),
    ("setup_8_15", "Zestawianie połączenia 8–15 s (zamiast 3–8 s)"),
)


def _minutes(value: Any) -> str:
    return "–" if value is None or pd.isna(value) else f"{float(value) / 60.0:.0f}"


def _time_cell(row: pd.Series[Any], metric: str, seeds: int) -> str:
    """„38 min (31–52)”, a gdy część przebiegów nie osiągnęła progu – z dopiskiem „k/n”."""
    reached = int(row[f"{metric}_reached"])
    if reached == 0:
        return "nie osiągnięto"
    med, low, high = (_minutes(row[f"{metric}_{part}"]) for part in ("med", "min", "max"))
    text = f"{med} min ({low}–{high})"
    return text if reached == seeds else f"{text}, tylko {reached}/{seeds} przebiegów"


def _pct_cell(row: pd.Series[Any], metric: str) -> str:
    med = row[f"{metric}_med"]
    if med is None or pd.isna(med):
        return "–"
    return f"{float(med):.1f}% ({float(row[f'{metric}_min']):.1f}–{float(row[f'{metric}_max']):.1f})"


def _med(row: pd.Series[Any], metric: str, digits: int = 0) -> str:
    value = row[f"{metric}_med"]
    return "–" if value is None or pd.isna(value) else f"{float(value):.{digits}f}"


def _table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def _one(
    summary: pd.DataFrame, variant: str, adoption: float, range_m: float, couriers: int
) -> pd.Series[Any] | None:
    hit = summary[
        (summary["variant"] == variant)
        & (summary["adoption"] == adoption)
        & (summary["range_m"] == range_m)
        & (summary["couriers"] == couriers)
    ]
    return None if hit.empty else hit.iloc[0]


def adoption_threshold(summary: pd.DataFrame, spec: BatchSpec, range_m: float | None = None) -> float | None:
    """Najmniejsza adopcja spełniająca kryterium „system ma sens” (przy kurierach odniesienia).

    Kryterium: połowa telefonów z aplikacją ma alert najpóźniej godzinę po jego wydaniu
    i na koniec symulacji ma go co najmniej 90% telefonów z aplikacją w strefie zagrożenia
    (mediany między seedami). Sam zasięg na koniec nie wystarcza: przy małej adopcji alert roznoszą
    głównie kurierzy i trwa to godzinami.
    """
    radio = spec.baseline_range if range_m is None else range_m
    for adoption in sorted(spec.adoption):
        row = _one(summary, FULL, adoption, radio, spec.baseline_couriers)
        if row is None:
            continue
        t50 = row["t50_app_s_med"]
        fast = t50 is not None and pd.notna(t50) and float(t50) <= THRESHOLD_T50_S
        if fast and float(row["alert_reach_zone_app_med"]) >= THRESHOLD_ZONE_PCT:
            return adoption
    return None


def _variant_rows(
    summary: pd.DataFrame, spec: BatchSpec, variants: tuple[tuple[str, str], ...], seeds: int
) -> list[list[str]]:
    rows: list[list[str]] = []
    for name, label in variants:
        row = _one(summary, name, spec.baseline_adoption, spec.baseline_range, spec.baseline_couriers)
        if row is None:
            continue
        rows.append(
            [
                label,
                _pct_cell(row, "alert_reach_app"),
                _pct_cell(row, "alert_reach_zone_app"),
                _time_cell(row, "t50_app_s", seeds),
                _pct_cell(row, "evacuated_zone"),
                _pct_cell(row, "reports_delivered_pct"),
            ]
        )
    return rows


def write_wyniki(
    runs: pd.DataFrame,
    summary: pd.DataFrame,
    spec: BatchSpec,
    docs_path: Path,
    batch_dir: Path,
    version: str,
) -> Path:
    """Zapisuje `docs/WYNIKI.md` i kopiuje wykresy do `docs/wykresy/` (żeby dokument był kompletny w repo)."""
    seeds = len(spec.seeds)
    hours = (spec.duration_s or 21600.0) / 3600.0
    ref_a, ref_r, ref_c = spec.baseline_adoption, spec.baseline_range, spec.baseline_couriers
    relay_runs = runs[runs["variant"] == FULL]
    ref = _one(summary, FULL, ref_a, ref_r, ref_c)

    def variant(name: str) -> pd.Series[Any] | None:
        return _one(summary, name, ref_a, ref_r, ref_c)

    base = variant("baseline")
    phones = variant("phones_only")
    couriers_only = variant("couriers_only")
    no_wom = variant("no_wom")
    household = variant("wom_household")
    short = _one(summary, FULL, ref_a, min(spec.ranges), ref_c) if min(spec.ranges) < ref_r else None
    out: list[str] = []
    add = out.append

    add("# Wyniki symulacji „Sztafeta” – przegląd parametrów")
    add("")
    add(
        "**To są wyniki modelu, nie pomiary z terenu.** Pokazują, jak system zachowuje się w symulacji przy "
        "założeniach opisanych w [MODEL.md](MODEL.md). Dokument jest generowany poleceniem `sztafeta batch` "
        "i nie jest poprawiany ręcznie; liczby nie są zaokrąglane na korzyść projektu."
    )
    add("")
    add("## Co zostało policzone")
    add("")
    add(f"- preset: `{Path(spec.preset).stem}`, mapa: {runs['map_source'].iloc[0]}")
    add(f"- czas symulacji: {hours:.0f} h od awarii sieci, {int(runs['residents'].iloc[0])} mieszkańców")
    add(f"- adopcja: {', '.join(f'{100 * a:.0f}%' for a in spec.adoption)}")
    add(f"- zasięg radia: {', '.join(f'{r:.0f} m' for r in spec.ranges)}")
    add(f"- liczba kurierów: {', '.join(str(c) for c in spec.couriers)}")
    add(f"- seedy: {seeds} na kombinację ({spec.seeds[0]}–{spec.seeds[-1]}); łącznie {len(runs)} uruchomień")
    add(
        "- przy ustawieniach odniesienia (adopcja "
        f"{100 * ref_a:.0f}%, zasięg {ref_r:.0f} m, {ref_c} kurierów) "
        "dodatkowo: wariant bez Sztafety, same telefony, sami kurierzy i warianty wrażliwości (punkty 5 i 6)"
    )
    add(f"- wersja kodu: `{version}`")
    add("")
    add(
        "W tabelach podajemy **medianę między seedami**, a w nawiasie **najmniejszą i największą wartość** "
        "(rozrzut). Czasy liczymy od wydania alertu. „Adopcja” oznacza telefony z zainstalowanym "
        "i działającym modułem (Bluetooth włączony, aplikacja może pracować w tle)."
    )
    add("")

    # ------------------------------------------------------------------ liczby na slajd
    add("## Liczby na slajd")
    add("")
    setup = f"adopcja {100 * ref_a:.0f}%, zasięg {ref_r:.0f} m, {ref_c} kurierów, {seeds} seedów"
    if ref is not None:
        text = (
            f"1. W modelu ({setup}) zweryfikowany alert po "
            f"{hours:.0f} h ma **{_med(ref, 'alert_reach_app')}% "
            f"telefonów z aplikacją** (rozrzut {float(ref['alert_reach_app_min']):.0f}–"
            f"{float(ref['alert_reach_app_max']):.0f}%), a w strefie zagrożenia "
            f"**{_med(ref, 'alert_reach_zone_app')}%**. Połowa telefonów ma go po "
            f"{_time_cell(ref, 't50_app_s', seeds)} od wydania."
        )
        if short is not None:
            text += (
                f" Przy zasięgu {min(spec.ranges):.0f} m: {_med(short, 'alert_reach_app')}% telefonów, "
                f"połowa po {_time_cell(short, 't50_app_s', seeds)}."
            )
        add(text)
        if base is not None and phones is not None and couriers_only is not None:
            add(
                f"2. Skąd bierze się ten wynik ({setup}): bez żadnego przekazywania alert ma "
                f"{_med(base, 'alert_reach_app', 1)}% telefonów; same telefony bez kurierów dają "
                f"{_med(phones, 'alert_reach_app')}% (w strefie {_med(phones, 'alert_reach_zone_app')}%); "
                f"sami kurierzy bez przekazywania telefon–telefon {_med(couriers_only, 'alert_reach_app')}% "
                f"(w strefie {_med(couriers_only, 'alert_reach_zone_app')}%); oba mechanizmy razem "
                f"**{_med(ref, 'alert_reach_app')}%** (w strefie {_med(ref, 'alert_reach_zone_app')}%). "
                "W strefie zagrożenia większość pracy wykonują kurierzy, poza nią telefony mieszkańców."
            )
        add(
            f"3. W modelu ({setup}) do PCZK dociera **{_med(ref, 'reports_delivered_zone_pct')}% zgłoszeń "
            f"mieszkańców strefy zagrożenia** i {_med(ref, 'reports_delivered_outside_pct')}% zgłoszeń spoza "
            f"strefy, gdzie kurierzy nie patrolują (łącznie {_med(ref, 'reports_delivered_pct')}%). Mediana "
            f"opóźnienia dostarczonych zgłoszeń to {_minutes(ref['delay_median_s_med'])} min. Potwierdzenie "
            f"„przyjęto” wraca do **{_med(ref, 'acks_received_pct')}%** "
            "zgłaszających, których zgłoszenie dotarło."
        )
        text = (
            f"4. W modelu ({setup}) ze strefy zagrożenia ewakuuje się **{_med(ref, 'evacuated_zone')}%** "
            f"mieszkańców: {_med(ref, 'evacuated_zone_app')}% to osoby z aplikacją, a "
            f"{_med(ref, 'evacuated_zone_wom')}% osoby bez aplikacji poinformowane ustnie przez domowników "
            "i sąsiadów."
        )
        if no_wom is not None and household is not None:
            text += (
                f" To założenie modelu: bez przekazu ustnego ewakuuje się {_med(no_wom, 'evacuated_zone')}%, "
                f"a gdy informują się tylko domownicy – {_med(household, 'evacuated_zone')}%."
            )
        add(text)
    worst = int(relay_runs["fake_verified_devices"].max())
    fake_med = float(relay_runs["fake_received_devices"].median())
    add(
        f"5. We wszystkich {len(relay_runs)} uruchomieniach "
        "pełnej siatki fałszywy alert uznało za zweryfikowany "
        f"**{worst} urządzeń** (dostało go: mediana {fake_med:.0f} urządzeń w bezpośrednim zasięgu trolla)."
    )
    add("")

    # ------------------------------------------------------------------ próg adopcji
    add("## Od jakiej adopcji system ma sens")
    add("")
    threshold = adoption_threshold(summary, spec)
    add(
        f"Kryterium (umowne, przy {ref_c} kurierach): połowa "
        "telefonów z aplikacją ma alert **najpóźniej godzinę "
        f"po jego wydaniu**, a po {hours:.0f} h ma go **co najmniej 90% telefonów z aplikacją w strefie "
        "zagrożenia** (mediany między seedami). Sam zasięg na koniec nie wystarcza: przy małej adopcji alert "
        "roznoszą głównie kurierzy i trwa to godzinami."
    )
    add("")
    rows = []
    for range_m in spec.ranges:
        value = adoption_threshold(summary, spec, range_m)
        never = f"nie osiągnięto (do {100 * max(spec.adoption):.0f}%)"
        rows.append([f"{range_m:.0f} m", never if value is None else f"{100 * value:.0f}%"])
    add(_table(["Zasięg radia", "Najmniejsza badana adopcja spełniająca kryterium"], rows))
    add("")
    if threshold is None:
        add(
            f"**Przy zasięgu {ref_r:.0f} m żadna z badanych wartości adopcji "
            f"(do {100 * max(spec.adoption):.0f}%) nie spełnia kryterium.**"
        )
    else:
        add(
            f"**Próg w modelu przy zasięgu {ref_r:.0f} m i {ref_c} "
            f"kurierach: adopcja {100 * threshold:.0f}%.** "
            "To najmniejsza z badanych wartości, a nie dokładna granica."
        )
        below = [a for a in sorted(spec.adoption) if a < threshold]
        if below:
            row = _one(summary, FULL, below[-1], ref_r, ref_c)
            if row is not None:
                add(
                    f"Przy adopcji {100 * below[-1]:.0f}% połowa telefonów ma alert dopiero po "
                    f"{_time_cell(row, 't50_app_s', seeds)}, a zasięg w strefie zagrożenia wynosi "
                    f"{float(row['alert_reach_zone_app_med']):.0f}%."
                )
    add("")
    add(
        "Uwagi: (1) próg zależy od zasięgu radia bardziej niż od czegokolwiek innego, a zasięgu w zabudowie "
        "nie znamy; (2) próg dotyczy sytuacji z kurierami w terenie; (3) nawet powyżej progu sama aplikacja "
        "obejmuje tylko swoich użytkowników, czyli przy adopcji "
        f"{100 * ref_a:.0f}% najwyżej {100 * ref_a:.0f}% "
        "mieszkańców; reszta zależy od przekazu ustnego i innych kanałów."
    )
    add("")

    # ------------------------------------------------------------------ tabela 1
    add(f"## 1. Czas do zasięgu 50% i 90% telefonów z aplikacją ({ref_c} kurierów)")
    add("")
    rows = []
    for adoption in spec.adoption:
        for range_m in spec.ranges:
            row = _one(summary, FULL, adoption, range_m, ref_c)
            if row is None:
                continue
            rows.append(
                [
                    f"{100 * adoption:.0f}%",
                    f"{range_m:.0f} m",
                    _time_cell(row, "t50_app_s", seeds),
                    _time_cell(row, "t90_app_s", seeds),
                    _pct_cell(row, "alert_reach_app"),
                    _pct_cell(row, "alert_reach_zone_app"),
                ]
            )
    add(
        _table(
            [
                "Adopcja",
                "Zasięg",
                "Czas do 50%",
                "Czas do 90%",
                f"Zasięg po {hours:.0f} h",
                "W strefie zagrożenia",
            ],
            rows,
        )
    )
    add("")
    add("![Czas do zasięgu w funkcji adopcji](wykresy/adopcja_czas_pl.png)")
    add("")
    add("![Zasięg alertu w funkcji adopcji i zasięgu radia](wykresy/adopcja_zasieg_pl.png)")
    add("")

    # ------------------------------------------------------------------ tabela 2
    add(f"## 2. Zgłoszenia dostarczone do PCZK (zasięg {ref_r:.0f} m)")
    add("")
    add(
        "Odsetek zgłoszeń wysłanych do danej chwili, które do tej chwili dotarły do PCZK (czas od awarii "
        "sieci). Kurierzy patrolują strefę zagrożenia i punkt ewakuacji, dlatego zgłoszenia ze strefy "
        "i spoza niej pokazujemy osobno. Liczba zgłoszeń rośnie z zasięgiem alertu, więc odsetki łączne "
        "z różnych wierszy nie są wprost porównywalne."
    )
    add("")
    rows = []
    for adoption in spec.adoption:
        for couriers in spec.couriers:
            row = _one(summary, FULL, adoption, ref_r, couriers)
            if row is None:
                continue
            rows.append(
                [
                    f"{100 * adoption:.0f}%",
                    str(couriers),
                    f"{float(row['reports_created_med']):.0f}",
                    _pct_cell(row, "reports_delivered_pct_1h"),
                    _pct_cell(row, "reports_delivered_pct_3h"),
                    _pct_cell(row, "reports_delivered_pct"),
                    _pct_cell(row, "reports_delivered_zone_pct"),
                    _pct_cell(row, "reports_delivered_outside_pct"),
                    _pct_cell(row, "need_help_delivered_pct"),
                    f"{_minutes(row['delay_median_s_med'])} min",
                ]
            )
    add(
        _table(
            [
                "Adopcja",
                "Kurierzy",
                "Zgłoszeń (mediana)",
                "Po 1 h",
                "Po 3 h",
                f"Po {hours:.0f} h",
                "Ze strefy",
                "Spoza strefy",
                "„Potrzebuję pomocy”",
                "Mediana opóźnienia dostarczonych",
            ],
            rows,
        )
    )
    add("")
    add("![Zgłoszenia w PCZK w funkcji liczby kurierów](wykresy/kurierzy_zgloszenia_pl.png)")
    add("")

    # ------------------------------------------------------------------ tabela 3
    add(f"## 3. Potwierdzenia (Ack), które wróciły do zgłaszających (zasięg {ref_r:.0f} m)")
    add("")
    add("Odsetek zgłoszeń dostarczonych do PCZK, których autor dostał podpisane potwierdzenie „przyjęto”.")
    add("")
    rows = []
    for adoption in spec.adoption:
        cells = [f"{100 * adoption:.0f}%"]
        for couriers in spec.couriers:
            row = _one(summary, FULL, adoption, ref_r, couriers)
            cells.append("–" if row is None else _pct_cell(row, "acks_received_pct"))
        rows.append(cells)
    add(_table(["Adopcja", *[f"{c} kurierów" for c in spec.couriers]], rows))
    add("")

    # ------------------------------------------------------------------ tabela 4
    add("## 4. Fałszywe alerty")
    add("")
    add(
        f"- urządzenia, które uznały fałszywy alert za zweryfikowany: **{worst}** (maksimum ze wszystkich "
        f"{len(relay_runs)} uruchomień pełnej siatki; oczekiwane 0)"
    )
    add(
        f"- urządzenia, które go odebrały i oznaczyły jako niezweryfikowany: mediana {fake_med:.0f}, "
        f"najwięcej {int(relay_runs['fake_received_devices'].max())}"
    )
    add(
        "- żadne urządzenie nie rozpoczęło ewakuacji ani nie zmieniło stanu z powodu fałszywego alertu "
        "(test automatyczny)"
    )
    add("")

    # ------------------------------------------------------------------ mechanizmy
    header = [
        "Wariant",
        "Zasięg alertu (telefony z aplikacją)",
        "Zasięg w strefie zagrożenia",
        "Czas do 50%",
        "Ewakuowani ze strefy",
        "Zgłoszenia w PCZK",
    ]
    mech = _variant_rows(summary, spec, MECHANISMS, seeds)
    if len(mech) > 1:
        add(f"## 5. Co daje który mechanizm ({setup})")
        add("")
        add(_table(header, mech))
        add("")
        add(
            "- **Bez Sztafety**: telefony nie przekazują pakietów, "
            "alert dostaje tylko urządzenie w zasięgu huba, "
            "zgłoszenie trzeba zanieść osobiście. Wariant nie obejmuje syren, megafonów ani obchodu służb – "
            "to dolna granica, nie opis tego, co się wydarzyło."
        )
        add(
            "- **Same telefony**: sieć niesiona ruchem ludzi. Bez kurierów alert rozchodzi się po mieście, "
            "ale wolno, a zgłoszenia prawie nie docierają do PCZK."
        )
        add(
            "- **Sami kurierzy**: kurier przekazuje alert "
            "telefonom, które mija, i zbiera od nich zgłoszenia, "
            "ale telefony nie podają niczego dalej. Wysoki "
            "odsetek zgłoszeń wynika też z tego, że poza strefą "
            "alert ma mniej osób, więc mniej osób w ogóle wysyła zgłoszenie."
        )
        add("")

    # ------------------------------------------------------------------ wrażliwość
    sens = _variant_rows(summary, spec, SENSITIVITY, seeds)
    if len(sens) > 1:
        add(f"## 6. Wrażliwość na założenia ({setup})")
        add("")
        add(
            "Po jednej zmianie względem ustawień odniesienia. Tych założeń nie da się dziś sprawdzić "
            "w terenie, a wpływają na wynik podobnie mocno jak zasięg radia."
        )
        add("")
        add(_table(header, sens))
        add("")

    add("## Koszt i mechanizmy, które w tym scenariuszu nie zadziałały")
    add("")
    add(
        f"- średnia bateria telefonów z aplikacją po {hours:.0f} h: mediana "
        f"{float(relay_runs['battery_mean'].median()):.0f}% (start: 35–100%). To prosta konsekwencja "
        "założonego zużycia, a nie wynik symulacji; rozładowane telefony: "
        f"najwięcej {int(relay_runs['devices_off'].max())} w jednym uruchomieniu"
    )
    add(
        f"- łączny transfer w mieście: mediana {float(relay_runs['bytes_total'].median()) / 1e6:.1f} MB "
        f"na uruchomienie; {float(relay_runs['ack_transfer_pct'].median()):.0f}% transferów to potwierdzenia "
        "(każdy Ack rozchodzi się po całym mieście, choć dotyczy najwyżej 32 zgłaszających) – "
        "to miejsce do optymalizacji"
    )
    add(
        f"- pakiety usunięte z przepełnionych buforów: najwięcej {int(relay_runs['packets_evicted'].max())} "
        f"w jednym uruchomieniu. Limit bufora, limit skoków i czasy życia pakietów są dłuższe niż potrzeby "
        f"scenariusza {hours:.0f}-godzinnego, więc przegląd ich nie testuje (robią to testy jednostkowe)"
    )
    add(f"- czas obliczeń jednego uruchomienia: mediana {float(runs['wall_s'].median()):.0f} s")
    add("")
    add(
        "Pliki źródłowe: `results/batch/runs.csv` (każde uruchomienie) "
        "i `results/batch/summary.csv` (agregacja)."
    )
    add("")

    docs_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.write_text("\n".join(out), encoding="utf-8", newline="\n")
    plots = batch_dir / "plots"
    target = docs_path.parent / "wykresy"
    if plots.exists():
        target.mkdir(parents=True, exist_ok=True)
        for png in sorted(plots.glob("*_pl.png")):
            shutil.copyfile(png, target / png.name)
    return docs_path
