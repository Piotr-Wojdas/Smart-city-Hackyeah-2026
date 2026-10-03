# Model symulacji „Sztafeta” – założenia i źródła

**To jest model, nie pomiar.** Wszystkie liczby, wykresy i animacje pochodzą z symulacji komputerowej
i pokazują, jak system *mógłby* działać przy opisanych niżej założeniach. Nie są danymi z terenu
ani rekonstrukcją powodzi z września 2024 r. Scenariusz jest nią inspirowany: lokalizacje huba
i punktu ewakuacji, przebieg strefy zagrożenia i oś czasu są umowne.

Zasada doboru wartości: **konserwatywnie**. Tam, gdzie nie mamy źródła, przyjmujemy wartość gorszą
dla Sztafety (krótszy zasięg, dłuższe zestawianie połączenia, mniejsza przepustowość) i oznaczamy ją
jako „założenie zespołu”. Wpływ najważniejszych założeń sprawdza przegląd parametrów (`sztafeta batch`).

Każdy parametr ma nazwę z kodu (`sekcja.pole` w `Params`, plik `src/sztafeta/engine/model.py`)
i można go nadpisać z linii poleceń: `sztafeta run --set radio.range_m=80`.

## 1. Czas i przebieg

| Parametr | Wartość | Uzasadnienie | Źródło |
|---|---|---|---|
| `dt` | 1 s | krok krótszy niż czas zestawienia połączenia (3–8 s), więc widać przerwane transfery | założenie zespołu |
| `duration_s` | 6 h | okres od awarii sieci do ustabilizowania sytuacji | założenie zespołu |
| `output.snapshot_interval_s` | 10 s | wystarcza do płynnej animacji, mały rozmiar plików | założenie zespołu |
| `output.metrics_interval_s` | 10 s | jak wyżej | założenie zespołu |

## 2. Mapa

- **Dane OSM** (preset `flood-stronie`): sieć ulic i budynki mieszkalne z OpenStreetMap, rzutowane do
  EPSG:2180. Krawędzie grafu są odcinkami prostymi (geometria ulic rozbita na węzły pośrednie).
  Graf traktujemy jako nieskierowany: piesi i służby poruszają się w obu kierunkach.
  Stronie Śląskie: promień 1800 m od środka miasta, sieć piesza (`network: walk`), 4729 węzłów,
  99 km ulic i ścieżek, 1025 budynków mieszkalnych (258 w strefie zagrożenia). Szczegóły pobrania:
  `data/stronie-slaskie/meta.json`.
- **Budynki mieszkalne**: wszystkie budynki z OSM o powierzchni co najmniej 40 m², z wyłączeniem typów
  na pewno niemieszkalnych (garaże, kościoły, szkoły, hale itp.). Waga budynku = powierzchnia × liczba
  kondygnacji (z tagu `building:levels`; gdy go brak: bloki 4, pozostałe 1,5–3 zależnie od powierzchni).
  Budynki oznaczone w OSM ogólnie (`building=yes`) traktujemy jako mieszkalne – to zawyża rozrzut
  mieszkańców po zabudowie gospodarczej (założenie zespołu).
- **Siatka proceduralna** (fallback i testy): nieregularna siatka ulic z „rzeką” przez środek.
  Nie odwzorowuje żadnego rzeczywistego miasta.
- **Strefa zagrożenia**: wielokąt wzdłuż rzeki (bufor 120 m wokół rzek z OSM, `waterway=river`).
  To nie jest mapa zalewowa ISOK.
- **Hub**: położenie urzędu (`amenity=townhall`) z OSM. **Punkt ewakuacji**: szkoła z OSM leżąca
  poza strefą zagrożenia. Wybór jest umowny i nie odtwarza rzeczywistej organizacji ewakuacji.
- **Hub i punkt ewakuacji** muszą leżeć poza strefą zagrożenia (sprawdzane przy budowie mapy).
- Ruch odbywa się wyłącznie po grafie ulic; nie modelujemy zalanych, nieprzejezdnych odcinków.

## 3. Populacja

