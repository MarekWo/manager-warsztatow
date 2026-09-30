"""The default wording of every e-mail template and the placeholders each one may use.

`seed_defaults` creates missing templates from `DEFAULTS`; "Przywróć domyślną treść" in the
panel copies them back. Placeholders are written in Polish, as the administrator sees them.
"""

from workshop_manager.communications.models import TemplateKey

#: Placeholders available in every e-mail about an application.
APPLICATION_PLACEHOLDERS: dict[str, str] = {
    "imie": "imię uczestnika",
    "nazwisko": "nazwisko uczestnika",
    "imie_nazwisko": "imię i nazwisko",
    "email": "adres e-mail uczestnika",
    "telefon": "telefon uczestnika",
    "warsztat": "tytuł warsztatu",
    "terminy": "lista spotkań (daty i godziny), każde w osobnym wierszu",
    "miejsce": "miejsce warsztatu z adresem",
    "poziom": "wybrany poziom",
    "cena": "cena wybranego poziomu",
    "odpowiedzi": "kopia zgłoszenia: dane kontaktowe i odpowiedzi na pytania",
    "uwagi": "uwagi wpisane w zgłoszeniu",
    "data_zgloszenia": "data i godzina wysłania zgłoszenia",
    "link_do_warsztatu": "adres strony warsztatu",
    "link_rezygnacji": "link, którym uczestnik może zrezygnować (także bez konta)",
    "link_do_konta": "adres strony „Moje warsztaty”",
}

#: Placeholders about the organiser, available in every template.
SITE_PLACEHOLDERS: dict[str, str] = {
    "organizacja": "nazwa organizatora (skrócona)",
    "kontakt": "e-mail kontaktowy organizatora",
    "konto_bankowe": "odbiorca i numer konta",
}

#: Decisions: the application's data, and the place on the waiting list.
DECISION_PLACEHOLDERS: dict[str, str] = (
    APPLICATION_PLACEHOLDERS
    | {"miejsce_na_liscie": "numer na liście rezerwowej (w e-mailu o liście rezerwowej)"}
    | SITE_PLACEHOLDERS
)

DECISION_KEYS = [
    TemplateKey.DECISION_ACCEPTED,
    TemplateKey.DECISION_WAITLISTED,
    TemplateKey.DECISION_REJECTED,
    TemplateKey.DECISION_CANCELLED,
    TemplateKey.WITHDRAWAL_CONFIRMED,
]

PLACEHOLDERS: dict[str, dict[str, str]] = {
    **dict.fromkeys(DECISION_KEYS, DECISION_PLACEHOLDERS),
    TemplateKey.APPLICATION_RECEIVED: APPLICATION_PLACEHOLDERS | SITE_PLACEHOLDERS,
    TemplateKey.ADMIN_NEW_APPLICATION: APPLICATION_PLACEHOLDERS
    | {"link_do_zgloszenia": "adres zgłoszenia w panelu"}
    | SITE_PLACEHOLDERS,
    TemplateKey.ADMIN_WITHDRAWAL: APPLICATION_PLACEHOLDERS
    | {
        "link_do_zgloszenia": "adres zgłoszenia w panelu",
        "powod": "powód podany przez uczestnika",
        "pierwszy_z_rezerwy": "pierwsza osoba z listy rezerwowej tego poziomu (jeśli zwolniło się "
        "miejsce)",
    }
    | SITE_PLACEHOLDERS,
    TemplateKey.ADMIN_DAILY_DIGEST: {
        "liczba": "liczba nowych zgłoszeń",
        "lista_zgloszen": "lista nowych zgłoszeń (osoba, warsztat, poziom)",
        "link_do_panelu": "adres panelu administratora",
    }
    | SITE_PLACEHOLDERS,
}

