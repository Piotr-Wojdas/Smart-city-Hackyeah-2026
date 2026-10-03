# Wyniki symulacji „Sztafeta” – przegląd parametrów

**To są wyniki modelu, nie pomiary z terenu.** Pokazują, jak system zachowuje się w symulacji przy założeniach opisanych w [MODEL.md](MODEL.md). Dokument jest generowany poleceniem `sztafeta batch` i nie jest poprawiany ręcznie; liczby nie są zaokrąglane na korzyść projektu.

## Co zostało policzone

- preset: `flood-stronie`, mapa: OpenStreetMap, Stronie Śląskie (© autorzy OpenStreetMap (ODbL))
- czas symulacji: 6 h od awarii sieci, 2999 mieszkańców
- alert i ewakuacja dotyczą **całego miasta** (scenariusz bez wydzielonej strefy zagrożenia); kurierzy patrolują ulice przy wszystkich budynkach
- adopcja: 5%, 10%, 20%, 30%, 50%
- zasięg radia: 25 m, 40 m, 80 m
- liczba kurierów: 2, 5, 10
- seedy: 5 na kombinację (1–5); łącznie 265 uruchomień
- przy ustawieniach odniesienia (adopcja 30%, zasięg 40 m, 5 kurierów) dodatkowo: wariant bez Sztafety, same telefony, sami kurierzy i warianty wrażliwości (punkty 5 i 6)
- wersja kodu: `0.1.0+ad4d1e9`

W tabelach podajemy **medianę między seedami**, a w nawiasie **najmniejszą i największą wartość** (rozrzut). Czasy liczymy od wydania alertu. „Adopcja” oznacza telefony z zainstalowanym i działającym modułem (Bluetooth włączony, aplikacja może pracować w tle).

## Liczby na slajd

1. W modelu (adopcja 30%, zasięg 40 m, 5 kurierów, 5 seedów) zweryfikowany alert po 6 h ma **88% telefonów z aplikacją** (rozrzut 86–90%). Połowa telefonów ma go po 34 min (33–47) od wydania. Przy zasięgu 25 m: 73% telefonów, połowa po 94 min (64–128).
2. Skąd bierze się ten wynik (adopcja 30%, zasięg 40 m, 5 kurierów, 5 seedów): bez żadnego przekazywania alert ma 2.5% telefonów; same telefony bez kurierów dają 60%; sami kurierzy bez przekazywania telefon–telefon 71%; oba mechanizmy razem **88%**.
3. W modelu (adopcja 30%, zasięg 40 m, 5 kurierów, 5 seedów) do PCZK dociera **99% zgłoszeń mieszkańców**. Mediana opóźnienia dostarczonych zgłoszeń to 13 min. Potwierdzenie „przyjęto” wraca do **97%** zgłaszających, których zgłoszenie dotarło.
4. W modelu (adopcja 30%, zasięg 40 m, 5 kurierów, 5 seedów) do punktu ewakuacji dociera **59%** mieszkańców miasta: 21% to osoby z aplikacją, a 38% osoby bez aplikacji poinformowane ustnie przez domowników i sąsiadów. To założenie modelu: bez przekazu ustnego ewakuuje się 21%, a gdy informują się tylko domownicy – 43%.
5. We wszystkich 225 uruchomieniach pełnej siatki fałszywy alert uznało za zweryfikowany **0 urządzeń** (dostało go: mediana 63 urządzeń w bezpośrednim zasięgu trolla).

## Od jakiej adopcji system ma sens

Kryterium (umowne, przy 5 kurierach): połowa telefonów z aplikacją ma alert **najpóźniej godzinę po jego wydaniu**, a po 6 h ma go **co najmniej 90% telefonów z aplikacją** (mediany między seedami). Sam zasięg na koniec nie wystarcza: przy małej adopcji alert roznoszą głównie kurierzy i trwa to godzinami.

| Zasięg radia | Najmniejsza badana adopcja spełniająca kryterium |
|---|---|
| 25 m | nie osiągnięto (do 50%) |
| 40 m | 50% |
| 80 m | 5% |

**Próg w modelu przy zasięgu 40 m i 5 kurierach: adopcja 50%.** To najmniejsza z badanych wartości, a nie dokładna granica.
Przy adopcji 30% kryterium nie jest spełnione (za mały zasięg): połowa telefonów ma alert po 34 min (33–47), a zasięg na koniec wynosi 88.1%.