| Parametr | Wartość | Uzasadnienie | Źródło |
|---|---|---|---|
| `population.n_residents` | 3000 | ok. 60% liczby mieszkańców miasta (4956 osób, GUS, stan na 31.12.2024), więc gęstość telefonów jest zaniżona (konserwatywnie); mieści się w limicie czasu obliczeń | założenie zespołu; liczba ludności: GUS za polskawliczbach.pl |
| `behavior.household_mean` | 2,5 osoby | rząd wielkości średniego gospodarstwa domowego w Polsce | GUS, NSP 2021 (ok. 2,5–2,6) |
| `behavior.adoption` | 30% | odsetek mieszkańców z zainstalowanym modułem; kluczowa niewiadoma, dlatego przegląd 10–70% | założenie zespołu |
| `behavior.lang_shares` | PL 90%, UK 5%, EN 2%, DE 2%, CS 1% | język telefonu; region przygraniczny i turystyczny | założenie zespołu |
| `population.n_couriers` | 4 | zastępy OSP/PSP/WOPR i wolontariusze z telefonem w trybie Ratownik | założenie zespołu |
| `population.courier_vehicle_share` | 50% | połowa kurierów w pojazdach, połowa pieszo | założenie zespołu |
| `population.n_trolls` | 1 | jeden agent rozsyłający fałszywe alerty | założenie zespołu |

Mieszkańcy są łączeni w gospodarstwa domowe (rozmiar 1 + Poisson, najwyżej 6) mieszkające w jednym
punkcie. Budynek gospodarstwa losujemy proporcjonalnie do wagi budynku (bloki > domy).
Zgłoszenie pierwszej osoby z aplikacją w gospodarstwie obejmuje też domowników bez aplikacji, więc
żadna osoba nie jest liczona w zgłoszeniach dwa razy.

## 4. Ruch

| Parametr | Wartość | Uzasadnienie | Źródło |
|---|---|---|---|
| `behavior.walk_speed_mean` / `walk_speed_sd` | 1,3 / 0,2 m/s (obcięte do 0,6–2,0) | typowa prędkość pieszego | literatura o prędkości chodu (np. Bohannon 1997: ok. 1,2–1,4 m/s) |
| `behavior.walk_rate_per_h` | 0,1 spaceru na godzinę | przed alertem ludzie są głównie w domu | założenie zespołu |
| `behavior.walk_radius_m` | 400 m | krótki spacer w obie strony | założenie zespołu |
| `population.courier_walk_speed` | 1,4 m/s | pieszy ratownik | założenie zespołu |
| `population.courier_vehicle_speed` | 5 m/s (18 km/h) | wolny przejazd patrolowy w warunkach powodzi | założenie zespołu |
| `population.courier_return_interval_s` | 30 min | po tym czasie kurier odwiedza punkt ewakuacji i wraca do huba | założenie zespołu |
| `population.courier_waypoint_dwell_s` | 60 s | postój w punkcie patrolu (rozmowa, sprawdzenie posesji) | założenie zespołu |
| `population.courier_hub_dwell_s` | 120 s | postój w hubie na synchronizację | założenie zespołu |
| `population.evac_spread_m` | 20 m | ludzie w punkcie ewakuacji nie stoją w jednym miejscu | założenie zespołu |

Kurierzy dzielą strefę zagrożenia na sąsiadujące sektory (wzdłuż głównej osi strefy) i objeżdżają
węzły swojego sektora w losowej, stałej kolejności.

## 5. Zachowania mieszkańców

