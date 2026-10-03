# Formaty wyjściowe silnika „Sztafeta” – kontrakt dla backendu i frontendu

Dokument opisuje wszystko, co silnik wystawia na zewnątrz: akcje, snapshot, zdarzenia, metryki, widok
telefonu, dashboard PCZK i pliki jednego uruchomienia. Schematy mają wersję w polu `schema`
(np. `sztafeta.snapshot/1`); zmiana niekompatybilna podnosi numer.

Wszystkie wartości pochodzą z symulacji – **to wynik modelu, nie pomiar**.

## 1. Konwencje

- **Czas**: `t` w sekundach czasu modelu od początku scenariusza (liczba zmiennoprzecinkowa).
  Czas zegarowy = `run.start` (ISO 8601) + `t`.
- **Współrzędne**: metry w układzie `map.crs` (dla danych OSM: EPSG:2180; dla siatki: `local-m`),
  zaokrąglone do 0,1 m.
- **Agent**: liczba całkowita `0..n-1`, stała przez całe uruchomienie. Kolejność: mieszkańcy
  (w tym trolle), kurierzy, hub.
- **Tablice kolumnowe**: stan agentów to równoległe tablice o długości `n` (indeks = id agenta),
  gotowe do wczytania jako typed arrays.
- **Wyliczenia**: w snapshocie jako liczby, słowniki nazw w `describe().enums`; w zdarzeniach
  i widokach jako napisy.
- **Identyfikatory pakietów**: 16 znaków hex = pierwsze 8 bajtów SHA-256 z treści i podpisu.

## 2. API silnika (Python dziś, endpointy jutro)

```python
from sztafeta.engine import Simulation
from sztafeta.scenarios import load_preset

params, scenario = load_preset("flood-stronie", overrides=["behavior.adoption=0.5"])
sim = Simulation(params, scenario, seed=42)
sim.step()  # jeden krok (domyślnie params.dt = 1 s)
sim.run(until=3600)  # do chwili t
```

| Metoda | Zwraca | Przyszły endpoint |
|---|---|---|
| `step(dt=None)` | – | pętla serwera |
| `run(until=None)` | – | `POST /sim/run` |
| `describe()` | część statyczna (pkt 3) | `GET /sim/static` |
| `snapshot()` | część dynamiczna (pkt 4) | `GET /sim/snapshot`, ramka WebSocket |
| `drain_events()` | lista zdarzeń od poprzedniego wywołania (pkt 5) | strumień WebSocket |
| `phone_view(agent)` | widok telefonu (pkt 7) | `GET /agents/{id}/phone` |
| `pczk_dashboard()` | dashboard sztabu (pkt 8) | `GET /pczk` |
| `network_down(label)` | – | `POST /actions/network-down` |
| `issue_alert(hazard, action, msg_type)` | id pakietu | `POST /actions/alert` |
| `cancel_alert()` | id pakietu | `POST /actions/alert/cancel` |
| `dispatch_couriers()` | lista id kurierów | `POST /actions/couriers/dispatch` |
| `troll_broadcast(forgery)` | lista id pakietów | `POST /actions/troll` |
| `submit_report(agent, kind, category, urgency, sensitive_len)` | id pakietu lub `null` | `POST /agents/{id}/reports` |
| `note(label)` | – | `POST /actions/note` |

Akcje można wywoływać w dowolnej chwili między krokami; oś czasu z presetu woła te same metody.
Silnik nie czyta zegara systemowego i nie robi I/O – ten sam seed i ta sama sekwencja akcji dają
identyczny przebieg.

## 3. Część statyczna: `Simulation.describe()` (`static.json`)

