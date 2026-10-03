# Wyniki symulacji „Sztafeta” – przegląd parametrów

**To są wyniki modelu, nie pomiary z terenu.** Pokazują, jak system zachowuje się w symulacji przy założeniach opisanych w [MODEL.md](MODEL.md). Dokument jest generowany poleceniem `sztafeta batch` i nie jest poprawiany ręcznie; liczby nie są zaokrąglane na korzyść projektu.

## Co zostało policzone

- preset: `flood-stronie`, mapa: OpenStreetMap, Stronie Śląskie (© autorzy OpenStreetMap (ODbL))
- czas symulacji: 6 h od awarii sieci, 2999 mieszkańców
- adopcja: 5%, 10%, 20%, 30%, 50%
- zasięg radia: 25 m, 40 m, 80 m
- liczba kurierów: 2, 5, 10
- seedy: 5 na kombinację (1–5); łącznie 230 uruchomień
- wersja kodu: `0.1.0+ece1190`

W tabelach podajemy **medianę między seedami**, a w nawiasie **najmniejszą i największą wartość** (rozrzut). Czasy liczymy od wydania alertu.

## Liczby na slajd

1. W modelu (adopcja 30%, zasięg 40 m, 5 kurierów, 5 seedów) zweryfikowany alert po 6 h ma **85% telefonów z aplikacją** (rozrzut 82–86%), a w strefie zagrożenia **95%**. Połowa telefonów ma go po 43 min (34–64) od wydania.
2. Bez Sztafety (alert tylko w bezpośrednim zasięgu huba, te same założenia) jest to **2.8%** telefonów z aplikacją. To dolna granica: wariant bazowy nie obejmuje syren, megafonów ani chodzenia służb od drzwi do drzwi.
3. W modelu (adopcja 30%, zasięg 40 m, 5 kurierów, 5 seedów) do PCZK dociera **75% zgłoszeń** mieszkańców (po 3 h: 71.9% (69.2–77.4)), mediana opóźnienia 13 min. Potwierdzenie „przyjęto” wraca do **96%** zgłaszających, których zgłoszenie dotarło.
4. W modelu (adopcja 30%, zasięg 40 m, 5 kurierów, 5 seedów) ze strefy zagrożenia ewakuuje się **63%** mieszkańców (z aplikacją i bez; osoby bez aplikacji dowiadują się ustnie od sąsiadów – ten kanał liczymy osobno: 48% wszystkich mieszkańców).
5. We wszystkich 225 uruchomieniach ze Sztafetą fałszywy alert uznało za zweryfikowany **0 urządzeń** (dostało go: mediana 54 urządzeń w bezpośrednim zasięgu trolla).

## Od jakiej adopcji system ma sens

Kryterium (umowne, przy 5 kurierach): połowa telefonów z aplikacją ma alert **najpóźniej godzinę po jego wydaniu**, a po 6 h ma go **co najmniej 90% telefonów z aplikacją w strefie zagrożenia** (mediany między seedami). Sam zasięg na koniec nie wystarcza: przy małej adopcji alert roznoszą głównie kurierzy i trwa to godzinami.

| Zasięg radia | Najmniejsza badana adopcja spełniająca kryterium |
|---|---|
| 25 m | nie osiągnięto (do 50%) |
| 40 m | 20% |
| 80 m | 5% |

**Próg w modelu przy zasięgu 40 m: adopcja 20%.** To najmniejsza z badanych wartości, a nie dokładna granica.
Przy adopcji 10% połowa telefonów ma alert dopiero po 98 min (79–168), a zasięg w strefie zagrożenia wynosi 94%.

Uwaga: nawet powyżej progu sama aplikacja obejmuje tylko swoich użytkowników. Przy adopcji 30% oznacza to najwyżej 30% mieszkańców; reszta zależy od przekazu ustnego i innych kanałów.

## 1. Czas do zasięgu 50% i 90% telefonów z aplikacją (5 kurierów)

