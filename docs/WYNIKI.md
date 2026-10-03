# Wyniki symulacji „Sztafeta” – przegląd parametrów

**To są wyniki modelu, nie pomiary z terenu.** Pokazują, jak system zachowuje się w symulacji przy założeniach opisanych w [MODEL.md](MODEL.md). Dokument jest generowany poleceniem `sztafeta batch` i nie jest poprawiany ręcznie; liczby nie są zaokrąglane na korzyść projektu.

## Co zostało policzone

- preset: `flood-stronie`, mapa: OpenStreetMap, Stronie Śląskie (© autorzy OpenStreetMap (ODbL))
- czas symulacji: 6 h od awarii sieci, 4955 mieszkańców
- alert i ewakuacja dotyczą **całego miasta** (scenariusz bez wydzielonej strefy zagrożenia); kurierzy patrolują ulice przy wszystkich zamieszkanych budynkach
- adopcja: 5%, 10%, 20%, 30%, 50%
- zasięg radia: 25 m, 40 m, 80 m
- liczba kurierów: 2, 5, 10
- seedy: 5 na kombinację (1–5); łącznie 275 uruchomień
- przy ustawieniach odniesienia (adopcja 30%, zasięg 40 m, 5 kurierów) dodatkowo: wariant bez Sztafety, same telefony, sami kurierzy i warianty wrażliwości (punkty 5 i 6)
- ustawienia presetu inne niż domyślne w modelu (opis w MODEL.md): `population.n_residents=4956`, `population.settled_share=0.25`, `behavior.p_comply=0.92`
- wersja kodu: `0.1.0+1fe9114`

W tabelach podajemy **medianę między seedami**, a w nawiasie **najmniejszą i największą wartość** (rozrzut). Czasy liczymy od wydania alertu. „Adopcja” oznacza telefony z zainstalowanym i działającym modułem (Bluetooth włączony, aplikacja może pracować w tle).

## Liczby na slajd

1. W modelu (adopcja 30%, zasięg 40 m, 5 kurierów, 5 seedów) zweryfikowany alert po 6 h ma **99.7% telefonów z aplikacją** (rozrzut 99.6–100%). Połowa telefonów ma go po 18 min (17–19) od wydania. Przy zasięgu 25 m: 98% telefonów, połowa po 23 min (23–29).
2. Skąd bierze się ten wynik (adopcja 30%, zasięg 40 m, 5 kurierów, 5 seedów): bez żadnego przekazywania alert ma 4.2% telefonów; same telefony bez kurierów dają 99%; sami kurierzy bez przekazywania telefon–telefon 96%; oba mechanizmy razem **99.7%**.
3. W modelu (adopcja 30%, zasięg 40 m, 5 kurierów, 5 seedów) do PCZK dociera **99.8% zgłoszeń mieszkańców**. Mediana opóźnienia dostarczonych zgłoszeń to 16 min. Potwierdzenie „przyjęto” wraca do **99.6%** zgłaszających, których zgłoszenie dotarło.
4. W modelu (adopcja 30%, zasięg 40 m, 5 kurierów, 5 seedów) do punktu ewakuacji dociera **84%** mieszkańców miasta: 26% to osoby z aplikacją, a 58% osoby bez aplikacji poinformowane ustnie przez domowników i sąsiadów. To założenie modelu: bez przekazu ustnego ewakuuje się 26%, a gdy informują się tylko domownicy – 54%. Wynik zależy też od gęstości zabudowy przyjętej w scenariuszu: gdy mieszkańcy są rozproszeni po wszystkich budynkach, do punktu ewakuacji dociera 70%, a alert ma 89% telefonów z aplikacją. Przy posłuszeństwie wobec alertu 85% zamiast 92% dociera 78%.
5. We wszystkich 225 uruchomieniach pełnej siatki fałszywy alert uznało za zweryfikowany **0 urządzeń** (dostało go: mediana 139 urządzeń w bezpośrednim zasięgu trolla).

## Od jakiej adopcji system ma sens

Kryterium (umowne, przy 5 kurierach): połowa telefonów z aplikacją ma alert **najpóźniej godzinę po jego wydaniu**, a po 6 h ma go **co najmniej 90% telefonów z aplikacją** (mediany między seedami). Sam zasięg na koniec nie wystarcza: przy małej adopcji alert roznoszą głównie kurierzy i trwa to godzinami.

