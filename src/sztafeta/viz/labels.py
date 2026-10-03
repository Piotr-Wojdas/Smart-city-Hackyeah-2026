"""Napisy wizualizacji po polsku i angielsku (`--lang en`)."""

from __future__ import annotations

_PL: dict[str, str] = {
    "title": "Sztafeta",
    "subtitle": "kanał kryzysowy telefon–telefon bez sieci komórkowej",
    "model_note": "Wynik modelu (symulacja komputerowa), nie pomiar z terenu.",
    "model_tag": "wynik modelu",
    "map_note": "Mapa: {source}",
    "since_outage": "{elapsed} od awarii sieci",
    "before_outage": "przed awarią sieci",
    "zone": "Strefa zagrożenia",
    "scale": "{m} m",
    "people": "{n} osób",
    "tile_alert": "Zweryfikowany alert w aplikacji",
    "tile_alert_value": "{pct:.0f}% telefonów",
    "tile_evac": "Ewakuowani ze strefy zagrożenia",
    "tile_evac_value": "{pct:.0f}% mieszkańców strefy",
    "tile_reports": "Zgłoszenia w PCZK",
    "tile_reports_value": "{delivered} z {created}",
    "tile_reports_sub": "w tym „potrzebuję pomocy”: {need_delivered} z {need_created}",
    "tile_acks_value": "potwierdzenie „przyjęto” wróciło do: {n}",
    "tile_fake": "Fałszywy alert",
    "tile_fake_value": "dostało: {received} · uznało za prawdziwy: {verified}",
    "legend_states": "Mieszkańcy (kolor i kształt = stan)",
    "state_0": "bez aplikacji",
    "state_1": "ma aplikację, nie ma alertu",
    "state_2": "ma zweryfikowany alert",
    "state_3": "ewakuuje się",
    "state_4": "bezpieczny w punkcie ewakuacji",
    "state_5": "potrzebuje pomocy",
    "courier": "kurier (ratownik, wolontariusz)",
    "troll": "troll z fałszywym alertem",
    "hub": "hub: urząd / PCZK",
    "evac": "punkt ewakuacji",
    "link": "transmisja między telefonami",
    "story": "Co się dzieje",
    "ev_network_down": "Awaria sieci komórkowej",
    "ev_alert_issued": "PCZK wydaje podpisany alert: ewakuacja",
    "ev_alert_relay": "Alert idzie sztafetą z telefonu do telefonu",
    "ev_reach_50": "Połowa telefonów z aplikacją ma alert",
    "ev_reach_90": "90% telefonów z aplikacją ma alert",
    "ev_couriers": "Kurierzy wyruszają w teren",
    "ev_troll": "Troll rozsyła fałszywy alert",
    "ev_rejected": "Fałszywka odrzucona: nieważny podpis",
    "ev_report": "Mieszkańcy wysyłają zgłoszenia",
    "ev_pickup": "Kurier zbiera zgłoszenia po drodze",
    "ev_delivered": "Zgłoszenia docierają do PCZK",
    "ev_ack": "Potwierdzenie „przyjęto” wraca do mieszkańca",
    "ev_alert_update": "Nowa wersja alertu zastępuje poprzednią",
    "run_note": (
        "Scenariusz: {scenario}, seed {seed}, {residents} mieszkańców, adopcja {adoption}%, "
        "zasięg {range_m} m, kurierów: {couriers}."
    ),
    "axis_hours": "czas od awarii sieci komórkowej [h]",
    "mark_alert": "alert wydany",
    "mark_update": "nowa wersja alertu",
    "mark_troll": "fałszywy alert",
    "series_relay": "Sztafeta",
    "series_base": "bez Sztafety (tylko zasięg huba)",
    "series_created": "zgłoszenia wysłane przez mieszkańców",
    "series_delivered": "dostarczone do PCZK (Sztafeta)",
    "series_delivered_base": "dostarczone bez Sztafety (osobiście)",
    "milestone": "{share}% po {elapsed}",
    "reach_title_vs": "Sztafeta dociera z alertem do {relay} telefonów z aplikacją; bez niej do {base}",
    "reach_title": "Podpisany alert dociera do {relay} telefonów z aplikacją w {hours:.0f} h bez sieci",
    "reach_sub": (
        "Odsetek telefonów z aplikacją, które odebrały i zweryfikowały alert urzędowy "
        "(przekaz ustny liczony osobno)."
    ),
    "reach_axis": "telefony z aplikacją, które mają alert",
    "evac_title_vs": "Ze strefy zagrożenia ewakuuje się {relay} mieszkańców; bez Sztafety {base}",
    "evac_title": "Ze strefy zagrożenia ewakuuje się {relay} mieszkańców",
    "evac_sub": (
        "Odsetek wszystkich mieszkańców strefy (z aplikacją i bez), którzy dotarli do punktu ewakuacji."
    ),
    "evac_axis": "mieszkańcy strefy w punkcie ewakuacji",
    "reports_title_vs": (
        "Kurierzy dowożą do PCZK {delivered} z {created} zgłoszeń; bez Sztafety dociera {base}"
    ),
    "reports_title": "Kurierzy dowożą do PCZK {delivered} z {created} zgłoszeń mieszkańców",
    "reports_sub": (
        "Mediana opóźnienia: {delay}. „Potrzebuję pomocy”: {need_delivered} z {need_created}. "
        "Potwierdzenie wróciło do {acks} zgłaszających."
    ),
    "reports_axis": "liczba zgłoszeń",
    "card_title": "Sztafeta: karta wyników jednego uruchomienia",
    "card_sub": (
        "{hours:.0f} h bez sieci komórkowej · {contacts} kontaktów · {megabytes:.1f} MB "
        "przesłanych danych · średnia bateria na koniec {battery:.0f}%"
    ),
    "card_base": "bez Sztafety: {value}",
    "card_never": "nie osiągnięto",
    "card_reach": "telefonów z aplikacją ma zweryfikowany alert",
    "card_reach_note": "połowa po {t50}. {base}",
    "card_zone": "telefonów w strefie zagrożenia ma alert",
    "card_zone_note": "90% po {t90}",
    "card_all": "wszystkich mieszkańców: aplikacja + przekaz ustny",
    "card_all_note": "przekaz ustny liczony osobno",
    "card_evac": "mieszkańców strefy w punkcie ewakuacji",
    "card_reports": "zgłoszeń dotarło do PCZK",
    "card_reports_note": "mediana opóźnienia {delay}.",
    "card_need": "zgłoszeń „potrzebuję pomocy” w PCZK",
    "card_acks": "zgłaszających dostało potwierdzenie",
    "card_acks_note": "{pct:.0f}% dostarczonych zgłoszeń",
    "card_fake": "urządzeń uznało fałszywy alert za prawdziwy",
    "card_fake_note": "dostało go {received} urządzeń",
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
    "series_t50": "czas do 50% telefonów z aplikacją",
    "series_t90": "czas do 90% telefonów z aplikacją",
    "reached_in": "{k} z {n} przebiegów",
    "range_label": "zasięg {range_m:.0f} m",
    "reach_batch_title": (
        "Przy adopcji {adoption:.0f}% zasięg {short:.0f} m daje alert {short_pct} telefonów, "
        "a {long:.0f} m: {long_pct}"
    ),
    "reach_batch_sub": (
        "Odsetek telefonów z aplikacją, które mają zweryfikowany alert po {hours:.0f} h bez sieci komórkowej."
    ),
    "series_rep_end": "na koniec symulacji",
    "series_rep_3h": "po 3 h",
    "series_rep_1h": "po 1 h",
    "couriers_title": "{few} kurierów dowozi do PCZK {few_pct} zgłoszeń, {many} kurierów: {many_pct}",
    "couriers_sub": "Odsetek zgłoszeń mieszkańców, które dotarły do PCZK (czas liczony od awarii sieci).",
    "time_title_hour": "Od adopcji {adoption:.0f}% połowa telefonów z aplikacją ma alert w ciągu godziny",
    "time_title_slow": "Przy żadnej badanej adopcji alert nie dociera do połowy telefonów w ciągu godziny",
    "time_sub_90": (
        "90% telefonów w każdym przebiegu od adopcji {adoption:.0f}%. Brak punktu: progu nie osiągnięto."
    ),
    "time_sub_90_never": (
        "Do 90% telefonów alert dociera tylko w części przebiegów. Brak punktu: progu nie osiągnięto."
    ),
    "couriers_title_1h": (
        "Po 1 h w PCZK jest {few_pct} zgłoszeń przy {few} kurierach i {many_pct} przy {many}"
    ),
    "couriers_sub_1h": (
        "Na koniec symulacji różnica maleje: {few_pct} i {many_pct}. Czas liczony od awarii sieci."
    ),
    "hours": "h",
    "minutes": "min",
}