| Adopcja | Zasięg | Czas do 50% | Czas do 90% | Zasięg po 6 h | W strefie zagrożenia |
|---|---|---|---|---|---|
| 5% | 25 m | nie osiągnięto | nie osiągnięto | 42.4% (33.8–49.3) | 75.7% (60.0–80.0) |
| 5% | 40 m | 176 min (88–184) | nie osiągnięto | 62.8% (60.5–65.8) | 91.4% (83.3–92.1) |
| 5% | 80 m | 39 min (22–53) | nie osiągnięto | 79.6% (71.6–83.9) | 100.0% (86.7–100.0) |
| 10% | 25 m | 235 min (235–235), tylko 1/5 przebiegów | nie osiągnięto | 48.2% (42.3–56.0) | 73.2% (69.2–81.3) |
| 10% | 40 m | 98 min (79–168) | nie osiągnięto | 73.6% (62.3–75.2) | 93.9% (83.1–95.6) |
| 10% | 80 m | 35 min (18–62) | nie osiągnięto | 84.1% (74.2–89.4) | 98.5% (93.8–100.0) |
| 20% | 25 m | 183 min (153–212) | nie osiągnięto | 63.4% (59.2–69.0) | 81.4% (78.9–85.0) |
| 20% | 40 m | 54 min (47–71) | nie osiągnięto | 80.5% (77.4–82.6) | 96.9% (92.5–97.6) |
| 20% | 80 m | 25 min (17–30) | 241 min (241–241), tylko 1/5 przebiegów | 88.5% (84.3–92.9) | 98.8% (97.6–100.0) |
| 30% | 25 m | 127 min (102–169) | nie osiągnięto | 72.3% (67.3–76.1) | 85.8% (78.1–86.5) |
| 30% | 40 m | 43 min (34–64) | nie osiągnięto | 85.2% (82.5–85.7) | 95.0% (93.3–97.2) |
| 30% | 80 m | 18 min (14–26) | 251 min (116–324), tylko 4/5 przebiegów | 92.7% (88.9–96.5) | 98.7% (98.1–100.0) |
| 50% | 25 m | 78 min (61–103) | nie osiągnięto | 79.5% (76.7–86.1) | 87.0% (85.5–91.3) |
| 50% | 40 m | 36 min (30–46) | 325 min (318–343), tylko 3/5 przebiegów | 90.7% (86.1–92.8) | 96.6% (95.7–98.8) |
| 50% | 80 m | 15 min (11–19) | 246 min (113–296), tylko 4/5 przebiegów | 94.2% (88.6–98.2) | 99.7% (98.6–100.0) |

![Czas do zasięgu w funkcji adopcji](wykresy/adopcja_czas_pl.png)

![Zasięg alertu w funkcji adopcji i zasięgu radia](wykresy/adopcja_zasieg_pl.png)

## 2. Zgłoszenia dostarczone do PCZK (zasięg 40 m)

Odsetek zgłoszeń wysłanych do danej chwili, które do tej chwili dotarły do PCZK (czas od awarii sieci).

| Adopcja | Kurierzy | Zgłoszeń (mediana) | Po 1 h | Po 3 h | Po 6 h | „Potrzebuję pomocy” | Mediana opóźnienia |
|---|---|---|---|---|---|---|---|
| 5% | 2 | 33 | 42.9% (0.0–57.1) | 76.7% (62.5–83.3) | 84.6% (70.0–88.2) | 33.3% (0.0–50.0) | 22 min |
| 5% | 5 | 37 | 62.5% (28.6–84.6) | 87.5% (78.6–100.0) | 82.9% (64.7–94.3) | 66.7% (33.3–100.0) | 13 min |
| 5% | 10 | 38 | 70.6% (55.0–77.8) | 85.7% (70.3–93.5) | 85.3% (69.8–97.1) | 66.7% (0.0–100.0) | 10 min |
| 10% | 2 | 81 | 37.5% (0.0–52.4) | 71.7% (48.1–86.8) | 80.0% (69.8–83.1) | 71.4% (42.9–75.0) | 17 min |
| 10% | 5 | 88 | 63.9% (38.2–67.7) | 81.8% (63.0–91.8) | 80.6% (70.5–84.2) | 66.7% (40.0–83.3) | 12 min |
| 10% | 10 | 85 | 71.2% (61.4–82.9) | 77.3% (68.9–93.1) | 78.8% (68.9–88.5) | 75.0% (66.7–80.0) | 11 min |
| 20% | 2 | 175 | 38.8% (0.0–56.2) | 68.0% (63.6–77.0) | 75.9% (69.8–83.4) | 71.4% (60.0–92.9) | 23 min |
| 20% | 5 | 183 | 59.0% (47.3–62.0) | 75.9% (71.4–78.9) | 79.5% (72.1–81.7) | 72.7% (64.7–72.7) | 12 min |
| 20% | 10 | 190 | 68.8% (59.2–73.3) | 78.8% (70.9–79.9) | 79.7% (73.7–82.6) | 85.0% (75.0–90.9) | 12 min |
| 30% | 2 | 284 | 44.2% (3.2–55.1) | 67.1% (62.0–68.9) | 72.8% (71.0–76.1) | 81.8% (61.9–87.5) | 19 min |
| 30% | 5 | 294 | 52.8% (41.3–64.7) | 71.9% (69.2–77.4) | 75.3% (71.8–81.3) | 83.3% (55.0–95.0) | 13 min |
| 30% | 10 | 281 | 67.6% (63.7–73.5) | 77.9% (72.7–78.6) | 77.9% (75.0–79.8) | 81.2% (68.2–92.0) | 12 min |
| 50% | 2 | 505 | 45.6% (0.7–54.4) | 70.0% (60.7–73.5) | 73.0% (70.5–78.0) | 75.7% (68.6–86.1) | 19 min |
| 50% | 5 | 509 | 52.5% (47.5–67.7) | 72.3% (70.5–76.7) | 74.8% (71.7–78.0) | 85.4% (71.0–87.9) | 13 min |
| 50% | 10 | 517 | 63.7% (57.0–68.6) | 74.1% (69.3–76.1) | 78.0% (72.1–79.3) | 85.7% (64.3–94.9) | 13 min |

