# Sztafeta – symulacja offline'owego kanału kryzysowego telefon–telefon

Projekt na HackYeah 2026 (kategoria SMART CITY). **Sztafeta** to koncepcja modułu do aplikacji
mObywatel, który w czasie kryzysu (powódź, blackout) przekazuje informacje z telefonu do telefonu bez
sieci komórkowej. To repozytorium zawiera **symulację w Pythonie**, która pokazuje i mierzy, jak taki
system zachowywałby się w mieście wielkości Stronia Śląskiego.

> **To jest model, nie pomiar.** Liczby, wykresy i animacje pochodzą z symulacji komputerowej przy
> założeniach opisanych w [docs/MODEL.md](docs/MODEL.md). Scenariusz jest inspirowany powodzią
> z września 2024 r., ale nie jest jej rekonstrukcją. Projekt nie jest oficjalnym produktem
> mObywatela i nie używa jego znaków.

Symulacja ma pokazać dwie rzeczy:

1. **Sztafeta Komunikatów** (urząd → ludzie): alert podpisany kluczem Ed25519 dociera do mieszkańców
   z telefonu do telefonu, a fałszywe alerty są odrzucane.
2. **Kurier Danych do Sztabu** (ludzie → urząd): zgłoszenia „Jestem bezpieczny” i „Potrzebuję pomocy”
   docierają do PCZK przez telefony ratowników, a podpisane potwierdzenia wracają do zgłaszających.

Pełna koncepcja: [docs/KONCEPT.md](docs/KONCEPT.md). Wyniki przeglądu parametrów:
[docs/WYNIKI.md](docs/WYNIKI.md).

## Instalacja

