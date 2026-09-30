"""The chapters of the in-app help (PRD §7.10), in reading order.

Each chapter is a template in `templates/help/panel/<slug>.html`; sections inside carry ids,
so a "?" next to a field (`{% help_link "slug" "section" %}`) opens the right place. The help
is part of the definition of done: a change in the panel updates its chapter.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Chapter:
    slug: str
    title: str
    summary: str
    icon: str

    @property
    def template(self) -> str:
        return f"help/panel/{self.slug}.html"


CHAPTERS = [
    Chapter(
        "pierwsze-kroki",
        "Pierwsze kroki",
        "Jak zbudowany jest panel i jak wygląda cały cykl jednego warsztatu.",
        "signpost-split",
    ),
    Chapter(
        "warsztaty",
        "Jak utworzyć warsztat",
        "Nowy warsztat albo kopia poprzedniego, terminy, poziomy, publikacja i zapisy.",
        "easel",
    ),
    Chapter(
        "formularz",
        "Jak ustawić formularz",
        "Pola standardowe, pytania dodatkowe, pytania dla jednego poziomu, szablony.",
        "ui-checks",
    ),
    Chapter(
        "zgloszenia",
        "Jak rozpatrywać zgłoszenia",
        "Statusy, decyzje z e-mailem, lista rezerwowa, zgłoszenia telefoniczne, dziennik.",
        "people",
    ),
    Chapter(
        "uczestnicy",
        "Uczestnicy i ich konta",
        "Jak uczestnicy się logują, co widzą w „Moich warsztatach”, rezygnacje, kartoteka.",
        "person-lines-fill",
    ),
    Chapter(
        "wiadomosci",
        "Jak wysłać wiadomość do uczestników",
        "Grupy odbiorców, pola z danymi, załącznik, podgląd przed wysyłką.",
        "send",
    ),
    Chapter(
        "wydruki",
        "Wydruki i eksporty",
        "Excel, lista obecności, lista kontaktowa, zestawienie materiałów.",
        "printer",
    ),
    Chapter(
        "poczta",
        "Ustawienia poczty i treść e-maili",
        "Serwer SMTP, hasło aplikacji, wiadomość testowa, szablony e-maili, dziennik wysyłki.",
        "envelope",
    ),
    Chapter(
        "ustawienia",
        "Ustawienia i słowniki",
        "Dane organizatora, logo, konto bankowe, rodzaje warsztatów, szablony, miejsca.",
        "gear",
    ),
    Chapter(
        "rodo",
        "RODO — dane osobowe",
        "Zgody i ich wersje, kopia danych osoby, usuwanie danych, wypis z informacji.",
        "shield-lock",
    ),
    Chapter(
        "pytania",
        "Najczęstsze pytania",
        "Krótkie odpowiedzi na typowe sytuacje.",
        "question-circle",
    ),
]

BY_SLUG = {chapter.slug: chapter for chapter in CHAPTERS}