| Parametr | Wartość | Uzasadnienie | Źródło |
|---|---|---|---|
| `behavior.reaction_median_s` / `reaction_sigma` / `reaction_max_s` | mediana 5 min, rozkład log-normalny σ = 0,8, najwyżej 60 min | ludzie nie ruszają natychmiast: sprawdzają, pakują się, zbierają rodzinę | założenie zespołu (kształt rozkładu zgodny z literaturą o czasie mobilizacji przed ewakuacją) |
| `behavior.p_comply` | 85% | część osób zostaje mimo alertu | założenie zespołu |
| `behavior.p_need_help_zone` | 6% | osoby w strefie, które nie mogą ewakuować się same (seniorzy, osoby leżące) | założenie zespołu |
| `behavior.p_need_help_blackout` | 1% w ciągu pierwszych 2 h | potrzeby wynikające z samej awarii (prąd dla sprzętu medycznego, leki) | założenie zespołu |
| `behavior.p_safe_report_evacuated` | 80% | odsetek ewakuowanych z aplikacją, którzy klikną „Jestem bezpieczny” | założenie zespołu |
| `behavior.p_safe_report_outside` | 25%, średnio po 10 min | osoby spoza strefy zgłaszające, że są bezpieczne | założenie zespołu |
| `behavior.p_report_update` | 15%, po ok. 30 min | aktualizacja zgłoszenia (nowa wersja nadpisuje starszą) | założenie zespołu |
| `behavior.p_sensitive` | 30% zgłoszeń NEED_HELP | zgłoszenia z częścią zaszyfrowaną dla służb | założenie zespołu |

Rozkłady treści zgłoszeń „potrzebuję pomocy” (założenie zespołu):
- w strefie zagrożenia: ewakuacja 45%, medyczna 25%, leki 20%, woda 10%; pilność 1/2/3 = 25% / 45% / 30%;
- po awarii sieci (poza powodzią): prąd 40%, leki 30%, medyczna 15%, woda 15%; pilność 1/2/3 = 50% / 40% / 10%;
- aktualizacja zgłoszenia podnosi pilność o jeden stopień (najwyżej do 3).

Osoba potrzebująca pomocy zostaje w domu. **Jeśli nie ma aplikacji, sztab o niej nie wie** – takie
osoby są w modelu (i na mapie), ale nie generują zgłoszeń.
Zgłoszenie „jestem bezpieczny” wysyła ewakuowany po dotarciu do punktu ewakuacji albo mieszkaniec
spoza strefy ze swojego domu.

Ewakuację wywołuje **wyłącznie** zweryfikowany alert z działaniem „ewakuuj” (albo informacja ustna od
osoby, która taki alert ma). Fałszywy alert nigdy nie zmienia zachowania agenta.
Mieszkańcy spoza strefy zagrożenia nie ewakuują się.

### Przekaz ustny (liczony osobno)

| Parametr | Wartość | Uzasadnienie | Źródło |
|---|---|---|---|
| `behavior.wom_enabled` | tak | domownik lub sąsiad z aplikacją mówi o alercie osobie bez aplikacji | założenie zespołu |
| `behavior.wom_range_m` | 10 m | to samo mieszkanie, klatka, sąsiednia posesja | założenie zespołu |
| `behavior.wom_prob_per_min` | 20% na minutę przebywania w zasięgu | nie każdy od razu puka do sąsiada | założenie zespołu |

Informować ustnie może tylko osoba z aplikacją i zweryfikowanym alertem; osoby poinformowane ustnie
nie przekazują informacji dalej (konserwatywnie). Zasięg ustny raportujemy w osobnych kolumnach
i nigdy nie doliczamy go do zasięgu aplikacji.

## 6. Radio i kontakty

| Parametr | Wartość | Uzasadnienie | Źródło |
|---|---|---|---|
| `radio.range_m` | 40 m | zabudowa, ściany, telefon w kieszeni | założenie zespołu; dokumentacja Google Nearby Connections mówi o zasięgu rzędu 100 m w dobrych warunkach |
| `radio.setup_min_s` – `setup_max_s` | 3–8 s (rozkład jednostajny) | wykrycie, akceptacja i zestawienie połączenia | założenie zespołu |
| `radio.scan_window_s` / `scan_period_s` | 10 s co 60 s | duty cycle telefonu mieszkańca (oszczędzanie baterii); kurier i hub skanują ciągle | założenie zespołu |
| `radio.summary_vector_s` | 1 s | wymiana list identyfikatorów na początku kontaktu | założenie zespołu |
| `radio.throughput_bps` | 2000 B/s | sam BLE, bez przełączenia na Wi-Fi | założenie zespołu (BLE GATT osiąga w praktyce kilka–kilkadziesiąt kB/s) |
| `radio.max_session_s` | 30 s | po tym czasie połączenie jest zamykane | założenie zespołu |
| `radio.max_links_resident` / `courier` / `hub` | 2 / 4 / 6 | jednoczesne połączenia jednego urządzenia | założenie zespołu (praktyczny limit Bluetooth to kilka połączeń) |
| `radio.max_candidate_pairs` | 3000 na krok | ograniczenie obliczeniowe w tłumie; nadmiarowe pary czekają na kolejny krok | założenie zespołu |

