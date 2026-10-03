from __future__ import annotations

import dataclasses

from sztafeta.engine.crypto import (
    KeyRing,
    Verifier,
    common_prefix,
    make_certificate,
    public_bytes,
    sign_ack,
    sign_alert,
    sign_report,
)
from sztafeta.engine.model import (
    Action,
    Alert,
    Certificate,
    Hazard,
    HelpCategory,
    MsgType,
    ReportKind,
    Verdict,
)
from sztafeta.engine.rng import make_streams

SCOPE = "u2u"


def _keys(seed: int = 1) -> KeyRing:
    return KeyRing.generate(make_streams(seed).crypto)


def _cert(
    keys: KeyRing, scope: str = SCOPE, not_before: float = -100.0, not_after: float = 1e6
) -> Certificate:
    return make_certificate(keys.root, "PCZK", public_bytes(keys.issuer), scope, not_before, not_after)


def _alert(keys: KeyRing, cert: Certificate, seq: int = 1, area: tuple[str, ...] = ("u2uabc",)) -> Alert:
    return sign_alert(
        keys.issuer,
        cert,
        incident="INC",
        seq=seq,
        msg_type=MsgType.ALERT,
        hazard=Hazard.FLOOD,
        action=Action.EVACUATE,
        area=area,
        place="EVAC-1",
        issued_at=10.0,
        expires_at=1000.0,
    )


def test_valid_alert_is_verified() -> None:
    keys = _keys()
    verifier = Verifier(keys.trust_store())
    assert verifier.verify(_alert(keys, _cert(keys))) == Verdict.VERIFIED


def test_tampered_alert_is_rejected() -> None:
    keys = _keys()
    verifier = Verifier(keys.trust_store())
    alert = _alert(keys, _cert(keys))
    tampered = dataclasses.replace(alert, action=Action.ALL_CLEAR)
    assert verifier.verify(tampered) == Verdict.BAD_SIGNATURE


def test_alert_signed_with_wrong_key_is_rejected() -> None:
    keys = _keys()
    verifier = Verifier(keys.trust_store())
    cert = _cert(keys)  # prawdziwy certyfikat PCZK, ale podpis kluczem trolla
    fake = sign_alert(
        keys.troll,
        cert,
        incident="INC",
        seq=5,
        msg_type=MsgType.CANCEL,
        hazard=Hazard.FLOOD,
        action=Action.ALL_CLEAR,
        area=("u2uabc",),
        place="EVAC-1",
        issued_at=10.0,
        expires_at=1000.0,
    )
    assert verifier.verify(fake) == Verdict.BAD_SIGNATURE


def test_certificate_outside_trust_chain_is_rejected() -> None:
    keys = _keys()
    verifier = Verifier(keys.trust_store())
    own_cert = make_certificate(keys.troll_root, "PCZK", public_bytes(keys.troll), SCOPE, -100.0, 1e6)
    fake = sign_alert(
        keys.troll,
        own_cert,
        incident="INC",
        seq=5,
        msg_type=MsgType.ALERT,
        hazard=Hazard.FLOOD,
        action=Action.EVACUATE,
        area=("u2uabc",),
        place="EVAC-1",
        issued_at=10.0,
        expires_at=1000.0,
    )
    assert verifier.verify(fake) == Verdict.UNTRUSTED_ISSUER


def test_certificate_not_valid_at_issue_time_is_rejected() -> None:
    keys = _keys()
    verifier = Verifier(keys.trust_store())
    expired = _cert(keys, not_before=-100.0, not_after=5.0)  # alert wydany w t=10
    assert verifier.verify(_alert(keys, expired)) == Verdict.CERT_EXPIRED


def test_alert_outside_issuer_scope_is_rejected() -> None:
    keys = _keys()
    verifier = Verifier(keys.trust_store())
    assert verifier.verify(_alert(keys, _cert(keys), area=("u3qabc",))) == Verdict.OUT_OF_SCOPE


def test_check_alert_rejects_replay_and_expired() -> None:
    keys = _keys()
    verifier = Verifier(keys.trust_store())
    alert = _alert(keys, _cert(keys), seq=2)
    assert verifier.check_alert(alert, now=20.0, known_seq=1) == Verdict.VERIFIED
    assert verifier.check_alert(alert, now=20.0, known_seq=2) == Verdict.STALE_SEQ
    assert verifier.check_alert(alert, now=20.0, known_seq=7) == Verdict.STALE_SEQ
    assert verifier.check_alert(alert, now=1000.0, known_seq=0) == Verdict.EXPIRED


def test_verification_is_cached_by_content() -> None:
    keys = _keys()
    verifier = Verifier(keys.trust_store())
    alert = _alert(keys, _cert(keys))
    verifier.verify(alert)
    checks = verifier.signature_checks
    for _ in range(5):
        assert verifier.verify(alert) == Verdict.VERIFIED
    assert verifier.signature_checks == checks
    assert verifier.cache_hits == 5
    # zmieniona treść z tym samym identyfikatorem nie korzysta z cache prawdziwego pakietu
    tampered = dataclasses.replace(alert, seq=9)
    assert tampered.pid == alert.pid
    assert verifier.verify(tampered) == Verdict.BAD_SIGNATURE


def test_keys_and_packet_ids_are_deterministic() -> None:
    a = _alert(_keys(3), _cert(_keys(3)))
    b = _alert(_keys(3), _cert(_keys(3)))
    c = _alert(_keys(4), _cert(_keys(4)))
    assert a.pid == b.pid and a.signature == b.signature
    assert a.pid != c.pid


def test_ack_is_signed_by_issuer() -> None:
    keys = _keys()
    verifier = Verifier(keys.trust_store())
    ack = sign_ack(keys.issuer, _cert(keys), (("00112233aabbccdd", 1),), 10.0, 500.0)
    assert verifier.verify(ack) == Verdict.VERIFIED
    forged = sign_ack(keys.troll, _cert(keys), (("00112233aabbccdd", 1),), 10.0, 500.0)
    assert verifier.verify(forged) == Verdict.BAD_SIGNATURE


def test_report_can_only_be_updated_by_its_author() -> None:
    keys = _keys()
    verifier = Verifier(keys.trust_store())
    report = sign_report(
        keys.troll_root,  # dowolny jednorazowy klucz urządzenia
        version=1,
        kind=ReportKind.NEED_HELP,
        category=HelpCategory.MEDICAL,
        persons=2,
        urgency=3,
        geohash="u2uabcd",
        created_at=5.0,
        expires_at=900.0,
        sensitive_len=48,
    )
    assert verifier.verify(report) == Verdict.VERIFIED
    assert report.sensitive_encrypted
    # ktoś obcy próbuje „nadpisać” zgłoszenie wyższą wersją, zachowując cudzy report_id
    hijack = sign_report(
        keys.troll,
        version=2,
        kind=ReportKind.SAFE,
        category=HelpCategory.NONE,
        persons=2,
        urgency=1,
        geohash="u2uabcd",
        created_at=6.0,
        expires_at=900.0,
    )
    forged = dataclasses.replace(hijack, report_id=report.report_id)
    assert verifier.verify(forged) == Verdict.BAD_SIGNATURE


def test_common_prefix_of_geohashes() -> None:
    assert common_prefix(("u2uabc", "u2uabd", "u2uzzz"), 4) == "u2u"
    assert common_prefix(("u2uabc",), 4) == "u2ua"
    assert common_prefix(("u2uabc", "v000"), 4) == ""
