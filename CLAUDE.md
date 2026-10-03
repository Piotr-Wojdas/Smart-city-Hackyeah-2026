# Sztafeta – symulacja offline'owego kanału kryzysowego (HackYeah 2026, SMART CITY)

## Czym jest projekt
Koncepcja modułu do aplikacji **mObywatel**, który w czasie kryzysu (powódź, blackout) przekazuje informacje
z telefonu do telefonu bez sieci komórkowej (Google Nearby Connections: BLE + Wi-Fi, store-and-forward).
Na tym etapie budujemy **symulację w Pythonie**, która pokazuje i mierzy, jak system działałby w prawdziwym mieście
(domyślnie: Stronie Śląskie, powódź 15.09.2024). Później silnik trafi na backend (np. FastAPI),
a wizualizacja do frontendu – dlatego API silnika i formaty wyjściowe muszą być od początku czyste i udokumentowane.

Dwa moduły na wspólnym silniku P2P:
1. **Sztafeta Komunikatów** (urząd → ludzie): komunikaty podpisane Ed25519, łańcuch zaufania, epidemic routing z TTL.
2. **Kurier Danych do Sztabu** (ludzie → urząd): zgłoszenia „Jestem bezpieczny” / „Potrzebuję pomocy”
   zbierane przez telefony ratowników i oddawane w hubie (PCZK); potwierdzenie „przyjęto” wraca sztafetą.

Pełny opis koncepcji: `docs/KONCEPT.md`. Założenia modelu i źródła: `docs/MODEL.md`. Formaty wyjściowe: `docs/FORMAT.md`.

## Słownik domeny
- **Pakiet** – jednostka przesyłana między urządzeniami: `Alert`, `Report`, `Ack`.
- **Alert** – komunikat urzędowy w stylu CAP (kod zagrożenia + kod działania + obszar), renderowany lokalnie w języku telefonu.
- **Report** – zgłoszenie mieszkańca (`SAFE` / `NEED_HELP`), wersjonowane; nowsza wersja nadpisuje starszą.
- **Ack** – podpisane przez PCZK potwierdzenie przyjęcia zgłoszenia.
- **Kontakt** – dwa urządzenia z aplikacją w zasięgu, oba w fazie skanowania; ma czas zestawienia i ograniczoną przepustowość.
- **Summary vector** – lista id pakietów wymieniana na początku kontaktu; przesyłamy tylko brakujące, według priorytetu.
- **Hub** – stały punkt z agregatem i łącznością (urząd, PCZK). **Kurier** – ratownik/wolontariusz w ruchu.
- **Troll** – agent rozsyłający fałszywe alerty (nieważny podpis); żadne urządzenie nie może uznać ich za zweryfikowane.
- **Adopcja** – odsetek mieszkańców z zainstalowanym modułem.

## Architektura (trzymaj się jej)
```
src/sztafeta/
  engine/          rdzeń – bez matplotlib, bez I/O plików, bez print; tylko numpy/scipy/networkx/cryptography
    model.py       dataclasses: agenci, pakiety, parametry, scenariusz
    rng.py         jedyne źródło losowości (numpy Generator z seeda)
    mobility.py    ruch po grafie ulic (wektorowo w numpy), ewakuacja, trasy kurierów
    contacts.py    wykrywanie kontaktów (scipy cKDTree), duty cycle, czas zestawienia, przepustowość
    routing.py     epidemic (alerty, acki), spray-and-wait (zgłoszenia), bufor i priorytety
    crypto.py      Ed25519 (biblioteka cryptography), łańcuch zaufania, cache weryfikacji po id pakietu
    metrics.py     zbieranie metryk w czasie
    sim.py         klasa Simulation: step(), run(), snapshot() -> dict serializowalny do JSON
  scenarios/       presety (YAML) + ładowanie
  io/              zapis wyników: metrics.csv, events.jsonl, snapshots (format w docs/FORMAT.md)
  viz/             matplotlib: wykresy, animacja mapy (MP4/GIF), raport PNG dla slajdów
  data/            pobieranie OSM (osmnx) i budowa grafu
  cli.py           komendy: fetch-osm, run, batch, animate, inspect
tests/             pytest
data/              wygenerowane grafy ulic (commitowane – symulacja ma działać offline)
results/           wyniki uruchomień (nie commitujemy, poza wybranymi do prezentacji)
```