```jsonc
{
  "schema": "sztafeta.static/1",
  "run": {"scenario": "flood-stronie", "seed": 42, "baseline": false,
          "dt": 1.0, "duration_s": 21600.0, "start": "2024-09-15T06:00:00+02:00"},
  "map": {
    "name": "Stronie Śląskie", "source": "OpenStreetMap, ... (© autorzy OpenStreetMap (ODbL))",
    "crs": "EPSG:2180",
    "bbox": [xmin, ymin, xmax, ymax],
    "streets": [[x1, y1, x2, y2], ...],        // odcinki proste
    "water": [[[x, y], ...], ...],            // linie rzek (tylko do rysowania)
    "hub": {"x": 0.0, "y": 0.0}, "evac_point": {"x": 0.0, "y": 0.0},
    "hazard_zone": [[x, y], ...],             // wielokąt bez powtórzonego domknięcia
    "hub_name": "Urząd / PCZK", "evac_name": "Szkoła – punkt ewakuacji",
    "radio_range_m": 40.0
  },
  "agents": {"n": 3005, "role": [...], "has_app": [...], "lang": [...],
             "home_x": [...], "home_y": [...], "in_zone": [...], "is_vehicle": [...]},
  "enums": {
    "role":  ["resident", "courier", "hub", "troll"],
    "state": ["no_app", "uninformed", "informed", "evacuating", "safe", "need_help"],
    "lang":  ["pl", "en", "uk", "de", "cs"],
    "link_phase": ["setup", "transfer"],
    "flags": {"alert": 1, "word_of_mouth": 2, "fake_seen": 4, "report_delivered": 8,
              "report_acked": 16, "device_off": 32, "radio_awake": 64, "moving": 128}
  }
}
```

## 4. Snapshot: `Simulation.snapshot()`

```jsonc
{
  "schema": "sztafeta.snapshot/1",
  "t": 1830.0,
  "agents": {
    "x": [...], "y": [...],        // metry
    "state": [...],                // indeks w enums.state
    "battery": [...],              // 0..100
    "flags": [...]                 // maska bitowa, enums.flags
  },
  "links": [[a, b, phase], ...],   // aktywne połączenia; phase: 0 = zestawianie, 1 = transfer
  "alerts": [
    {"id": "9b63978e26380c1b", "seq": 1, "msg_type": "ALERT", "hazard": "FLOOD", "action": "EVACUATE",
     "issued_at": 600.0, "verified": true, "verdict": "verified",
     "status": "active",           // active | superseded | expired | rejected
     "holders": 412}               // ile urządzeń ma pakiet w buforze
  ],
  "pczk": { /* liczniki, jak w pkt 8 "counters" */ },
  "metrics": { /* ostatni wiersz metryk, pkt 6 */ }
}
```

Stany agenta (`state`):

| Kod | Nazwa | Znaczenie |
|---|---|---|
| 0 | `no_app` | nie ma aplikacji i nie wie o alercie |
| 1 | `uninformed` | ma aplikację, nie ma alertu |
| 2 | `informed` | ma zweryfikowany alert albo informację ustną; nie ewakuuje się |
| 3 | `evacuating` | idzie do punktu ewakuacji |
| 4 | `safe` | dotarł do punktu ewakuacji |
| 5 | `need_help` | potrzebuje pomocy, zostaje na miejscu |

Fałszywy alert nigdy nie zmienia `state`; jego odbiór widać tylko we fladze `fake_seen`.

## 5. Zdarzenia: `drain_events()` (`events.jsonl`, jedno zdarzenie w wierszu)

```json
{"t": 1212.0, "type": "alert_rejected", "agent": 187, "peer": 93, "packet": "a3f1c2d4e5f60718", "data": {"reason": "bad_signature"}}
```

Pola `agent`, `peer`, `packet` i `data` są pomijane, gdy nie dotyczą zdarzenia.

| `type` | `agent` | `peer` | `data` |
|---|---|---|---|
| `network_down` | – | – | `label` |
| `note` | – | – | `label` |
| `alert_issued` | hub | – | `seq`, `hazard`, `action`, `msg_type`, `bytes` |
| `alert_received` | odbiorca | – | `seq`, `hops`, `first` (pierwszy zweryfikowany alert na tym urządzeniu) |
| `alert_rejected` | odbiorca | nadawca | `reason`: `bad_signature`, `untrusted_issuer`, `cert_expired`, `out_of_scope`, `stale_seq`, `expired` |
| `troll_broadcast` | troll | – | `forgery`, `verdict` |
| `word_of_mouth` | osoba poinformowana ustnie | – | – |
| `contact` | urządzenie a | urządzenie b | `start`, `duration`, `reason` (`done`, `out_of_range`, `timeout`, `device_off`), `packets` |
| `transfer` | nadawca | odbiorca | `packets`, `bytes` (łącznie w jednym kontakcie i kierunku) |
| `evacuation_start` | mieszkaniec | – | – |
| `evacuation_done` | mieszkaniec | – | – |
| `report_created` | zgłaszający | – | `kind`, `category`, `urgency`, `persons`, `version` |
| `report_picked_up` | kurier | od kogo | – (pierwsze przejęcie zgłoszenia przez kuriera) |
| `report_delivered` | hub | kto oddał | `report`, `kind`, `urgency`, `version`, `first`, `delay` |
| `ack_issued` | hub | – | `reports` (ile zgłoszeń obejmuje), `bytes` |
| `ack_received` | zgłaszający | – | `report`, `version` |
| `courier_dispatched` | kurier | – | – |
| `courier_at_hub` | kurier | – | – |
| `battery_dead` | urządzenie | – | – |
| `packet_evicted` | urządzenie | – | – (usunięcie z przepełnionego bufora) |

