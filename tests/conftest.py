from __future__ import annotations

import pytest

from sztafeta.engine.model import Params, Scenario
from sztafeta.scenarios import load_preset


@pytest.fixture
def small() -> tuple[Params, Scenario]:
    """Mały scenariusz na siatce proceduralnej (bez sieci, bez danych OSM)."""
    return load_preset("test-small")
