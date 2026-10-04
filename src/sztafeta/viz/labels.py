"""Napisy wizualizacji po polsku i angielsku (`--lang en`)."""

from __future__ import annotations

from collections.abc import Mapping

_PL: dict[str, str] = {
    "title": "Netless",
    "subtitle": "kanał kryzysowy telefon–telefon bez sieci komórkowej",
    "model_note": "Wynik modelu (symulacja komputerowa), nie pomiar z terenu.",
    "model_tag": "wynik modelu",
    "map_note": "Mapa: {source}",
    "since_outage": "{elapsed} od awarii sieci · czas modelu",
    "before_outage": "przed awarią sieci · czas modelu",
    "zone": "Strefa zagrożenia",
    "scale": "{m} m",
    "tile_alert": "Zweryfikowany alert w aplikacji",
    "tile_alert_value": "{pct:.0f}% telefonów z aplikacją",
    "tile_evac": "Ewakuowani ze strefy zagrożenia",
    "tile_evac_value": "{pct:.0f}% mieszkańców strefy",
    "story": "Co się dzieje",
    "ev_network_down": "Awaria sieci komórkowej",
    "ev_alert_issued": "PCZK wydaje podpisany alert",
    "ev_alert_relay": "Telefony przekazują sobie alert",
    "ev_reach_50": "Połowa telefonów ma już alert",
    "ev_reach_90": "90% telefonów ma już alert",
    "ev_couriers": "Kurierzy wyruszają w teren",
    "run_note": (
        "Jedno uruchomienie: {scenario}, seed {seed}, {residents} mieszkańców, adopcja "
        "{adoption}%, zasięg {range_m} m, kurierów: {couriers}. Rozrzut między seedami: "
        "docs/WYNIKI.md."
    ),
    "axis_hours": "czas od awarii sieci komórkowej [h]",
    "mark_alert": "alert wydany",
    "mark_update": "nowa wersja alertu",
    "mark_troll": "fałszywy alert",
    "series_relay": "Sztafeta",
    "series_base": "bez Sztafety (tylko zasięg huba)",
    "series_created": "wysłane przez mieszkańców",
    "series_delivered": "dostarczone do PCZK",
    "series_delivered_base": "bez Sztafety",
    "milestone": "{share}% po {elapsed} od alertu",
    "reach_title_vs": "Sztafeta dociera z alertem do {relay} telefonów z aplikacją; bez niej do {base}",
    "reach_title": "Podpisany alert dociera do {relay} telefonów z aplikacją w {hours:.0f} h bez sieci",
    "reach_sub": (
        "Odsetek telefonów z aplikacją, które odebrały i zweryfikowały alert urzędowy "
        "(przekaz ustny liczony osobno)."
    ),
    "reach_axis": "telefony z aplikacją, które mają alert",
    "evac_title": "Dzięki alertowi do punktu ewakuacji dociera {relay} mieszkańców strefy",
    "evac_sub": "Wszyscy mieszkańcy strefy zagrożenia, z aplikacją i bez (ci drudzy dowiadują się ustnie).",
    "evac_axis": "mieszkańcy strefy w punkcie ewakuacji",
    "reports_title_vs": (
        "Kurierzy dowożą do PCZK {delivered} z {created} zgłoszeń; bez Sztafety dociera "
        "{base} z {base_created}"
    ),
    "reports_title": "Kurierzy dowożą do PCZK {delivered} z {created} zgłoszeń mieszkańców",
    "reports_sub": (
        "Mediana opóźnienia: {delay}. „Potrzebuję pomocy”: {need_delivered} z {need_created}. "
        "Potwierdzenie wróciło do {acks} zgłaszających."
    ),
    "reports_axis": "liczba zgłoszeń",
    "card_title": (
        "{hours:.0f} h bez sieci: {reach} telefonów z alertem, {delivered} zgłoszeń w PCZK, "
        "{fake} przyjętych fałszywek"
    ),
    "card_sub": (
        "{contacts} kontaktów między telefonami · {megabytes:.1f} MB przesłanych danych · "
        "średnia bateria na koniec {battery:.0f}%"
    ),
    "card_base": "bez Sztafety: {value}",
    "card_never": "nie osiągnięto",
    "card_reach": "telefonów z aplikacją ma zweryfikowany alert",
    "card_reach_note": "połowa po {t50} od alertu",
    "card_zone_note": "w strefie zagrożenia: {zone}",
    "card_all": "wszystkich mieszkańców: przez aplikację + ustnie od sąsiadów",
    "card_all_note": "przekaz ustny to założenie modelu, liczony osobno",
    "card_evac": "mieszkańców strefy w punkcie ewakuacji",
    "card_reports": "zgłoszeń dotarło do PCZK",
    "card_need": "zgłoszeń „potrzebuję pomocy” w PCZK",
    "card_acks": "zgłaszających dostało potwierdzenie",
    "card_acks_note": "{pct:.0f}% dostarczonych zgłoszeń",
    "card_fake": "urządzeń uznało fałszywy alert za prawdziwy",
    "card_fake_note": "dostało go i odrzuciło: {received} urządzeń",
    "axis_adoption": "adopcja: odsetek mieszkańców z zainstalowanym modułem",
    "axis_minutes": "minuty od wydania alertu",
    "axis_couriers": "liczba kurierów (ratowników i wolontariuszy z telefonem)",
    "axis_reports_pct": "zgłoszenia dostarczone do PCZK",
    "batch_note": (
        "Scenariusz: {preset}. Linia: mediana z {seeds} seedów, pas: najmniejsza i największa "
        "wartość. {fixed}"
    ),
    "fixed_range_couriers": "Zasięg {range_m:.0f} m, kurierów: {couriers}.",
    "fixed_couriers": "Kurierów: {couriers}.",
    "fixed_adoption_range": "Adopcja {adoption:.0f}%, zasięg {range_m:.0f} m.",
    "series_t50": "czas, po którym połowa telefonów z aplikacją ma alert",
    "reached_in": "{k} z {n} przebiegów",
    "range_label": "zasięg {range_m:.0f} m",
    "reach_batch_title": (
        "Przy adopcji {adoption:.0f}% zasięg {short:.0f} m daje alert {short_pct} telefonów, "
        "a {long:.0f} m: {long_pct}"
    ),
    "reach_batch_sub": (
        "Odsetek telefonów z aplikacją, które mają zweryfikowany alert po {hours:.0f} h bez sieci komórkowej."
    ),
    "series_rep_end": "na koniec",
    "series_rep_3h": "po 3 h",
    "series_rep_1h": "po 1 h",
    "couriers_title": "{few} kurierów dowozi do PCZK {few_pct} zgłoszeń, {many} kurierów: {many_pct}",
    "couriers_sub": (
        "Na koniec symulacji różnica maleje: {few_pct} i {many_pct}. W nawiasach rozrzut między seedami."
    ),
    "time_title_hour": (
        "Od adopcji {adoption:.0f}% połowa telefonów ma alert w ciągu godziny (mediana z {seeds} seedów)"
    ),
    "time_title_slow": "Przy żadnej badanej adopcji alert nie dociera do połowy telefonów w ciągu godziny",
    "time_sub_90": "Do 90% telefonów alert dociera w każdym przebiegu od adopcji {adoption:.0f}%.",
    "time_sub_90_never": (
        "Do 90% telefonów alert nie dociera we wszystkich przebiegach przy żadnej adopcji "
        "(najwięcej: {k} z {n} przy {adoption:.0f}%)."
    ),
    "couriers_title_1h": (
        "Po 1 h w PCZK jest {few_pct} zgłoszeń przy {few} kurierach i {many_pct} przy {many}"
    ),
    "evac_sub_vs": (
        "Wszyscy mieszkańcy strefy. Wariant bazowy nie obejmuje syren ani służb: to dolna "
        "granica, nie prognoza."
    ),
    "card_row_alerts": "SZTAFETA KOMUNIKATÓW: urząd → mieszkańcy",
    "card_row_reports": "KURIER DANYCH DO SZTABU: mieszkańcy → urząd",
    "card_evac_note": "z aplikacją i bez",
    "card_of": "{a} z {b}",
    "card_need_note": "osoby bez aplikacji nie mogą wysłać zgłoszenia",
    "card_delay": "mediana czasu od zgłoszenia do PCZK",
    "card_delay_note": "90% zgłoszeń w ciągu {p90}",
    "with_range": "{med} ({lo:.0f}–{hi:.0f}%)",
    "people_one": "{n} osoba",
    "people_few": "{n} osoby",
    "people_many": "{n} osób",
    "leg_idle": "telefon bez alertu",
    "leg_alert": "telefon z alertem",
    "leg_handover": "przekazanie alertu",
    "leg_ring": "właśnie odebrał alert",
    "leg_evac": "ewakuuje się",
    "leg_courier": "kurier (ratownik)",
    "closeup_caption": "ZBLIŻENIE · przerywana linia: telefony się łączą · niebieska: alert jest przesyłany",
    "scale_range": "{m} m: zasięg radia",
    "ev_evac_start": "Strefa zaczyna się ewakuować",
    "ev_evac_half": "Połowa strefy jest bezpieczna",
    "ev_end": "Ewakuowano {pct:.0f}% mieszkańców strefy",
    # warianty „_city”: scenariusz bez strefy zagrożenia, alert i ewakuacja dotyczą całego miasta
    "tile_evac_city": "Mieszkańcy w punkcie ewakuacji",
    "tile_evac_value_city": "{pct:.0f}% mieszkańców miasta",
    "ev_couriers_city": "Kurierzy roznoszą alert po mieście",
    "ev_evac_start_city": "Miasto zaczyna się ewakuować",
    "ev_evac_half_city": "Połowa miasta jest bezpieczna",
    "ev_end_city": "Ewakuowano {pct:.0f}% mieszkańców",
    "evac_title_city": "Dzięki alertowi do punktu ewakuacji dociera {relay} mieszkańców miasta",
    "evac_sub_city": "Wszyscy mieszkańcy miasta, z aplikacją i bez (ci drudzy dowiadują się ustnie).",
    "evac_sub_vs_city": (
        "Wszyscy mieszkańcy miasta. Wariant bazowy nie obejmuje syren ani służb: to dolna "
        "granica, nie prognoza."
    ),
    "evac_axis_city": "mieszkańcy miasta w punkcie ewakuacji",
    "card_evac_city": "mieszkańców miasta w punkcie ewakuacji",
    "hours": "h",
    "minutes": "min",
}

