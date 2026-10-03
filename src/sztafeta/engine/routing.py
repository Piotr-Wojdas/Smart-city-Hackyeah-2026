"""Store-and-forward: rejestr pakietów, bufory urządzeń, routing epidemiczny i Spray-and-Wait.

Stan buforów to macierze `urządzenie x pakiet`. Obok nich utrzymywane są upakowane bitowo kopie
(`_kb`, `_ob`, `_rb`), dzięki którym pytanie „czy ta para ma sobie coś do przekazania” dla setek par
kandydatów naraz jest kilkoma operacjami numpy, bez pętli Pythona.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from numpy.typing import NDArray

from sztafeta.engine.crypto import Verifier, key_from_rng, sign_report
from sztafeta.engine.events import EventLog, EventType
from sztafeta.engine.model import (
    Ack,
    AgentArrays,
    Alert,
    BoolArr,
    HelpCategory,
    IntArr,
    Packet,
    PacketKind,
    Params,
    Priority,
    Report,
    ReportKind,
    Role,
    Verdict,
)

_ONE = np.uint64(1)


@dataclass(slots=True)
class ReportTrack:
    """Los jednego zgłoszenia (wszystkich jego wersji) – podstawa metryk i widoku telefonu."""

    report_id: str
    reporter: int
    kind: ReportKind
    category: HelpCategory
    urgency: int
    persons: int
    created_t: float
    latest_version: int = 1
    packets: list[int] = field(default_factory=list)  # indeks pakietu dla kolejnych wersji
    picked_up_t: float = float("nan")
    delivered_t: float = float("nan")
    delivered_version: int = 0
    acked_t: float = float("nan")
    acked_version: int = 0


@dataclass(slots=True)
class Delivery:
    """Zgłoszenie oddane w hubie w bieżącym kroku."""

    packet: int
    carrier: int
    first: bool


class Router:
    """Rejestr pakietów i bufory wszystkich urządzeń."""

    def __init__(
        self,
        params: Params,
        agents: AgentArrays,
        verifier: Verifier,
        events: EventLog,
        rng_crypto: np.random.Generator,
        hub_id: int,
    ) -> None:
        self._p = params.routing
        self._agents = agents
        self._verifier = verifier
        self._events = events
        self._rng_crypto = rng_crypto
        self.hub_id = hub_id
        n = agents.n
        self.n_agents = n
        self.n = 0  # liczba zarejestrowanych pakietów
        self.packets: list[Packet] = []
        self.index: dict[str, int] = {}

        role = agents.role
        self.custodian: BoolArr = (role == int(Role.COURIER)) | (role == int(Role.HUB))
        self.buf_limit: IntArr = np.full(n, self._p.buffer_resident, dtype=np.int64)
        self.buf_limit[role == int(Role.COURIER)] = self._p.buffer_courier
        self.buf_limit[role == int(Role.HUB)] = self._p.buffer_hub
        self.count: IntArr = np.zeros(n, dtype=np.int64)

        self._alloc(512)

        # alerty: najnowszy przyjęty numer sekwencyjny na urządzenie i incydent
        self.incidents: list[str] = []
        self.alert_seq: NDArray[np.int32] = np.zeros((n, 0), dtype=np.int32)
        self._incident_packets: list[list[int]] = []

        # zgłoszenia
        self.tracks: list[ReportTrack] = []
        self.track_of_agent: dict[int, int] = {}
        self._track_by_id: dict[str, int] = {}
        self._device_keys: dict[int, Ed25519PrivateKey] = {}
        self._own_times: dict[int, list[float]] = {}
        self._ack_tracks: dict[int, list[tuple[int, int]]] = {}  # pakiet Ack -> [(zgłoszenie, wersja)]

        # fałszywe alerty
        self.fake_seen: BoolArr = np.zeros(n, dtype=np.bool_)
        # urządzenie -> [(pakiet, czas odbioru, werdykt)] dla każdego alertu, który do niego dotarł
        self.alert_log: dict[int, list[tuple[int, float, int]]] = {}
        self.fake_accepted: BoolArr = np.zeros(n, dtype=np.bool_)  # musi pozostać puste

        # wyniki bieżącego kroku, odbierane przez Simulation
        self.new_alerts: list[tuple[int, int, int]] = []  # (odbiorca, pakiet, nadawca albo -1)
        self.deliveries: list[Delivery] = []

        # liczniki
        self.n_transfers = 0
        self.bytes_total = 0
        self.n_evicted = 0
        self.n_verifications = 0
        self.transfers_by_kind: list[int] = [0, 0, 0]

    # ------------------------------------------------------------------ pamięć

    def _alloc(self, cap: int) -> None:
        n = self.n_agents
        self.cap = cap
        words = (cap + 63) // 64
        self.have: BoolArr = np.zeros((n, cap), dtype=np.bool_)
        self.known: BoolArr = np.zeros((n, cap), dtype=np.bool_)
        self.copies: NDArray[np.int16] = np.zeros((n, cap), dtype=np.int16)
        self.hops: NDArray[np.uint8] = np.zeros((n, cap), dtype=np.uint8)
        self._kb: NDArray[np.uint64] = np.zeros((n, words), dtype=np.uint64)  # zna identyfikator
        self._ob: NDArray[np.uint64] = np.zeros((n, words), dtype=np.uint64)  # oferuje każdemu
        self._rb: NDArray[np.uint64] = np.zeros((n, words), dtype=np.uint64)  # zgłoszenia dla kuriera/huba
        self.kind: NDArray[np.uint8] = np.zeros(cap, dtype=np.uint8)
        self.prio: NDArray[np.uint8] = np.zeros(cap, dtype=np.uint8)
        self.size: IntArr = np.zeros(cap, dtype=np.int64)
        self.expires: NDArray[np.float64] = np.zeros(cap, dtype=np.float64)
        self.created: NDArray[np.float64] = np.zeros(cap, dtype=np.float64)
        self.origin: IntArr = np.full(cap, -1, dtype=np.int64)
        self.verdict: NDArray[np.uint8] = np.zeros(cap, dtype=np.uint8)
        self.ttl: NDArray[np.int16] = np.zeros(cap, dtype=np.int16)
        self.seq: NDArray[np.int32] = np.zeros(cap, dtype=np.int32)  # numer sekwencyjny alertu
        self.live: BoolArr = np.zeros(cap, dtype=np.bool_)
        self.forged: BoolArr = np.zeros(cap, dtype=np.bool_)
        self.track: IntArr = np.full(cap, -1, dtype=np.int64)  # dla zgłoszeń: indeks w `tracks`
        self._epi: BoolArr = np.zeros(cap, dtype=np.bool_)  # zweryfikowany alert albo Ack
        self._rep: BoolArr = np.zeros(cap, dtype=np.bool_)
        self._unv: BoolArr = np.zeros(cap, dtype=np.bool_)  # treść niezweryfikowana
        idx = np.arange(cap, dtype=np.int64)
        self._w: IntArr = idx >> 6
        self._b: NDArray[np.uint64] = _ONE << (idx & 63).astype(np.uint64)

    def _grow(self) -> None:
        old = {
            name: getattr(self, name)
            for name in (
                "have",
                "known",
                "copies",
                "hops",
                "_kb",
                "_ob",
                "_rb",
                "kind",
                "prio",
                "size",
                "expires",
                "created",
                "origin",
                "verdict",
                "ttl",
                "seq",
                "live",
                "forged",
                "track",
                "_epi",
                "_rep",
                "_unv",
            )
        }
        self._alloc(self.cap * 2)
        for name, arr in old.items():
            new = getattr(self, name)
            if arr.ndim == 2:
                new[:, : arr.shape[1]] = arr
            else:
                new[: arr.shape[0]] = arr

    # ------------------------------------------------------------------ rejestr pakietów

    def register(self, packet: Packet, origin: int, forged: bool = False) -> int:
        """Dodaje pakiet do rejestru symulacji i zwraca jego indeks. Weryfikacja liczona jest raz."""
        if packet.pid in self.index:
            return self.index[packet.pid]
        if self.n >= self.cap:
            self._grow()
        p = self.n
        self.n += 1
        self.packets.append(packet)
        self.index[packet.pid] = p
        verdict = self._verifier.verify(packet)
        self.verdict[p] = int(verdict)
        self.size[p] = packet.size
        self.expires[p] = packet.expires_at
        self.origin[p] = origin
        self.live[p] = True
        self.forged[p] = forged
        verified = verdict == Verdict.VERIFIED
        if isinstance(packet, Alert):
            self.kind[p] = int(PacketKind.ALERT)
            self.created[p] = packet.issued_at
            self.ttl[p] = packet.ttl_hops
            self.seq[p] = packet.seq
            self.prio[p] = int(Priority.ALERT if verified else Priority.UNVERIFIED)
            self._epi[p] = verified
            self._unv[p] = not verified
            if verified:
                self.expires[p] = min(packet.expires_at, packet.cert.not_after)
        elif isinstance(packet, Ack):
            self.kind[p] = int(PacketKind.ACK)
            self.created[p] = packet.issued_at
            self.ttl[p] = packet.ttl_hops
            self.prio[p] = int(Priority.ACK if verified else Priority.UNVERIFIED)
            self._epi[p] = verified
            self._unv[p] = not verified
            self._ack_tracks[p] = [
                (self._track_by_id[rid], ver) for rid, ver in packet.reports if rid in self._track_by_id
            ]
        else:
            self.kind[p] = int(PacketKind.REPORT)
            self.created[p] = packet.created_at
            self.ttl[p] = 255
            need = packet.kind == ReportKind.NEED_HELP
            self.prio[p] = (
                int(Priority.NEED_HELP if need else Priority.SAFE) if verified else int(Priority.UNVERIFIED)
            )
            self._rep[p] = verified
            self._unv[p] = not verified
            self.track[p] = self._track_by_id.get(packet.report_id, -1)
        return p

    def _incident_index(self, incident: str) -> int:
        if incident not in self.incidents:
            self.incidents.append(incident)
            self._incident_packets.append([])
            self.alert_seq = np.hstack([self.alert_seq, np.zeros((self.n_agents, 1), dtype=np.int32)])
        return self.incidents.index(incident)

    # ------------------------------------------------------------------ elementarne zmiany bufora

    def _know(self, j: int, p: int) -> None:
        if not self.known[j, p]:
            self.known[j, p] = True
            self._kb[j, self._w[p]] |= self._b[p]

    def _refresh_offer(self, j: int, p: int) -> None:
        """Przelicza, czy urządzenie `j` oferuje pakiet `p` zwykłym urządzeniom i kurierom."""
        w = self._w[p]
        b = self._b[p]
        offer = False
        custody = False
        if self.have[j, p] and self.live[p]:
            if self._epi[p]:
                offer = bool(self.hops[j, p] < self.ttl[p])
            elif self._rep[p]:
                offer = bool(self.copies[j, p] > 1)
                custody = True
            elif self._unv[p]:
                offer = bool(self.hops[j, p] <= self._p.unverified_forward_hops)
        if offer:
            self._ob[j, w] |= b
        else:
            self._ob[j, w] &= ~b
        if custody:
            self._rb[j, w] |= b
        else:
            self._rb[j, w] &= ~b

    def _hold(self, j: int, p: int, hop: int, copies: int, t: float) -> None:
        if not self.have[j, p]:
            self.have[j, p] = True
            self.count[j] += 1
        self.hops[j, p] = min(hop, 255)
        self.copies[j, p] = copies
        self._know(j, p)
        self._refresh_offer(j, p)
        if self.count[j] > self.buf_limit[j]:
            self._enforce_buffer(j, t)

    def _drop(self, j: int, p: int) -> None:
        if self.have[j, p]:
            self.have[j, p] = False
            self.count[j] -= 1
            self.copies[j, p] = 0
            self._refresh_offer(j, p)

    def _enforce_buffer(self, j: int, t: float) -> None:
        """Polityka usuwania: najpierw wygasłe, potem najniższy priorytet, potem najstarsze."""
        while self.count[j] > self.buf_limit[j]:
            held = np.flatnonzero(self.have[j, : self.n])
            own = (self.origin[held] == j) & self._rep[held]
            cand = held[~own]
            if cand.size == 0:
                return
            expired = self.expires[cand] <= t
            if expired.any():
                victim = int(cand[expired][0])
            else:
                order = np.lexsort((self.created[cand], -self.prio[cand].astype(np.int64)))
                victim = int(cand[order[0]])
            self._drop(j, victim)
            self.n_evicted += 1
            self._events.emit(t, EventType.PACKET_EVICTED, agent=j, packet=self.packets[victim].pid)

    # ------------------------------------------------------------------ nadawanie lokalne

    def inject(self, agent: int, p: int, t: float, copies: int = 0) -> None:
        """Urządzenie `agent` samo wytworzyło pakiet `p` (hub: alert i Ack, troll: fałszywka)."""
        self._hold(agent, p, 0, copies, t)

    def issue_alert(self, alert: Alert, agent: int, t: float, forged: bool = False) -> int:
        """Rejestruje alert i wkłada go do bufora urządzenia nadającego."""
        p = self.register(alert, origin=agent, forged=forged)
        if self.verdict[p] == Verdict.VERIFIED:
            inc = self._incident_index(alert.incident)
            self._incident_packets[inc].append(p)
            self._accept_alert(agent, p, alert, inc, 0, t, -1)
        else:
            self._hold(agent, p, 0, 0, t)
        return p

    def issue_ack(self, ack: Ack, agent: int, t: float) -> int:
        p = self.register(ack, origin=agent)
        self._accept_ack(agent, p, 0, t)
        return p

    def can_report(self, agent: int, t: float) -> bool:
        """Limit nadawania własnych zgłoszeń na godzinę."""
        times = self._own_times.get(agent)
        if not times:
            return True
        recent = [x for x in times if x > t - 3600.0]
        self._own_times[agent] = recent
        return len(recent) < self._p.max_own_reports_per_hour

    def create_report(
        self,
        agent: int,
        kind: ReportKind,
        category: HelpCategory,
        urgency: int,
        geohash: str,
        t: float,
        sensitive_len: int = 0,
    ) -> int | None:
        """Mieszkaniec tworzy zgłoszenie albo jego nową wersję. Zwraca indeks pakietu lub None (limit)."""
        if not self.can_report(agent, t):
            return None
        key = self._device_keys.get(agent)
        if key is None:
            key = key_from_rng(self._rng_crypto)
            self._device_keys[agent] = key
        ti = self.track_of_agent.get(agent)
        version = 1 if ti is None else self.tracks[ti].latest_version + 1
        persons = int(self._agents.report_persons[agent])
        report = sign_report(
            key,
            version=version,
            kind=kind,
            category=category,
            persons=persons,
            urgency=urgency,
            geohash=geohash,
            created_at=t,
            expires_at=t + self._p.report_lifetime_s,
            sensitive_len=sensitive_len,
        )
        if ti is None:
            ti = len(self.tracks)
            self.tracks.append(
                ReportTrack(
                    report_id=report.report_id,
                    reporter=agent,
                    kind=kind,
                    category=category,
                    urgency=urgency,
                    persons=persons,
                    created_t=t,
                )
            )
            self.track_of_agent[agent] = ti
            self._track_by_id[report.report_id] = ti
        track = self.tracks[ti]
        track.latest_version = version
        track.kind = kind
        track.category = category
        track.urgency = urgency
        p = self.register(report, origin=agent)
        self.track[p] = ti
        for old in track.packets:
            self._drop(agent, old)
            self._know(agent, old)
        track.packets.append(p)
        self._own_times.setdefault(agent, []).append(t)
        copies = self._p.spray_copies if self._p.relay_enabled else 1
        self._hold(agent, p, 0, copies, t)
        self._events.emit(
            t,
            EventType.REPORT_CREATED,
            agent=agent,
            packet=report.pid,
            kind=kind.name,
            category=category.name,
            urgency=urgency,
            persons=persons,
            version=version,
        )
        return p

    # ------------------------------------------------------------------ kontakt: co wymienić

    def need_exchange(self, ii: IntArr, jj: IntArr) -> BoolArr:
        """Dla par (ii[k], jj[k]): czy którakolwiek strona ma pakiet, którego druga nie zna."""
        return self._one_way(ii, jj) | self._one_way(jj, ii)

    def _one_way(self, src: IntArr, dst: IntArr) -> BoolArr:
        unknown = ~self._kb[dst]
        out: BoolArr = (self._ob[src] & unknown).any(axis=1)
        cust = self.custodian[dst]
        if cust.any():
            out[cust] |= (self._rb[src[cust]] & unknown[cust]).any(axis=1)
        return out

    def _offer_list(self, src: int, dst: int) -> IntArr:
        """Pakiety, które `src` wysłałby do `dst` (po wymianie summary vector), w kolejności priorytetu."""
        unknown = ~self._kb[dst]
        bits = self._ob[src] & unknown
        if self.custodian[dst]:
            bits = bits | (self._rb[src] & unknown)
        if not bits.any():
            return np.empty(0, dtype=np.int64)
        mask = np.unpackbits(bits.view(np.uint8), bitorder="little")[: self.n]
        return np.flatnonzero(mask)

    def plan(self, a: int, b: int) -> tuple[IntArr, BoolArr]:
        """Plan transferu dla kontaktu a-b: indeksy pakietów i kierunek (True = z b do a)."""
        ab = self._offer_list(a, b)
        ba = self._offer_list(b, a)
        pk = np.concatenate([ab, ba])
        rev = np.concatenate([np.zeros(ab.size, dtype=np.bool_), np.ones(ba.size, dtype=np.bool_)])
        if pk.size > 1:
            order = np.lexsort((self.created[pk], self.prio[pk]))
            pk = pk[order]
            rev = rev[order]
        return pk, rev

    def can_send(self, src: int, dst: int, p: int, t: float) -> bool:
        """Czy `src` może w chwili `t` wysłać pakiet `p` do `dst` (także: czy pakiet nie wygasł)."""
        if not self.have[src, p] or self.known[dst, p] or not self.live[p] or self.expires[p] <= t:
            return False
        if self._rep[p]:
            return bool(self.copies[src, p] > 1) or bool(self.custodian[dst])
        return True

    # ------------------------------------------------------------------ odbiór

    def transfer(self, src: int, dst: int, p: int, t: float) -> None:
        """Pakiet `p` przeszedł w całości z `src` do `dst`."""
        self.n_transfers += 1
        self.bytes_total += int(self.size[p])
        kind = int(self.kind[p])
        self.transfers_by_kind[kind] += 1
        hop = int(self.hops[src, p]) + 1
        self._know(dst, p)
        self.n_verifications += 1
        packet = self.packets[p]
        if self.verdict[p] != Verdict.VERIFIED:
            self._reject_unverified(src, dst, p, hop, t)
        elif isinstance(packet, Alert):
            self._receive_alert(src, dst, p, packet, hop, t)
        elif isinstance(packet, Ack):
            self._accept_ack(dst, p, hop, t)
        else:
            self._receive_report(src, dst, p, packet, hop, t)

    def _reject_unverified(self, src: int, dst: int, p: int, hop: int, t: float) -> None:
        if self.kind[p] == PacketKind.ALERT:
            self.fake_seen[dst] = True
            self.alert_log.setdefault(dst, []).append((p, t, int(self.verdict[p])))
        self._events.emit(
            t,
            EventType.ALERT_REJECTED,
            agent=dst,
            peer=src,
            packet=self.packets[p].pid,
            reason=Verdict(int(self.verdict[p])).name.lower(),
        )
        if hop <= self._p.unverified_forward_hops:
            # wariant do analizy wrażliwości: treść niezweryfikowana niesiona dalej z najniższym priorytetem
            self._hold(dst, p, hop, 0, t)

    def _receive_alert(self, src: int, dst: int, p: int, alert: Alert, hop: int, t: float) -> None:
        inc = self._incident_index(alert.incident)
        verdict = self._verifier.check_alert(alert, t, int(self.alert_seq[dst, inc]))
        if verdict != Verdict.VERIFIED:
            self.alert_log.setdefault(dst, []).append((p, t, int(verdict)))
            self._events.emit(
                t,
                EventType.ALERT_REJECTED,
                agent=dst,
                peer=src,
                packet=alert.pid,
                reason=verdict.name.lower(),
            )
            return
        self._accept_alert(dst, p, alert, inc, hop, t, src)

    def _accept_alert(self, j: int, p: int, alert: Alert, inc: int, hop: int, t: float, sender: int) -> None:
        if self.forged[p]:
            self.fake_accepted[j] = True  # nie powinno się zdarzyć – strażnik w metrykach
        self.alert_seq[j, inc] = alert.seq
        self.alert_log.setdefault(j, []).append((p, t, int(Verdict.VERIFIED)))
        for old in self._incident_packets[inc]:
            if old != p and self.seq[old] < alert.seq:
                self._drop(j, old)
                self._know(j, old)
        self._hold(j, p, hop, 0, t)
        self.new_alerts.append((j, p, sender))

    def _accept_ack(self, j: int, p: int, hop: int, t: float) -> None:
        self._hold(j, p, hop, 0, t)
        for ti, version in self._ack_tracks.get(p, ()):
            track = self.tracks[ti]
            # Ack działa jak antypakiet: kopie potwierdzonych wersji nie są już potrzebne
            for rp in track.packets[:version]:
                self._drop(j, rp)
                self._know(j, rp)
            if track.reporter == j and version > track.acked_version:
                if np.isnan(track.acked_t):
                    track.acked_t = t
                track.acked_version = version
                self._events.emit(
                    t,
                    EventType.ACK_RECEIVED,
                    agent=j,
                    packet=self.packets[p].pid,
                    report=track.report_id,
                    version=version,
                )

    def _receive_report(self, src: int, dst: int, p: int, report: Report, hop: int, t: float) -> None:
        ti = int(self.track[p])
        track = self.tracks[ti]
        for rp in track.packets[: report.version - 1]:
            self._drop(dst, rp)
            self._know(dst, rp)
        if dst == self.hub_id:
            first = np.isnan(track.delivered_t)
            newer = report.version > track.delivered_version
            if first:
                track.delivered_t = t
            if newer:
                track.delivered_version = report.version
                self.deliveries.append(Delivery(packet=p, carrier=src, first=bool(first)))
            return
        if self.custodian[dst]:
            copies = 1
            if np.isnan(track.picked_up_t):
                track.picked_up_t = t
                self._events.emit(t, EventType.REPORT_PICKED_UP, agent=dst, peer=src, packet=report.pid)
        else:
            give = int(self.copies[src, p]) // 2
            self.copies[src, p] -= give
            self._refresh_offer(src, p)
            copies = give
        self._hold(dst, p, hop, copies, t)

    # ------------------------------------------------------------------ porządki

    def sweep(self, t: float) -> None:
        """Usuwa z buforów pakiety po `expires_at`."""
        expired = np.flatnonzero(self.live[: self.n] & (self.expires[: self.n] <= t))
        for p in expired.tolist():
            self.live[p] = False
            for j in np.flatnonzero(self.have[:, p]).tolist():
                self._drop(j, p)

    # ------------------------------------------------------------------ odczyty dla metryk i widoków

    def holders(self, p: int) -> int:
        return int(self.have[:, p].sum())

    def buffer_of(self, agent: int) -> list[int]:
        return [int(p) for p in np.flatnonzero(self.have[agent, : self.n])]
