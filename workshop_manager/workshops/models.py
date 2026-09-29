"""Workshops: what is announced, when, where, for whom (PRD §5, §7.2).

A workshop's publication state is never stored: it follows from its dates at the moment of the
request (`Workshop.state()`), so a workshop scheduled for 9:00 is public at 9:00 without any
background job (PLAN D6).
"""

from datetime import date, datetime, time
from typing import Any

from django.conf import settings
from django.db import models
from django.db.models import Max, Min, Q
from django.urls import reverse
from django.utils import timezone

from workshop_manager.core.text import unique_slug


class WorkshopType(models.Model):
    """Iconography, gilding, mosaic, … — a dictionary the administrator can extend."""

    name = models.CharField("nazwa", max_length=100, unique=True)
    default_levels = models.TextField(
        "domyślne poziomy",
        blank=True,
        help_text="Jeden poziom w wierszu, np. „Początkujący”. Nowy warsztat tego rodzaju "
        "dostanie te poziomy na start.",
    )
    default_form_template = models.ForeignKey(
        "forms_builder.FormTemplate",
        verbose_name="domyślny szablon formularza",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    order = models.PositiveSmallIntegerField("kolejność", default=0)
    is_active = models.BooleanField("aktywny", default=True)

    class Meta:
        verbose_name = "rodzaj warsztatów"
        verbose_name_plural = "rodzaje warsztatów"
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name

    def level_names(self) -> list[str]:
        return [line.strip() for line in self.default_levels.splitlines() if line.strip()]


class Location(models.Model):
    """Where workshops take place — reusable, never hard-coded (client's answer B4)."""

    name = models.CharField("nazwa", max_length=150)
    address = models.CharField("adres", max_length=250)
    map_url = models.URLField("link do mapy", blank=True)
    directions = models.TextField("wskazówki dojazdu", blank=True)
    is_active = models.BooleanField("aktywne", default=True)

    class Meta:
        verbose_name = "miejsce"
        verbose_name_plural = "miejsca"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name}, {self.address}"


class FieldMode(models.TextChoices):
    REQUIRED = "required", "wymagane"
    OPTIONAL = "optional", "opcjonalne"
    HIDDEN = "hidden", "ukryte"


class WorkshopQuerySet(models.QuerySet["Workshop"]):
    # `Any`: django-stubs cannot follow annotations such as `first_date` into later lookups.
    def with_dates(self) -> Any:
        return self.annotate(first_date=Min("sessions__date"), last_date=Max("sessions__date"))

    def public(self, now: datetime | None = None) -> "WorkshopQuerySet":
        """What the home page lists: published, not archived, not over yet."""
        now = now or timezone.now()
        today = timezone.localdate(now)
        return (
            self.filter(publish_at__lte=now, is_archived=False)
            .with_dates()
            .filter(last_date__gte=today)
            .order_by("first_date", "title")
        )

    def in_tab(self, tab: str, now: datetime | None = None) -> "WorkshopQuerySet":
        """The administrator's list tabs (PRD §7.2)."""
        now = now or timezone.now()
        today = timezone.localdate(now)
        qs = self.with_dates()
        if tab == "archived":
            return qs.filter(is_archived=True).order_by("-last_date")
        qs = qs.filter(is_archived=False)
        if tab == "draft":
            return qs.filter(publish_at__isnull=True).order_by("-updated_at")
        if tab == "scheduled":
            return qs.filter(publish_at__gt=now).order_by("publish_at")
        if tab == "finished":
            return qs.filter(publish_at__lte=now, last_date__lt=today).order_by("-last_date")
        # "published": public now, including those whose sessions are not set yet.
        return (
            qs.filter(publish_at__lte=now)
            .filter(Q(last_date__gte=today) | Q(last_date__isnull=True))
            .order_by("first_date")
        )