Reguły kontaktu:
- kontakt mogą zacząć tylko dwa urządzenia z aplikacją, włączone, w zasięgu i **oba w oknie skanowania**;
- początek okna skanowania jest losowany w każdym cyklu (przy stałych fazach część sąsiadów nigdy by się nie spotkała);
- zestawione połączenie trwa do końca wymiany, utraty zasięgu albo `max_session_s`, także po końcu okna;
- zerwanie kontaktu przerywa transfer: pakiety, które nie zdążyły przejść, nie są dostarczone;
- urządzenia zestawiają połączenie tylko wtedy, gdy mają sobie coś do przekazania. Zakładamy, że wiedzą
  to ze skrótu zawartości bufora rozgłaszanego przy wykrywaniu. **Uproszczenie na korzyść Sztafety:**
  jałowych połączeń (skrót różny, a nic do wysłania) i ich kosztu baterii nie modelujemy;
- gdy w zasięgu jest więcej chętnych niż wolnych połączeń, pary są wybierane losowo.

## 7. Pakiety i routing

| Parametr | Wartość | Uzasadnienie | Źródło |
|---|---|---|---|
| `routing.alert_ttl_hops` / `ack_ttl_hops` | 100 skoków | średnica miasta przy zasięgu 40 m to kilkadziesiąt skoków | założenie zespołu |
| `routing.alert_lifetime_s` | 12 h | `expires_at` alertu | założenie zespołu |
| `routing.ack_lifetime_s` | 6 h | `expires_at` potwierdzenia | założenie zespołu |
| `routing.report_lifetime_s` | 12 h | `expires_at` zgłoszenia | założenie zespołu |
| `routing.spray_copies` | L = 8 | binarny Spray-and-Wait | Spyropoulos, Psounis, Raghavendra, „Spray and Wait”, WDTN 2005 |
| `routing.buffer_resident` / `courier` / `hub` | 200 / 5000 / 100 000 pakietów | telefon mieszkańca ma mały bufor, kurier duży | założenie zespołu |
| `routing.max_own_reports_per_hour` | 4 | ochrona przed zalaniem sieci | założenie zespołu |
| `routing.unverified_forward_hops` | 0 | fałszywego alertu nie przekazujemy dalej | decyzja zespołu (patrz niżej) |
| `routing.ack_batch_size` | 32 zgłoszenia na Ack | potwierdzenia zbiorcze | decyzja zespołu |
| `routing.ack_delay_s` | 120 s | czas obsługi zgłoszenia w PCZK | założenie zespołu |

- **Alert i Ack**: routing epidemiczny (Vahdat, Becker, „Epidemic Routing for Partially-Connected
  Ad Hoc Networks”, 2000) z limitem skoków i `expires_at`.
- **Report**: binarny Spray-and-Wait; kurier i hub przyjmują zgłoszenie zawsze (custody).
  Nadawca zachowuje swoją kopię do czasu otrzymania Acka, kurier oddaje zgłoszenia tylko w hubie.
- **PCZK** deduplikuje zgłoszenia po `report_id` (zostaje najnowsza wersja) i potwierdza je zbiorczo
  w cyklu obsługi co `ack_delay_s`; jeden Ack obejmuje do `ack_batch_size` zgłoszeń.
- **Priorytet przesyłania**: zweryfikowany alert > Ack > NEED_HELP > SAFE > treści niezweryfikowane.
- **Bufor**: przy przepełnieniu usuwamy najpierw pakiety wygasłe, potem o najniższym priorytecie,
  potem najstarsze. Własnych niepotwierdzonych zgłoszeń urządzenie nie usuwa.
