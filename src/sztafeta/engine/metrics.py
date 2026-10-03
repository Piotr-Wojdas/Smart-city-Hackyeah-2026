"""Zbieranie metryk w czasie. Kolumny `MetricsRow` to kolumny `metrics.csv` (opis: docs/FORMAT.md)."""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass

import numpy as np

from sztafeta.engine.contacts import ContactEngine
from sztafeta.engine.model import AgentArrays, BoolArr, FloatArr, ReportKind, Role
from sztafeta.engine.routing import Router


@dataclass(slots=True)
class MetricsRow:
    t: float
    # zasięg zweryfikowanego alertu w aplikacji (procent)
    alert_reach_app: float  # wśród mieszkańców z aplikacją
    alert_reach_all: float  # wśród wszystkich mieszkańców (tylko aplikacja)
    alert_reach_zone_app: float  # jak wyżej, tylko mieszkańcy strefy zagrożenia
    alert_reach_zone_all: float
    # przekaz ustny – liczony osobno, nigdy nie doliczany do zasięgu aplikacji
    wom_reach_all: float
    wom_reach_zone_all: float
    # ewakuacja mieszkańców strefy (procent)
    evac_started_zone: float
    evacuated_zone: float
    # zgłoszenia
    reports_created: int
    reports_delivered: int
    need_help_created: int
    need_help_delivered: int
    delay_median_s: float
    delay_p90_s: float
    acks_received: int
    acks_received_pct: float  # odsetek dostarczonych zgłoszeń, których autor dostał potwierdzenie
    # fałszywe alerty
    fake_received_devices: int
    fake_verified_devices: int  # musi być 0
    # urządzenia i sieć
    battery_mean: float
    devices_off: int
    links_active: int
    contacts_total: int
    transfers_total: int
    bytes_total: int


def _pct(part: float, whole: float) -> float:
    return round(100.0 * part / whole, 3) if whole > 0 else 0.0


def _quantile_time(times: FloatArr, share: float, population: int) -> float | None:
    """Chwila, w której odsetek `share` populacji miał już zdarzenie (None, jeśli nie osiągnięto)."""
    done = np.sort(times[~np.isnan(times)])
    need = math.ceil(share * population)
    if population == 0 or need == 0 or done.size < need:
        return None
    return float(done[need - 1])


