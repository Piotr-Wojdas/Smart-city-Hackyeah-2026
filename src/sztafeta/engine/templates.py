"""Szablony alertów: kody (zagrożenie + działanie + miejsce) -> tekst w języku telefonu.

Pakiet niesie tylko kody, więc jest mały, a każdy telefon pokazuje komunikat we własnym języku.
Tłumaczenia UK/DE/CS są robocze – przed wdrożeniem wymagają weryfikacji przez native speakerów.
"""

from __future__ import annotations

from dataclasses import dataclass

from sztafeta.engine.model import Action, Alert, Hazard, Lang, MsgType

# kolejność w krotkach: PL, EN, UK, DE, CS (jak w wyliczeniu Lang)
_HAZARD: dict[Hazard, tuple[str, str, str, str, str]] = {
    Hazard.FLOOD: ("Powódź", "Flood", "Повінь", "Hochwasser", "Povodeň"),
    Hazard.DAM_FAILURE: (
        "Przerwanie zapory",
        "Dam failure",
        "Прорив дамби",
        "Dammbruch",
        "Protržení hráze",
    ),
    Hazard.BLACKOUT: ("Awaria zasilania", "Power outage", "Знеструмлення", "Stromausfall", "Výpadek proudu"),
    Hazard.FIRE: ("Pożar", "Fire", "Пожежа", "Brand", "Požár"),
    Hazard.CHEMICAL: (
        "Zagrożenie chemiczne",
        "Chemical hazard",
        "Хімічна небезпека",
        "Chemische Gefahr",
        "Chemické nebezpečí",
    ),
    Hazard.STORM: ("Gwałtowna burza", "Severe storm", "Сильна буря", "Schweres Unwetter", "Silná bouře"),
}

_ACTION: dict[Action, tuple[str, str, str, str, str]] = {
    Action.EVACUATE: (
        "Ewakuuj się natychmiast do: {place}.",
        "Evacuate immediately to: {place}.",
        "Негайно евакуюйтеся до: {place}.",
        "Begeben Sie sich sofort zu: {place}.",
        "Okamžitě se evakuujte do: {place}.",
    ),
    Action.SHELTER: (
        "Zostań w budynku, zamknij okna i drzwi.",
        "Stay indoors, close windows and doors.",
        "Залишайтеся в приміщенні, зачиніть вікна та двері.",
        "Bleiben Sie im Gebäude, schließen Sie Fenster und Türen.",
        "Zůstaňte v budově, zavřete okna a dveře.",
    ),
    Action.AVOID_AREA: (
        "Nie zbliżaj się do zagrożonego obszaru.",
        "Stay away from the affected area.",
        "Не наближайтеся до небезпечної зони.",
        "Meiden Sie das betroffene Gebiet.",
        "Nepřibližujte se k ohrožené oblasti.",
    ),
    Action.BOIL_WATER: (
        "Woda z kranu jest niezdatna do picia. Przegotuj ją przed użyciem.",
        "Tap water is not safe to drink. Boil it before use.",
        "Вода з-під крана непридатна для пиття. Кип'ятіть її перед вживанням.",
        "Leitungswasser ist nicht trinkbar. Kochen Sie es vor Gebrauch ab.",
        "Voda z kohoutku není pitná. Před použitím ji převařte.",
    ),
    Action.ALL_CLEAR: (
        "Zagrożenie minęło. Alert odwołany.",
        "The danger has passed. The alert is cancelled.",
        "Небезпека минула. Попередження скасовано.",
        "Die Gefahr ist vorüber. Die Warnung ist aufgehoben.",
        "Nebezpečí pominulo. Výstraha je odvolána.",
    ),
}

_MSG_PREFIX: dict[MsgType, tuple[str, str, str, str, str]] = {
    MsgType.ALERT: ("", "", "", "", ""),
    MsgType.UPDATE: ("Aktualizacja: ", "Update: ", "Оновлення: ", "Aktualisierung: ", "Aktualizace: "),
    MsgType.CANCEL: ("Odwołanie: ", "Cancellation: ", "Скасування: ", "Aufhebung: ", "Odvolání: "),
}

_VERIFIED = (
    "ZWERYFIKOWANY KOMUNIKAT URZĘDOWY",
    "VERIFIED OFFICIAL ALERT",
    "ПЕРЕВІРЕНЕ ОФІЦІЙНЕ ПОВІДОМЛЕННЯ",
    "VERIFIZIERTE AMTLICHE WARNUNG",
    "OVĚŘENÁ ÚŘEDNÍ VÝSTRAHA",
)
_UNVERIFIED = (
    "NIEZWERYFIKOWANE – nie ufaj tej wiadomości",
    "UNVERIFIED – do not trust this message",
    "НЕПЕРЕВІРЕНО – не довіряйте цьому повідомленню",
    "NICHT VERIFIZIERT – vertrauen Sie dieser Nachricht nicht",
    "NEOVĚŘENO – této zprávě nedůvěřujte",
)


@dataclass(frozen=True, slots=True)
class RenderedAlert:
    """Alert tak, jak pokazuje go telefon: nagłówek klasy treści, tytuł, treść, piktogramy."""

    header: str
    title: str
    body: str
    pictograms: tuple[str, str]
    lang: str


def render_alert(alert: Alert, lang: Lang, verified: bool, places: dict[str, str]) -> RenderedAlert:
    """Renderuje alert lokalnie w języku telefonu. `places` zamienia kod miejsca na nazwę."""
    k = int(lang)
    place = places.get(alert.place, alert.place)
    return RenderedAlert(
        header=(_VERIFIED if verified else _UNVERIFIED)[k],
        title=_MSG_PREFIX[alert.msg_type][k] + _HAZARD[alert.hazard][k],
        body=_ACTION[alert.action][k].format(place=place),
        pictograms=(alert.hazard.name.lower(), alert.action.name.lower()),
        lang=lang.name.lower(),
    )
