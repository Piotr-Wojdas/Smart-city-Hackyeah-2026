# Model symulacji „Sztafeta” – założenia i źródła

**To jest model, nie pomiar.** Wszystkie liczby, wykresy i animacje pochodzą z symulacji komputerowej
i pokazują, jak system *mógłby* działać przy opisanych niżej założeniach. Nie są danymi z terenu
ani rekonstrukcją powodzi z września 2024 r. Scenariusz jest nią inspirowany: lokalizacje huba
i punktu ewakuacji, zasięg ewakuacji (całe miasto) i oś czasu są umowne.

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
- **Obszar alertu** (`scenario.area` w presecie). W scenariuszu demo `flood-stronie` ma wartość
  `city`: **nie ma wydzielonej strefy zagrożenia**, alert „ewakuuj” dotyczy wszystkich mieszkańców,
  a kurierzy patrolują całe miasto (pkt 4). To założenie zespołu – upraszcza scenariusz do jednej
  historii „całe miasto idzie do punktu ewakuacji” i nie odtwarza rzeczywistego zasięgu powodzi.
  Wartość `zone` (domyślna dla presetów bez tego pola, używana w testach) ogranicza alert,
  ewakuację i patrole do strefy zagrożenia z mapy.
- **Strefa zagrożenia** (tylko przy `scenario.area: zone`): wielokąt wzdłuż rzeki (bufor 120 m wokół
  rzek z OSM, `waterway=river`). To nie jest mapa zalewowa ISOK. Wielokąt zostaje w danych mapy
  także wtedy, gdy scenariusz go nie używa.
- **Hub**: położenie urzędu (`amenity=townhall`) z OSM. **Punkt ewakuacji**: szkoła z OSM leżąca
  poza strefą zagrożenia. Wybór jest umowny i nie odtwarza rzeczywistej organizacji ewakuacji.
- **Hub i punkt ewakuacji** muszą leżeć poza strefą zagrożenia (sprawdzane przy budowie mapy).
  W scenariuszu dla całego miasta punkt ewakuacji leży w obszarze alertu: jest miejscem zbiórki,
  z którego w rzeczywistości ludzi wywoziłby transport. **Pojemności punktu ewakuacji nie modelujemy**
  (w Stroniu trafia tam w modelu ponad połowa z 3000 mieszkańców).
- Ruch odbywa się wyłącznie po grafie ulic; nie modelujemy zalanych, nieprzejezdnych odcinków.

## 3. Populacja

| Parametr | Wartość | Uzasadnienie | Źródło |
|---|---|---|---|
| `population.n_residents` | domyślnie 3000; **w scenariuszu demo 4956** | 4956 to pełna liczba mieszkańców miasta (GUS, stan na 31.12.2024). Domyślne 3000 (ok. 60%) zaniża gęstość telefonów i jest używane w testach oraz presetach bez tego ustawienia | liczba ludności: GUS za polskawliczbach.pl |
| `population.settled_share` | domyślnie 1,0; **w scenariuszu demo 0,25** | zwarta zabudowa: ludzie mieszkają tylko w tej części budynków, wokół której zabudowa jest najgęstsza; przy 0,25 jest to 256 z 1025 budynków, a rozproszone domy na obrzeżach są puste. Wartość dobrana tak, żeby scenariusz demo pokazywał gęsto zaludnione miasto – nie odwzorowuje rzeczywistego rozkładu ludności Stronia | założenie zespołu |
| `population.settled_radius_m` | 150 m | promień, w którym liczona jest gęstość zabudowy wokół budynku (suma wag budynków) | założenie zespołu |
| `behavior.household_mean` | 2,5 osoby | rząd wielkości średniego gospodarstwa domowego w Polsce | GUS, NSP 2021 (ok. 2,5–2,6) |
| `behavior.adoption` | 30% | odsetek mieszkańców z zainstalowanym **i działającym** modułem (Bluetooth włączony, aplikacja może pracować w tle); kluczowa niewiadoma, dlatego przegląd 5–50% | założenie zespołu |
| `behavior.lang_shares` | PL 90%, UK 5%, EN 2%, DE 2%, CS 1% | język telefonu; region przygraniczny i turystyczny | założenie zespołu |
| `population.n_couriers` | 5 | zastępy OSP/PSP/WOPR i wolontariusze z telefonem w trybie Ratownik; przegląd 2–10 oraz wariant bez kurierów | założenie zespołu |
| `population.courier_vehicle_share` | 50% | połowa kurierów w pojazdach, połowa pieszo | założenie zespołu |
| `population.n_trolls` | 1 | jeden agent rozsyłający fałszywe alerty; skanuje ciągle, a poza fałszywką zachowuje się jak zwykły telefon (przekazuje też prawdziwe pakiety) | założenie zespołu |

