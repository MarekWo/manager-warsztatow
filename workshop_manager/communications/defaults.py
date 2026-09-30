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
}

#: Placeholders about the organiser, available in every template.
SITE_PLACEHOLDERS: dict[str, str] = {
    "organizacja": "nazwa organizatora (skrócona)",
    "kontakt": "e-mail kontaktowy organizatora",
    "konto_bankowe": "odbiorca i numer konta",
}

PLACEHOLDERS: dict[str, dict[str, str]] = {
    TemplateKey.APPLICATION_RECEIVED: APPLICATION_PLACEHOLDERS | SITE_PLACEHOLDERS,
    TemplateKey.ADMIN_NEW_APPLICATION: APPLICATION_PLACEHOLDERS
    | {"link_do_zgloszenia": "adres zgłoszenia w panelu"}
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

Jeśli chcesz coś zmienić w zgłoszeniu, po prostu odpowiedz na tę wiadomość.

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
}
