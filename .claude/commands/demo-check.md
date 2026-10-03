---
description: Sprawdź, czy scenariusz demo działa od początku do końca
---
Uruchom `uv run sztafeta run --preset flood-stronie --seed 42` i na podstawie `events.jsonl`, metryk i snapshotów sprawdź, że:
1. Alert podpisany przez PCZK startuje z huba i rozchodzi się falą; mieszkańcy, którzy go dostali, zaczynają ewakuację.
2. Alert trolla trafia na urządzenia, ale żadne nie uznaje go za zweryfikowany i nie wywołuje ewakuacji.
3. Mieszkańcy generują zgłoszenia SAFE / NEED_HELP.
4. Kurier zbiera zgłoszenia i po dotarciu do huba są one dostarczone do PCZK (zdeduplikowane).
5. Ack wraca do przynajmniej części zgłaszających.
6. `sztafeta inspect` dla losowego agenta zwraca stan zgodny ze zdarzeniami.
7. Drugie uruchomienie z tym samym seedem daje identyczne metryki.
8. `sztafeta animate` generuje animację, na której widać kroki 1–5.
Wypisz listę OK / PROBLEM. Problemy napraw, jeśli są w zakresie scenariusza demo; resztę opisz.