Uwagi: (1) próg zależy od zasięgu radia bardziej niż od czegokolwiek innego, a zasięgu w zabudowie nie znamy; (2) próg dotyczy sytuacji z kurierami w terenie; (3) nawet powyżej progu sama aplikacja obejmuje tylko swoich użytkowników, czyli przy adopcji 30% najwyżej 30% mieszkańców; reszta zależy od przekazu ustnego i innych kanałów.

## 1. Czas do zasięgu 50% i 90% telefonów z aplikacją (5 kurierów)

| Adopcja | Zasięg | Czas do 50% | Czas do 90% | Zasięg po 6 h |
|---|---|---|---|---|
| 5% | 25 m | 231 min (143–343) | nie osiągnięto | 55.2% (50.3–62.8) |
| 5% | 40 m | 67 min (58–86) | nie osiągnięto | 79.7% (75.2–86.0) |
| 5% | 80 m | 27 min (21–28) | 225 min (182–277), tylko 3/5 przebiegów | 91.7% (88.0–94.3) |
| 10% | 25 m | 188 min (127–279) | nie osiągnięto | 60.1% (55.5–60.9) |
| 10% | 40 m | 47 min (33–104) | nie osiągnięto | 83.0% (80.1–83.4) |
| 10% | 80 m | 21 min (16–25) | 195 min (182–214), tylko 4/5 przebiegów | 92.4% (89.6–94.0) |
| 20% | 25 m | 128 min (99–178) | nie osiągnięto | 68.5% (64.3–71.2) |
| 20% | 40 m | 35 min (33–50) | nie osiągnięto | 85.5% (84.7–88.1) |
| 20% | 80 m | 20 min (16–22) | 168 min (116–240) | 95.3% (92.2–97.1) |
| 30% | 25 m | 94 min (64–128) | nie osiągnięto | 73.3% (71.3–77.4) |
| 30% | 40 m | 34 min (33–47) | 329 min (329–329), tylko 1/5 przebiegów | 88.1% (86.2–90.2) |
| 30% | 80 m | 17 min (13–18) | 200 min (145–218) | 94.1% (92.3–95.5) |
| 50% | 25 m | 58 min (45–76) | nie osiągnięto | 78.6% (76.2–80.4) |
| 50% | 40 m | 29 min (26–36) | 302 min (223–337), tylko 4/5 przebiegów | 90.7% (89.2–94.0) |
| 50% | 80 m | 14 min (13–15) | 100 min (61–115) | 95.9% (94.2–98.4) |

![Czas do zasięgu w funkcji adopcji](wykresy/adopcja_czas_pl.png)

![Zasięg alertu w funkcji adopcji i zasięgu radia](wykresy/adopcja_zasieg_pl.png)

## 2. Zgłoszenia dostarczone do PCZK (zasięg 40 m)

Odsetek zgłoszeń wysłanych do danej chwili, które do tej chwili dotarły do PCZK (czas od awarii sieci). Kurierzy patrolują całe miasto i punkt ewakuacji. Liczba zgłoszeń rośnie z zasięgiem alertu, więc odsetki łączne z różnych wierszy nie są wprost porównywalne.

