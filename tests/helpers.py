"""Mały „świat” do testów routingu i kontaktów: kilka urządzeń w zadanych miejscach, bez mapy."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from sztafeta.engine.contacts import ContactEngine
from sztafeta.engine.crypto import KeyRing, Verifier, make_certificate, public_bytes, sign_ack, sign_alert
from sztafeta.engine.events import EventLog
from sztafeta.engine.model import (
    Ack,
    Action,
    AgentArrays,
    AgentState,
    Alert,
    Certificate,
    Hazard,
    MsgType,
    Params,
    Role,
)
from sztafeta.engine.rng import make_streams
from sztafeta.engine.routing import Router

SCOPE = "u2u"
AREA = ("u2uxyz",)


@dataclass
class World:
    params: Params
    agents: AgentArrays
    pos: NDArray[np.float64]
    events: EventLog
    keys: KeyRing
    cert: Certificate
    verifier: Verifier
    router: Router
    radio: ContactEngine
    hub: int
    t: float = 0.0

    def alert(self, seq: int = 1, t: float = 0.0, ttl_hops: int = 100, lifetime: float = 3600.0) -> Alert:
        return sign_alert(
            self.keys.issuer,
            self.cert,
            incident="T",
            seq=seq,
            msg_type=MsgType.ALERT,
            hazard=Hazard.FLOOD,
            action=Action.EVACUATE,
            area=AREA,
            place="EVAC-1",
            issued_at=t,
            expires_at=t + lifetime,
            ttl_hops=ttl_hops,
        )

    def fake_alert(self, t: float = 0.0) -> Alert:
        return sign_alert(
            self.keys.troll,
            self.cert,
            incident="T",
            seq=99,
            msg_type=MsgType.CANCEL,
            hazard=Hazard.FLOOD,
            action=Action.ALL_CLEAR,
            area=AREA,
            place="EVAC-1",
            issued_at=t,
            expires_at=t + 3600.0,
        )

    def ack(self, reports: tuple[tuple[str, int], ...], t: float = 0.0) -> Ack:
        return sign_ack(self.keys.issuer, self.cert, reports, t, t + 3600.0)

    def steps(self, n: int, dt: float = 1.0) -> None:
        for _ in range(n):
            self.radio.step(self.t, dt, self.pos)
            self.t += dt


def make_world(
    positions: list[tuple[float, float]],
    roles: list[Role],
    params: Params | None = None,
    has_app: list[bool] | None = None,
    always_awake: bool = True,
    seed: int = 1,
) -> World:
    """Urządzenia w podanych pozycjach. Ostatni HUB na liście jest hubem (jeśli brak – indeks 0)."""
    params = params or Params()
    if always_awake:
        params.radio.scan_window_s = params.radio.scan_period_s
    n = len(positions)
    role = np.array([int(r) for r in roles], dtype=np.uint8)
    app = np.array(has_app if has_app is not None else [True] * n, dtype=np.bool_)
    pos = np.array(positions, dtype=np.float64)
    agents = AgentArrays(
        n=n,
        role=role,
        has_app=app,
        lang=np.zeros(n, dtype=np.uint8),
        home_xy=pos.copy(),
        household=np.arange(n, dtype=np.int64),
        report_persons=np.ones(n, dtype=np.uint8),
        in_zone=np.zeros(n, dtype=np.bool_),
        is_vehicle=np.zeros(n, dtype=np.bool_),
        state=np.full(n, int(AgentState.UNINFORMED), dtype=np.uint8),
        battery=np.full(n, 100.0),
        informed_t=np.full(n, np.nan),
        wom_t=np.full(n, np.nan),
        evac_order_t=np.full(n, np.nan),
        evac_start_t=np.full(n, np.nan),
        evac_done_t=np.full(n, np.nan),
    )
    hubs = np.flatnonzero(role == int(Role.HUB))
    hub = int(hubs[-1]) if hubs.size else 0
    rng = make_streams(seed)
    keys = KeyRing.generate(rng.crypto)
    cert = make_certificate(keys.root, "PCZK", public_bytes(keys.issuer), SCOPE, -1e6, 1e6)
    verifier = Verifier(keys.trust_store())
    events = EventLog()
    router = Router(params, agents, verifier, events, rng.crypto, hub)
    radio = ContactEngine(params, agents, router, rng.radio, events, hub)
    return World(params, agents, pos, events, keys, cert, verifier, router, radio, hub)