| Zasięg radia | Najmniejsza badana adopcja spełniająca kryterium |
|---|---|
| 25 m | 10% |
| 40 m | 5% |
| 80 m | 5% |

**Próg w modelu przy zasięgu 40 m i 5 kurierach: adopcja 5%.** To najmniejsza z badanych wartości, a nie dokładna granica.

Uwagi: (1) próg zależy od zasięgu radia bardziej niż od czegokolwiek innego, a zasięgu w zabudowie nie znamy; (2) próg dotyczy sytuacji z kurierami w terenie; (3) nawet powyżej progu sama aplikacja obejmuje tylko swoich użytkowników, czyli przy adopcji 30% najwyżej 30% mieszkańców; reszta zależy od przekazu ustnego i innych kanałów.

## 1. Czas do zasięgu 50% i 90% telefonów z aplikacją (5 kurierów)

| Adopcja | Zasięg | Czas do 50% | Czas do 90% | Zasięg po 6 h |
|---|---|---|---|---|
| 5% | 25 m | 61 min (37–89) | 321 min (321–321), tylko 1/5 przebiegów | 89.5% (88.7–96.4) |
| 5% | 40 m | 23 min (20–28) | 124 min (69–175) | 98.4% (96.4–99.1) |
| 5% | 80 m | 14 min (14–15) | 24 min (23–27) | 100.0% (100.0–100.0) |
| 10% | 25 m | 40 min (31–43) | 221 min (185–242) | 95.6% (94.0–97.1) |
| 10% | 40 m | 21 min (19–26) | 108 min (48–123) | 99.6% (98.2–99.8) |
| 10% | 80 m | 13 min (13–14) | 21 min (18–24) | 100.0% (100.0–100.0) |
| 20% | 25 m | 26 min (25–32) | 138 min (124–182) | 98.5% (96.1–98.9) |
| 20% | 40 m | 19 min (18–20) | 54 min (43–92) | 99.7% (99.3–99.9) |
| 20% | 80 m | 13 min (9–14) | 15 min (13–20) | 100.0% (100.0–100.0) |
| 30% | 25 m | 23 min (23–29) | 76 min (48–117) | 98.4% (98.2–98.9) |
| 30% | 40 m | 18 min (17–19) | 32 min (28–38) | 99.7% (99.7–100.0) |
| 30% | 80 m | 12 min (7–13) | 15 min (12–16) | 100.0% (100.0–100.0) |
| 50% | 25 m | 23 min (22–24) | 64 min (42–83) | 99.1% (98.1–99.2) |
| 50% | 40 m | 17 min (12–18) | 31 min (28–39) | 99.7% (99.6–100.0) |
| 50% | 80 m | 10 min (8–12) | 14 min (13–15) | 100.0% (100.0–100.0) |

![Czas do zasięgu w funkcji adopcji](wykresy/adopcja_czas_pl.png)

![Zasięg alertu w funkcji adopcji i zasięgu radia](wykresy/adopcja_zasieg_pl.png)

## 2. Zgłoszenia dostarczone do PCZK (zasięg 40 m)

Odsetek zgłoszeń wysłanych do danej chwili, które do tej chwili dotarły do PCZK (czas od awarii sieci). Kurierzy patrolują całe miasto i punkt ewakuacji. Liczba zgłoszeń rośnie z zasięgiem alertu, więc odsetki łączne z różnych wierszy nie są wprost porównywalne.

