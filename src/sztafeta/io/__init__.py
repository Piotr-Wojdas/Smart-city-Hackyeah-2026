"""Zapis i odczyt wyników uruchomienia (format: docs/FORMAT.md)."""

from sztafeta.io.reader import RunData, load_light, load_run
from sztafeta.io.writer import RunWriter

__all__ = ["RunData", "RunWriter", "load_light", "load_run"]
