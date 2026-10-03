"""Odczyt wyników uruchomienia z `results/<run_id>/` (dla wizualizacji i narzędzi)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from numpy.typing import NDArray

from sztafeta.io import writer as w


@dataclass(slots=True)
class RunData:
    """Wszystko, co zapisało jedno uruchomienie."""

    path: Path
    params: dict[str, Any]
    static: dict[str, Any]
    summary: dict[str, Any]
    pczk: dict[str, Any]
    metrics: pd.DataFrame
    events: list[dict[str, Any]]
    t: NDArray[np.float64]
    x: NDArray[np.float32]
    y: NDArray[np.float32]
    state: NDArray[np.uint8]
    battery: NDArray[np.uint8]
    flags: NDArray[np.uint8]
    links: NDArray[np.int32]
    links_ptr: NDArray[np.int64]

    def links_at(self, frame: int) -> NDArray[np.int32]:
        """Aktywne połączenia w klatce: wiersze [a, b, faza]."""
        return self.links[self.links_ptr[frame] : self.links_ptr[frame + 1]]


def load_events(run_dir: Path, types: set[str] | None = None) -> list[dict[str, Any]]:
    """Wczytuje `events.jsonl`; `types` ogranicza do wybranych rodzajów zdarzeń."""
    out: list[dict[str, Any]] = []
    with (run_dir / w.EVENTS_FILE).open(encoding="utf-8") as fh:
        for line in fh:
            if types is not None and not any(f'"type": "{name}"' in line for name in types):
                continue
            out.append(json.loads(line))
    return out


def load_light(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame]:
    """Parametry, podsumowanie i metryki – bez snapshotów i zdarzeń (do wykresów)."""
    if not (run_dir / w.SUMMARY_FILE).exists():
        raise FileNotFoundError(f"W katalogu {run_dir} nie ma wyników uruchomienia ({w.SUMMARY_FILE})")
    params = yaml.safe_load((run_dir / w.PARAMS_FILE).read_text(encoding="utf-8"))
    summary = json.loads((run_dir / w.SUMMARY_FILE).read_text(encoding="utf-8"))
    return params, summary, pd.read_csv(run_dir / w.METRICS_FILE)


def load_run(run_dir: Path, event_types: set[str] | None = None) -> RunData:
    if not (run_dir / w.SNAPSHOTS_FILE).exists():
        raise FileNotFoundError(f"W katalogu {run_dir} nie ma wyników uruchomienia ({w.SNAPSHOTS_FILE})")
    with np.load(run_dir / w.SNAPSHOTS_FILE) as z:
        arrays = {name: np.array(z[name]) for name in z.files}
    return RunData(
        path=run_dir,
        params=yaml.safe_load((run_dir / w.PARAMS_FILE).read_text(encoding="utf-8")),
        static=json.loads((run_dir / w.STATIC_FILE).read_text(encoding="utf-8")),
        summary=json.loads((run_dir / w.SUMMARY_FILE).read_text(encoding="utf-8")),
        pczk=json.loads((run_dir / w.PCZK_FILE).read_text(encoding="utf-8")),
        metrics=pd.read_csv(run_dir / w.METRICS_FILE),
        events=load_events(run_dir, event_types),
        t=arrays["t"],
        x=arrays["x"],
        y=arrays["y"],
        state=arrays["state"],
        battery=arrays["battery"],
        flags=arrays["flags"],
        links=arrays["links"],
        links_ptr=arrays["links_ptr"],
    )