#: Who receives each kind of e-mail — shown next to the template in the panel.
RECIPIENTS: dict[str, str] = {
    TemplateKey.APPLICATION_RECEIVED: "uczestnik, zaraz po wysłaniu formularza",
    TemplateKey.ADMIN_NEW_APPLICATION: "organizator, gdy powiadomienia są ustawione na „od razu”",
    TemplateKey.ADMIN_DAILY_DIGEST: "organizator, wieczorem, gdy powiadomienia są ustawione na "
    "„raz dziennie”",
    TemplateKey.DECISION_ACCEPTED: "uczestnik, po przyjęciu zgłoszenia",
    TemplateKey.DECISION_WAITLISTED: "uczestnik, po wpisaniu na listę rezerwową",
    TemplateKey.DECISION_REJECTED: "uczestnik, po odrzuceniu zgłoszenia",
    TemplateKey.DECISION_CANCELLED: "uczestnik, gdy organizator anuluje jego udział",
    TemplateKey.WITHDRAWAL_CONFIRMED: "uczestnik, po rezygnacji (własnej lub zapisanej przez "
    "organizatora)",
    TemplateKey.ADMIN_WITHDRAWAL: "organizator, gdy uczestnik sam zrezygnuje",
}

DEFAULTS: dict[str, tuple[str, str]] = {
    TemplateKey.APPLICATION_RECEIVED: (
        "Otrzymaliśmy Twoje zgłoszenie: {warsztat}",
        """Dzień dobry {imie},

dziękujemy za zgłoszenie na warsztaty „{warsztat}”. Zgłoszenie trafiło do organizatora — o jego \
decyzji poinformujemy Cię osobnym e-mailem.

Terminy spotkań:
{terminy}

Miejsce: {miejsce}

Kopia Twojego zgłoszenia:
{odpowiedzi}

Strona warsztatów: {link_do_warsztatu}

Jeśli chcesz coś zmienić w zgłoszeniu, po prostu odpowiedz na tę wiadomość. Swoje zgłoszenia \
zobaczysz też po zalogowaniu: {link_do_konta}

Jeśli jednak nie możesz wziąć udziału, zrezygnuj tutaj: {link_rezygnacji}

Z serdecznymi pozdrowieniami
{organizacja}""",
    ),
    TemplateKey.ADMIN_NEW_APPLICATION: (
        "Nowe zgłoszenie: {imie_nazwisko} — {warsztat}",
        """Nowe zgłoszenie na warsztaty „{warsztat}” (poziom: {poziom}).

{odpowiedzi}

Wysłano: {data_zgloszenia}
Zgłoszenie w panelu: {link_do_zgloszenia}""",
    ),
    TemplateKey.ADMIN_DAILY_DIGEST: (
        "Nowe zgłoszenia na warsztaty ({liczba})",
        """Od ostatniego podsumowania wpłynęły nowe zgłoszenia ({liczba}):

{lista_zgloszen}

Panel administratora: {link_do_panelu}""",
    ),
}

