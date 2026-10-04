"""Klikalny prototyp aplikacji (prototyp/): komplet ikon, istniejące ekrany docelowe, test dymny w Node."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototyp"


def _read(name: str) -> str:
    return (PROTOTYPE / name).read_text(encoding="utf-8")


def test_every_icon_used_by_the_prototype_is_defined() -> None:
    defined = set(re.findall(r'^  "([a-z0-9-]+)":', _read("icons.js"), flags=re.MULTILINE))
    app = _read("app.js")
    # nazwy ikon: wprost w icon("..."), w liście poradników oraz jako argument funkcji budujących
    # zakładki i opcje (drugi napis w wywołaniu, w shellTab pierwszy)
    used = set(re.findall(r'icon\(\s*"([a-z0-9-]+)"', app))
    used |= set(re.findall(r'\? "([a-z0-9-]+)" : "([a-z0-9-]+)", 20, "primary"', app)[0])
    used |= set(re.findall(r'name: "([a-z0-9-]+)"', app))
    used |= set(re.findall(r'\b(?:tab|option)\("[a-z]+", "([a-z0-9-]+)"', app))
    used |= set(re.findall(r'shellTab\("([a-z0-9-]+)"', app))
    assert len(defined) >= 30 and len(used) >= 30
    assert used <= defined, f"brakujące ikony: {sorted(used - defined)}"
    assert defined <= used, f"nieużywane ikony: {sorted(defined - used)}"
    # ikony są wpisane w plik, więc prototyp nie potrzebuje sieci, żeby je pokazać
    assert "http" not in _read("icons.js").replace("https://lucide.dev", "")


def test_every_navigation_target_is_an_existing_screen() -> None:
    app = _read("app.js")
    block = app[app.index("const SCREENS = {") : app.index("};", app.index("const SCREENS = {"))]
    screens = set(re.findall(r"^  ([a-z]+): screen", block, flags=re.MULTILINE))
    assert screens == {
        "home",
        "messages",
        "chat",
        "notice",
        "report",
        "guides",
        "guide",
        "assistant",
        "shell",
        "mdowod",
    }
    targets = set(re.findall(r'data-go="([a-z]+)"', app)) | set(re.findall(r'tab\("([a-z]+)"', app)) - {
        "more"
    }
    assert targets <= screens, f"przejścia do nieistniejących ekranów: {sorted(targets - screens)}"
    assert screens - {"shell"} <= targets  # do każdego ekranu da się dojść klikając (shell to ekran startowy)
    index = _read("index.html")
    for asset in ("styles.css", "icons.js", "app.js"):
        assert asset in index and (PROTOTYPE / asset).exists()


def test_mobywatel_variant_is_marked_as_a_demo_and_uses_no_official_marks() -> None:
    app = _read("app.js")
    for label in (
        "PROPOZYCJA INTEGRACJI • DEMO",
        "DEMO — nie jest dokumentem tożsamości",
        "Wzór koncepcyjny. Nie potwierdza tożsamości.",
        "Dane fikcyjne • bez numeru PESEL",
    ):
        assert label in app, label
    assert "to nie jest oficjalna aplikacja" in _read("index.html")
    # żadnych grafik: ani logo, ani godła – same ikony konturowe z icons.js
    sources = app + _read("index.html") + _read("styles.css")
    assert "<img" not in sources and "url(" not in sources


def test_prototype_smoke_run_in_node() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("brak Node.js – test dymny prototypu pominięty")
    result = subprocess.run(
        [node, str(ROOT / "tests" / "prototype_smoke.js")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.startswith("ok: 10 ekranów")