class MetricsCollector:
    """Próbkuje stan symulacji i liczy podsumowanie uruchomienia."""

    def __init__(self, agents: AgentArrays, router: Router, radio: ContactEngine) -> None:
        self._agents = agents
        self._router = router
        self._radio = radio
        res: BoolArr = agents.role == int(Role.RESIDENT)
        self._res = res
        self._res_app = res & agents.has_app
        self._zone = res & agents.in_zone
        self._zone_app = self._zone & agents.has_app
        self._n_res = int(res.sum())
        self._n_res_app = int(self._res_app.sum())
        self._n_zone = int(self._zone.sum())
        self._n_zone_app = int(self._zone_app.sum())
        self.rows: list[MetricsRow] = []

    @staticmethod
    def columns() -> list[str]:
        return [f.name for f in dataclasses.fields(MetricsRow)]

    def sample(self, t: float) -> MetricsRow:
        ag = self._agents
        router = self._router
        radio = self._radio
        informed = ~np.isnan(ag.informed_t)
        oral_only = ~np.isnan(ag.wom_t) & ~informed
        tracks = router.tracks
        delivered = [tr for tr in tracks if not math.isnan(tr.delivered_t)]
        delays = np.array([tr.delivered_t - tr.created_t for tr in delivered], dtype=np.float64)
        acked = sum(1 for tr in delivered if not math.isnan(tr.acked_t))
        res_app = self._res_app
        row = MetricsRow(
            t=t,
            alert_reach_app=_pct(float((informed & res_app).sum()), self._n_res_app),
            alert_reach_all=_pct(float((informed & self._res).sum()), self._n_res),
            alert_reach_zone_app=_pct(float((informed & self._zone_app).sum()), self._n_zone_app),
            alert_reach_zone_all=_pct(float((informed & self._zone).sum()), self._n_zone),
            wom_reach_all=_pct(float((oral_only & self._res).sum()), self._n_res),
            wom_reach_zone_all=_pct(float((oral_only & self._zone).sum()), self._n_zone),
            evac_started_zone=_pct(float((~np.isnan(ag.evac_start_t) & self._zone).sum()), self._n_zone),
            evacuated_zone=_pct(float((~np.isnan(ag.evac_done_t) & self._zone).sum()), self._n_zone),
            reports_created=len(tracks),
            reports_delivered=len(delivered),
            need_help_created=sum(1 for tr in tracks if tr.kind == ReportKind.NEED_HELP),
            need_help_delivered=sum(1 for tr in delivered if tr.kind == ReportKind.NEED_HELP),
            delay_median_s=round(float(np.median(delays)), 1) if delays.size else 0.0,
            delay_p90_s=round(float(np.quantile(delays, 0.9)), 1) if delays.size else 0.0,
            acks_received=acked,
            acks_received_pct=_pct(acked, len(delivered)),
            fake_received_devices=int(router.fake_seen.sum()),
            fake_verified_devices=int(router.fake_accepted.sum()),
            battery_mean=round(float(ag.battery[res_app].mean()), 2) if self._n_res_app else 0.0,
            devices_off=int((res_app & ~radio.on).sum()),
            links_active=len(radio.links),
            contacts_total=radio.n_contacts,
            transfers_total=router.n_transfers,
            bytes_total=router.bytes_total,
        )
        self.rows.append(row)
        return row

    def _row_at(self, t: float) -> MetricsRow | None:
        """Ostatnia próbka nie późniejsza niż `t` (None, gdy symulacja była krótsza)."""
        if not self.rows or self.rows[-1].t < t:
            return None
        found = self.rows[0]
        for row in self.rows:
            if row.t > t:
                break
            found = row
        return found

    def _at(self, t: float, column: str) -> float | None:
        row = self._row_at(t)
        return None if row is None else float(getattr(row, column))

    def _share_at(self, t: float) -> float | None:
        """Odsetek zgłoszeń wysłanych do chwili `t`, które do tej chwili dotarły do PCZK."""
        row = self._row_at(t)
        return None if row is None else _pct(row.reports_delivered, row.reports_created)

    def summary(self, alert_issued_t: float | None) -> dict[str, float | int | None]:
        """Kluczowe liczby uruchomienia (zawartość `summary.json`)."""
        ag = self._agents
        last = self.rows[-1] if self.rows else self.sample(0.0)
        t0 = alert_issued_t

        def since_alert(times: FloatArr, share: float, population: int) -> float | None:
            when = _quantile_time(times, share, population)
            if when is None or t0 is None:
                return None
            return round(when - t0, 1)

        app_t = ag.informed_t[self._res_app]
        zone_app_t = ag.informed_t[self._zone_app]
        evac_t = ag.evac_done_t[self._zone]
        return {
            "residents": self._n_res,
            "residents_with_app": self._n_res_app,
            "zone_residents": self._n_zone,
            "zone_residents_with_app": self._n_zone_app,
            "alert_issued_t": t0,
            "t50_app_s": since_alert(app_t, 0.5, self._n_res_app),
            "t90_app_s": since_alert(app_t, 0.9, self._n_res_app),
            "t50_zone_app_s": since_alert(zone_app_t, 0.5, self._n_zone_app),
            "t90_zone_app_s": since_alert(zone_app_t, 0.9, self._n_zone_app),
            "t50_evacuated_zone_s": since_alert(evac_t, 0.5, self._n_zone),
            "alert_reach_app": last.alert_reach_app,
            "alert_reach_app_1h": self._at(3600.0, "alert_reach_app"),
            "alert_reach_app_3h": self._at(10800.0, "alert_reach_app"),
            "alert_reach_all": last.alert_reach_all,
            "alert_reach_zone_app": last.alert_reach_zone_app,
            "alert_reach_zone_all": last.alert_reach_zone_all,
            "wom_reach_all": last.wom_reach_all,
            "wom_reach_zone_all": last.wom_reach_zone_all,
            "evac_started_zone": last.evac_started_zone,
            "evacuated_zone": last.evacuated_zone,
            "reports_created": last.reports_created,
            "reports_delivered": last.reports_delivered,
            "reports_delivered_pct": _pct(last.reports_delivered, last.reports_created),
            "reports_delivered_pct_1h": self._share_at(3600.0),
            "reports_delivered_pct_3h": self._share_at(10800.0),
            "need_help_created": last.need_help_created,
            "need_help_delivered": last.need_help_delivered,
            "need_help_delivered_pct": _pct(last.need_help_delivered, last.need_help_created),
            "delay_median_s": last.delay_median_s,
            "delay_p90_s": last.delay_p90_s,
            "acks_received": last.acks_received,
            "acks_received_pct": last.acks_received_pct,
            "fake_received_devices": last.fake_received_devices,
            "fake_verified_devices": last.fake_verified_devices,
            "battery_mean": last.battery_mean,
            "devices_off": last.devices_off,
            "contacts_total": last.contacts_total,
            "contacts_interrupted": self._radio.n_interrupted,
            "transfers_total": last.transfers_total,
            "bytes_total": last.bytes_total,
            "packets_evicted": self._router.n_evicted,
        }