_EN: dict[str, str] = {
    "title": "Sztafeta",
    "subtitle": "phone-to-phone crisis channel without a mobile network",
    "model_note": "Model output (computer simulation), not field measurements.",
    "model_tag": "model output",
    "map_note": "Map: {source}",
    "since_outage": "{elapsed} since network outage",
    "before_outage": "before network outage",
    "zone": "Hazard zone",
    "scale": "{m} m",
    "people": "{n} people",
    "tile_alert": "Verified alert in the app",
    "tile_alert_value": "{pct:.0f}% of phones",
    "tile_evac": "Evacuated from the hazard zone",
    "tile_evac_value": "{pct:.0f}% of zone residents",
    "tile_reports": "Reports at the crisis centre",
    "tile_reports_value": "{delivered} of {created}",
    "tile_reports_sub": "of which “need help”: {need_delivered} of {need_created}",
    "tile_acks_value": "“received” acknowledgement returned to: {n}",
    "tile_fake": "Fake alert",
    "tile_fake_value": "received: {received} · accepted as genuine: {verified}",
    "legend_states": "Residents (colour and shape = state)",
    "state_0": "no app",
    "state_1": "has the app, no alert yet",
    "state_2": "has a verified alert",
    "state_3": "evacuating",
    "state_4": "safe at the evacuation point",
    "state_5": "needs help",
    "courier": "courier (rescuer, volunteer)",
    "troll": "troll with a fake alert",
    "hub": "hub: town hall / crisis centre",
    "evac": "evacuation point",
    "link": "phone-to-phone transfer",
    "story": "What is happening",
    "ev_network_down": "Mobile network goes down",
    "ev_alert_issued": "Crisis centre issues a signed alert: evacuate",
    "ev_alert_relay": "The alert is relayed from phone to phone",
    "ev_reach_50": "Half of the phones with the app have the alert",
    "ev_reach_90": "90% of the phones with the app have the alert",
    "ev_couriers": "Couriers head out",
    "ev_troll": "A troll broadcasts a fake alert",
    "ev_rejected": "Fake rejected: invalid signature",
    "ev_report": "Residents send reports",
    "ev_pickup": "A courier collects reports on the way",
    "ev_delivered": "Reports reach the crisis centre",
    "ev_ack": "“Received” acknowledgement returns to the resident",
    "ev_alert_update": "A new alert version replaces the old one",
    "run_note": (
        "Scenario: {scenario}, seed {seed}, {residents} residents, adoption {adoption}%, "
        "range {range_m} m, couriers: {couriers}."
    ),
    "axis_hours": "time since the mobile network went down [h]",
    "mark_alert": "alert issued",
    "mark_update": "new alert version",
    "mark_troll": "fake alert",
    "series_relay": "Sztafeta",
    "series_base": "without Sztafeta (hub range only)",
    "series_created": "reports sent by residents",
    "series_delivered": "delivered to the crisis centre (Sztafeta)",
    "series_delivered_base": "delivered without Sztafeta (in person)",
    "milestone": "{share}% after {elapsed}",
    "reach_title_vs": "Sztafeta brings the alert to {relay} of phones with the app; without it {base}",
    "reach_title": "A signed alert reaches {relay} of phones with the app in {hours:.0f} h with no network",
    "reach_sub": (
        "Share of phones with the app that received and verified the official alert (word of "
        "mouth counted separately)."
    ),
    "reach_axis": "phones with the app that have the alert",
    "evac_title_vs": "{relay} of hazard-zone residents evacuate; without Sztafeta {base}",
    "evac_title": "{relay} of hazard-zone residents evacuate",
    "evac_sub": "Share of all zone residents (with and without the app) who reached the evacuation point.",
    "evac_axis": "zone residents at the evacuation point",
    "reports_title_vs": (
        "Couriers bring {delivered} of {created} reports to the crisis centre; without Sztafeta {base} arrive"
    ),
    "reports_title": "Couriers bring {delivered} of {created} resident reports to the crisis centre",
    "reports_sub": (
        "Median delay: {delay}. “Need help”: {need_delivered} of {need_created}. "
        "Acknowledgement returned to {acks} reporters."
    ),
    "reports_axis": "number of reports",
    "card_title": "Sztafeta: scorecard of a single run",
    "card_sub": (
        "{hours:.0f} h without a mobile network · {contacts} contacts · {megabytes:.1f} MB "
        "transferred · mean battery at the end {battery:.0f}%"
    ),
    "card_base": "without Sztafeta: {value}",
    "card_never": "not reached",
    "card_reach": "of phones with the app have a verified alert",
    "card_reach_note": "half after {t50}. {base}",
    "card_zone": "of phones in the hazard zone have the alert",
    "card_zone_note": "90% after {t90}",
    "card_all": "of all residents: app + word of mouth",
    "card_all_note": "word of mouth counted separately",
    "card_evac": "of zone residents at the evacuation point",
    "card_reports": "reports reached the crisis centre",
    "card_reports_note": "median delay {delay}.",
    "card_need": "“need help” reports at the crisis centre",
    "card_acks": "reporters received an acknowledgement",
    "card_acks_note": "{pct:.0f}% of delivered reports",
    "card_fake": "devices accepted the fake alert as genuine",
    "card_fake_note": "{received} devices received it",
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
    "series_t50": "time to 50% of phones with the app",
    "series_t90": "time to 90% of phones with the app",
    "reached_in": "{k} of {n} runs",
    "range_label": "range {range_m:.0f} m",
    "reach_batch_title": (
        "At {adoption:.0f}% adoption a {short:.0f} m range reaches {short_pct} of phones, "
        "{long:.0f} m: {long_pct}"
    ),
    "reach_batch_sub": (
        "Share of phones with the app holding a verified alert after {hours:.0f} h without a mobile network."
    ),
    "series_rep_end": "at the end of the simulation",
    "series_rep_3h": "after 3 h",
    "series_rep_1h": "after 1 h",
    "couriers_title": (
        "{few} couriers bring {few_pct} of reports to the crisis centre, {many} couriers: {many_pct}"
    ),
    "couriers_sub": (
        "Share of resident reports that reached the crisis centre (time since the network went down)."
    ),
    "time_title_hour": (
        "From {adoption:.0f}% adoption half of the phones with the app get the alert within an hour"
    ),
    "time_title_slow": "At no tested adoption does the alert reach half of the phones within an hour",
    "time_sub_90": (
        "90% of phones in every run from {adoption:.0f}% adoption. No point: threshold not reached."
    ),
    "time_sub_90_never": (
        "The alert reaches 90% of phones only in some runs. No point: threshold not reached."
    ),
    "couriers_title_1h": (
        "After 1 h the centre has {few_pct} of reports with {few} couriers and {many_pct} with {many}"
    ),
    "couriers_sub_1h": (
        "By the end the gap narrows: {few_pct} and {many_pct}. Time since the network went down."
    ),
    "hours": "h",
    "minutes": "min",
}

_LANGS: dict[str, dict[str, str]] = {"pl": _PL, "en": _EN}


def tr(lang: str, key: str, **fmt: object) -> str:
    """Napis w języku `lang` (nieznany język = polski)."""
    table = _LANGS.get(lang, _PL)
    text = table.get(key, _PL.get(key, key))
    return text.format(**fmt) if fmt else text


def elapsed(lang: str, seconds: float) -> str:
    """Czas trwania w postaci „1 h 05 min”."""
    total = int(max(seconds, 0.0)) // 60
    hours, minutes = divmod(total, 60)
    if hours:
        return f"{hours} {tr(lang, 'hours')} {minutes:02d} {tr(lang, 'minutes')}"
    return f"{minutes} {tr(lang, 'minutes')}"
