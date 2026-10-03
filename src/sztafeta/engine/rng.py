"""Jedyne źródło losowości silnika.

Każdy podsystem dostaje własny, niezależny strumień wyprowadzony z jednego seeda. Dzięki temu zmiana
w jednym podsystemie (np. wyłączenie sztafety w wariancie bazowym) nie przesuwa losowań w pozostałych:
populacja, domy i zachowania są identyczne dla tego samego seeda.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

STREAMS: tuple[str, ...] = ("population", "mobility", "radio", "behavior", "crypto")


@dataclass(slots=True)
class RngStreams:
    """Niezależne generatory dla podsystemów silnika."""

    population: np.random.Generator
    mobility: np.random.Generator
    radio: np.random.Generator
    behavior: np.random.Generator
    crypto: np.random.Generator


def make_streams(seed: int) -> RngStreams:
    """Tworzy komplet strumieni z jednego seeda (deterministycznie)."""
    children = np.random.SeedSequence(seed).spawn(len(STREAMS))
    gens = [np.random.Generator(np.random.PCG64(child)) for child in children]
    return RngStreams(*gens)


def make_generator(seed: int, purpose: str) -> np.random.Generator:
    """Pojedynczy generator do zadań poza pętlą symulacji (np. budowa proceduralnej mapy).

    `purpose` rozdziela strumienie o tym samym seedzie, żeby mapa i symulacja nie dzieliły losowań.
    """
    tag = [ord(ch) for ch in purpose]
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, *tag])))