Wymagany Python 3.11+ i [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

Mapa Stronia Śląskiego jest w repozytorium (`data/stronie-slaskie/`), więc symulacja działa offline.
Eksport MP4 korzysta z programu ffmpeg dostarczanego przez pakiet `imageio-ffmpeg`; gdy go nie ma,
animacja zapisuje się jako GIF.

## Uruchomienie

```bash
# jedno uruchomienie scenariusza demo -> results/flood-stronie_s42/
uv run sztafeta run --preset flood-stronie --seed 42

# to samo w wariancie bazowym „bez Sztafety” -> results/flood-stronie_s42_baseline/
uv run sztafeta run --preset flood-stronie --seed 42 --baseline

# wykresy do slajdów i karta wyników (PNG 16:9); wariant bazowy jest wykrywany automatycznie
uv run sztafeta charts results/flood-stronie_s42

# animacja mapy (MP4 1920x1080, ok. 1 min): widok miasta i zbliżenie na osiedle, w którym telefony
# łączą się i przekazują sobie alert; --no-closeup pomija zbliżenie, --t-from/--t-to wycinają fragment,
# --lang en daje napisy angielskie
uv run sztafeta animate results/flood-stronie_s42

# pojedyncza klatka jako PNG: widok miasta w chwili t albo kadr zbliżenia
uv run sztafeta frame results/flood-stronie_s42 --t 5400
uv run sztafeta frame results/flood-stronie_s42 --closeup

# stan telefonu agenta w chwili t (JSON): alerty z oznaczeniem weryfikacji i tekstem w języku
# telefonu, własne zgłoszenia, bufor, bateria
uv run sztafeta inspect results/flood-stronie_s42 --agent 120 --t 3600

# przegląd parametrów (adopcja x zasięg x kurierzy x seedy) -> results/batch/ i docs/WYNIKI.md
uv run sztafeta batch

# ponowne pobranie mapy z OpenStreetMap (wymaga sieci)
uv run sztafeta fetch-osm --preset flood-stronie
```

Parametry nadpisuje się opcją `--set`, na przykład:

```bash
uv run sztafeta run --set behavior.adoption=0.5 --set radio.range_m=80 --set population.n_couriers=8
```

Lista parametrów z wartościami domyślnymi, uzasadnieniem i źródłem: [docs/MODEL.md](docs/MODEL.md).

### Co powstaje po `run`

| Plik | Zawartość |
|---|---|
| `params.yaml` | pełne parametry, seed, wersja kodu, oś czasu scenariusza |
| `metrics.csv` | metryki co 10 s czasu modelu |
| `events.jsonl` | zdarzenia: kontakt, transfer, odrzucenie, dostarczenie, ewakuacja, potwierdzenie |
| `snapshots.npz` | pozycje i stany agentów co 10 s (materiał do animacji i do odtwarzania we frontendzie) |
| `static.json` | mapa i cechy agentów |
| `pczk.json` | dashboard sztabu na koniec: liczniki i zgłoszenia według pilności |
| `summary.json` | kluczowe liczby |

Formaty są opisane w [docs/FORMAT.md](docs/FORMAT.md) – to kontrakt dla przyszłego backendu i frontendu.

## Scenariusz demo (`flood-stronie`)

Oś czasu (czas modelu, 6 h):

| Chwila | Wydarzenie |
|---|---|
| T+0 | awaria sieci komórkowej |
| T+10 min | PCZK wydaje podpisany alert „powódź – ewakuacja” |
| T+20 min | kurierzy wyruszają na patrol strefy zagrożenia, wracają do huba co ok. 30 min |
| T+30 min | troll rozsyła fałszywy alert „odwołanie ewakuacji” |
| T+3 h | nowa wersja alertu zastępuje poprzednią |

Mieszkańcy strefy zagrożenia, którzy dostali zweryfikowany alert, po czasie reakcji idą do punktu
ewakuacji; część zostaje i zgłasza potrzebę pomocy. Kurierzy zbierają zgłoszenia po drodze
i oddają je w hubie, a PCZK odsyła potwierdzenia zbiorcze.

Animacja celowo pokazuje tylko sztafetę: telefony z aplikacją, przekazania alertu, ewakuację, zgłoszenia
i kurierów. Osób bez aplikacji i wątku fałszywego alertu na niej nie ma, żeby obraz był czytelny;
oba są w liczbach, na wykresach i w karcie wyników.

## Architektura

```
src/sztafeta/
  engine/        rdzeń: tylko numpy, scipy i cryptography; bez plików, bez wykresów, bez print
    model.py       typy: pakiety (Alert, Report, Ack), parametry, scenariusz, tablice agentów
    rng.py         jedyne źródło losowości: niezależne strumienie z jednego seeda
    graph.py       graf ulic jako tablice + najkrótsze ścieżki
    geo.py         geohash, punkt w wielokącie, przeliczenie metrów na stopnie
    population.py  budowa populacji (gospodarstwa domowe, adopcja, języki)
    mobility.py    wektorowy ruch po trasach, patrole kurierów
    behavior.py    spacery, reakcja na alert, ewakuacja, zgłoszenia, przekaz ustny
    crypto.py      Ed25519, łańcuch zaufania, weryfikacja z cache
    contacts.py    wykrywanie kontaktów (cKDTree), duty cycle, zestawianie połączenia, transfer, bateria
    routing.py     bufory, routing epidemiczny i Spray-and-Wait, priorytety, eksmisja
    pczk.py        sztab: deduplikacja, potwierdzenia zbiorcze, dashboard
    templates.py   kody alertu -> tekst w języku telefonu (PL/EN/UK/DE/CS)
    metrics.py     metryki w czasie i podsumowanie
    events.py      strumień zdarzeń
    sim.py         klasa Simulation: step(), run(), snapshot(), akcje scenariusza
  scenarios/     presety YAML i ich ładowanie
  data/          siatka proceduralna (fallback), import z OpenStreetMap, zapis map
  io/            zapis i odczyt wyników uruchomienia
  viz/           animacja mapy, wykresy do slajdów, karta wyników (matplotlib)
  runner.py      jedno uruchomienie z presetu
  batch.py       przegląd parametrów (multiprocessing)
  wyniki.py      generator docs/WYNIKI.md
  cli.py         polecenia: fetch-osm, run, batch, animate, frame, charts, inspect
tests/           pytest
data/            mapy (commitowane, żeby symulacja działała offline)
results/         wyniki uruchomień (poza repozytorium)
```

Zasady, których trzyma się kod:

- **Determinizm**: cała losowość przechodzi przez `engine/rng.py`; ten sam seed i parametry dają
  identyczne pliki wyników (sprawdza to test).
- **Silnik bez warstwy prezentacji**: `engine/` nie importuje `viz/`, `io/` ani `cli.py`; na zewnątrz
  wychodzą tylko `snapshot()`, `describe()` i strumień zdarzeń.
- **Wydajność**: stan agentów i buforów to tablice numpy, kontakty przez `cKDTree`, pętle Pythona
  tylko po faktycznych kontaktach. Scenariusz 6 h dla ok. 3000 agentów liczy się w kilkanaście sekund.

## Testy i jakość

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest
```

## Ograniczenia modelu

- Zasięg radia to stały promień; nie modelujemy tłumienia przez ściany, zakłóceń ani różnic między
  telefonami i ograniczeń systemu działającego w tle.
- Urządzenia łączą się tylko wtedy, gdy mają sobie coś do przekazania; jałowych połączeń i ich kosztu
  baterii nie liczymy (uproszczenie na korzyść Sztafety).
- Strefa zagrożenia to bufor wokół rzek, a nie mapa zalewowa; nie ma zalanych ani nieprzejezdnych ulic.
- Zachowania ludzi (czas reakcji, posłuszeństwo wobec alertu, zgłoszenia) to założenia zespołu,
  nie dane z badań.
- Wariant bazowy „bez Sztafety” nie obejmuje syren, megafonów ani obchodu służb – jest dolną granicą.
  Wyłącza też jednocześnie telefony i kurierów, dlatego [docs/WYNIKI.md](docs/WYNIKI.md) pokazuje osobno
  warianty „same telefony” i „sami kurierzy”.
- Duża część ewakuowanych to osoby bez aplikacji poinformowane ustnie przez domowników i sąsiadów.
  Siła tego przekazu jest założeniem; wyniki bez niego i w wariancie „tylko domownicy” są w WYNIKI.md.
- Kurierzy patrolują tylko strefę zagrożenia i punkt ewakuacji, więc zgłoszenia spoza strefy docierają
  do PCZK znacznie rzadziej.
- Duty cycle skanowania (10 s co 60 s) i zasięg radia wpływają na wynik podobnie mocno; żadnego z nich
  nie zmierzyliśmy w terenie.
- Tłumaczenia szablonów alertów na ukraiński, niemiecki i czeski są robocze.
- Atakujący to tylko troll z fałszywym alertem; nie symulujemy zagłuszania ani ataków Sybil.

Pełna lista założeń z wartościami i źródłami: [docs/MODEL.md](docs/MODEL.md).

## Jak przenieść silnik na backend

Silnik jest zwykłą klasą Pythona bez I/O, więc opakowanie w API to cienka warstwa:

1. Proces serwera (np. FastAPI) trzyma obiekt `Simulation(params, scenario, seed)` i w pętli w tle
   woła `step()`.
2. Klient dostaje raz `describe()` (mapa, agenci, słowniki), a potem przez WebSocket ramki
   `snapshot()` i zdarzenia z `drain_events()`.
3. Akcje scenariusza to metody silnika: `issue_alert`, `cancel_alert`, `dispatch_couriers`,
   `troll_broadcast`, `submit_report`, `network_down` – każda staje się endpointem `POST`.
4. Widok telefonu w module aplikacji to `phone_view(agent)`, a dashboard sztabu to `pczk_dashboard()`.
5. Gotowe uruchomienia można odtwarzać we frontendzie bez silnika: wystarczą `static.json`,
   `snapshots.npz` i `events.jsonl`.

Tabela metod z proponowanymi endpointami i wszystkie schematy: [docs/FORMAT.md](docs/FORMAT.md).

## Źródła, licencje, użycie AI

[docs/ZRODLA.md](docs/ZRODLA.md) – biblioteki, dane (OpenStreetMap, ODbL), literatura i informacja
o użyciu AI, zgodnie z regulaminem HackYeah.
