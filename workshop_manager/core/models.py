"""Site-wide settings the administrator edits in the panel (PRD §7.8, §7.5).

One row (`pk=1`), created by `seed_defaults` and read through `SiteSettings.load()`. The SMTP
password is stored encrypted (`core.crypto`) and never shown again after saving.
"""

from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone

from workshop_manager.core import consents, crypto


class SmtpSecurity(models.TextChoices):
    STARTTLS = "starttls", "STARTTLS (zwykle port 587)"
    SSL = "ssl", "SSL/TLS (zwykle port 465)"
    NONE = "none", "brak (tylko serwer w sieci lokalnej)"


class AdminNotifications(models.TextChoices):
    IMMEDIATE = "immediate", "od razu po każdym zgłoszeniu"
    DAILY = "daily", "raz dziennie — podsumowanie nowych zgłoszeń"
    OFF = "off", "nie wysyłaj"


class SiteSettings(models.Model):
    # --- Organisation ---
    org_name = models.CharField(
        "pełna nazwa organizatora",
        max_length=200,
        default="Chrześcijańskie Stowarzyszenie Twórców Sztuki Sakralnej „Ecclesia”",
    )
    org_short_name = models.CharField(
        "nazwa skrócona",
        max_length=100,
        default="Stowarzyszenie Ecclesia",
        help_text="W nagłówku strony i jako nazwa nadawcy e-maili, jeśli nie podano innej.",
    )
    org_address = models.CharField("adres", max_length=250, blank=True)
    contact_email = models.EmailField(
        "e-mail kontaktowy",
        blank=True,
        help_text="Pokazywany uczestnikom jako adres do kontaktu z organizatorem.",
    )
    contact_phone = models.CharField("telefon kontaktowy", max_length=32, blank=True)
    logo = models.ImageField(
        "logo",
        upload_to="site/",
        blank=True,
        help_text="Plik PNG lub JPG, najlepiej poziomy, do ok. 400 px szerokości.",
    )

    # --- Bank account ---
    bank_account_holder = models.CharField("odbiorca przelewu", max_length=200, blank=True)
    bank_account_number = models.CharField(
        "numer konta", max_length=40, blank=True, help_text="Np. 12 3456 7890 1234 5678 9012 3456"
    )

    # --- Consents (PRD §8) ---
    privacy_policy_url = models.URLField(
        "link do polityki prywatności", default=consents.PRIVACY_POLICY_URL
    )
    privacy_text = models.TextField(
        "zgoda na przetwarzanie danych (klauzula w formularzu)", default=consents.PRIVACY_TEXT
    )
    privacy_version = models.CharField(
        "wersja klauzuli", max_length=20, default=consents.PRIVACY_VERSION, editable=False
    )
    marketing_text = models.CharField(
        "zgoda na informacje o kolejnych warsztatach",
        max_length=300,
        default=consents.MARKETING_TEXT,
    )

    # --- Outgoing mail (PRD §7.5, §13) ---
    smtp_enabled = models.BooleanField(
        "wysyłaj przez poniższy serwer SMTP",
        default=False,
        help_text="Wyłączone = poczta idzie przez serwer skonfigurowany przy instalacji.",
    )
    smtp_host = models.CharField("serwer SMTP", max_length=200, blank=True)
    smtp_port = models.PositiveIntegerField("port", default=587)
    smtp_security = models.CharField(
        "szyfrowanie", max_length=10, choices=SmtpSecurity.choices, default=SmtpSecurity.STARTTLS
    )
    smtp_username = models.CharField("użytkownik", max_length=200, blank=True)
    smtp_password_encrypted = models.TextField("hasło (zaszyfrowane)", blank=True, editable=False)
    from_name = models.CharField(
        "nazwa nadawcy", max_length=100, blank=True, help_text="Np. „Warsztaty Ecclesia”."
    )
    from_email = models.EmailField(
        "adres nadawcy",
        blank=True,
        help_text="Musi być adresem, z którego serwer SMTP pozwala wysyłać (zwykle ten sam co "
        "użytkownik).",
    )
    reply_to = models.EmailField(
        "odpowiedzi kieruj na (Reply-To)",
        blank=True,
        help_text="Gdy uczestnik kliknie „Odpowiedz”. Puste = adres nadawcy.",
    )

    # --- Administrator notifications ---
    admin_notifications = models.CharField(
        "powiadomienia o nowych zgłoszeniach",
        max_length=10,
        choices=AdminNotifications.choices,
        default=AdminNotifications.IMMEDIATE,
    )
    admin_notification_email = models.EmailField(
        "wysyłaj powiadomienia na adres",
        blank=True,
        help_text="Puste = e-mail kontaktowy organizatora.",
    )
    last_digest_at = models.DateTimeField(null=True, blank=True, editable=False)

    updated_at = models.DateTimeField("zmieniono", auto_now=True)

    class Meta:
        verbose_name = "ustawienia"
        verbose_name_plural = "ustawienia"

    def __str__(self) -> str:
        return "Ustawienia"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.pk = 1
        previous = SiteSettings.objects.filter(pk=1).values_list("privacy_text", flat=True).first()
        if previous is not None and previous.strip() != self.privacy_text.strip():
            # A new wording is a new version; consents given before keep the old one.
            self.privacy_version = timezone.localtime().strftime("%Y-%m-%d %H:%M")
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "SiteSettings":
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    # --- SMTP password -------------------------------------------------------------------------

    @property
    def smtp_password(self) -> str:
        return crypto.decrypt(self.smtp_password_encrypted)

    def set_smtp_password(self, value: str) -> None:
        self.smtp_password_encrypted = crypto.encrypt(value)

    @property
    def has_smtp_password(self) -> bool:
        return bool(self.smtp_password_encrypted)

    # --- Derived values ------------------------------------------------------------------------

    def uses_own_smtp(self) -> bool:
        return self.smtp_enabled and bool(self.smtp_host)

    def admin_recipient(self) -> str:
        return self.admin_notification_email or self.contact_email

    def logo_url(self) -> str:
        """Absolute address of the logo, as e-mails need it; empty without a logo."""
        if not self.logo:
            return ""
        return absolute_url(self.logo.url)


def absolute_url(path: str) -> str:
    """`path` on the public site (`SITE_URL`) — links in e-mails must be absolute."""
    if path.startswith(("http://", "https://")):
        return path
    return f"{settings.SITE_URL}/{path.lstrip('/')}"