![Zgłoszenia w PCZK w funkcji liczby kurierów](wykresy/kurierzy_zgloszenia_pl.png)

## 3. Potwierdzenia (Ack), które wróciły do zgłaszających (zasięg 40 m)

Odsetek zgłoszeń dostarczonych do PCZK, których autor dostał podpisane potwierdzenie „przyjęto”.

| Adopcja | 2 kurierów | 5 kurierów | 10 kurierów |
|---|---|---|---|
| 5% | 96.4% (93.9–100.0) | 100.0% (97.0–100.0) | 93.3% (89.7–97.0) |
| 10% | 88.3% (85.9–94.2) | 96.1% (93.5–100.0) | 93.7% (91.0–98.5) |
| 20% | 96.6% (91.5–98.1) | 95.0% (90.6–99.3) | 96.1% (94.3–98.7) |
| 30% | 95.4% (94.3–97.6) | 95.8% (91.2–97.3) | 96.3% (94.8–98.1) |
| 50% | 96.9% (96.1–97.9) | 97.0% (95.8–97.8) | 96.2% (95.9–97.8) |

## 4. Fałszywe alerty

- urządzenia, które uznały fałszywy alert za zweryfikowany: **0** (maksimum ze wszystkich 225 uruchomień; oczekiwane 0)
- urządzenia, które go odebrały i oznaczyły jako niezweryfikowany: mediana 54, najwięcej 307
- żadne urządzenie nie rozpoczęło ewakuacji ani nie zmieniło stanu z powodu fałszywego alertu (test automatyczny)

## 5. Sztafeta kontra wariant bazowy (adopcja 30%, zasięg 40 m, 5 kurierów, 5 seedów)

| Miara | Sztafeta | Bez Sztafety |
|---|---|---|
| Zasięg alertu, telefony z aplikacją | 85.2% (82.5–85.7) | 2.8% (1.9–3.0) |
| Zasięg alertu w strefie zagrożenia | 95.0% (93.3–97.2) | 0.0% (0.0–0.0) |
| Ewakuowani ze strefy | 62.9% (56.9–65.4) | 0.0% (0.0–0.0) |
| Zgłoszenia dostarczone do PCZK | 75.3% (71.8–81.3) | 0.0% (0.0–17.6) |

Wariant bazowy: telefony nie przekazują pakietów między sobą, alert dostaje tylko urządzenie w zasięgu huba, zgłoszenie trzeba zanieść osobiście. Nie obejmuje syren, megafonów ani obchodu służb.

## Koszt

- średnia bateria telefonów z aplikacją po 6 h: mediana 51% (start: 35–100%)
- łączny transfer w mieście: mediana 2.9 MB na uruchomienie
- czas obliczeń jednego uruchomienia: mediana 10 s

Pliki źródłowe: `results/batch/runs.csv` (każde uruchomienie) i `results/batch/summary.csv` (agregacja).
