"""Recording an application (PRD §6.3)."""

from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from workshop_manager.applications.forms import ApplicationForm
from workshop_manager.applications.models import (
    ACTIVE_STATUSES,
    Answer,
    Application,
    Participant,
)
from workshop_manager.communications import notifications


class DuplicateApplication(Exception):
    """The address already has a live application for this workshop."""


def has_active_application(workshop: Any, email: str) -> bool:
    return Application.objects.filter(
        workshop=workshop, participant__email=email.strip().lower(), status__in=ACTIVE_STATUSES
    ).exists()


def submit_application(form: ApplicationForm, *, user: Any = None) -> Application:
    """Store a valid form as a new application; raise `DuplicateApplication` for a repeat.

    The confirmation e-mail and the organiser's notification are queued in the same
    transaction and sent by the worker after the commit.

    The participant is found by email. Their stored name and phone follow the latest
    application unless they have an account — then only they may change their details
    (Stage 5), not whoever types their address into a form.
    """
    data = form.cleaned_data
    workshop = form.workshop
    email = data["email"]
    now = timezone.now()
    if has_active_application(workshop, email):
        raise DuplicateApplication
    try:
        with transaction.atomic():
            participant, created = Participant.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "phone": data.get("phone", ""),
                },
            )
            if not created and participant.user_id is None:
                participant.first_name = data["first_name"]
                participant.last_name = data["last_name"]
                participant.phone = data.get("phone") or participant.phone
            if data.get("marketing") and not participant.marketing_consent:
                participant.marketing_consent = True
                participant.marketing_consent_at = now
            if user is not None and user.is_authenticated and user.email == email:
                participant.user = user
            participant.save()

            application = Application.objects.create(
                workshop=workshop,
                level=data["level"],
                participant=participant,
                first_name=data["first_name"],
                last_name=data["last_name"],
                email=email,
                phone=data.get("phone", ""),
                remarks=data.get("remarks", ""),
                adult_confirmed=bool(data.get("adult")),
                privacy_consent_at=now,
                privacy_consent_version=form.privacy_version,
                marketing_consent=bool(data.get("marketing")),
            )
            Answer.objects.bulk_create(
                Answer(
                    application=application,
                    question=question,
                    label=question.label,
                    value=value,
                    order=order,
                )
                for order, (question, value) in enumerate(form.answers())
            )
            notifications.application_submitted(application)
    except IntegrityError as error:  # two submissions racing past the check above
        raise DuplicateApplication from error
    return application