Mieszkańcy są łączeni w gospodarstwa domowe (rozmiar 1 + Poisson, najwyżej 6) mieszkające w jednym
punkcie. Budynek gospodarstwa losujemy proporcjonalnie do wagi budynku (bloki > domy), spośród
budynków zamieszkanych w scenariuszu (`settled_share`).

**Gęste zaludnienie w scenariuszu demo.** Preset `flood-stronie` ustawia pełną liczbę mieszkańców
i zwartą zabudowę, bo o zasięgu decyduje to, ilu ludzi mieszka blisko siebie: w budynku z wieloma
mieszkańcami prawie zawsze ktoś ma aplikację i przekazuje alert sąsiadom, a telefony w zwartej zabudowie
są w zasięgu radia. **Zasady radia, routingu, przekazu ustnego i adopcja są takie same** jak przy
rozproszonej zabudowie; zmienia się tylko to, gdzie mieszkają ludzie. Ile wynik zależy od tego
założenia, pokazuje WYNIKI.md (pkt 6, wariant „zabudowa rozproszona”).
**Budynek jest w modelu punktem**: wszystkie jego gospodarstwa leżą w odległości kilku metrów od środka
(rozrzut σ = 3 m, założenie zespołu). W bloku każdy ma więc wszystkich sąsiadów „w zasięgu 10 m”, co
wzmacnia przekaz ustny (pkt 5) i ułatwia łączność między telefonami w tym samym budynku.
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

Kurierzy dzielą obszar patrolu na sąsiadujące sektory (wzdłuż jego głównej osi) i objeżdżają węzły
swojego sektora w losowej, stałej kolejności; co `courier_return_interval_s` odwiedzają punkt
ewakuacji i wracają do huba. Obszar patrolu zależy od `scenario.area`:
- `city` (scenariusz demo): **całe miasto**, czyli węzły ulic najbliższe budynkom mieszkalnym
  (w Stroniu 751 z 4729 węzłów). Ścieżek, przy których nikt nie mieszka, kurierzy nie objeżdżają;
- `zone`: tylko węzły w strefie zagrożenia, punkt ewakuacji i hub – nie reszta miasta, więc
  zgłoszenia spoza strefy docierają wtedy do PCZK znacznie rzadziej.

Pojazdy kurierów jeżdżą po tej samej sieci co piesi. Kurier przekazuje alert **wyłącznie przez
aplikację** (telefon–telefon, jak każde inne urządzenie) i w ten sam sposób zbiera zgłoszenia.
Nikogo nie informuje ustnie – to założenie konserwatywne: osoba bez aplikacji dowiaduje się
o ewakuacji tylko od domowników i sąsiadów (przekaz ustny, pkt 5).

## 5. Zachowania mieszkańców