Zdarzenie `contact` jest emitowane na końcu kontaktu i zawiera czas jego rozpoczęcia; transfery są
agregowane na kontakt, żeby plik nie miał milionów wierszy. Zdarzenia w pliku są uporządkowane w czasie.

## 6. Metryki (`metrics.csv`, próbka co `output.metrics_interval_s`)

| Kolumna | Jednostka | Opis |
|---|---|---|
| `t` | s | chwila próbki |
| `alert_reach_app` | % | mieszkańcy z aplikacją, którzy mają zweryfikowany alert |
| `alert_reach_all` | % | to samo względem wszystkich mieszkańców (sama aplikacja) |
| `alert_reach_zone_app` | % | jak `alert_reach_app`, tylko mieszkańcy strefy zagrożenia |
| `alert_reach_zone_all` | % | jak `alert_reach_all`, tylko mieszkańcy strefy |
| `wom_reach_all` | % | mieszkańcy poinformowani **wyłącznie ustnie** (liczeni osobno) |
| `wom_reach_zone_all` | % | to samo w strefie zagrożenia |
| `evac_started_zone` | % | mieszkańcy strefy, którzy rozpoczęli ewakuację |
| `evacuated_zone` | % | mieszkańcy strefy, którzy dotarli do punktu ewakuacji |
| `evacuated_zone_app` | % | w tym osoby z aplikacją (część `evacuated_zone`, ten sam mianownik) |
| `evacuated_zone_wom` | % | w tym osoby bez aplikacji, poinformowane ustnie |
| `reports_created` | liczba | zgłoszenia wysłane (po deduplikacji wersji) |
| `reports_delivered` | liczba | zgłoszenia, które dotarły do PCZK |
| `need_help_created` / `need_help_delivered` | liczba | jak wyżej, tylko „potrzebuję pomocy” |
| `reports_zone_created` / `reports_zone_delivered` | liczba | zgłoszenia mieszkańców strefy zagrożenia |
| `reports_outside_created` / `reports_outside_delivered` | liczba | zgłoszenia mieszkańców spoza strefy |
| `delay_median_s` / `delay_p90_s` | s | opóźnienie dostarczenia (od utworzenia do PCZK), liczone **tylko po zgłoszeniach dostarczonych** |
| `acks_received` | liczba | zgłaszający, do których wróciło potwierdzenie |
| `acks_received_pct` | % | to samo względem zgłoszeń dostarczonych |
| `fake_received_devices` | liczba | urządzenia, które odebrały fałszywy alert |
| `fake_verified_devices` | liczba | urządzenia, które uznały go za zweryfikowany (**musi być 0**) |
| `battery_mean` | % | średnia bateria telefonów mieszkańców z aplikacją |
| `devices_off` | liczba | rozładowane telefony |
| `links_active` | liczba | połączenia aktywne w chwili próbki |
| `contacts_total` / `transfers_total` / `bytes_total` | liczba / liczba / B | narastająco |

Mianownikiem są mieszkańcy z rolą `resident` (bez trolla, kurierów i huba).

`summary.json` zawiera wartości końcowe oraz: `t50_app_s`, `t90_app_s`, `t50_zone_app_s`,
`t90_zone_app_s`, `t50_evacuated_zone_s` (sekundy od wydania alertu; `null` = nie osiągnięto),
`alert_reach_app_1h` / `_3h`, `reports_delivered_pct`, `reports_delivered_pct_1h` / `_3h`,
`reports_delivered_zone_pct`, `reports_delivered_outside_pct`, `need_help_delivered_pct`,
`evacuated_zone_app`, `evacuated_zone_wom`, `ack_transfer_pct` (odsetek transferów będących
potwierdzeniami), `contacts_interrupted`, `packets_evicted`, liczebności populacji
i identyfikację uruchomienia (`run_id`, `preset`, `seed`, `baseline`).

