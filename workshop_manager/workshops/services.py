"""Creating and duplicating workshops (PRD §7.2) — the operations that touch several models."""

from datetime import date, timedelta
from typing import Any

from django.db import transaction

from workshop_manager.forms_builder.models import FormTemplate, Question, copy_template
from workshop_manager.workshops.models import Level, Session, Workshop, WorkshopType

#: A workshop's own fields that a duplicate takes over as they are.
_COPIED_FIELDS = [
    "type",
    "subtitle",
    "description",
    "leader",
    "show_leader",
    "location",
    "show_location",
    "program",
    "show_program",
    "what_to_bring",
    "show_what_to_bring",
    "accommodation",
    "show_accommodation",
    "notes",
    "show_notes",
    "cover_image",
    "show_cover_image",
    "phone_mode",
    "adult_confirmation_mode",
    "remarks_mode",
]


@transaction.atomic
def create_workshop(
    *,
    workshop_type: WorkshopType,
    title: str,
    template: FormTemplate | None,
    user: Any = None,
    location: Any = None,
) -> Workshop:
    """A new draft with the type's default levels and the template's questions."""
    workshop = Workshop.objects.create(
        type=workshop_type, title=title, location=location, created_by=user
    )
    names = workshop_type.level_names() or ["Wszyscy uczestnicy"]
    for order, name in enumerate(names):
        Level.objects.create(workshop=workshop, name=name, order=order)
    if template is not None:
        copy_template(template, workshop)
    return workshop


@transaction.atomic
def duplicate_workshop(
    source: Workshop, *, title: str, first_date: date | None, user: Any = None
) -> Workshop:
    """A draft copy of `source`: levels, questions, sections and sessions.

    Sessions keep their weekdays and spacing and move so that the first one falls on
    `first_date` (unchanged when it is None). Publication and registration dates are never
    copied: the copy is a draft until the administrator schedules it.
    """
    copy = Workshop(title=title, created_by=user)
    for field in _COPIED_FIELDS:
        setattr(copy, field, getattr(source, field))
    copy.save()

    sessions = source.ordered_sessions()
    shift = timedelta(0)
    if first_date is not None and sessions:
        shift = first_date - sessions[0].date
    Session.objects.bulk_create(
        Session(
            workshop=copy,
            date=session.date + shift,
            start_time=session.start_time,
            end_time=session.end_time,
            note=session.note,
        )
        for session in sessions
    )

    level_map: dict[int, Level] = {}
    for level in source.levels.all():
        level_map[level.pk] = Level.objects.create(
            workshop=copy,
            name=level.name,
            description=level.description,
            capacity=level.capacity,
            price=level.price,
            price_note=level.price_note,
            order=level.order,
        )
    for question in source.questions.all():
        Question.objects.create(
            workshop=copy,
            level=level_map.get(question.level_id) if question.level_id else None,
            is_active=question.is_active,
            **question.copy_fields(),
        )
    return copy