| Adopcja | Kurierzy | Zgłoszeń (mediana) | Po 1 h | Po 3 h | Po 6 h | „Potrzebuję pomocy” | Mediana opóźnienia dostarczonych |
|---|---|---|---|---|---|---|---|
| 5% | 2 | 183 | 76.5% (63.1–87.6) | 98.7% (97.1–99.4) | 99.5% (97.8–100.0) | 95.0% (91.7–100.0) | 12 min |
| 5% | 5 | 183 | 89.6% (82.1–92.0) | 98.9% (96.1–99.4) | 99.5% (99.4–100.0) | 93.8% (90.9–100.0) | 11 min |
| 5% | 10 | 185 | 89.3% (87.3–94.7) | 99.5% (99.4–100.0) | 99.5% (99.4–100.0) | 100.0% (93.3–100.0) | 10 min |
| 10% | 2 | 343 | 77.0% (58.7–83.1) | 99.3% (96.9–99.7) | 99.7% (98.8–100.0) | 100.0% (96.7–100.0) | 15 min |
| 10% | 5 | 361 | 86.5% (79.8–90.8) | 99.4% (98.8–99.5) | 100.0% (99.4–100.0) | 100.0% (93.3–100.0) | 11 min |
| 10% | 10 | 358 | 91.6% (89.0–93.9) | 99.7% (99.4–100.0) | 100.0% (99.7–100.0) | 100.0% (96.6–100.0) | 11 min |
| 20% | 2 | 767 | 48.4% (42.5–70.3) | 99.7% (98.2–99.9) | 99.9% (99.5–100.0) | 100.0% (98.4–100.0) | 18 min |
| 20% | 5 | 742 | 70.3% (65.2–82.1) | 99.9% (98.6–100.0) | 99.9% (98.9–99.9) | 98.6% (98.3–100.0) | 13 min |
| 20% | 10 | 756 | 89.0% (78.7–90.8) | 100.0% (99.9–100.0) | 100.0% (100.0–100.0) | 100.0% (100.0–100.0) | 13 min |
| 30% | 2 | 1105 | 29.3% (23.1–64.1) | 95.4% (93.0–97.1) | 99.9% (99.5–99.9) | 98.8% (95.0–99.0) | 28 min |
| 30% | 5 | 1102 | 53.3% (50.4–68.0) | 99.8% (99.2–99.9) | 99.8% (99.8–99.9) | 99.0% (97.6–100.0) | 16 min |
| 30% | 10 | 1118 | 80.2% (70.7–86.0) | 99.9% (99.8–100.0) | 100.0% (99.8–100.0) | 100.0% (98.0–100.0) | 15 min |
| 50% | 2 | 1869 | 22.1% (16.5–43.1) | 81.7% (78.7–84.2) | 99.8% (99.3–100.0) | 98.2% (96.8–100.0) | 55 min |
| 50% | 5 | 1874 | 37.0% (29.4–49.9) | 99.8% (99.7–99.9) | 99.9% (99.8–100.0) | 99.3% (98.2–100.0) | 22 min |
| 50% | 10 | 1870 | 67.1% (58.6–74.4) | 99.9% (99.8–100.0) | 100.0% (99.9–100.0) | 100.0% (99.4–100.0) | 16 min |

![Zgłoszenia w PCZK w funkcji liczby kurierów](wykresy/kurierzy_zgloszenia_pl.png)

## 3. Potwierdzenia (Ack), które wróciły do zgłaszających (zasięg 40 m)

Odsetek zgłoszeń dostarczonych do PCZK, których autor dostał podpisane potwierdzenie „przyjęto”.

| Adopcja | 2 kurierów | 5 kurierów | 10 kurierów |
|---|---|---|---|
| 5% | 98.0% (96.7–99.5) | 99.4% (97.0–100.0) | 100.0% (99.5–100.0) |
| 10% | 98.3% (96.2–99.1) | 99.4% (99.0–100.0) | 99.5% (99.2–100.0) |
| 20% | 98.6% (95.1–99.0) | 99.6% (98.6–99.9) | 99.9% (99.4–100.0) |
| 30% | 99.0% (98.5–99.2) | 99.6% (99.5–99.9) | 99.8% (99.6–100.0) |
| 50% | 98.1% (96.6–98.8) | 99.6% (99.4–99.8) | 99.8% (99.7–99.9) |

## 4. Fałszywe alerty

- urządzenia, które uznały fałszywy alert za zweryfikowany: **0** (maksimum ze wszystkich 225 uruchomień pełnej siatki; oczekiwane 0)
- urządzenia, które go odebrały i oznaczyły jako niezweryfikowany: mediana 139, najwięcej 337
- żadne urządzenie nie rozpoczęło ewakuacji ani nie zmieniło stanu z powodu fałszywego alertu (test automatyczny)

## 5. Co daje który mechanizm (adopcja 30%, zasięg 40 m, 5 kurierów, 5 seedów)

| Wariant | Zasięg alertu (telefony z aplikacją) | Czas do 50% | Mieszkańcy w punkcie ewakuacji | Zgłoszenia w PCZK |
|---|---|---|---|---|
| Bez Sztafety: tylko zasięg huba, zgłoszenia osobiście | 4.2% (3.8–4.7) | nie osiągnięto | 10.1% (9.1–13.0) | 1.9% (0.0–3.8) |
| Same telefony, bez kurierów | 98.8% (98.4–99.5) | 31 min (21–35) | 83.1% (82.0–84.3) | 4.6% (3.1–5.2) |
| Sami kurierzy, bez przekazywania telefon–telefon | 95.7% (94.9–97.1) | 44 min (38–53) | 81.7% (81.0–83.1) | 70.2% (68.5–73.3) |
| Pełna Sztafeta: telefony i kurierzy | 99.7% (99.7–100.0) | 18 min (17–19) | 83.7% (83.5–83.8) | 99.8% (99.8–99.9) |