DEFAULTS.update(
    {
        TemplateKey.DECISION_ACCEPTED: (
            "Zgłoszenie przyjęte: {warsztat}",
            """Dzień dobry {imie},

z radością informujemy, że Twoje zgłoszenie na warsztaty „{warsztat}” (poziom: {poziom}) \
zostało przyjęte.

Terminy spotkań:
{terminy}

Miejsce: {miejsce}

Cena: {cena}
Dane do przelewu:
{konto_bankowe}

Szczegóły warsztatów: {link_do_warsztatu}

Jeśli nie możesz wziąć udziału, prosimy o jak najszybszą informację — odpowiedz na tę \
wiadomość albo zrezygnuj tutaj: {link_rezygnacji} — Twoje miejsce otrzyma osoba z listy \
rezerwowej.

Do zobaczenia!
{organizacja}""",
        ),
        TemplateKey.DECISION_WAITLISTED: (
            "Lista rezerwowa: {warsztat}",
            """Dzień dobry {imie},

dziękujemy za zgłoszenie na warsztaty „{warsztat}” (poziom: {poziom}). Wszystkie miejsca są \
już zajęte, dlatego wpisaliśmy Cię na listę rezerwową (miejsce na liście: {miejsce_na_liscie}).

Jeśli ktoś zrezygnuje, odezwiemy się do Ciebie — nie musisz nic robić. Jeśli wolisz \
już nie czekać, zrezygnuj tutaj: {link_rezygnacji}

Terminy spotkań:
{terminy}

Z serdecznymi pozdrowieniami
{organizacja}""",
        ),
        TemplateKey.DECISION_REJECTED: (
            "Zgłoszenie na warsztaty: {warsztat}",
            """Dzień dobry {imie},

dziękujemy za zgłoszenie na warsztaty „{warsztat}”. Niestety tym razem nie możemy go przyjąć.

Zapraszamy na kolejne warsztaty — aktualną listę znajdziesz na naszej stronie.

Z serdecznymi pozdrowieniami
{organizacja}""",
        ),
        TemplateKey.DECISION_CANCELLED: (
            "Anulowanie udziału w warsztatach: {warsztat}",
            """Dzień dobry {imie},

informujemy, że Twój udział w warsztatach „{warsztat}” (poziom: {poziom}) został anulowany.

W razie pytań odpowiedz na tę wiadomość.

Z serdecznymi pozdrowieniami
{organizacja}""",
        ),
        TemplateKey.WITHDRAWAL_CONFIRMED: (
            "Potwierdzenie rezygnacji: {warsztat}",
            """Dzień dobry {imie},

potwierdzamy Twoją rezygnację z udziału w warsztatach „{warsztat}”. Dziękujemy za informację.

Zapraszamy na kolejne warsztaty.

Z serdecznymi pozdrowieniami
{organizacja}""",
        ),
    }
)

DEFAULTS[TemplateKey.ADMIN_WITHDRAWAL] = (
    "Rezygnacja: {imie_nazwisko} — {warsztat}",
    """{imie_nazwisko} rezygnuje z udziału w warsztatach „{warsztat}” (poziom: {poziom}).

Powód: {powod}

{pierwszy_z_rezerwy}

Zgłoszenie w panelu: {link_do_zgloszenia}""",
)

#: Example values for the preview in the panel (no real personal data).
SAMPLE_CONTEXT: dict[str, str] = {
    "imie": "Anna",
    "nazwisko": "Przykładowa",
    "imie_nazwisko": "Anna Przykładowa",
    "email": "anna.przykladowa@example.com",
    "telefon": "600 100 200",
    "warsztat": "Rekolekcje z ikoną — Boże Narodzenie",
    "terminy": "sobota, 28 listopada 2026, 10:00–16:00\nniedziela, 29 listopada 2026, 10:00–14:00",
    "miejsce": "Pracownia Stowarzyszenia Ecclesia, ul. Kopernika 26, Kraków",
    "poziom": "Początkujący",
    "cena": "450 zł",
    "odpowiedzi": "Imię i nazwisko: Anna Przykładowa\nE-mail: anna.przykladowa@example.com\n"
    "Telefon: 600 100 200\nPoziom: Początkujący\n"
    "Opisz dotychczasowe doświadczenia malarskie. Maluję akwarelą od kilku lat.",
    "uwagi": "Proszę o fakturę.",
    "data_zgloszenia": "30.09.2026, 18:45",
    "link_do_warsztatu": "https://warsztaty.example.com/warsztaty/rekolekcje-z-ikona/",
    "link_do_zgloszenia": "https://warsztaty.example.com/panel/",
    "liczba": "2",
    "lista_zgloszen": "• Anna Przykładowa — Rekolekcje z ikoną (Początkujący)\n"
    "• Jan Przykładowy — Rekolekcje z ikoną (Zaawansowani)",
    "link_do_panelu": "https://warsztaty.example.com/panel/",
    "miejsce_na_liscie": "2",
    "link_rezygnacji": "https://warsztaty.example.com/rezygnacja/przyklad/",
    "link_do_konta": "https://warsztaty.example.com/moje-warsztaty/",
    "powod": "Choroba w rodzinie.",
    "pierwszy_z_rezerwy": "Zwolniło się miejsce. Pierwsza osoba z listy rezerwowej: Jan "
    "Przykładowy (https://warsztaty.example.com/panel/zgloszenia/2/).",
}