## 7. Widok telefonu: `Simulation.phone_view(agent)` (`sztafeta inspect`)

```jsonc
{
  "schema": "sztafeta.phone/1",
  "t": 3600.0, "agent": 192, "role": "resident", "has_app": true, "lang": "cs",
  "state": "safe", "in_zone": true,
  "position": {"x": 348450.1, "y": 271837.6, "geohash": "u2gy8k4"},
  "battery": 56.6, "device_on": true,
  "radio": {"scanning": false, "links": 0},
  "informed_by_word_of_mouth": false,
  "alerts": [
    {"id": "9b63978e26380c1b", "verified": true, "verdict": "verified", "status": "active",
     "seq": 1, "msg_type": "ALERT", "hazard": "FLOOD", "action": "EVACUATE",
     "received_t": 906.0, "hops": 4, "issuer": "PCZK",
     "text": {"lang": "cs", "header": "OVĚŘENÁ ÚŘEDNÍ VÝSTRAHA", "title": "Povodeň",
              "body": "Okamžitě se evakuujte do: Szkoła – punkt ewakuacji.",
              "pictograms": ["flood", "evacuate"]}},
    {"id": "628e06640a3fe146", "verified": false, "verdict": "bad_signature", "status": "rejected",
     "text": {"header": "NEOVĚŘENO – této zprávě nedůvěřujte", "...": "..."}}
  ],
  "own_reports": [
    {"report_id": "353407d4906769ff", "version": 1, "kind": "SAFE", "category": "NONE",
     "urgency": 1, "persons": 2, "created_t": 2114.0,
     "phone_status": "sent",          // sent | acked – to, co wie telefon
     "acked_t": null,
     "truth": {"status": "delivered", // waiting | picked_up | delivered | acked – wiedza symulacji
               "picked_up_t": 2410.0, "delivered_t": 2988.0}}
  ],
  "buffer": {"count": 7, "limit": 200, "by_kind": {"alert": 1, "ack": 2, "report": 4},
             "packets": [{"id": "...", "kind": "report", "priority": 3, "hops": 2,
                          "copies": 1, "bytes": 153, "own": false}]}
}
```

- Tekst alertu jest renderowany lokalnie z kodów w języku telefonu (PL/EN/UK/DE/CS); nazwy miejsc
  nie są tłumaczone. `pictograms` to identyfikatory ikon (zagrożenie, działanie).
- Treść zweryfikowana i niezweryfikowana ma inny nagłówek i nigdy nie jest mieszana.
- Pole `truth` to wiedza symulacji, której telefon nie ma (np. zgłoszenie już w PCZK, a Ack jeszcze
  nie wrócił). Frontend widoku telefonu powinien pokazywać `phone_status`.
- `sztafeta inspect <run_dir> --agent <id> --t <s>` odtwarza stan przez ponowne przeliczenie symulacji
  z `params.yaml` do chwili `t` (dokładne dzięki determinizmowi).

## 8. Dashboard sztabu: `Simulation.pczk_dashboard()` (`pczk.json`)

```jsonc
{
  "t": 21600.0,
  "counters": {
    "reports": 210, "safe_reports": 199, "safe_persons": 431,
    "need_help_reports": 11, "need_help_persons": 24, "need_help_critical": 4,
    "by_category": {"EVACUATION": 5, "MEDICAL": 3, "MEDICINE": 2, "POWER": 1},
    "acks_issued": 19, "last_update_t": 21376.0
  },
  "reports": [   // najpierw NEED_HELP od najpilniejszych, potem SAFE; po deduplikacji
    {"report_id": "...", "version": 2, "kind": "NEED_HELP", "category": "MEDICAL",
     "persons": 2, "urgency": 3, "geohash": "u2gy8k4",
     "created_t": 1410.0, "received_t": 3120.0, "updated_t": 4930.0, "delay_s": 1710.0,
     "carrier": 3001, "sensitive_encrypted": true, "acked": true}
  ]
}
```

`geohash` ma precyzję 7 (komórka ok. 150 m) – lokalizacja zgrubna. Dokładne dane wrażliwe byłyby
w części zaszyfrowanej dla służb; w modelu to tylko flaga `sensitive_encrypted` i rozmiar pakietu.

## 9. Pliki jednego uruchomienia: `results/<run_id>/`

