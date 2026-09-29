"""Applications for workshops (PRD §5, §6.3, §7.3).

A `Participant` is a person known by their email address, with or without an account. An
`Application` keeps a snapshot of the contact details given at the time and the answers, with
each question's wording copied, so later edits of the form never change what someone wrote.
"""

from typing import Any

from django.conf import settings
from django.db import models
from django.db.models import Q


class Participant(models.Model):
    email = models.EmailField("adres e-mail", unique=True)
    first_name = models.CharField("imię", max_length=100)
    last_name = models.CharField("nazwisko", max_length=100)
    phone = models.CharField("telefon", max_length=32, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="konto",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="participant",
    )
    marketing_consent = models.BooleanField("zgoda na informacje o warsztatach", default=False)
    marketing_consent_at = models.DateTimeField("data zgody na informacje", null=True, blank=True)
    created_at = models.DateTimeField("utworzono", auto_now_add=True)
    updated_at = models.DateTimeField("zmieniono", auto_now=True)

    class Meta:
        verbose_name = "uczestnik"
        verbose_name_plural = "uczestnicy"
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} <{self.email}>"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Status(models.TextChoices):
    NEW = "new", "nowe"
    ACCEPTED = "accepted", "przyjęte"
    WAITLISTED = "waitlisted", "lista rezerwowa"
    REJECTED = "rejected", "odrzucone"
    WITHDRAWN = "withdrawn", "wycofane"
    CANCELLED = "cancelled", "anulowane"


#: Applications that hold (or wait for) a place — what counts against a level's capacity and
#: what blocks a second application from the same address.
ACTIVE_STATUSES = [Status.NEW, Status.ACCEPTED, Status.WAITLISTED]


class Application(models.Model):
    workshop = models.ForeignKey(
        "workshops.Workshop",
        verbose_name="warsztat",
        on_delete=models.PROTECT,
        related_name="applications",
    )
    level = models.ForeignKey(
        "workshops.Level",
        verbose_name="poziom",
        on_delete=models.PROTECT,
        related_name="applications",
    )
    participant = models.ForeignKey(
        Participant,
        verbose_name="uczestnik",
        on_delete=models.PROTECT,
        related_name="applications",
    )
    # Snapshot of the contact details as given in this application.
    first_name = models.CharField("imię", max_length=100)
    last_name = models.CharField("nazwisko", max_length=100)
    email = models.EmailField("adres e-mail")
    phone = models.CharField("telefon", max_length=32, blank=True)
    remarks = models.TextField("uwagi do zgłoszenia", blank=True)
    adult_confirmed = models.BooleanField("potwierdzenie pełnoletności", default=False)
    privacy_consent_at = models.DateTimeField("zgoda na przetwarzanie danych")
    privacy_consent_version = models.CharField("wersja klauzuli", max_length=20)
    marketing_consent = models.BooleanField("zgoda na informacje o warsztatach", default=False)

    status = models.CharField(
        "status", max_length=12, choices=Status.choices, default=Status.NEW, db_index=True
    )
    is_seen = models.BooleanField("przejrzane", default=False)
    admin_notes = models.TextField("notatki organizatora", blank=True)
    submitted_at = models.DateTimeField("data zgłoszenia", auto_now_add=True)
    updated_at = models.DateTimeField("zmieniono", auto_now=True)

    class Meta:
        verbose_name = "zgłoszenie"
        verbose_name_plural = "zgłoszenia"
        ordering = ["submitted_at"]
        constraints = [
            # One live application per person and workshop (a withdrawn one may be followed by
            # a new one).
            models.UniqueConstraint(
                fields=["workshop", "participant"],
                condition=Q(status__in=ACTIVE_STATUSES),
                name="one_active_application_per_person",
            )
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} — {self.workshop}"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Answer(models.Model):
    application = models.ForeignKey(
        Application, verbose_name="zgłoszenie", on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(
        "forms_builder.Question",
        verbose_name="pytanie",
        null=True,
        on_delete=models.SET_NULL,
        related_name="answers",
    )
    label = models.CharField("treść pytania", max_length=300)
    value = models.TextField("odpowiedź", blank=True)
    order = models.PositiveSmallIntegerField("kolejność", default=0)

    class Meta:
        verbose_name = "odpowiedź"
        verbose_name_plural = "odpowiedzi"
        ordering = ["order", "pk"]

    def __str__(self) -> str:
        return f"{self.label}: {self.value[:50]}"