class Workshop(models.Model):
    type = models.ForeignKey(
        WorkshopType, verbose_name="rodzaj", on_delete=models.PROTECT, related_name="workshops"
    )
    title = models.CharField("tytuł", max_length=200)
    subtitle = models.CharField(
        "podtytuł",
        max_length=250,
        blank=True,
        help_text="Np. „Warsztaty ikonopisania dla początkujących i zaawansowanych”.",
    )
    slug = models.SlugField("adres strony", max_length=220, unique=True, editable=False)

    description = models.TextField(
        "opis",
        blank=True,
        help_text="Zwykły tekst. Pusta linia rozpoczyna nowy akapit, adresy stron stają się "
        "linkami.",
    )
    leader = models.CharField("prowadzący", max_length=200, blank=True)
    show_leader = models.BooleanField("pokazuj prowadzącego", default=True)
    location = models.ForeignKey(
        Location,
        verbose_name="miejsce",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="workshops",
    )
    show_location = models.BooleanField("pokazuj miejsce", default=True)

    # Optional sections (PRD §6.2): shown when switched on and not empty.
    program = models.TextField("program", blank=True)
    show_program = models.BooleanField("pokazuj program", default=False)
    what_to_bring = models.TextField("co zabrać", blank=True)
    show_what_to_bring = models.BooleanField("pokazuj „co zabrać”", default=False)
    accommodation = models.TextField("noclegi i wyżywienie", blank=True)
    show_accommodation = models.BooleanField("pokazuj noclegi i wyżywienie", default=False)
    notes = models.TextField(
        "uwagi organizacyjne",
        blank=True,
        help_text="Np. cena, numer konta, termin wpłaty, „deska płatna osobno”.",
    )
    show_notes = models.BooleanField("pokazuj uwagi organizacyjne", default=True)
    cover_image = models.ImageField("zdjęcie", upload_to="workshops/", blank=True)
    show_cover_image = models.BooleanField("pokazuj zdjęcie", default=True)

    # Publication and registration window (PRD §7.2).
    publish_at = models.DateTimeField(
        "publikacja od",
        null=True,
        blank=True,
        help_text="Od tej chwili warsztat jest widoczny na liście. Puste = szkic.",
    )
    registration_opens_at = models.DateTimeField(
        "zapisy od", null=True, blank=True, help_text="Puste = od chwili publikacji."
    )
    registration_closes_at = models.DateTimeField(
        "zapisy do", null=True, blank=True, help_text="Puste = do rozpoczęcia pierwszego spotkania."
    )
    registration_closed = models.BooleanField(
        "zapisy zamknięte ręcznie",
        default=False,
        help_text="Zamyka zapisy od razu, niezależnie od dat.",
    )
    is_cancelled = models.BooleanField("odwołany", default=False)
    cancellation_note = models.CharField("informacja o odwołaniu", max_length=250, blank=True)
    is_archived = models.BooleanField("w archiwum", default=False)

    # Standard fields of the application form (PRD §6.3); name, email and consent are always on.
    phone_mode = models.CharField(
        "telefon", max_length=10, choices=FieldMode.choices, default=FieldMode.REQUIRED
    )
    adult_confirmation_mode = models.CharField(
        "potwierdzenie pełnoletności",
        max_length=10,
        choices=[(FieldMode.REQUIRED, "wymagane"), (FieldMode.HIDDEN, "ukryte")],
        default=FieldMode.REQUIRED,
    )
    remarks_mode = models.CharField(
        "uwagi do zgłoszenia",
        max_length=10,
        choices=[(FieldMode.OPTIONAL, "opcjonalne"), (FieldMode.HIDDEN, "ukryte")],
        default=FieldMode.OPTIONAL,
    )

    created_at = models.DateTimeField("utworzono", auto_now_add=True)
    updated_at = models.DateTimeField("zmieniono", auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="utworzył(a)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    objects = WorkshopQuerySet.as_manager()

    class Meta:
        verbose_name = "warsztat"
        verbose_name_plural = "warsztaty"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            self.slug = unique_slug(Workshop, self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("public:workshop", kwargs={"slug": self.slug})

    # --- Dates ---------------------------------------------------------------------------------

    def ordered_sessions(self) -> list["Session"]:
        """Sessions by date; uses a prefetch when there is one."""
        return sorted(self.sessions.all(), key=lambda s: (s.date, s.start_time))

    def first_session_date(self) -> date | None:
        sessions = self.ordered_sessions()
        return sessions[0].date if sessions else None

    def last_session_date(self) -> date | None:
        sessions = self.ordered_sessions()
        return sessions[-1].date if sessions else None

    def starts_at(self) -> datetime | None:
        sessions = self.ordered_sessions()
        return sessions[0].starts_at() if sessions else None

    def ends_at(self) -> datetime | None:
        sessions = self.ordered_sessions()
        return max(s.ends_at() for s in sessions) if sessions else None

    # --- Publication and registration ----------------------------------------------------------

    def state(self, now: datetime | None = None) -> str:
        """draft · scheduled · published · finished · archived (cancellation is a flag on top)."""
        now = now or timezone.now()
        if self.is_archived:
            return "archived"
        if self.publish_at is None:
            return "draft"
        if self.publish_at > now:
            return "scheduled"
        ends = self.ends_at()
        if ends is not None and ends < now:
            return "finished"
        return "published"

    def state_label(self, now: datetime | None = None) -> str:
        return STATE_LABELS[self.state(now)]

    def is_public(self, now: datetime | None = None) -> bool:
        return self.state(now) in ("published", "finished")

    def registration_opens(self) -> datetime | None:
        return self.registration_opens_at or self.publish_at

    def registration_closes(self) -> datetime | None:
        return self.registration_closes_at or self.starts_at()

    def registration_status(self, now: datetime | None = None) -> str:
        """not_published · closed · not_yet · open · over (PRD §6.1 card badge)."""
        now = now or timezone.now()
        if self.state(now) != "published":
            return "not_published"
        if self.is_cancelled or self.registration_closed:
            return "closed"
        opens, closes = self.registration_opens(), self.registration_closes()
        if opens is not None and now < opens:
            return "not_yet"
        if closes is not None and now >= closes:
            return "over"
        return "open"

    def is_registration_open(self, now: datetime | None = None) -> bool:
        return self.registration_status(now) == "open"

    # --- Sections ------------------------------------------------------------------------------

    def visible_sections(self) -> list[tuple[str, str]]:
        """(heading, text) of the optional sections to show on the public page, in order."""
        sections = [
            ("Program", self.program, self.show_program),
            ("Co zabrać", self.what_to_bring, self.show_what_to_bring),
            ("Noclegi i wyżywienie", self.accommodation, self.show_accommodation),
            ("Informacje organizacyjne", self.notes, self.show_notes),
        ]
        return [(heading, text) for heading, text, shown in sections if shown and text.strip()]


STATE_LABELS = {
    "draft": "szkic",
    "scheduled": "zaplanowany",
    "published": "opublikowany",
    "finished": "zakończony",
    "archived": "w archiwum",
}


class Session(models.Model):
    """One meeting of a workshop: dates and hours are always shown (client's answer B4)."""

    workshop = models.ForeignKey(
        Workshop, verbose_name="warsztat", on_delete=models.CASCADE, related_name="sessions"
    )
    date = models.DateField("data")
    start_time = models.TimeField("od godziny")
    end_time = models.TimeField("do godziny")
    note = models.CharField("uwaga", max_length=150, blank=True)

    class Meta:
        verbose_name = "spotkanie"
        verbose_name_plural = "spotkania"
        ordering = ["date", "start_time"]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_time__gt=models.F("start_time")),
                name="session_ends_after_it_starts",
            )
        ]

    def __str__(self) -> str:
        return f"{self.date:%d.%m.%Y} {self.start_time:%H:%M}–{self.end_time:%H:%M}"

    def _aware(self, moment: time) -> datetime:
        return timezone.make_aware(datetime.combine(self.date, moment))

    def starts_at(self) -> datetime:
        return self._aware(self.start_time)

    def ends_at(self) -> datetime:
        return self._aware(self.end_time)