## Komendy
- `uv sync` – instalacja zależności
- `uv run pytest` – testy
- `uv run ruff check . && uv run ruff format --check .` – lint i formatowanie
- `uv run mypy src` – typy
- `uv run sztafeta fetch-osm --preset flood-stronie` – dane OSM do `data/`
- `uv run sztafeta run --preset flood-stronie --seed 42` – jedno uruchomienie → `results/<run_id>/`
- `uv run sztafeta animate results/<run_id>` – animacja mapy (MP4, fallback GIF)
- `uv run sztafeta batch` – przegląd parametrów → `results/batch/*.csv` i `docs/WYNIKI.md`
- `uv run sztafeta inspect results/<run_id> --agent <id> --t <s>` – stan telefonu agenta w danej chwili (JSON)

## Zasady pracy
- **Determinizm**: cała losowość przez `engine/rng.py`. Nigdy moduł `random`, nigdy czas systemowy w silniku.
  Ten sam seed + parametry = identyczne metryki (test to sprawdza).
- **Silnik bez warstwy prezentacji**: `engine/` nie importuje `viz/`, `io/` ani `cli.py`. Komunikacja na zewnątrz
  wyłącznie przez `Simulation.snapshot()` i strumień zdarzeń – to będzie kontrakt z przyszłym backendem/frontendem.
- **Założenia konserwatywne**: zasięg domyślnie 40 m, czas zestawienia połączenia 3–8 s, ograniczona przepustowość.
  Każde liczbowe założenie musi mieć wpis w `docs/MODEL.md` (wartość, uzasadnienie, źródło lub „założenie zespołu”).
- **Uczciwość wyników**: to model, nie pomiar. Wykresy i dokumenty nie mogą sugerować, że to dane z terenu.
- **Wydajność**: ~3000 agentów, scenariusz 6 h przy kroku 1 s ma liczyć się w < 2 min na laptopie.
  Ruch wektorowo w numpy, kontakty przez cKDTree, pętle Pythona tylko po faktycznych kontaktach.
- **Typy**: type hints wszędzie, mypy bez błędów. Dataclasses (`slots=True`) zamiast słowników w silniku.
- **Testy**: każda zmiana w `routing.py`, `contacts.py` lub `crypto.py` wymaga testu w pytest.
- **Wykresy i animacja**: opisy po polsku (opcja `--lang en`), czytelne z projektora, nie kodujemy informacji tylko kolorem.
- **Branding**: koncepcja modułu mObywatela – NIE używamy oficjalnego logo mObywatela, godła ani innych znaków urzędowych.
- **Zależności**: tylko potrzebne, open source. Każdą nową bibliotekę dopisz do `docs/ZRODLA.md`
  (wymóg regulaminu HackYeah: ujawnienie bibliotek, danych, API i znaczącego użycia AI).

## Definicja „gotowe”
`uv run ruff check . && uv run mypy src && uv run pytest` przechodzą bez błędów,
a scenariusz demo (`/demo-check`) działa od początku do końca.

## Kontekst hackathonu
Czas: ok. 24 h. Ocena: innowacyjność 30%, dopasowanie do kategorii 20%, użyteczność 20%, design 20%,
kompletność 10%. Wynikiem tego etapu są liczby, wykresy i animacja na slajdy oraz silnik gotowy do opakowania w API.
Gdy musisz wybierać – najpierw działający scenariusz demo i poprawne metryki, potem dodatki.