- **Bez Sztafety**: telefony nie przekazują pakietów, alert dostaje tylko urządzenie w zasięgu huba, zgłoszenie trzeba zanieść osobiście. Wariant nie obejmuje syren, megafonów ani obchodu służb – to dolna granica, nie opis tego, co się wydarzyło.
- **Same telefony**: sieć niesiona wyłącznie ruchem mieszkańców. Nikt nie zbiera zgłoszeń po drodze, więc do PCZK trafiają tylko te, których nosiciel znalazł się w zasięgu huba.
- **Sami kurierzy**: kurier przekazuje alert telefonom, które mija, i zbiera od nich zgłoszenia, ale telefony nie podają niczego dalej. Odsetek zgłoszeń liczymy od zgłoszeń wysłanych, a tych jest mniej, gdy alert ma mniej osób.

## 6. Wrażliwość na założenia (adopcja 30%, zasięg 40 m, 5 kurierów, 5 seedów)

Po jednej zmianie względem ustawień odniesienia. Tych założeń nie da się dziś sprawdzić w terenie, a wpływają na wynik podobnie mocno jak zasięg radia.

| Wariant | Zasięg alertu (telefony z aplikacją) | Czas do 50% | Mieszkańcy w punkcie ewakuacji | Zgłoszenia w PCZK |
|---|---|---|---|---|
| Ustawienia odniesienia | 99.7% (99.7–100.0) | 18 min (17–19) | 83.7% (83.5–83.8) | 99.8% (99.8–99.9) |
| Bez przekazu ustnego | 99.8% (99.3–100.0) | 17 min (17–19) | 25.8% (25.2–26.3) | 100.0% (99.8–100.0) |
| Przekaz ustny tylko między domownikami | 99.8% (99.7–99.9) | 18 min (16–19) | 53.8% (53.1–54.5) | 99.9% (99.8–100.0) |
| Okno skanowania 5 s co 60 s (zamiast 10 s) | 99.7% (99.5–99.9) | 20 min (19–22) | 83.1% (82.6–84.4) | 99.8% (99.8–100.0) |
| Okno skanowania 5 s co 120 s | 99.4% (99.1–99.8) | 26 min (26–27) | 83.2% (82.2–84.4) | 99.8% (99.5–100.0) |
| Zestawianie połączenia 8–15 s (zamiast 3–8 s) | 99.7% (99.3–100.0) | 20 min (19–21) | 83.5% (83.0–84.1) | 99.9% (99.8–100.0) |
| Zabudowa rozproszona: mieszkańcy we wszystkich budynkach | 89.5% (87.9–91.3) | 28 min (27–37) | 69.5% (66.1–70.4) | 98.4% (97.9–99.4) |
| Posłuszeństwo wobec alertu 85% | 99.7% (99.7–99.7) | 18 min (17–19) | 77.8% (76.9–78.6) | 100.0% (99.7–100.0) |

## Koszt i mechanizmy, które w tym scenariuszu nie zadziałały

- średnia bateria telefonów z aplikacją po 6 h: mediana 50% (start: 35–100%). To prosta konsekwencja założonego zużycia, a nie wynik symulacji; rozładowane telefony: najwięcej 0 w jednym uruchomieniu
- łączny transfer w mieście: mediana 19.0 MB na uruchomienie; 79% transferów to potwierdzenia (każdy Ack rozchodzi się po całym mieście, choć dotyczy najwyżej 32 zgłaszających) – to miejsce do optymalizacji
- pakiety usunięte z przepełnionych buforów: najwięcej 0 w jednym uruchomieniu. Limit bufora, limit skoków i czasy życia pakietów są dłuższe niż potrzeby scenariusza 6-godzinnego, więc przegląd ich nie testuje (robią to testy jednostkowe)
- czas obliczeń jednego uruchomienia: mediana 54 s

Pliki źródłowe: `results/batch/runs.csv` (każde uruchomienie) i `results/batch/summary.csv` (agregacja).
