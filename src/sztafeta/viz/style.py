"""Wspólny styl wykresów i animacji: stonowany, „urzędowy”, czytelny z projektora.

Kolory stanów na mapie sprawdzone walidatorem palet pod kątem daltonizmu (wszystkie pary:
niebieski / żółty / morski / czerwony, ΔE ≥ 9 dla deuteranopii i protanopii). Stan jest zawsze
kodowany także kształtem znacznika, nigdy samym kolorem.
"""

from __future__ import annotations

from dataclasses import dataclass

import matplotlib as mpl

SURFACE = "#fcfcfb"
PANEL = "#f4f3ef"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
STREET = "#d2d1c9"
NO_APP = "#b3b2a8"
WATER = "#9ec5f4"

BLUE = "#2a78d6"
YELLOW = "#eda100"
AQUA = "#1baf7a"
RED = "#d03b3b"
VIOLET = "#4a3aa7"
ORANGE = "#eb6834"
HAZARD_FILL = "#f6dcd9"
HAZARD_EDGE = "#d03b3b"


@dataclass(frozen=True, slots=True)
class Marker:
    """Wygląd znacznika: kształt i kolor niosą tę samą informację."""

    marker: str
    size: float
    face: str
    edge: str
    lw: float


# indeks = AgentState: NO_APP, UNINFORMED, INFORMED, EVACUATING, SAFE, NEED_HELP
STATE_MARKERS: tuple[Marker, ...] = (
    Marker(".", 22.0, NO_APP, "none", 0.0),
    Marker("o", 16.0, SURFACE, MUTED, 1.0),
    Marker("o", 20.0, BLUE, "none", 0.0),
    Marker("^", 34.0, YELLOW, INK, 0.5),
    Marker("s", 22.0, AQUA, "none", 0.0),
    Marker("P", 90.0, RED, SURFACE, 0.8),
)

COURIER = Marker("D", 150.0, VIOLET, SURFACE, 1.6)
TROLL = Marker("X", 190.0, INK, SURFACE, 1.4)
HUB = Marker("*", 620.0, INK, SURFACE, 1.6)
EVAC = Marker("p", 420.0, SURFACE, AQUA, 3.0)


def apply_style() -> None:
    """Ustawia domyślne parametry matplotlib dla całego pakietu."""
    mpl.rcParams.update(
        {
            "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
            "font.size": 13,
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": AXIS,
            "axes.labelcolor": INK2,
            "axes.titlecolor": INK,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "grid.linestyle": "-",
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelcolor": INK2,
            "ytick.labelcolor": INK2,
            "text.color": INK,
            "legend.frameon": False,
            "lines.linewidth": 2.0,
            "lines.solid_capstyle": "round",
        }
    )
