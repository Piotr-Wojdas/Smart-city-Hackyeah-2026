"""Typy domenowe silnika: wyliczenia, pakiety, parametry, scenariusz, tablice agentów.

Wartości liczbowe parametrów są opisane (z uzasadnieniem i źródłem) w docs/MODEL.md.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum

import numpy as np
from numpy.typing import NDArray

from sztafeta.engine.geo import GeoRef
from sztafeta.engine.graph import StreetGraph

FloatArr = NDArray[np.float64]
IntArr = NDArray[np.int64]
BoolArr = NDArray[np.bool_]


# --------------------------------------------------------------------------- wyliczenia


class Role(IntEnum):
    RESIDENT = 0
    COURIER = 1
    HUB = 2
    TROLL = 3


class AgentState(IntEnum):
    """Stan agenta widoczny na mapie (kolor markera)."""

    NO_APP = 0  # bez aplikacji i bez informacji
    UNINFORMED = 1  # ma aplikację, nie ma alertu
    INFORMED = 2  # ma zweryfikowany alert (lub informację ustną), nie ewakuuje się
    EVACUATING = 3
    SAFE = 4  # dotarł do punktu ewakuacji
    NEED_HELP = 5


class PacketKind(IntEnum):
    ALERT = 0
    ACK = 1
    REPORT = 2


class ReportKind(IntEnum):
    SAFE = 0
    NEED_HELP = 1


class Hazard(IntEnum):
    FLOOD = 0
    DAM_FAILURE = 1
    BLACKOUT = 2
    FIRE = 3
    CHEMICAL = 4
    STORM = 5


class Action(IntEnum):
    EVACUATE = 0
    SHELTER = 1
    AVOID_AREA = 2
    BOIL_WATER = 3
    ALL_CLEAR = 4


class MsgType(IntEnum):
    ALERT = 0
    UPDATE = 1
    CANCEL = 2


class HelpCategory(IntEnum):
    NONE = 0
    MEDICAL = 1
    EVACUATION = 2
    WATER = 3
    MEDICINE = 4
    POWER = 5


class Lang(IntEnum):
    PL = 0
    EN = 1
    UK = 2
    DE = 3
    CS = 4


class Verdict(IntEnum):
    """Wynik weryfikacji pakietu na urządzeniu."""

    VERIFIED = 0
    BAD_SIGNATURE = 1
    UNTRUSTED_ISSUER = 2
    CERT_EXPIRED = 3
    OUT_OF_SCOPE = 4
    STALE_SEQ = 5
    EXPIRED = 6


class Priority(IntEnum):
    """Priorytet w kolejce przesyłania i przy usuwaniu z bufora (mniejsza liczba = ważniejszy)."""

    ALERT = 0
    ACK = 1
    NEED_HELP = 2
    SAFE = 3
    UNVERIFIED = 4


class Forgery(IntEnum):
    """Sposób, w jaki troll fałszuje alert."""

    BAD_SIGNATURE = 0  # prawdziwy certyfikat PCZK, podpis innym kluczem
    UNTRUSTED_ISSUER = 1  # własny certyfikat spoza łańcucha zaufania


class ActionKind(StrEnum):
    """Akcje scenariusza – w przyszłości endpointy backendu."""

    NETWORK_DOWN = "network_down"
    ISSUE_ALERT = "issue_alert"
    DISPATCH_COURIERS = "dispatch_couriers"
    TROLL_BROADCAST = "troll_broadcast"
    NOTE = "note"


# --------------------------------------------------------------------------- serializacja kanoniczna


def _s(text: str) -> bytes:
    raw = text.encode("utf-8")
    return struct.pack(">B", len(raw)) + raw


def _t(seconds: float) -> bytes:
    """Czas modelu jako całkowite milisekundy (int64, big-endian)."""
    return struct.pack(">q", round(seconds * 1000.0))


# --------------------------------------------------------------------------- pakiety


@dataclass(frozen=True, slots=True)
class Certificate:
    """Certyfikat wydawcy podpisany kluczem głównym (RCB / wojewoda)."""

    issuer_id: str
    public_key: bytes
    scope: str  # prefiks geohash – obszar, na którym wydawca może ostrzegać
    not_before: float
    not_after: float
    signature: bytes

    def signed_bytes(self) -> bytes:
        return (
            b"SZC1"
            + _s(self.issuer_id)
            + self.public_key
            + _s(self.scope)
            + _t(self.not_before)
            + _t(self.not_after)
        )

    def to_bytes(self) -> bytes:
        return self.signed_bytes() + self.signature


@dataclass(frozen=True, slots=True)
class Alert:
    """Komunikat urzędowy w stylu CAP: kody zamiast wolnego tekstu, renderowane lokalnie w języku telefonu."""

    pid: str
    incident: str
    seq: int
    msg_type: MsgType
    hazard: Hazard
    action: Action
    area: tuple[str, ...]  # geohashe obszaru
    place: str  # kod miejsca docelowego (np. punkt ewakuacji)
    issued_at: float
    expires_at: float
    priority: int
    ttl_hops: int
    cert: Certificate
    signature: bytes

    def signed_bytes(self) -> bytes:
        return alert_body(
            self.incident,
            self.seq,
            self.msg_type,
            self.hazard,
            self.action,
            self.area,
            self.place,
            self.issued_at,
            self.expires_at,
            self.priority,
            self.ttl_hops,
            self.cert,
        )

    @property
    def size(self) -> int:
        return len(self.signed_bytes()) + len(self.signature)


def alert_body(
    incident: str,
    seq: int,
    msg_type: MsgType,
    hazard: Hazard,
    action: Action,
    area: tuple[str, ...],
    place: str,
    issued_at: float,
    expires_at: float,
    priority: int,
    ttl_hops: int,
    cert: Certificate,
) -> bytes:
    """Kanoniczna postać alertu, po której liczony jest podpis."""
    parts = [
        b"SZA1",
        _s(incident),
        struct.pack(">IBBB", seq, int(msg_type), int(hazard), int(action)),
        struct.pack(">B", len(area)),
        *[_s(g) for g in area],
        _s(place),
        _t(issued_at),
        _t(expires_at),
        struct.pack(">BB", priority, ttl_hops),
        cert.to_bytes(),
    ]
    return b"".join(parts)


@dataclass(frozen=True, slots=True)
class Report:
    """Zgłoszenie mieszkańca, podpisane jednorazowym kluczem urządzenia (nikt obcy go nie nadpisze)."""

    pid: str
    report_id: str  # skrót klucza zgłaszającego (hex, 8 bajtów)
    version: int
    kind: ReportKind
    category: HelpCategory
    persons: int
    urgency: int  # 1 = niska, 2 = pilna, 3 = zagrożenie życia
    geohash: str  # lokalizacja zgrubna
    created_at: float
    expires_at: float
    sensitive_len: int  # długość części zaszyfrowanej dla służb (0 = brak)
    reporter_key: bytes
    signature: bytes

    def signed_bytes(self) -> bytes:
        return report_body(
            self.report_id,
            self.version,
            self.kind,
            self.category,
            self.persons,
            self.urgency,
            self.geohash,
            self.created_at,
            self.expires_at,
            self.sensitive_len,
            self.reporter_key,
        )

    @property
    def sensitive_encrypted(self) -> bool:
        return self.sensitive_len > 0

    @property
    def size(self) -> int:
        return len(self.signed_bytes()) + len(self.signature) + self.sensitive_len


def report_body(
    report_id: str,
    version: int,
    kind: ReportKind,
    category: HelpCategory,
    persons: int,
    urgency: int,
    geohash: str,
    created_at: float,
    expires_at: float,
    sensitive_len: int,
    reporter_key: bytes,
) -> bytes:
    parts = [
        b"SZR1",
        bytes.fromhex(report_id),
        struct.pack(">HBBBB", version, int(kind), int(category), persons, urgency),
        _s(geohash),
        _t(created_at),
        _t(expires_at),
        struct.pack(">H", sensitive_len),
        reporter_key,
    ]
    return b"".join(parts)


@dataclass(frozen=True, slots=True)
class Ack:
    """Zbiorcze potwierdzenie „przyjęto zgłoszenie”, podpisane przez PCZK."""

    pid: str
    reports: tuple[tuple[str, int], ...]  # (report_id, wersja)
    issued_at: float
    expires_at: float
    ttl_hops: int
    cert: Certificate
    signature: bytes

    def signed_bytes(self) -> bytes:
        return ack_body(self.reports, self.issued_at, self.expires_at, self.ttl_hops, self.cert)

    @property
    def size(self) -> int:
        return len(self.signed_bytes()) + len(self.signature)


def ack_body(
    reports: tuple[tuple[str, int], ...],
    issued_at: float,
    expires_at: float,
    ttl_hops: int,
    cert: Certificate,
) -> bytes:
    parts = [b"SZK1", struct.pack(">H", len(reports))]
    for report_id, version in reports:
        parts.append(bytes.fromhex(report_id) + struct.pack(">H", version))
    parts += [_t(issued_at), _t(expires_at), struct.pack(">B", ttl_hops), cert.to_bytes()]
    return b"".join(parts)


Packet = Alert | Report | Ack


# --------------------------------------------------------------------------- parametry


@dataclass(slots=True)
class RadioParams:
    range_m: float = 40.0
    setup_min_s: float = 3.0
    setup_max_s: float = 8.0
    scan_window_s: float = 10.0
    scan_period_s: float = 60.0
    summary_vector_s: float = 1.0
    throughput_bps: float = 2000.0  # bajty na sekundę (konserwatywnie: sam BLE)
    max_session_s: float = 30.0
    max_links_resident: int = 2
    max_links_courier: int = 4
    max_links_hub: int = 6
    max_candidate_pairs: int = 3000


@dataclass(slots=True)
class RoutingParams:
    relay_enabled: bool = True  # False = wariant bazowy „bez Sztafety”
    alert_ttl_hops: int = 100
    ack_ttl_hops: int = 100
    alert_lifetime_s: float = 12 * 3600.0
    ack_lifetime_s: float = 6 * 3600.0
    report_lifetime_s: float = 12 * 3600.0
    spray_copies: int = 8
    buffer_resident: int = 200
    buffer_courier: int = 5000
    buffer_hub: int = 100_000
    max_own_reports_per_hour: int = 4
    unverified_forward_hops: int = 0
    ack_batch_size: int = 32
    ack_delay_s: float = 120.0


@dataclass(slots=True)
class BatteryParams:
    start_min_pct: float = 35.0
    start_max_pct: float = 100.0
    idle_pct_per_h: float = 2.0
    scan_pct_per_h: float = 5.0  # dodatkowo przy ciągłym skanowaniu; skalowane przez duty cycle
    link_pct_per_h: float = 6.0  # dodatkowo w czasie aktywnego połączenia


@dataclass(slots=True)
class BehaviorParams:
    adoption: float = 0.30
    lang_shares: tuple[float, float, float, float, float] = (0.90, 0.02, 0.05, 0.02, 0.01)  # PL EN UK DE CS
    walk_rate_per_h: float = 0.10
    walk_radius_m: float = 400.0
    walk_speed_mean: float = 1.3
    walk_speed_sd: float = 0.2
    reaction_median_s: float = 300.0
    reaction_sigma: float = 0.8
    reaction_max_s: float = 3600.0
    p_comply: float = 0.85
    p_need_help_zone: float = 0.06
    p_need_help_blackout: float = 0.01
    need_help_blackout_window_s: float = 2 * 3600.0
    p_safe_report_evacuated: float = 0.80
    p_safe_report_outside: float = 0.25
    safe_report_delay_s: float = 600.0
    p_report_update: float = 0.15
    report_update_delay_s: float = 1800.0
    p_sensitive: float = 0.30
    wom_enabled: bool = True
    wom_range_m: float = 10.0
    wom_prob_per_min: float = 0.20
    wom_interval_s: float = 10.0
    household_mean: float = 2.5


@dataclass(slots=True)
class PopulationParams:
    n_residents: int = 3000
    n_couriers: int = 4
    n_trolls: int = 1
    courier_vehicle_share: float = 0.5
    courier_walk_speed: float = 1.4
    courier_vehicle_speed: float = 5.0
    courier_return_interval_s: float = 1800.0
    courier_hub_dwell_s: float = 120.0
    courier_waypoint_dwell_s: float = 60.0
    evac_spread_m: float = 20.0


@dataclass(slots=True)
class OutputParams:
    snapshot_interval_s: float = 10.0
    metrics_interval_s: float = 10.0


@dataclass(slots=True)
class Params:
    """Komplet parametrów jednego uruchomienia."""

    dt: float = 1.0
    duration_s: float = 6 * 3600.0
    radio: RadioParams = field(default_factory=RadioParams)
    routing: RoutingParams = field(default_factory=RoutingParams)
    battery: BatteryParams = field(default_factory=BatteryParams)
    behavior: BehaviorParams = field(default_factory=BehaviorParams)
    population: PopulationParams = field(default_factory=PopulationParams)
    output: OutputParams = field(default_factory=OutputParams)


# --------------------------------------------------------------------------- scenariusz


@dataclass(slots=True)
class CityMap:
    """Mapa: graf ulic, budynki mieszkalne i lokalizacje specjalne. Współrzędne w metrach."""

    name: str
    crs: str
    graph: StreetGraph
    buildings_xy: FloatArr  # (B, 2)
    building_weight: FloatArr  # (B,) względna liczba mieszkańców
    hub_xy: FloatArr  # (2,)
    evac_xy: FloatArr  # (2,)
    hazard_zone: FloatArr  # (K, 2) wielokąt
    georef: GeoRef
    water: list[FloatArr] = field(default_factory=list)  # linie rzek (tylko do rysowania)
    source: str = "proceduralna siatka"


@dataclass(slots=True)
class ScheduledAction:
    """Akcja scenariusza zaplanowana na chwilę `t` (sekundy od początku)."""

    t: float
    kind: ActionKind
    hazard: Hazard = Hazard.FLOOD
    action: Action = Action.EVACUATE
    msg_type: MsgType = MsgType.ALERT
    forgery: Forgery = Forgery.BAD_SIGNATURE
    label: str = ""


@dataclass(slots=True)
class Scenario:
    name: str
    city: CityMap
    timeline: list[ScheduledAction] = field(default_factory=list)
    start_iso: str = "2024-09-15T06:00:00+02:00"
    hub_name: str = "Urząd / PCZK"
    evac_name: str = "Punkt ewakuacji"
    incident: str = "INC-1"


# --------------------------------------------------------------------------- agenci


@dataclass(slots=True)
class AgentArrays:
    """Stan agentów jako tablice numpy (indeks = id agenta).

    Kolejność: mieszkańcy (w tym trolle), potem kurierzy, na końcu hub.
    """

    n: int
    role: NDArray[np.uint8]
    has_app: BoolArr
    lang: NDArray[np.uint8]
    home_xy: FloatArr  # (N, 2)
    household: IntArr
    report_persons: NDArray[np.uint8]  # ile osób obejmie zgłoszenie tego agenta
    in_zone: BoolArr  # dom w strefie zagrożenia
    is_vehicle: BoolArr
    state: NDArray[np.uint8]
    battery: FloatArr  # 0..100
    informed_t: FloatArr  # czas zweryfikowanego alertu w aplikacji (nan = brak)
    wom_t: FloatArr  # czas informacji ustnej (nan = brak)
    evac_start_t: FloatArr
    evac_done_t: FloatArr

    @property
    def residents(self) -> BoolArr:
        mask: BoolArr = (self.role == int(Role.RESIDENT)) | (self.role == int(Role.TROLL))
        return mask
