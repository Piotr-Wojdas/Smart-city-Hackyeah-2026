# Koncepcja projektu „Sztafeta”

# Projekt: „Sztafeta” – offline'owy kanał kryzysowy telefon–telefon (HackYeah 2026, SMART CITY)

## Kontekst
Budujemy prototyp na hackathon HackYeah 2026 (zadanie SMART CITY: reagowanie na awarie i sytuacje kryzysowe w mieście). Czas: ok. 24 h. Kryteria oceny: innowacyjność 30%, dopasowanie do kategorii 20%, praktyczna użyteczność 20%, design 20%, kompletność/gotowość wdrożeniowa 10%.

Produkt składa się z dwóch modułów na wspólnym silniku P2P:
1. Sztafeta Komunikatów – podpisane komunikaty urzędowe propagowane z telefonu do telefonu.
2. Kurier Danych do Sztabu – zgłoszenia mieszkańców (w tym „Jestem bezpieczny”) zanoszone do centrum zarządzania kryzysowego przez telefony ratowników i wolontariuszy.

## Problem (fakty z realnych kryzysów)
- Powódź 2024 (Kotlina Kłodzka): blisko połowa stacji bazowych Orange w regionie nie działała z powodu braku prądu i zalań. Zapora w Stroniu Śląskim nie miała nawet łączności radiowej. Mieszkańcy byli odcięci, rodziny szukały bliskich na Facebooku, a urząd z agregatem miał Wi-Fi, ale nie było jak połączyć go z ludźmi dookoła.
- Huragan Maria (2017): 95,2% stacji bazowych w Portoryko nie działało, choć centra alarmowe działały. Padła „ostatnia mila”.
- Blackout iberyjski (2025): sieć komórkowa padła razem z prądem, a telefony na baterii działały dłużej niż sieć.
- Polska nie ma Cell Broadcast. Alert RCB to SMS-y, które wymagają działającej sieci komórkowej.
- Istniejące aplikacje mesh (Bridgefy, Briar, Bitchat, FireChat) to czaty równorzędne. Nie odróżniają komunikatu urzędu od plotki, nie mają integracji ze sztabem kryzysowym, a Bridgefy i Bitchat miały poważne podatności (podszywanie się, MITM).

## Moduł 1: Sztafeta Komunikatów
**Idea:** urząd gminy / PCZK podpisuje komunikat kluczem Ed25519. Telefony przekazują go sobie automatycznie (store-and-forward, epidemic routing z TTL). Każdy telefon weryfikuje podpis offline kluczem wbudowanym w aplikację.

**Scenariusz:** Nysa, pada sieć komórkowa. Burmistrz w urzędzie z agregatem wydaje komunikat „Ewakuacja ulic X i Y do SP nr 2”. Pierwszy telefon odbiera go przez hub w urzędzie, a w ciągu minut dociera on do sąsiadów, kolejnych bloków i dzielnicy.

**Kluczowe cechy:**
- Łańcuch zaufania: klucz główny (np. RCB / wojewoda) podpisuje certyfikaty wydawców (gmina, PCZK, PSP) z zakresem obszaru i datą ważności. Klucz główny jest przypięty w aplikacji.
- Komunikat zawiera: id, wersję/numer sekwencyjny, wydawcę + certyfikat, typ zagrożenia, działanie, obszar (geohash), czas wydania, expires_at, priorytet, podpis.
- Komunikaty „anuluj/zastąp” oraz odrzucanie starszych wersji (ochrona przed replay).
- Komunikaty jako szablony kodów (w stylu CAP: typ zagrożenia + działanie + miejsce), a nie wolny tekst. Każdy telefon renderuje je w swoim języku (PL/EN/UA/DE/CZ), z piktogramami i syntezą mowy. Pakiet jest mały, a dostępność wbudowana.
- UI rozróżnia dwie klasy treści: „urzędowe zweryfikowane” (zielone) i „niezweryfikowane” (czerwone/szare). Nigdy ich nie mieszamy.
- Podpisane komunikaty mają priorytet w kolejce przesyłania.

## Moduł 2: Kurier Danych do Sztabu
**Idea:** mieszkańcy zostawiają w lokalnej sieci P2P krótkie zgłoszenia. Telefony ratowników (PSP, OSP, WOPR) i wolontariuszy przechodzących przez rejon zbierają je automatycznie i oddają w PCZK. Kierunek jest odwrotny niż w module 1: mieszkaniec → sztab.

**Scenariusz:** Stronie Śląskie bez zasięgu. Mieszkańcy klikają „Jestem bezpieczny” albo „Potrzebuję pomocy: 2 osoby, senior leżący, brak leków”. Zastęp OSP przejeżdża ulicą, a jego telefony zbierają zgłoszenia. Po powrocie do urzędu z hubem na dashboardzie PCZK pojawia się mapa z 37 zgłoszeniami, zdeduplikowanymi i posortowanymi według pilności.