_EN: dict[str, str] = {
    "title": "Netless",
    "subtitle": "phone-to-phone crisis channel without a mobile network",
    "model_note": "Model output (computer simulation), not field measurements.",
    "model_tag": "model output",
    "map_note": "Map: {source}",
    "since_outage": "{elapsed} since network outage · model time",
    "before_outage": "before network outage · model time",
    "zone": "Hazard zone",
    "scale": "{m} m",
    "tile_alert": "Verified alert in the app",
    "tile_alert_value": "{pct:.0f}% of phones with the app",
    "tile_evac": "Evacuated from the hazard zone",
    "tile_evac_value": "{pct:.0f}% of zone residents",
    "story": "What is happening",
    "ev_network_down": "Mobile network goes down",
    "ev_alert_issued": "Crisis centre issues a signed alert",
    "ev_alert_relay": "Phones pass the alert to each other",
    "ev_reach_50": "Half of the phones have the alert",
    "ev_reach_90": "90% of the phones have the alert",
    "ev_couriers": "Couriers head out",
    "run_note": (
        "Single run: {scenario}, seed {seed}, {residents} residents, adoption {adoption}%, "
        "range {range_m} m, couriers: {couriers}. Spread across seeds: docs/WYNIKI.md."
    ),
    "axis_hours": "time since the mobile network went down [h]",
    "mark_alert": "alert issued",
    "mark_update": "new alert version",
    "mark_troll": "fake alert",
    "series_relay": "Sztafeta",
    "series_base": "without Sztafeta (hub range only)",
    "series_created": "sent by residents",
    "series_delivered": "delivered to the crisis centre",
    "series_delivered_base": "without Sztafeta",
    "milestone": "{share}% {elapsed} after the alert",
    "reach_title_vs": "Sztafeta brings the alert to {relay} of phones with the app; without it {base}",
    "reach_title": "A signed alert reaches {relay} of phones with the app in {hours:.0f} h with no network",
    "reach_sub": (
        "Share of phones with the app that received and verified the official alert (word of "
        "mouth counted separately)."
    ),
    "reach_axis": "phones with the app that have the alert",
    "evac_title": "Thanks to the alert {relay} of zone residents reach the evacuation point",
    "evac_sub": "All hazard-zone residents, with and without the app (the latter learn by word of mouth).",
    "evac_axis": "zone residents at the evacuation point",
    "reports_title_vs": (
        "Couriers deliver {delivered} of {created} reports; without Sztafeta {base} of {base_created} arrive"
    ),
    "reports_title": "Couriers bring {delivered} of {created} resident reports to the crisis centre",
    "reports_sub": (
        "Median delay: {delay}. “Need help”: {need_delivered} of {need_created}. "
        "Acknowledgement returned to {acks} reporters."
    ),
    "reports_axis": "number of reports",
    "card_title": (
        "{hours:.0f} h with no network: {reach} of phones alerted, {delivered} reports "
        "delivered, {fake} fakes accepted"
    ),
    "card_sub": (
        "{contacts} phone-to-phone contacts · {megabytes:.1f} MB transferred · mean battery "
        "at the end {battery:.0f}%"
    ),
    "card_base": "without Sztafeta: {value}",
    "card_never": "not reached",
    "card_reach": "of phones with the app have a verified alert",
    "card_reach_note": "half {t50} after the alert",
    "card_zone_note": "in the hazard zone: {zone}",
    "card_all": "of all residents: via the app + by word of mouth",
    "card_all_note": "word of mouth is a model assumption, counted separately",
    "card_evac": "of zone residents at the evacuation point",
    "card_reports": "reports reached the crisis centre",
    "card_need": "“need help” reports at the crisis centre",
    "card_acks": "reporters received an acknowledgement",
    "card_acks_note": "{pct:.0f}% of delivered reports",
    "card_fake": "devices accepted the fake alert as genuine",
    "card_fake_note": "received and rejected it: {received} devices",
    "axis_adoption": "adoption: share of residents with the module installed",
    "axis_minutes": "minutes since the alert was issued",
    "axis_couriers": "number of couriers (rescuers and volunteers with a phone)",
    "axis_reports_pct": "reports delivered to the crisis centre",
    "batch_note": (
        "Scenario: {preset}. Line: median of {seeds} seeds, band: lowest and highest value. {fixed}"
    ),
    "fixed_range_couriers": "Range {range_m:.0f} m, couriers: {couriers}.",
    "fixed_couriers": "Couriers: {couriers}.",
    "fixed_adoption_range": "Adoption {adoption:.0f}%, range {range_m:.0f} m.",
    "series_t50": "time until half of the phones with the app have the alert",
    "reached_in": "{k} of {n} runs",
    "range_label": "range {range_m:.0f} m",
    "reach_batch_title": (
        "At {adoption:.0f}% adoption a {short:.0f} m range reaches {short_pct} of phones, "
        "{long:.0f} m: {long_pct}"
    ),
    "reach_batch_sub": (
        "Share of phones with the app holding a verified alert after {hours:.0f} h without a mobile network."
    ),
    "series_rep_end": "at the end",
    "series_rep_3h": "after 3 h",
    "series_rep_1h": "after 1 h",
    "couriers_title": "{few} couriers deliver {few_pct} of reports, {many} couriers: {many_pct}",
    "couriers_sub": "By the end the gap narrows: {few_pct} and {many_pct}. Brackets: spread across seeds.",
    "time_title_hour": (
        "From {adoption:.0f}% adoption half of the phones get the alert within an hour "
        "(median of {seeds} seeds)"
    ),
    "time_title_slow": "At no tested adoption does the alert reach half of the phones within an hour",
    "time_sub_90": "The alert reaches 90% of phones in every run from {adoption:.0f}% adoption.",
    "time_sub_90_never": (
        "The alert never reaches 90% of phones in all runs (best: {k} of {n} at {adoption:.0f}%)."
    ),
    "couriers_title_1h": (
        "After 1 h the centre has {few_pct} of reports with {few} couriers and {many_pct} with {many}"
    ),
    "evac_sub_vs": (
        "All zone residents. The baseline has no sirens or patrols: it is a lower bound, not a forecast."
    ),
    "card_row_alerts": "ALERT RELAY: authority → residents",
    "card_row_reports": "DATA COURIER: residents → authority",
    "card_evac_note": "with and without the app",
    "card_of": "{a} of {b}",
    "card_need_note": "people without the app cannot send a report",
    "card_delay": "median time from report to the crisis centre",
    "card_delay_note": "90% of reports within {p90}",
    "with_range": "{med} ({lo:.0f}–{hi:.0f}%)",
    "people_one": "{n} person",
    "people_few": "{n} people",
    "people_many": "{n} people",
    "leg_idle": "phone without the alert",
    "leg_alert": "phone with the alert",
    "leg_handover": "alert handed over",
    "leg_ring": "has just received it",
    "leg_evac": "evacuating",
    "leg_courier": "courier (rescuer)",
    "closeup_caption": "CLOSE-UP · dashed line: phones are connecting · blue: the alert is being sent",
    "scale_range": "{m} m: radio range",
    "ev_evac_start": "The zone starts evacuating",
    "ev_evac_half": "Half of the zone is safe",
    "ev_end": "{pct:.0f}% of zone residents evacuated",
    "tile_evac_city": "Residents at the evacuation point",
    "tile_evac_value_city": "{pct:.0f}% of town residents",
    "ev_couriers_city": "Couriers carry the alert across town",
    "ev_evac_start_city": "The town starts evacuating",
    "ev_evac_half_city": "Half of the town is safe",
    "ev_end_city": "{pct:.0f}% of residents evacuated",
    "evac_title_city": "Thanks to the alert {relay} of the town's residents reach the evacuation point",
    "evac_sub_city": "All town residents, with and without the app (the latter learn by word of mouth).",
    "evac_sub_vs_city": (
        "All town residents. The baseline has no sirens or patrols: it is a lower bound, not a forecast."
    ),
    "evac_axis_city": "town residents at the evacuation point",
    "card_evac_city": "of the town's residents at the evacuation point",
    "hours": "h",
    "minutes": "min",
}

