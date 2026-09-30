"""Demonstration data for DEV and TEST (PLAN §2.3) — never run it on production.

Three icon workshops (finished, ongoing, upcoming) with made-up people at `@example.com` in
every status. Idempotent: a workshop that already exists (by title) is left alone. No e-mails
are queued — the data is written directly, not through the form or the decision services.
"""

import random
from datetime import date, time, timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from workshop_manager.applications.models import Answer, Application, Participant, Status
from workshop_manager.core.management.commands.seed_defaults import ICON_TEMPLATE
from workshop_manager.forms_builder.models import FormTemplate
from workshop_manager.workshops.models import Location, Session, Workshop, WorkshopType
from workshop_manager.workshops.services import create_workshop

FIRST_NAMES = ["Anna", "Maria", "Katarzyna", "Barbara", "Teresa", "Jan", "Piotr", "Ewa", "Zofia"]
LAST_NAMES = [
    "Przykładowa",
    "Testowa",
    "Pokazowa",
    "Wzorcowa",
    "Próbna",
    "Demonstracyjna",
    "Ćwiczebna",
    "Szkicowa",
]

#: (title, first session relative to today in days, number of days, applications per level)
WORKSHOPS = [
    ("Pokaz: Ikona Zwiastowania (zakończone)", -40, 3, 6),
    ("Pokaz: Rekolekcje z ikoną (trwające)", 0, 3, 7),
    ("Pokaz: Ikona Bożego Narodzenia", 30, 4, 8),
]


class Command(BaseCommand):
    help = "Create demonstration workshops and applications (DEV/TEST only)."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        rng = random.Random(2026)  # the same data on every run  # noqa: S311
        workshop_type = WorkshopType.objects.filter(name="Ikonopisanie").first()
        if workshop_type is None:
            self.stderr.write("Run seed_defaults first.")
            return
        template = FormTemplate.objects.filter(name=ICON_TEMPLATE).first()
        location = Location.objects.filter(is_active=True).first()
        today = timezone.localdate()
        people = self._people()
        created = 0
        for title, offset, days, per_level in WORKSHOPS:
            if Workshop.objects.filter(title=title).exists():
                continue
            workshop = create_workshop(
                workshop_type=workshop_type, title=title, template=template, location=location
            )
            workshop.description = "Warsztat pokazowy z danymi przykładowymi."
            workshop.leader = "o. Przykładowy SJ"
            workshop.publish_at = timezone.now() - timedelta(days=60)
            workshop.save()
            first = today + timedelta(days=offset)
            for day in range(days):
                Session.objects.create(
                    workshop=workshop,
                    date=first + timedelta(days=day),
                    start_time=time(9, 30),
                    end_time=time(17, 0),
                )
            free = list(people)
            for level in workshop.levels.all():
                level.capacity = 4
                level.price = 450 if level.order == 0 else 520
                level.save()
                chosen = rng.sample(free, per_level)
                free = [p for p in free if p not in chosen]  # one application per person
                self._applications(workshop, level, chosen, first, rng)
            created += 1
        self.stdout.write(f"Demonstration workshops created: {created}.")

    def _people(self) -> list[Participant]:
        people = []
        for i, (first, last) in enumerate(
            (f, lname) for lname in LAST_NAMES for f in FIRST_NAMES[:5]
        ):
            person, _ = Participant.objects.get_or_create(
                email=f"demo{i + 1}@example.com",
                defaults={"first_name": first, "last_name": last, "phone": f"600 000 {i:03d}"},
            )
            people.append(person)
        return people

    def _applications(
        self, workshop: Workshop, level: Any, people: list[Participant], first: date, rng: Any
    ) -> None:
        plan = [Status.ACCEPTED] * 4 + [Status.WAITLISTED, Status.REJECTED, Status.WITHDRAWN]
        plan += [Status.WAITLISTED]
        if first > timezone.localdate():
            plan = [Status.ACCEPTED] * 3 + [Status.NEW, Status.NEW, Status.NEW]
            plan += [Status.WAITLISTED, Status.REJECTED]
        questions = list(workshop.questions.filter(is_active=True))
        position = 0
        for person, status in zip(people, plan, strict=False):
            if Application.objects.filter(workshop=workshop, participant=person).exists():
                continue
            if status == Status.WAITLISTED:
                position += 1
            application = Application.objects.create(
                workshop=workshop,
                level=level,
                participant=person,
                first_name=person.first_name,
                last_name=person.last_name,
                email=person.email,
                phone=person.phone,
                adult_confirmed=True,
                privacy_consent_at=timezone.now(),
                privacy_consent_version="demo",
                status=status,
                waitlist_position=position if status == Status.WAITLISTED else None,
                is_seen=status != Status.NEW,
            )
            for order, question in enumerate(questions):
                if question.level_id not in (None, level.pk):
                    continue
                choices = question.choice_list()
                value = rng.choice(choices) if choices else "Odpowiedź przykładowa."
                Answer.objects.create(
                    application=application,
                    question=question,
                    label=question.label,
                    value=value,
                    order=order,
                )