**Typy zgłoszeń:**
- „Jestem bezpieczny” (+ miejsce pobytu, liczba osób). Gdy jakiś telefon odzyska internet, paczka statusów trafia na serwer, a rodzina sprawdza status po numerze telefonu (przechowywany jest tylko hash).
- „Potrzebuję pomocy” (kategoria: medyczna / ewakuacja / woda / leki / prąd, liczba osób, pilność, przybliżona lokalizacja).
- Opcjonalnie dane wrażliwe (np. osoba leżąca, 3. piętro) szyfrowane kluczem publicznym służb („szyfrowanie dla roli”). Sąsiad przenosi pakiet, ale nie może go odczytać.

**Kluczowe cechy:**
- Deduplikacja po id zgłoszenia, aktualizacja statusu (nowsza wersja nadpisuje starszą).
- Limit kopii (w stylu Spray and Wait) i limit liczby wiadomości na urządzenie na godzinę (ochrona przed zalaniem sieci).
- Potwierdzenie dostarczenia: sztab może odesłać podpisane „przyjęto zgłoszenie”, które wraca tą samą sztafetą do mieszkańca.
- Dashboard PCZK (web): mapa, lista zgłoszeń według pilności, liczniki („bezpieczni: X, potrzebujący pomocy: Y”), czas ostatniej aktualizacji.

## Wspólny silnik techniczny
- Android, Kotlin. Transport: Google Nearby Connections, strategia P2P_CLUSTER (BLE do wykrywania + Wi-Fi do transferu, zasięg ok. 100 m, bez systemowego dialogu parowania – akceptację robi aplikacja).
- Nie używamy surowego Wi-Fi Direct: wymaga potwierdzeń użytkownika, każdy group owner ma IP 192.168.49.1, a Android nie obsługuje wielu grup naraz, więc multi-hop jest praktycznie niemożliwy.
- Warstwa store-and-forward: lokalna baza (Room/SQLite) z pakietami. Przy spotkaniu dwóch urządzeń wymiana list id (summary vector), potem przesłanie brakujących pakietów. TTL i expires_at, deduplikacja.
- Kryptografia: Ed25519 przez libsodium (lazysodium) albo Google Tink. Żadnej własnej kryptografii.
- Prywatność: rotujące identyfikatory urządzeń, brak danych osobowych w rozgłaszanych nazwach, lokalizacja zgrubna (geohash), dokładna tylko w pakietach szyfrowanych dla służb, automatyczne usuwanie po TTL.
- Tryby aplikacji: Mieszkaniec / Ratownik (kurier) / Hub (urząd, punkt z agregatem; tablet jako stacja synchronizacji i tablica ogłoszeń).
- Panel wydawcy: laptop „PCZK” do tworzenia i podpisywania komunikatów + dashboard zgłoszeń. Synchronizacja z hubem przez lokalną sieć lub USB.
- Na demo aplikacja działa na pierwszym planie (foreground service z powiadomieniem).

## Bezpieczeństwo i zaufanie
- Fałszywe komunikaty: odrzucane, bo nie mają ważnego podpisu w łańcuchu zaufania.
- Replay: numery sekwencyjne i daty ważności.
- Spam/Sybil: limity nadawania, priorytet dla podpisanych treści. Pełnej odporności na Sybil bez tożsamości nie da się zapewnić – mówimy o tym otwarcie.
- RODO: minimalizacja danych, zgoda na dane wrażliwe, szyfrowanie dla służb, automatyczne usuwanie. Administratorem danych w produkcji byłaby gmina.
- Zgodność z ustawą z 5 grudnia 2024 r. o ochronie ludności i obronie cywilnej: obowiązek ostrzegania spoczywa na organie, który pierwszy dowie się o zagrożeniu. Sztafeta daje mu kanał, gdy nie działa sieć. Uzupełnia Alert RCB, nie zastępuje go.

## Zakres na 24 h (priorytety)
1. (0–8 h) Silnik P2P + store-and-forward + podpisy Ed25519 + ekran komunikatów z weryfikacją.
2. (8–16 h) Zgłoszenia mieszkańców, tryb Ratownik/Kurier, dashboard PCZK z mapą.
3. (16–22 h) Szablony wielojęzyczne + piktogramy + TTS, dopracowanie designu, potwierdzenia dostarczenia.
4. (22–24 h) Próba generalna demo.
Integracja z RCB / mObywatelem / 112 – tylko symulacja i slajd z roadmapą.

## Scenariusz demo dla jury
5–6 telefonów z Androidem w trybie samolotowym (Wi-Fi i Bluetooth włączone), laptop „PCZK Kłodzko”.
Narracja: „15 września 2024, pada sieć w Stroniu Śląskim”.
1. PCZK podpisuje komunikat ewakuacyjny. Rozchodzi się falą po telefonach rozstawionych po sali, każdy w innym języku.
2. Telefon „trolla” wysyła fałszywy alert. Wszystkie telefony oznaczają go jako niezweryfikowany.
3. „Mieszkańcy” klikają „Jestem bezpieczny” / „Potrzebuję pomocy”.
4. „Strażak” z telefonem przechodzi obok mieszkańców i wraca do laptopa. Na mapie dashboardu pojawiają się zgłoszenia.
5. Sztab odsyła „przyjęto”, a potwierdzenie wraca do mieszkańca.
Na koniec slajd z faktami: 95,2% stacji nieczynnych (Maria), blisko połowa stacji w Kotlinie Kłodzkiej, brak Cell Broadcast w Polsce.