- **Ack jako antypakiet**: urządzenie, które dostało Ack, usuwa kopie potwierdzonych zgłoszeń.
- **Polityka wobec fałszywek**: telefon weryfikuje alert przy odbiorze. Niezweryfikowany alert jest
  pokazywany jako „niezweryfikowany”, nie trafia do bufora i nie jest przekazywany dalej. Powód:
  weryfikacja jest tania i działa offline, a przekazywanie zrobiłoby z uczciwych telefonów wzmacniacz
  dezinformacji i pozwoliło zapychać bufory. Skutek: fałszywka dociera tylko do urządzeń w bezpośrednim
  zasięgu trolla.

## 8. Kryptografia

- Podpisy **Ed25519** (RFC 8032) z biblioteki `cryptography`; żadnej własnej kryptografii.
- Łańcuch zaufania: klucz główny (RCB / wojewoda, przypięty w aplikacji) podpisuje certyfikat wydawcy
  (PCZK) z zakresem obszaru (prefiks geohash) i okresem ważności; wydawca podpisuje alerty i Acki.
- Podpis liczony jest po kanonicznej serializacji binarnej pakietu (opis w `docs/FORMAT.md`).
- Zgłoszenie mieszkańca jest podpisane jednorazowym kluczem urządzenia, a `report_id` to skrót klucza
  publicznego – nowszą wersję zgłoszenia może wystawić tylko to samo urządzenie.
- Klucze są wyprowadzane z seeda symulacji (powtarzalność); w produkcji byłyby generowane losowo.
- W symulacji wynik weryfikacji jest cachowany po identyfikatorze pakietu (skrót treści i podpisu),
  bo wszystkie urządzenia mają ten sam klucz główny i dochodzą do tego samego wyniku.
- „Dane wrażliwe zaszyfrowane dla służb” są w modelu flagą i dodatkowym rozmiarem pakietu;
  samego szyfrowania nie symulujemy.

## 9. Bateria

| Parametr | Wartość | Uzasadnienie | Źródło |
|---|---|---|---|
| `battery.start_min_pct` – `start_max_pct` | 35–100% (jednostajnie) | awaria zastaje telefony w różnym stanie naładowania | założenie zespołu |
| `battery.idle_pct_per_h` | 2%/h | zwykłe użycie telefonu bez sieci (ekran, latarka) | założenie zespołu |
| `battery.scan_pct_per_h` | 5%/h przy ciągłym skanowaniu, skalowane przez duty cycle | koszt wykrywania BLE/Wi-Fi | założenie zespołu |
| `battery.link_pct_per_h` | 6%/h w czasie aktywnego połączenia | koszt transmisji | założenie zespołu |

Telefon z baterią 0% wypada z sieci do końca symulacji (brak prądu = brak ładowania). Kurierzy i hub
mają zasilanie (powerbank, agregat) i się nie rozładowują.

## 10. Wariant bazowy „bez Sztafety”

Ten sam seed i ta sama populacja, ale telefony nie przekazują pakietów między sobą
(`routing.relay_enabled = false`): alert dostaje tylko urządzenie, które samo znajdzie się w zasięgu
huba, a zgłoszenie dociera do PCZK tylko wtedy, gdy zgłaszający osobiście podejdzie do huba.
Przekaz ustny działa tak samo w obu wariantach.

**Zastrzeżenie:** wariant bazowy nie obejmuje syren, megafonów, radia ani chodzenia służb od drzwi do
drzwi. Jest dolną granicą „bez żadnego kanału zastępczego”, a nie opisem tego, co faktycznie się wydarzyło.

## 11. Czego model nie obejmuje

- propagacji radiowej (tłumienie przez ściany, zakłócenia) – zasięg to stały promień;
- różnic między modelami telefonów i ograniczeń systemu w tle;
- zalanych i nieprzejezdnych ulic, korków, paniki;
- ataków innych niż fałszywy alert (np. zagłuszanie, Sybil – pełnej odporności na Sybil bez tożsamości nie ma);
- powrotu sieci komórkowej i ładowania telefonów.