class Level(models.Model):
    """A group within a workshop with its own capacity and price (client's answer B3)."""

    workshop = models.ForeignKey(
        Workshop, verbose_name="warsztat", on_delete=models.CASCADE, related_name="levels"
    )
    name = models.CharField("nazwa", max_length=100)
    description = models.CharField("opis", max_length=250, blank=True)
    capacity = models.PositiveSmallIntegerField(
        "limit miejsc",
        null=True,
        blank=True,
        help_text="Tylko wskazówka — zgłoszeń ponad limit system nie blokuje.",
    )
    price = models.DecimalField("cena (zł)", max_digits=8, decimal_places=2, null=True, blank=True)
    price_note = models.CharField(
        "uwaga do ceny", max_length=150, blank=True, help_text="Np. „deska płatna osobno”."
    )
    order = models.PositiveSmallIntegerField("kolejność", default=0)

    class Meta:
        verbose_name = "poziom"
        verbose_name_plural = "poziomy"
        ordering = ["order", "pk"]

    def __str__(self) -> str:
        return self.name

    @property
    def price_display(self) -> str:
        if self.price is None:
            return ""
        whole = self.price == self.price.to_integral_value()
        amount = f"{self.price:.0f}" if whole else f"{self.price:.2f}".replace(".", ",")
        return f"{amount} zł"