| Parametr | Wartość | Uzasadnienie | Źródło |
|---|---|---|---|
| `behavior.reaction_median_s` / `reaction_sigma` / `reaction_max_s` | mediana 5 min, rozkład log-normalny σ = 0,8, najwyżej 60 min | ludzie nie ruszają natychmiast: sprawdzają, pakują się, zbierają rodzinę | założenie zespołu (kształt rozkładu zgodny z literaturą o czasie mobilizacji przed ewakuacją) |
| `behavior.p_comply` | domyślnie 85%; **w scenariuszu demo 92%** | część osób zostaje mimo alertu. Odsetek ewakuowanych nie może przekroczyć (1 − `p_need_help_zone`) × `p_comply` nawet wtedy, gdy o ewakuacji wiedzą wszyscy: 80% przy wartościach domyślnych, 86% w scenariuszu demo. Wartość 92% jest założeniem optymistycznym, dobranym dla scenariusza demo; wynik dla 85% jest w WYNIKI.md (pkt 6) | założenie zespołu |
| `behavior.p_need_help_zone` | 6% | osoby objęte alertem, które nie mogą ewakuować się same (seniorzy, osoby leżące) | założenie zespołu |
| `behavior.p_need_help_blackout` | 1% w ciągu pierwszych 2 h | potrzeby wynikające z samej awarii (prąd dla sprzętu medycznego, leki) | założenie zespołu |
| `behavior.p_safe_report_evacuated` | 80% | odsetek ewakuowanych z aplikacją, którzy klikną „Jestem bezpieczny” | założenie zespołu |
| `behavior.p_safe_report_outside` | 25%, średnio po 10 min | osoby spoza strefy zgłaszające, że są bezpieczne (tylko przy `scenario.area: zone`; w scenariuszu dla całego miasta nikogo takiego nie ma) | założenie zespołu |
| `behavior.p_report_update` | 15%, po ok. 30 min | aktualizacja zgłoszenia (nowa wersja nadpisuje starszą) | założenie zespołu |
| `behavior.p_sensitive` | 30% zgłoszeń NEED_HELP | zgłoszenia z częścią zaszyfrowaną dla służb | założenie zespołu |

Rozkłady treści zgłoszeń „potrzebuję pomocy” (założenie zespołu):
- po alercie ewakuacyjnym: ewakuacja 45%, medyczna 25%, leki 20%, woda 10%; pilność 1/2/3 = 25% / 45% / 30%;
- po awarii sieci (poza powodzią): prąd 40%, leki 30%, medyczna 15%, woda 15%; pilność 1/2/3 = 50% / 40% / 10%;
- aktualizacja zgłoszenia podnosi pilność o jeden stopień (najwyżej do 3).

Osoba potrzebująca pomocy zostaje w domu. **Jeśli nie ma aplikacji, sztab o niej nie wie** – takie
osoby są w modelu (i na mapie), ale nie generują zgłoszeń.
Zgłoszenie „jestem bezpieczny” wysyła ewakuowany po dotarciu do punktu ewakuacji (a w scenariuszu
ze strefą zagrożenia także mieszkaniec spoza strefy, ze swojego domu).

Ewakuację wywołuje **wyłącznie** zweryfikowany alert z działaniem „ewakuuj” (albo informacja ustna od
osoby, która taki alert ma). Fałszywy alert nigdy nie zmienia zachowania agenta.
Alert z innym działaniem (np. „zostań w budynku”) nie uruchamia ewakuacji ani przekazu ustnego i nie
blokuje późniejszego alertu „ewakuuj”. Zweryfikowane odwołanie alertu zatrzymuje przekaz ustny od
telefonu, który je dostał, oraz reakcję jego właściciela, jeśli jeszcze nie ruszył; osoby już idące
nie zawracają. Ewakuują się tylko mieszkańcy objęci alertem: w scenariuszu demo wszyscy, a przy
`scenario.area: zone` tylko mieszkańcy strefy zagrożenia.

### Przekaz ustny (liczony osobno)

| Parametr | Wartość | Uzasadnienie | Źródło |
|---|---|---|---|
| `behavior.wom_enabled` | tak | osoba z aplikacją mówi o alercie osobom bez aplikacji | założenie zespołu |
| domownicy | od razu (przy najbliższym sprawdzeniu, co `wom_interval_s` = 10 s), jeśli są w zasięgu `wom_range_m` | kto dostał alert ewakuacyjny, mówi o nim rodzinie w mieszkaniu | założenie zespołu |
| `behavior.wom_prob_per_min` | sąsiedzi z innych gospodarstw: 20% na minutę przebywania w zasięgu | nie każdy od razu puka do sąsiada | założenie zespołu |
| `behavior.wom_range_m` | 10 m | to samo mieszkanie, klatka, sąsiednia posesja | założenie zespołu |
| `behavior.wom_household_only` | nie | po włączeniu ustnie informują się tylko domownicy (wariant ostrożny) | założenie zespołu |

Informować ustnie może tylko osoba z aplikacją i zweryfikowanym alertem „ewakuuj”; osoby poinformowane
ustnie nie przekazują informacji dalej (konserwatywnie). Zasięg ustny raportujemy w osobnych kolumnach
i nigdy nie doliczamy go do zasięgu aplikacji, a odsetek ewakuowanych rozbijamy na osoby z aplikacją
i bez niej.

