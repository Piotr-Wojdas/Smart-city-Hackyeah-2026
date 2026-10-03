"""Sztab (PCZK): przyjmowanie zgłoszeń z huba, deduplikacja, potwierdzenia zbiorcze, dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sztafeta.engine.crypto import sign_ack
from sztafeta.engine.events import EventLog, EventType
from sztafeta.engine.model import Certificate, HelpCategory, Report, ReportKind, RoutingParams
from sztafeta.engine.routing import Router


@dataclass(slots=True)
class PczkEntry:
    """Jedno zgłoszenie na dashboardzie (po deduplikacji: najnowsza wersja)."""

    report_id: str
    version: int
    kind: ReportKind
    category: HelpCategory
    persons: int
    urgency: int
    geohash: str
    created_t: float
    received_t: float  # kiedy pierwsza wersja dotarła do sztabu
    updated_t: float  # kiedy dotarła bieżąca wersja
    carrier: int  # kto oddał zgłoszenie w hubie (kurier albo sam zgłaszający)
    sensitive_encrypted: bool
    acked: bool = False


class Pczk:
    """Stan sztabu. Zgłoszenia są potwierdzane zbiorczo, w cyklu obsługi co `ack_delay_s`."""

    __slots__ = (
        "_cert",
        "_events",
        "_hub",
        "_key",
        "_next_cycle_t",
        "_p",
        "_pending",
        "_router",
        "acks_issued",
        "entries",
        "last_update_t",
    )

    def __init__(
        self,
        params: RoutingParams,
        key: Ed25519PrivateKey,
        cert: Certificate,
        router: Router,
        events: EventLog,
        hub_id: int,
    ) -> None:
        self._p = params
        self._key = key
        self._cert = cert
        self._router = router
        self._events = events
        self._hub = hub_id
        self.entries: dict[str, PczkEntry] = {}
        self._pending: list[tuple[str, int]] = []
        self._next_cycle_t = params.ack_delay_s
        self.acks_issued = 0
        self.last_update_t: float | None = None

    def receive(self, report: Report, carrier: int, t: float) -> None:
        """Zgłoszenie oddane w hubie. Nowsza wersja nadpisuje starszą, starsza jest ignorowana."""
        entry = self.entries.get(report.report_id)
        if entry is not None and report.version <= entry.version:
            return
        first = entry is None
        received_t = t if entry is None else entry.received_t
        self.entries[report.report_id] = PczkEntry(
            report_id=report.report_id,
            version=report.version,
            kind=report.kind,
            category=report.category,
            persons=report.persons,
            urgency=report.urgency,
            geohash=report.geohash,
            created_t=report.created_at,
            received_t=received_t,
            updated_t=t,
            carrier=carrier,
            sensitive_encrypted=report.sensitive_encrypted,
        )
        self._pending.append((report.report_id, report.version))
        self.last_update_t = t
        self._events.emit(
            t,
            EventType.REPORT_DELIVERED,
            agent=self._hub,
            peer=carrier,
            packet=report.pid,
            report=report.report_id,
            kind=report.kind.name,
            urgency=report.urgency,
            version=report.version,
            first=first,
            delay=round(t - report.created_at, 1),
        )

    def step(self, t: float) -> None:
        """Cykl obsługi: potwierdza wszystkie zgłoszenia przyjęte od poprzedniego cyklu."""
        if t < self._next_cycle_t:
            return
        self._next_cycle_t = t + self._p.ack_delay_s
        if not self._pending:
            return
        size = max(self._p.ack_batch_size, 1)
        for start in range(0, len(self._pending), size):
            batch = tuple(self._pending[start : start + size])
            ack = sign_ack(self._key, self._cert, batch, t, t + self._p.ack_lifetime_s, self._p.ack_ttl_hops)
            self._router.issue_ack(ack, self._hub, t)
            self.acks_issued += 1
            for report_id, version in batch:
                entry = self.entries[report_id]
                if entry.version == version:
                    entry.acked = True
            self._events.emit(
                t, EventType.ACK_ISSUED, agent=self._hub, packet=ack.pid, reports=len(batch), bytes=ack.size
            )
        self._pending.clear()

    def counters(self) -> dict[str, Any]:
        """Liczniki dashboardu („bezpieczni: X, potrzebujący pomocy: Y”)."""
        entries = list(self.entries.values())
        safe = [e for e in entries if e.kind == ReportKind.SAFE]
        need = [e for e in entries if e.kind == ReportKind.NEED_HELP]
        by_category: dict[str, int] = {}
        for e in need:
            by_category[e.category.name] = by_category.get(e.category.name, 0) + 1
        return {
            "reports": len(entries),
            "safe_reports": len(safe),
            "safe_persons": sum(e.persons for e in safe),
            "need_help_reports": len(need),
            "need_help_persons": sum(e.persons for e in need),
            "need_help_critical": sum(1 for e in need if e.urgency >= 3),
            "by_category": dict(sorted(by_category.items())),
            "acks_issued": self.acks_issued,
            "last_update_t": self.last_update_t,
        }

    def dashboard(self, t: float) -> dict[str, Any]:
        """Stan dashboardu sztabu: liczniki i lista zgłoszeń według pilności (zawartość `pczk.json`)."""
        ordered = sorted(
            self.entries.values(),
            key=lambda e: (e.kind != ReportKind.NEED_HELP, -e.urgency, e.received_t, e.report_id),
        )
        return {
            "t": t,
            "counters": self.counters(),
            "reports": [
                {
                    "report_id": e.report_id,
                    "version": e.version,
                    "kind": e.kind.name,
                    "category": e.category.name,
                    "persons": e.persons,
                    "urgency": e.urgency,
                    "geohash": e.geohash,
                    "created_t": e.created_t,
                    "received_t": e.received_t,
                    "updated_t": e.updated_t,
                    "delay_s": round(e.received_t - e.created_t, 1),
                    "carrier": e.carrier,
                    "sensitive_encrypted": e.sensitive_encrypted,
                    "acked": e.acked,
                }
                for e in ordered
            ],
        }