| Adopcja | Kurierzy | Zgłoszeń (mediana) | Po 1 h | Po 3 h | Po 6 h | „Potrzebuję pomocy” | Mediana opóźnienia dostarczonych |
|---|---|---|---|---|---|---|---|
| 5% | 2 | 67 | 0.0% (0.0–80.0) | 87.0% (84.6–96.5) | 96.8% (92.9–100.0) | 70.0% (55.6–100.0) | 16 min |
| 5% | 5 | 80 | 76.0% (66.7–91.9) | 97.0% (92.6–98.6) | 96.2% (90.9–98.8) | 62.5% (45.5–83.3) | 11 min |
| 5% | 10 | 88 | 80.0% (73.1–90.2) | 98.8% (95.0–100.0) | 100.0% (97.8–100.0) | 100.0% (83.3–100.0) | 8 min |
| 10% | 2 | 144 | 3.1% (0.0–87.5) | 89.1% (82.1–98.6) | 96.7% (89.6–99.3) | 71.4% (58.8–91.7) | 18 min |
| 10% | 5 | 161 | 74.7% (67.9–86.0) | 97.3% (94.4–98.5) | 97.5% (96.6–98.8) | 88.9% (61.5–94.7) | 11 min |
| 10% | 10 | 184 | 86.2% (76.7–92.7) | 97.8% (96.4–98.8) | 98.5% (96.9–99.5) | 88.9% (66.7–93.8) | 9 min |
| 20% | 2 | 338 | 4.2% (0.0–86.0) | 90.2% (88.0–96.6) | 97.6% (95.9–98.7) | 80.8% (76.5–88.9) | 18 min |
| 20% | 5 | 351 | 71.8% (69.5–84.6) | 97.3% (93.6–99.4) | 98.5% (98.0–99.2) | 90.2% (82.9–94.7) | 12 min |
| 20% | 10 | 377 | 86.4% (81.2–89.0) | 99.0% (96.7–99.2) | 99.5% (98.5–99.7) | 94.1% (87.1–100.0) | 9 min |
| 30% | 2 | 518 | 7.5% (1.6–72.0) | 92.6% (88.0–97.7) | 98.1% (95.8–98.8) | 89.1% (81.8–94.8) | 20 min |
| 30% | 5 | 552 | 61.9% (55.8–74.1) | 97.9% (96.6–99.2) | 98.8% (98.0–99.3) | 94.9% (79.5–97.0) | 13 min |
| 30% | 10 | 584 | 83.9% (77.7–88.3) | 99.1% (98.5–99.6) | 99.1% (99.0–99.7) | 93.3% (89.7–96.2) | 10 min |
| 50% | 2 | 909 | 5.8% (3.4–53.8) | 89.6% (86.7–95.4) | 99.2% (99.1–99.7) | 94.6% (92.2–96.5) | 26 min |
| 50% | 5 | 976 | 46.1% (44.4–66.6) | 98.7% (97.7–99.4) | 99.3% (98.5–99.4) | 94.4% (91.4–96.3) | 16 min |
| 50% | 10 | 995 | 73.0% (70.3–76.0) | 99.1% (98.8–99.4) | 99.3% (99.2–99.7) | 94.2% (93.5–99.0) | 11 min |

![Zgłoszenia w PCZK w funkcji liczby kurierów](wykresy/kurierzy_zgloszenia_pl.png)

## 3. Potwierdzenia (Ack), które wróciły do zgłaszających (zasięg 40 m)

Odsetek zgłoszeń dostarczonych do PCZK, których autor dostał podpisane potwierdzenie „przyjęto”.

| Adopcja | 2 kurierów | 5 kurierów | 10 kurierów |
|---|---|---|---|
| 5% | 95.1% (89.4–97.0) | 97.6% (96.1–100.0) | 97.7% (96.4–98.9) |
| 10% | 98.6% (92.4–99.3) | 97.8% (96.1–99.4) | 99.0% (97.5–100.0) |
| 20% | 96.3% (94.5–97.1) | 97.4% (95.0–98.4) | 98.7% (97.1–99.4) |
| 30% | 96.6% (94.0–97.6) | 97.4% (96.9–97.8) | 98.2% (97.1–98.5) |
| 50% | 96.8% (94.3–97.8) | 97.9% (96.9–98.3) | 98.4% (97.6–98.6) |

## 4. Fałszywe alerty

- urządzenia, które uznały fałszywy alert za zweryfikowany: **0** (maksimum ze wszystkich 225 uruchomień pełnej siatki; oczekiwane 0)
- urządzenia, które go odebrały i oznaczyły jako niezweryfikowany: mediana 63, najwięcej 256
- żadne urządzenie nie rozpoczęło ewakuacji ani nie zmieniło stanu z powodu fałszywego alertu (test automatyczny)

## 5. Co daje który mechanizm (adopcja 30%, zasięg 40 m, 5 kurierów, 5 seedów)