**To najmocniejsze założenie po stronie ewakuacji.** Ponieważ budynek jest punktem, większość osób bez
aplikacji ma kogoś z aplikacją w promieniu 10 m, a sąsiedzki przekaz ustny odpowiada za dużą część
ewakuowanych. Dlatego przegląd parametrów liczy trzy warianty: bez przekazu ustnego, tylko domownicy,
domownicy i sąsiedzi (WYNIKI.md, punkt 6).

## 6. Radio i kontakty

| Parametr | Wartość | Uzasadnienie | Źródło |
|---|---|---|---|
| `radio.range_m` | 40 m | zabudowa, ściany, telefon w kieszeni. To wartość środkowa, nie pesymistyczna: przez ściany zasięg BLE bywa mniejszy, dlatego liczby podajemy też dla 25 m | założenie zespołu; dokumentacja Google Nearby Connections mówi o zasięgu rzędu 100 m w dobrych warunkach |
| `radio.setup_min_s` – `setup_max_s` | 3–8 s (rozkład jednostajny) | wykrycie, akceptacja i zestawienie połączenia | założenie zespołu |
| `radio.scan_window_s` / `scan_period_s` | 10 s co 60 s | duty cycle telefonu mieszkańca (oszczędzanie baterii); kurier i hub skanują ciągle | założenie zespołu |
| `radio.summary_vector_s` | 1 s | wymiana list identyfikatorów na początku kontaktu | założenie zespołu |
| `radio.throughput_bps` | 2000 B/s na każde połączenie (hub z sześcioma połączeniami przesyła 6 × 2000 B/s) | sam BLE, bez przełączenia na Wi-Fi | założenie zespołu (BLE GATT osiąga w praktyce kilka–kilkadziesiąt kB/s) |
| `radio.max_session_s` | 30 s | po tym czasie połączenie jest zamykane | założenie zespołu |
| `radio.max_links_resident` / `courier` / `hub` | 2 / 4 / 6 | jednoczesne połączenia jednego urządzenia | założenie zespołu (praktyczny limit Bluetooth to kilka połączeń) |
| `radio.max_candidate_pairs` | 3000 na krok | ograniczenie obliczeniowe w tłumie; nadmiarowe pary czekają na kolejny krok | założenie zespołu |

Reguły kontaktu:
- kontakt mogą zacząć tylko dwa urządzenia z aplikacją, włączone, w zasięgu i **oba w oknie skanowania**;
- początek okna skanowania jest losowany w każdym cyklu (przy stałych fazach część sąsiadów nigdy by się nie spotkała);
  cykle wszystkich telefonów mają wspólną granicę co `scan_period_s`, a do rozpoczęcia zestawiania
  wystarcza 1 s wspólnego okna. **Duty cycle wpływa na wynik tak samo mocno jak zasięg radia** –
  wrażliwość pokazuje WYNIKI.md, punkt 6;
- zestawione połączenie trwa do końca wymiany, utraty zasięgu albo `max_session_s`, także po końcu okna;
- zerwanie kontaktu przerywa transfer: pakiety, które nie zdążyły przejść, nie są dostarczone;
- urządzenia zestawiają połączenie tylko wtedy, gdy mają sobie coś do przekazania. Zakładamy, że wiedzą
  to ze skrótu zawartości bufora rozgłaszanego przy wykrywaniu. **Uproszczenie na korzyść Sztafety:**
  jałowych połączeń (skrót różny, a nic do wysłania) i ich kosztu baterii nie modelujemy. Recenzja
  modelu sprawdziła to eksperymentem (2 seedy): gdyby telefony łączyły się zawsze, gdy ich zbiory
  identyfikatorów się różnią, połączeń byłoby 5–11 razy więcej, a bateria po 6 h niższa o 1–2 punkty
  procentowe; zasięg i czasy zmieniły się w granicach rozrzutu między seedami;
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
| `routing.relay_enabled` | tak | wyłączenie daje wariant bazowy „bez Sztafety” (pkt 10) | – |
| `routing.phone_relay` | tak | wyłączenie daje wariant „sami kurierzy”: telefony mieszkańców nie przekazują pakietów między sobą | – |