| Plik | Zawartość |
|---|---|
| `params.yaml` | `run_id`, `preset`, `preset_source`, `seed`, `baseline`, `overrides`, `code_version`, opis scenariusza (mapa, oś czasu) i pełne parametry |
| `metrics.csv` | pkt 6 |
| `events.jsonl` | pkt 5 |
| `snapshots.npz` | stan co `output.snapshot_interval_s` (niżej) |
| `static.json` | pkt 3 |
| `pczk.json` | pkt 8, stan na koniec |
| `summary.json` | kluczowe liczby |
| `wykresy/*.png`, `animacja_*.mp4` | po `sztafeta charts` i `sztafeta animate` |

`run_id` jest deterministyczny: `<preset>_s<seed>[_baseline][_<skrót nadpisań>]`.
`metrics.csv`, `events.jsonl`, `summary.json` i `pczk.json` są bajt w bajt identyczne dla tego samego
seeda i parametrów (sprawdza to test).

`snapshots.npz` (numpy, skompresowany), `T` klatek, `N` agentów:

| Tablica | Kształt | Typ | Opis |
|---|---|---|---|
| `t` | `(T,)` | float64 | czas klatki |
| `x`, `y` | `(T, N)` | float32 | pozycje w metrach |
| `state` | `(T, N)` | uint8 | jak `agents.state` w snapshocie |
| `battery` | `(T, N)` | uint8 | 0..100 |
| `flags` | `(T, N)` | uint8 | maska bitowa |
| `links` | `(M, 3)` | int32 | wiersze `[a, b, phase]` wszystkich klatek po kolei |
| `links_ptr` | `(T+1,)` | int64 | połączenia klatki `k` to `links[links_ptr[k]:links_ptr[k+1]]` |
| `role`, `has_app`, `lang`, `in_zone` | `(N,)` | – | cechy stałe (kopie z `static.json`) |

## 10. Pakiety (kanoniczna serializacja, po której liczony jest podpis)

Liczby całkowite big-endian; napis = 1 bajt długości + UTF-8; czas = int64 milisekund czasu modelu.

| Pakiet | Treść podpisywana | Podpis |
|---|---|---|
| Certyfikat | `"SZC1"`, `issuer_id`, klucz publiczny (32 B), zakres (prefiks geohash), `not_before`, `not_after` | klucz główny, 64 B |
| Alert | `"SZA1"`, `incident`, `seq` (u32), `msg_type`, `hazard`, `action` (u8), lista geohashy obszaru, kod miejsca, `issued_at`, `expires_at`, priorytet, `ttl_hops`, certyfikat z podpisem | klucz wydawcy (PCZK), 64 B |
| Report | `"SZR1"`, `report_id` (8 B), wersja (u16), `kind`, `category`, `persons`, `urgency` (u8), geohash, `created_at`, `expires_at`, długość części zaszyfrowanej (u16), klucz publiczny zgłaszającego (32 B) | jednorazowy klucz urządzenia, 64 B |
| Ack | `"SZK1"`, liczba zgłoszeń (u16), pary `report_id` (8 B) + wersja (u16), `issued_at`, `expires_at`, `ttl_hops`, certyfikat z podpisem | klucz wydawcy (PCZK), 64 B |

Rozmiary w scenariuszu `flood-stronie` (zmierzone na pakietach z symulacji): alert 327 B (obszar
z 12 komórek geohash), zgłoszenie 140 B plus 48–160 B części zaszyfrowanej, Ack od 221 B (jedno
zgłoszenie) do 531 B (32 zgłoszenia).

Weryfikacja alertu na urządzeniu, w tej kolejności: podpis certyfikatu kluczem głównym
(`untrusted_issuer`), ważność certyfikatu w chwili wydania (`cert_expired`), obszar w zakresie
certyfikatu (`out_of_scope`), podpis alertu (`bad_signature`), `expires_at` (`expired`), numer
sekwencyjny większy od ostatnio przyjętego dla tego incydentu (`stale_seq`).

## 11. Jak to opakować w backend

1. `Simulation` trzymać w procesie serwera (FastAPI); pętla w tle woła `step()` z wybraną prędkością.
2. Po każdym kroku (albo co N kroków) wysyłać przez WebSocket `drain_events()` oraz `snapshot()`;
   `describe()` wysłać raz po połączeniu.
3. Akcje z pkt 2 wystawić jako `POST` – wywołują metody silnika między krokami.
4. Odtwarzanie zapisanego uruchomienia: `static.json` + `snapshots.npz` + `events.jsonl` wystarczają
   frontendowi bez uruchamiania silnika.
