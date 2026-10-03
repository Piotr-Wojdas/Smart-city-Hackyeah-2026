"""Podpisy Ed25519 i łańcuch zaufania (biblioteka `cryptography`, żadnej własnej kryptografii).

Łańcuch: klucz główny (RCB / wojewoda, przypięty w aplikacji) -> certyfikat wydawcy (PCZK) z zakresem
obszaru i okresem ważności -> podpis pakietu. Klucze są wyprowadzane ze strumienia `crypto` generatora
losowego, więc ten sam seed daje te same klucze, podpisy i identyfikatory pakietów.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from sztafeta.engine.model import (
    Ack,
    Action,
    Alert,
    Certificate,
    Hazard,
    HelpCategory,
    MsgType,
    Packet,
    Report,
    ReportKind,
    Verdict,
    ack_body,
    alert_body,
    report_body,
)


def key_from_rng(rng: np.random.Generator) -> Ed25519PrivateKey:
    """Klucz prywatny z 32 bajtów strumienia losowego (deterministycznie)."""
    return Ed25519PrivateKey.from_private_bytes(rng.bytes(32))


def public_bytes(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes_raw()


def packet_id(body: bytes, signature: bytes) -> str:
    """Identyfikator pakietu = skrót treści i podpisu (adresowanie treścią)."""
    return hashlib.sha256(body + signature).hexdigest()[:16]


def report_id_for(public_key: bytes) -> str:
    """Identyfikator zgłoszenia = skrót jednorazowego klucza publicznego zgłaszającego."""
    return hashlib.sha256(public_key).hexdigest()[:16]


def verify_signature(public_key: bytes, signature: bytes, body: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, body)
    except (InvalidSignature, ValueError):
        return False
    return True


@dataclass(frozen=True, slots=True)
class TrustStore:
    """To, co aplikacja ma „przypięte”: klucz publiczny głównego urzędu."""

    root_public: bytes


@dataclass(slots=True)
class KeyRing:
    """Klucze uczestników symulacji."""

    root: Ed25519PrivateKey  # RCB / wojewoda
    issuer: Ed25519PrivateKey  # PCZK
    troll: Ed25519PrivateKey
    troll_root: Ed25519PrivateKey  # „urząd” wymyślony przez trolla

    @staticmethod
    def generate(rng: np.random.Generator) -> KeyRing:
        return KeyRing(
            root=key_from_rng(rng),
            issuer=key_from_rng(rng),
            troll=key_from_rng(rng),
            troll_root=key_from_rng(rng),
        )

    def trust_store(self) -> TrustStore:
        return TrustStore(root_public=public_bytes(self.root))


def make_certificate(
    root: Ed25519PrivateKey,
    issuer_id: str,
    public_key: bytes,
    scope: str,
    not_before: float,
    not_after: float,
) -> Certificate:
    unsigned = Certificate(issuer_id, public_key, scope, not_before, not_after, b"")
    return Certificate(
        issuer_id, public_key, scope, not_before, not_after, root.sign(unsigned.signed_bytes())
    )


def sign_alert(
    key: Ed25519PrivateKey,
    cert: Certificate,
    *,
    incident: str,
    seq: int,
    msg_type: MsgType,
    hazard: Hazard,
    action: Action,
    area: tuple[str, ...],
    place: str,
    issued_at: float,
    expires_at: float,
    priority: int = 0,
    ttl_hops: int = 100,
) -> Alert:
    body = alert_body(
        incident, seq, msg_type, hazard, action, area, place, issued_at, expires_at, priority, ttl_hops, cert
    )
    signature = key.sign(body)
    return Alert(
        pid=packet_id(body, signature),
        incident=incident,
        seq=seq,
        msg_type=msg_type,
        hazard=hazard,
        action=action,
        area=area,
        place=place,
        issued_at=issued_at,
        expires_at=expires_at,
        priority=priority,
        ttl_hops=ttl_hops,
        cert=cert,
        signature=signature,
    )


def sign_ack(
    key: Ed25519PrivateKey,
    cert: Certificate,
    reports: tuple[tuple[str, int], ...],
    issued_at: float,
    expires_at: float,
    ttl_hops: int = 100,
) -> Ack:
    body = ack_body(reports, issued_at, expires_at, ttl_hops, cert)
    signature = key.sign(body)
    return Ack(
        pid=packet_id(body, signature),
        reports=reports,
        issued_at=issued_at,
        expires_at=expires_at,
        ttl_hops=ttl_hops,
        cert=cert,
        signature=signature,
    )


def sign_report(
    key: Ed25519PrivateKey,
    *,
    version: int,
    kind: ReportKind,
    category: HelpCategory,
    persons: int,
    urgency: int,
    geohash: str,
    created_at: float,
    expires_at: float,
    sensitive_len: int = 0,
) -> Report:
    public = public_bytes(key)
    report_id = report_id_for(public)
    body = report_body(
        report_id,
        version,
        kind,
        category,
        persons,
        urgency,
        geohash,
        created_at,
        expires_at,
        sensitive_len,
        public,
    )
    signature = key.sign(body)
    return Report(
        pid=packet_id(body, signature),
        report_id=report_id,
        version=version,
        kind=kind,
        category=category,
        persons=persons,
        urgency=urgency,
        geohash=geohash,
        created_at=created_at,
        expires_at=expires_at,
        sensitive_len=sensitive_len,
        reporter_key=public,
        signature=signature,
    )


class Verifier:
    """Weryfikacja pakietów offline, z cache po skrócie treści.

    Sprawdzenia kryptograficzne (łańcuch, zakres, podpis) nie zależą od czasu ani od urządzenia, więc
    ich wynik można zapamiętać. Wygaśnięcie i numer sekwencyjny sprawdza `check_alert` – te zależą od
    chwili i od tego, co urządzenie już widziało.
    """

    __slots__ = ("_cache", "_trust", "cache_hits", "signature_checks")

    def __init__(self, trust: TrustStore) -> None:
        self._trust = trust
        self._cache: dict[str, Verdict] = {}
        self.cache_hits = 0
        self.signature_checks = 0

    def verify(self, packet: Packet) -> Verdict:
        """Wynik sprawdzeń kryptograficznych pakietu dowolnego rodzaju."""
        body = packet.signed_bytes()
        key = packet_id(body, packet.signature)
        cached = self._cache.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        if key != packet.pid:
            # identyfikator nie zgadza się z treścią: pakiet zmieniony po podpisaniu
            verdict = Verdict.BAD_SIGNATURE
        elif isinstance(packet, Alert):
            verdict = self._verify_issued(packet.cert, packet.issued_at, packet.area, packet.signature, body)
        elif isinstance(packet, Ack):
            verdict = self._verify_issued(packet.cert, packet.issued_at, (), packet.signature, body)
        else:
            verdict = self._verify_report(packet, body)
        self._cache[key] = verdict
        return verdict

    def check_alert(self, alert: Alert, now: float, known_seq: int) -> Verdict:
        """Pełna decyzja urządzenia: kryptografia, ważność w czasie, ochrona przed powtórzeniem (replay)."""
        verdict = self.verify(alert)
        if verdict != Verdict.VERIFIED:
            return verdict
        if now > alert.cert.not_after:
            return Verdict.CERT_EXPIRED
        if now >= alert.expires_at:
            return Verdict.EXPIRED
        if alert.seq <= known_seq:
            return Verdict.STALE_SEQ
        return Verdict.VERIFIED

    def _verify_issued(
        self, cert: Certificate, issued_at: float, area: tuple[str, ...], signature: bytes, body: bytes
    ) -> Verdict:
        self.signature_checks += 1
        if not verify_signature(self._trust.root_public, cert.signature, cert.signed_bytes()):
            return Verdict.UNTRUSTED_ISSUER
        if not (cert.not_before <= issued_at <= cert.not_after):
            return Verdict.CERT_EXPIRED
        if any(not cell.startswith(cert.scope) for cell in area):
            return Verdict.OUT_OF_SCOPE
        self.signature_checks += 1
        if not verify_signature(cert.public_key, signature, body):
            return Verdict.BAD_SIGNATURE
        return Verdict.VERIFIED

    def _verify_report(self, report: Report, body: bytes) -> Verdict:
        self.signature_checks += 1
        if report_id_for(report.reporter_key) != report.report_id:
            return Verdict.BAD_SIGNATURE
        if not verify_signature(report.reporter_key, report.signature, body):
            return Verdict.BAD_SIGNATURE
        return Verdict.VERIFIED


def common_prefix(cells: tuple[str, ...], max_len: int) -> str:
    """Najdłuższy wspólny prefiks geohashy, nie dłuższy niż `max_len` (zakres certyfikatu)."""
    if not cells:
        return ""
    prefix = cells[0][:max_len]
    for cell in cells[1:]:
        while prefix and not cell.startswith(prefix):
            prefix = prefix[:-1]
    return prefix
