"""Zapis wyników jednego uruchomienia do `results/<run_id>/`."""

from __future__ import annotations

import csv
import dataclasses
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from sztafeta import __version__
from sztafeta.engine.events import Event
from sztafeta.engine.metrics import MetricsCollector
from sztafeta.engine.sim import Simulation

PARAMS_FILE = "params.yaml"
METRICS_FILE = "metrics.csv"
EVENTS_FILE = "events.jsonl"
SNAPSHOTS_FILE = "snapshots.npz"
STATIC_FILE = "static.json"
PCZK_FILE = "pczk.json"
SUMMARY_FILE = "summary.json"


def code_version() -> str:
    """Wersja pakietu z krótkim skrótem commita (jeśli katalog jest repozytorium git)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).resolve().parent,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return __version__
    return f"{__version__}+{out.stdout.strip()}"


class RunWriter:
    """Zbiera snapshoty i zdarzenia w trakcie symulacji, a na końcu zapisuje komplet plików."""

    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        self._events = (out_dir / EVENTS_FILE).open("w", encoding="utf-8", newline="\n")
        self._t: list[float] = []
        self._x: list[np.ndarray[Any, np.dtype[np.float32]]] = []
        self._y: list[np.ndarray[Any, np.dtype[np.float32]]] = []
        self._state: list[np.ndarray[Any, np.dtype[np.uint8]]] = []
        self._battery: list[np.ndarray[Any, np.dtype[np.uint8]]] = []
        self._flags: list[np.ndarray[Any, np.dtype[np.uint8]]] = []
        self._links: list[list[int]] = []
        self._links_ptr: list[int] = [0]
        self.n_events = 0

    def write_params(self, meta: dict[str, Any]) -> None:
        """`params.yaml`: pełne parametry, seed, wersja kodu, opis scenariusza."""
        text = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
        (self.out_dir / PARAMS_FILE).write_text(text, encoding="utf-8", newline="\n")

    def add_snapshot(self, sim: Simulation) -> None:
        pos = sim.mobility.pos
        self._t.append(sim.t)
        self._x.append(pos[:, 0].astype(np.float32))
        self._y.append(pos[:, 1].astype(np.float32))
        self._state.append(sim.agents.state.copy())
        self._battery.append(np.clip(np.round(sim.agents.battery), 0, 100).astype(np.uint8))
        self._flags.append(sim.flags())
        self._links.extend(sim.radio.link_list(sim.t))
        self._links_ptr.append(len(self._links))

    def write_events(self, events: list[Event]) -> None:
        for event in events:
            self._events.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        self.n_events += len(events)

    def finish(self, sim: Simulation, extra_summary: dict[str, Any]) -> dict[str, Any]:
        """Zamyka pliki i zapisuje metryki, snapshoty, opis statyczny, stan PCZK i podsumowanie."""
        self.write_events(sim.drain_events())
        self._events.close()

        with (self.out_dir / METRICS_FILE).open("w", encoding="utf-8", newline="") as fh:
            out = csv.writer(fh, lineterminator="\n")
            out.writerow(MetricsCollector.columns())
            for row in sim.metrics.rows:
                out.writerow(dataclasses.astuple(row))

        ag = sim.agents
        links = np.asarray(self._links, dtype=np.int32).reshape(-1, 3)
        np.savez_compressed(
            self.out_dir / SNAPSHOTS_FILE,
            t=np.asarray(self._t, dtype=np.float64),
            x=np.stack(self._x),
            y=np.stack(self._y),
            state=np.stack(self._state),
            battery=np.stack(self._battery),
            flags=np.stack(self._flags),
            links=links,
            links_ptr=np.asarray(self._links_ptr, dtype=np.int64),
            role=ag.role,
            has_app=ag.has_app,
            lang=ag.lang,
            in_zone=ag.in_zone,
        )
        _dump(self.out_dir / STATIC_FILE, sim.describe(), indent=None)
        _dump(self.out_dir / PCZK_FILE, sim.pczk_dashboard())
        summary = {**extra_summary, **sim.metrics.summary(sim.alert_issued_t), "events": self.n_events}
        _dump(self.out_dir / SUMMARY_FILE, summary)
        return summary


def _dump(path: Path, data: Any, indent: int | None = 2) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=indent)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")
