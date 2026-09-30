"""Applications for workshops (PRD §5, §6.3, §7.3).

A `Participant` is a person known by their email address, with or without an account. An
`Application` keeps a snapshot of the contact details given at the time and the answers, with
each question's wording copied, so later edits of the form never change what someone wrote.
"""

from typing import Any

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


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

#: Which status an application may move to from each status (PRD §7.3). "Withdrawn" is the
#: participant's own decision — the administrator records it when told by phone or e-mail.
TRANSITIONS: dict[str, list[str]] = {
    Status.NEW: [Status.ACCEPTED, Status.WAITLISTED, Status.REJECTED, Status.WITHDRAWN],
    Status.ACCEPTED: [Status.WAITLISTED, Status.CANCELLED, Status.WITHDRAWN],
    Status.WAITLISTED: [Status.ACCEPTED, Status.REJECTED, Status.WITHDRAWN],
    Status.REJECTED: [Status.ACCEPTED, Status.WAITLISTED],
    Status.WITHDRAWN: [Status.ACCEPTED, Status.WAITLISTED],
    Status.CANCELLED: [Status.ACCEPTED, Status.WAITLISTED],
}

#: The button that leads to each status, as the administrator reads it.
ACTION_LABELS: dict[str, str] = {
    Status.ACCEPTED: "Przyjmij",
    Status.WAITLISTED: "Na listę rezerwową",
    Status.REJECTED: "Odrzuć",
    Status.CANCELLED: "Anuluj udział",
    Status.WITHDRAWN: "Zapisz rezygnację",
}


class Source(models.TextChoices):
    FORM = "form", "formularz na stronie"
    PANEL = "panel", "dodane w panelu"


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
    waitlist_position = models.PositiveIntegerField(
        "miejsce na liście rezerwowej", null=True, blank=True
    )
    source = models.CharField("źródło", max_length=8, choices=Source.choices, default=Source.FORM)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="dodane przez",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
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

    def get_panel_url(self) -> str:
        return reverse("panel:application_detail", args=[self.pk])

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def allowed_transitions(self) -> list[tuple[str, str]]:
        """(status, button label) pairs for the decisions available now."""
        return [(status, ACTION_LABELS[status]) for status in TRANSITIONS[self.status]]


class StatusChange(models.Model):
    """One entry in an application's history: a new status, or a level or data correction.

    For corrections `old_status` equals `new_status` and `comment` says what changed.
    """

    application = models.ForeignKey(
        Application, verbose_name="zgłoszenie", on_delete=models.CASCADE, related_name="history"
    )
    old_status = models.CharField("poprzedni status", max_length=12, choices=Status.choices)
    new_status = models.CharField("nowy status", max_length=12, choices=Status.choices)
    comment = models.TextField("komentarz", blank=True)
    notified = models.BooleanField("wysłano powiadomienie", default=False)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="kto",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    changed_at = models.DateTimeField("kiedy", default=timezone.now)

    class Meta:
        verbose_name = "zmiana w zgłoszeniu"
        verbose_name_plural = "historia zgłoszeń"
        ordering = ["changed_at", "pk"]

    def __str__(self) -> str:
        return f"{self.application}: {self.old_status} → {self.new_status}"

    @property
    def is_status_change(self) -> bool:
        return self.old_status != self.new_status


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
