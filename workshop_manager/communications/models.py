"""E-mail templates and the log of every e-mail sent (PRD §7.5).

`EmailTemplate` holds the wording the administrator edits (plain text with `{placeholders}`).
`EmailMessage` is both the queue and the log: a row is written in the same transaction as the
change that caused it, the worker sends it after the commit, and a failure only schedules
another attempt — sending never blocks an application or a decision.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class TemplateKey(models.TextChoices):
    APPLICATION_RECEIVED = "application_received", "Potwierdzenie otrzymania zgłoszenia"
    ADMIN_NEW_APPLICATION = "admin_new_application", "Powiadomienie o nowym zgłoszeniu"
    ADMIN_DAILY_DIGEST = "admin_daily_digest", "Dzienne podsumowanie zgłoszeń"


class EmailTemplate(models.Model):
    key = models.CharField("rodzaj", max_length=40, choices=TemplateKey.choices, unique=True)
    subject = models.CharField("temat", max_length=200)
    body = models.TextField(
        "treść",
        help_text="Zwykły tekst. Pusta linia rozpoczyna nowy akapit, adresy stron stają się "
        "linkami. Pola w nawiasach klamrowych zostaną zastąpione danymi.",
    )
    updated_at = models.DateTimeField("zmieniono", auto_now=True)

    class Meta:
        verbose_name = "szablon e-maila"
        verbose_name_plural = "szablony e-maili"
        ordering = ["key"]

    def __str__(self) -> str:
        return self.get_key_display()


class MessageStatus(models.TextChoices):
    QUEUED = "queued", "w kolejce"
    SENDING = "sending", "wysyłanie"
    SENT = "sent", "wysłano"
    FAILED = "failed", "błąd"


class EmailMessage(models.Model):
    to_email = models.EmailField("odbiorca")
    to_name = models.CharField("nazwa odbiorcy", max_length=200, blank=True)
    subject = models.CharField("temat", max_length=250)
    body_text = models.TextField("treść")
    body_html = models.TextField("treść HTML", blank=True)
    reply_to = models.EmailField("Reply-To", blank=True)
    template_key = models.CharField(
        "szablon", max_length=40, choices=TemplateKey.choices, blank=True
    )
    application = models.ForeignKey(
        "applications.Application",
        verbose_name="zgłoszenie",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="emails",
    )

    status = models.CharField(
        "status",
        max_length=10,
        choices=MessageStatus.choices,
        default=MessageStatus.QUEUED,
        db_index=True,
    )
    attempts = models.PositiveSmallIntegerField("próby", default=0)
    last_error = models.TextField("ostatni błąd", blank=True)
    next_attempt_at = models.DateTimeField("następna próba", default=timezone.now, db_index=True)
    created_at = models.DateTimeField("utworzono", auto_now_add=True)
    sent_at = models.DateTimeField("wysłano", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="nadawca w panelu",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        verbose_name = "e-mail"
        verbose_name_plural = "e-maile"
        ordering = ["-created_at", "-pk"]

    def __str__(self) -> str:
        return f"{self.subject} → {self.to_email}"

    @property
    def is_retrying(self) -> bool:
        """Queued again after a failed attempt (the panel shows the error and the next try)."""
        return self.status == MessageStatus.QUEUED and self.attempts > 0
