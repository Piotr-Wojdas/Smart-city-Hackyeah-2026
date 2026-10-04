# Źródła, biblioteki i użycie AI (wymóg regulaminu HackYeah)

## Biblioteki
| Biblioteka | Licencja | Do czego |
|---|---|---|
| numpy | BSD-3-Clause | stan agentów jako tablice, losowość (`Generator`) |
| scipy | BSD-3-Clause | `cKDTree` (kontakty), `sparse.csgraph` (najkrótsze ścieżki) |
| cryptography | Apache-2.0 / BSD-3-Clause | podpisy Ed25519 |
| pyyaml | MIT | presety scenariuszy, zapis parametrów |
| typer | MIT | interfejs wiersza poleceń |
| pandas | BSD-3-Clause | metryki, agregacja przeglądu parametrów |
| matplotlib | licencja Matplotlib (zgodna z PSF/BSD) | wykresy i animacja mapy |
| pillow | MIT-CMU (HPND) | eksport GIF |
| imageio-ffmpeg | BSD-2-Clause (dołączony program ffmpeg: GPL/LGPL, używany jako zewnętrzne narzędzie) | eksport MP4 bez systemowego ffmpeg |
| osmnx | MIT | pobranie sieci ulic i budynków z OpenStreetMap (tylko `sztafeta fetch-osm`) |
| networkx, geopandas, shapely, pyproj | BSD-3-Clause / BSD-3-Clause / BSD-3-Clause / MIT | zależności osmnx: graf, geometrie, rzutowanie do EPSG:2180 |
| pytest, ruff, mypy, types-PyYAML | MIT / MIT / MIT / Apache-2.0 | testy, lint, kontrola typów (tylko deweloperskie) |
| Lucide (zestaw ikon) | ISC | kontury ikon prototypu aplikacji, wpisane w `prototyp/icons.js` |
| Inter (czcionka) | SIL Open Font License 1.1 | czcionka prototypu aplikacji, pobierana z Google Fonts |

## Dane
| Zbiór | Licencja | Do czego |
|---|---|---|
| OpenStreetMap | ODbL | graf ulic i budynków |

## Literatura
| Pozycja | Do czego |
|---|---|
| A. Vahdat, D. Becker, „Epidemic Routing for Partially-Connected Ad Hoc Networks”, 2000 | routing alertów i potwierdzeń |
| T. Spyropoulos, K. Psounis, C. Raghavendra, „Spray and Wait”, WDTN 2005 | routing zgłoszeń |
| RFC 8032 (Ed25519) | podpisy |
| OASIS Common Alerting Protocol (CAP) 1.2 | struktura alertu: kody zamiast wolnego tekstu |

## Użycie AI
Projekt był rozwijany z pomocą Claude (claude.ai: research i koncepcja; Claude Code: implementacja symulacji).
Klikalny prototyp aplikacji (`prototyp/`) został zaimplementowany z pomocą Claude Code na podstawie makiet
zespołu; w `prototyp/eksport-figma/` są opisy stylów przygotowane jako prompty dla Figma AI i Claude.
Zespół rozumie i potrafi obronić każdą część rozwiązania.

## Praca sprzed hackathonu
Brak – całość powstała w trakcie HackYeah 2026.