| Wariant | Zasięg alertu (telefony z aplikacją) | Czas do 50% | Mieszkańcy w punkcie ewakuacji | Zgłoszenia w PCZK |
|---|---|---|---|---|
| Bez Sztafety: tylko zasięg huba, zgłoszenia osobiście | 2.5% (2.3–3.3) | nie osiągnięto | 3.9% (2.8–4.9) | 0.0% (0.0–5.0) |
| Same telefony, bez kurierów | 60.1% (53.8–61.0) | 176 min (162–208) | 40.6% (37.6–43.5) | 3.3% (2.7–4.3) |
| Sami kurierzy, bez przekazywania telefon–telefon | 71.4% (68.2–74.1) | 109 min (92–129) | 50.2% (49.0–51.4) | 87.2% (86.2–91.0) |
| Pełna Sztafeta: telefony i kurierzy | 88.1% (86.2–90.2) | 34 min (33–47) | 59.5% (59.0–59.8) | 98.8% (98.0–99.3) |

- **Bez Sztafety**: telefony nie przekazują pakietów, alert dostaje tylko urządzenie w zasięgu huba, zgłoszenie trzeba zanieść osobiście. Wariant nie obejmuje syren, megafonów ani obchodu służb – to dolna granica, nie opis tego, co się wydarzyło.
- **Same telefony**: sieć niesiona wyłącznie ruchem mieszkańców. Nikt nie zbiera zgłoszeń po drodze, więc do PCZK trafiają tylko te, których nosiciel znalazł się w zasięgu huba.
- **Sami kurierzy**: kurier przekazuje alert telefonom, które mija, i zbiera od nich zgłoszenia, ale telefony nie podają niczego dalej. Odsetek zgłoszeń liczymy od zgłoszeń wysłanych, a tych jest mniej, gdy alert ma mniej osób.

## 6. Wrażliwość na założenia (adopcja 30%, zasięg 40 m, 5 kurierów, 5 seedów)

Po jednej zmianie względem ustawień odniesienia. Tych założeń nie da się dziś sprawdzić w terenie, a wpływają na wynik podobnie mocno jak zasięg radia.

| Wariant | Zasięg alertu (telefony z aplikacją) | Czas do 50% | Mieszkańcy w punkcie ewakuacji | Zgłoszenia w PCZK |
|---|---|---|---|---|
| Ustawienia odniesienia | 88.1% (86.2–90.2) | 34 min (33–47) | 59.5% (59.0–59.8) | 98.8% (98.0–99.3) |
| Bez przekazu ustnego | 87.0% (86.2–91.0) | 33 min (29–46) | 21.2% (19.9–21.8) | 98.6% (96.4–99.4) |
| Przekaz ustny tylko między domownikami | 87.1% (85.5–90.0) | 34 min (31–40) | 42.6% (41.5–44.1) | 98.5% (97.8–99.3) |
| Okno skanowania 5 s co 60 s (zamiast 10 s) | 86.2% (84.4–87.6) | 39 min (37–51) | 58.0% (57.9–59.8) | 98.9% (97.1–99.1) |
| Okno skanowania 5 s co 120 s | 76.9% (74.5–77.9) | 76 min (65–99) | 51.6% (51.0–53.7) | 97.8% (93.5–98.2) |
| Zestawianie połączenia 8–15 s (zamiast 3–8 s) | 86.9% (86.2–89.9) | 38 min (36–58) | 58.4% (57.6–59.1) | 98.4% (97.0–98.9) |

## Koszt i mechanizmy, które w tym scenariuszu nie zadziałały

- średnia bateria telefonów z aplikacją po 6 h: mediana 50% (start: 35–100%). To prosta konsekwencja założonego zużycia, a nie wynik symulacji; rozładowane telefony: najwięcej 0 w jednym uruchomieniu
- łączny transfer w mieście: mediana 6.0 MB na uruchomienie; 76% transferów to potwierdzenia (każdy Ack rozchodzi się po całym mieście, choć dotyczy najwyżej 32 zgłaszających) – to miejsce do optymalizacji
- pakiety usunięte z przepełnionych buforów: najwięcej 0 w jednym uruchomieniu. Limit bufora, limit skoków i czasy życia pakietów są dłuższe niż potrzeby scenariusza 6-godzinnego, więc przegląd ich nie testuje (robią to testy jednostkowe)
- czas obliczeń jednego uruchomienia: mediana 20 s

Pliki źródłowe: `results/batch/runs.csv` (każde uruchomienie) i `results/batch/summary.csv` (agregacja).
