---
description: Przegląd parametrów symulacji i liczby do prezentacji dla jury
---
Uruchom `uv run sztafeta batch` $ARGUMENTS (jeśli brak argumentów: domyślny przegląd
adopcja 5/10/20/30/50% × zasięg 25/40/80 m × kurierzy 2/5/10, po 5 seedów na kombinację; równolegle przez multiprocessing).

Następnie zaktualizuj `docs/WYNIKI.md` i wygeneruj wykresy do `results/batch/plots/`:
1. Tabela: czas do zasięgu 50% i 90% mieszkańców z aplikacją (mediana i rozrzut między seedami).
2. Odsetek zgłoszeń dostarczonych do PCZK po 1 h i 3 h oraz mediana opóźnienia.
3. Odsetek potwierdzeń (Ack), które wróciły do mieszkańców.
4. Fałszywe alerty uznane za zweryfikowane (oczekiwane 0 – jeśli więcej, to błąd: zgłoś go).
5. Sekcja „Liczby na slajd”: 3–5 zdań gotowych do prezentacji, każde z parametrami, przy których zachodzi,
   sformułowane uczciwie („w modelu, przy założeniach X”).
6. Próg adopcji, od którego system zaczyna mieć sens – wskaż go wprost.
Nie zaokrąglaj wyników na korzyść projektu.
