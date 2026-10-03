"""Wspólny styl wykresów i animacji: stonowany, „urzędowy”, czytelny z projektora.

Kolory na mapie sprawdzone walidatorem palet pod kątem daltonizmu (wszystkie pary:
niebieski / żółty / morski / czerwony, ΔE ≥ 9 dla deuteranopii i protanopii). Znaczenie jest zawsze
kodowane także kształtem znacznika, nigdy samym kolorem.
"""

from __future__ import annotations

from dataclasses import dataclass

import matplotlib as mpl

SURFACE = "#fcfcfb"
PANEL = "#f4f3ef"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#6f6e69"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
STREET = "#d2d1c9"
STREET_LIGHT = "#e3e2db"
PHONE_GRAY = "#aeada3"
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


# Animacja pokazuje tylko to, co niesie historię. Osoby bez aplikacji nie są rysowane,
# dopóki się nie ewakuują; telefon bez alertu jest celowo blady, żeby niebieskie „ma alert” było widać.
PHONE_IDLE = Marker("o", 11.0, PHONE_GRAY, "none", 0.0)
PHONE_ALERT = Marker("o", 17.0, BLUE, "none", 0.0)
EVACUEE = Marker("^", 17.0, YELLOW, "none", 0.0)
NEED_HELP = Marker("P", 52.0, RED, SURFACE, 0.7)
# telefon, który właśnie odebrał zweryfikowany alert
RING = Marker("o", 130.0, "none", BLUE, 1.5)
# „pakiet” lecący od nadawcy do odbiorcy (tylko w zbliżeniu)
PACKET = Marker("o", 70.0, SURFACE, BLUE, 2.4)

COURIER = Marker("D", 105.0, VIOLET, SURFACE, 1.3)
HUB = Marker("*", 430.0, INK, SURFACE, 1.5)
EVAC = Marker("p", 340.0, SURFACE, AQUA, 2.8)


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
