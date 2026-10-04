---
description: Lint, typy i testy – napraw wszystko, co nie przechodzi
---
Uruchom po kolei: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, `uv run pytest`.
Jeśli coś nie przechodzi, napraw przyczynę (nie wyciszaj reguł, nie usuwaj testów, nie dodawaj `# type: ignore` bez uzasadnienia).
Na końcu wypisz krótko: co było zepsute, co poprawiłeś, wynik każdego kroku.