_LANGS: dict[str, dict[str, str]] = {"pl": _PL, "en": _EN}


def tr(lang: str, key: str, **fmt: object) -> str:
    """Napis w języku `lang` (nieznany język = polski)."""
    table = _LANGS.get(lang, _PL)
    text = table.get(key, _PL.get(key, key))
    return text.format(**fmt) if fmt else text


def whole_city(summary: Mapping[str, object]) -> bool:
    """Czy uruchomienie nie miało strefy zagrożenia (pole `area` w podsumowaniu; brak pola = strefa)."""
    return summary.get("area") == "city"


def area_key(key: str, whole_city: bool) -> str:
    """Klucz napisu zależnego od obszaru alertu: wariant „_city”, gdy scenariusz nie ma strefy zagrożenia."""
    return f"{key}_city" if whole_city else key


def elapsed(lang: str, seconds: float) -> str:
    """Czas trwania w postaci „1 h 05 min”."""
    total = int(max(seconds, 0.0)) // 60
    hours, minutes = divmod(total, 60)
    if hours:
        return f"{hours} {tr(lang, 'hours')} {minutes:02d} {tr(lang, 'minutes')}"
    return f"{minutes} {tr(lang, 'minutes')}"


def people(lang: str, n: int) -> str:
    """„1 osoba”, „3 osoby”, „12 osób” – z polską odmianą liczebnika."""
    if n == 1:
        key = "people_one"
    elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        key = "people_few"
    else:
        key = "people_many"
    return tr(lang, key, n=n)