- **Alert i Ack**: routing epidemiczny (Vahdat, Becker, „Epidemic Routing for Partially-Connected
  Ad Hoc Networks”, 2000) z limitem skoków i `expires_at`.
- **Report**: binarny Spray-and-Wait; kurier i hub przyjmują zgłoszenie zawsze (custody).
  Nadawca zachowuje swoją kopię do czasu otrzymania Acka; kurier oddaje zgłoszenia w hubie
  (i innym kurierom), nigdy mieszkańcom.
- **PCZK** deduplikuje zgłoszenia po `report_id` (zostaje najnowsza wersja) i potwierdza je zbiorczo
  w cyklu obsługi co `ack_delay_s`; jeden Ack obejmuje do `ack_batch_size` zgłoszeń.
- **Priorytet przesyłania**: zweryfikowany alert > Ack > NEED_HELP > SAFE > treści niezweryfikowane.
- **Bufor**: przy przepełnieniu usuwamy najpierw pakiety wygasłe, potem o najniższym priorytecie,
  potem najstarsze. Własnych niepotwierdzonych zgłoszeń urządzenie nie usuwa.
- **Ack jako antypakiet**: urządzenie, które dostało Ack, usuwa kopie potwierdzonych zgłoszeń.
  Każdy Ack rozchodzi się epidemicznie po całym mieście, choć dotyczy najwyżej 32 zgłaszających;
  w scenariuszu demo to większość wszystkich transferów. Do optymalizacji w kolejnej wersji:
  Ack kumulatywny z numerem sekwencyjnym (nowszy zastępuje starszy).
- **Wygasanie**: pakiet po `expires_at` nie jest wysyłany (sprawdzane przy każdym transferze),
  a z buforów jest usuwany co 10 s.
- W scenariuszu 6-godzinnym limity bufora, limit skoków i czasy życia pakietów nie są osiągane,
  więc przegląd parametrów ich nie sprawdza; robią to testy jednostkowe.
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
mają zasilanie (powerbank, agregat) i się nie rozładowują. W scenariuszu 6-godzinnym przy tych stawkach
nie rozładowuje się prawie żaden telefon, więc „średnia bateria na koniec” jest prostą konsekwencją
założeń, a nie wynikiem symulacji.

## 10. Wariant bazowy „bez Sztafety”

Ten sam seed i ta sama populacja, ale telefony nie przekazują pakietów między sobą
(`routing.relay_enabled = false`): alert dostaje tylko urządzenie, które samo znajdzie się w zasięgu
huba, a zgłoszenie dociera do PCZK tylko wtedy, gdy zgłaszający osobiście podejdzie do huba.
Przekaz ustny działa tak samo w obu wariantach.

**Zastrzeżenie:** wariant bazowy nie obejmuje syren, megafonów, radia ani chodzenia służb od drzwi do
drzwi. Jest dolną granicą „bez żadnego kanału zastępczego”, a nie opisem tego, co faktycznie się wydarzyło.

Wariant bazowy wyłącza jednocześnie telefony i kurierów, więc samo porównanie z nim nie mówi, co daje
który mechanizm. Dlatego przegląd liczy też dwa warianty pośrednie (WYNIKI.md, punkt 5):
- **same telefony** (`population.n_couriers = 0`): przekazują mieszkańcy, kurierów nie ma;
- **sami kurierzy** (`routing.phone_relay = false`): kurier przekazuje alert mijanym telefonom i zbiera
  zgłoszenia, ale telefony mieszkańców niczego nie podają dalej.

## 11. Czego model nie obejmuje

- propagacji radiowej (tłumienie przez ściany, zakłócenia) – zasięg to stały promień;
- różnic między modelami telefonów i ograniczeń systemu w tle;
- zalanych i nieprzejezdnych ulic, korków, paniki;
- pojemności punktu ewakuacji, transportu z niego i wielu punktów ewakuacji (w scenariuszu demo
  całe miasto idzie do jednego punktu);
- ataków innych niż fałszywy alert (np. zagłuszanie, Sybil – pełnej odporności na Sybil bez tożsamości nie ma);
- powrotu sieci komórkowej i ładowania telefonów.
