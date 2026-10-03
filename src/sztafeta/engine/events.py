"""Strumień zdarzeń silnika – część kontraktu z przyszłym backendem (format w docs/FORMAT.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

EventValue = str | int | float | bool | list[str] | dict[str, int]


class EventType(StrEnum):
    NETWORK_DOWN = "network_down"
    NOTE = "note"
    ALERT_ISSUED = "alert_issued"
    ALERT_RECEIVED = "alert_received"
    ALERT_REJECTED = "alert_rejected"
    TROLL_BROADCAST = "troll_broadcast"
    WORD_OF_MOUTH = "word_of_mouth"
    CONTACT_START = "contact_start"
    CONTACT_END = "contact_end"
    TRANSFER = "transfer"
    EVACUATION_START = "evacuation_start"
    EVACUATION_DONE = "evacuation_done"
    REPORT_CREATED = "report_created"
    REPORT_PICKED_UP = "report_picked_up"
    REPORT_DELIVERED = "report_delivered"
    ACK_ISSUED = "ack_issued"
    ACK_RECEIVED = "ack_received"
    COURIER_DISPATCHED = "courier_dispatched"
    COURIER_AT_HUB = "courier_at_hub"
    BATTERY_DEAD = "battery_dead"
    PACKET_EVICTED = "packet_evicted"


@dataclass(slots=True)
class Event:
    """Jedno zdarzenie. `agent` to urządzenie, którego dotyczy; `peer` – druga strona (lub -1)."""

    t: float
    type: EventType
    agent: int = -1
    peer: int = -1
    packet: str = ""
    data: dict[str, EventValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {"t": round(self.t, 3), "type": str(self.type)}
        if self.agent >= 0:
            out["agent"] = self.agent
        if self.peer >= 0:
            out["peer"] = self.peer
        if self.packet:
            out["packet"] = self.packet
        if self.data:
            out["data"] = self.data
        return out


class EventLog:
    """Bufor zdarzeń. Odbiorca (zapis do pliku, WebSocket) opróżnia go przez `drain()`."""

    __slots__ = ("_events", "counts")

    def __init__(self) -> None:
        self._events: list[Event] = []
        self.counts: dict[str, int] = {}

    def emit(
        self,
        t: float,
        type_: EventType,
        agent: int = -1,
        peer: int = -1,
        packet: str = "",
        **data: EventValue,
    ) -> None:
        self._events.append(Event(t, type_, agent, peer, packet, dict(data)))
        key = str(type_)
        self.counts[key] = self.counts.get(key, 0) + 1

    def drain(self) -> list[Event]:
        out = self._events
        self._events = []
        return out

    def __len__(self) -> int:
        return len(self._events)
