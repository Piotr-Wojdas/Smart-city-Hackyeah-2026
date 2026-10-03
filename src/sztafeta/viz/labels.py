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
