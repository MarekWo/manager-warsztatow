"""The administrator's decisions on applications (PRD §7.3).

Every change goes through this module, so each one is checked against `TRANSITIONS`, written to
the application's history and to the event log, and — when asked — followed by an e-mail queued
in the same transaction (sent by the worker after the commit, never blocking the decision).

The waiting list is kept per level: `waitlist_position` runs 1, 2, 3, … and is renumbered
whenever someone leaves the list, so the number is also the person's place in the queue.
"""

from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.db.models import Max

from workshop_manager.applications.models import (
    ACTIVE_STATUSES,
    TRANSITIONS,
    Application,
    Status,
    StatusChange,
)
from workshop_manager.communications.models import TemplateKey
from workshop_manager.communications.rendering import (
    RenderedEmail,
    application_context,
    render,
    site_context,
)
from workshop_manager.communications.services import get_template, queue_email
from workshop_manager.core import audit
from workshop_manager.core.models import SiteSettings

#: The e-mail that tells the participant about each status.
STATUS_TEMPLATES: dict[str, str] = {
    Status.ACCEPTED: TemplateKey.DECISION_ACCEPTED,
    Status.WAITLISTED: TemplateKey.DECISION_WAITLISTED,
    Status.REJECTED: TemplateKey.DECISION_REJECTED,
    Status.CANCELLED: TemplateKey.DECISION_CANCELLED,
    Status.WITHDRAWN: TemplateKey.WITHDRAWAL_CONFIRMED,
}

#: How the event log names each decision.
AUDIT_ACTIONS: dict[str, str] = {
    Status.NEW: "Przywrócono zgłoszenie jako nowe",
    Status.ACCEPTED: "Przyjęto zgłoszenie",
    Status.WAITLISTED: "Wpisano na listę rezerwową",
    Status.REJECTED: "Odrzucono zgłoszenie",
    Status.CANCELLED: "Anulowano udział",
    Status.WITHDRAWN: "Zapisano rezygnację",
}


class TransitionError(Exception):
    """The change is not allowed; the message is meant for the administrator."""


@dataclass
class EmailText:
    """A decision e-mail as the administrator saw (and possibly edited) it."""

    subject: str
    body: str


# --- Waiting list ------------------------------------------------------------------------------


def _waitlist(workshop_id: int, level_id: int) -> Any:
    return Application.objects.filter(
        workshop_id=workshop_id, level_id=level_id, status=Status.WAITLISTED
    ).order_by("waitlist_position", "submitted_at", "pk")


def _next_position(application: Application) -> int:
    last = _waitlist(application.workshop_id, application.level_id).aggregate(
        Max("waitlist_position")
    )["waitlist_position__max"]
    return (last or 0) + 1


def _renumber(workshop_id: int, level_id: int) -> None:
    for position, pk in enumerate(
        _waitlist(workshop_id, level_id).values_list("pk", flat=True), start=1
    ):
        Application.objects.filter(pk=pk).exclude(waitlist_position=position).update(
            waitlist_position=position
        )


def move_on_waitlist(application: Application, direction: str) -> None:
    """Swap the person with their neighbour on the level's waiting list."""
    if application.status != Status.WAITLISTED:
        return
    items = list(_waitlist(application.workshop_id, application.level_id))
    index = next(i for i, item in enumerate(items) if item.pk == application.pk)
    other = index - 1 if direction == "up" else index + 1
    if not 0 <= other < len(items):
        return
    items[index], items[other] = items[other], items[index]
    with transaction.atomic():
        for position, item in enumerate(items, start=1):
            if item.waitlist_position != position:
                Application.objects.filter(pk=item.pk).update(waitlist_position=position)


def first_waitlisted(level: Any) -> Application | None:
    return _waitlist(level.workshop_id, level.pk).first()


def free_places(level: Any) -> int | None:
    """Places left under the level's (soft) limit; None when the level has no limit."""
    if level.capacity is None:
        return None
    accepted = level.applications.filter(status=Status.ACCEPTED).count()
    return level.capacity - accepted


# --- Decisions ---------------------------------------------------------------------------------


def _check_transition(application: Application, new_status: str) -> None:
    if new_status not in TRANSITIONS[application.status]:
        raise TransitionError(
            f"Zgłoszenia o statusie „{application.get_status_display()}” nie można zmienić na "
            f"„{Status(new_status).label}”."
        )
    if new_status in ACTIVE_STATUSES and application.status not in ACTIVE_STATUSES:
        other = (
            Application.objects.filter(
                workshop_id=application.workshop_id,
                participant_id=application.participant_id,
                status__in=ACTIVE_STATUSES,
            )
            .exclude(pk=application.pk)
            .exists()
        )
        if other:
            raise TransitionError(
                "Ta osoba ma już inne aktywne zgłoszenie na ten warsztat — zmień najpierw tamto."
            )


def decision_email(application: Application, new_status: str) -> EmailText | None:
    """The e-mail the participant would get for `new_status`, with the data filled in."""
    key = STATUS_TEMPLATES.get(new_status)
    if key is None:
        return None
    template = get_template(key)
    context = application_context(application)
    if new_status == Status.WAITLISTED and application.status != Status.WAITLISTED:
        context["miejsce_na_liscie"] = str(_next_position(application))
    site = SiteSettings.load()
    rendered = render(template.subject, template.body, site_context(site) | context, site)
    return EmailText(subject=rendered.subject, body=rendered.text.rstrip("\n"))


def _queue_decision_email(
    application: Application, new_status: str, email: EmailText | None, user: Any
) -> bool:
    key = STATUS_TEMPLATES.get(new_status)
    if key is None:
        return False
    text = email or decision_email(application, new_status)
    if text is None:
        return False
    # Placeholders typed into the edited text are filled in too.
    site = SiteSettings.load()
    context = site_context(site) | application_context(application)
    rendered: RenderedEmail = render(text.subject, text.body, context, site)
    queue_email(
        to_email=application.email,
        to_name=application.full_name,
        subject=rendered.subject,
        text=rendered.text,
        html=rendered.html,
        template_key=key,
        application=application,
        created_by=user,
    )
    return True


def change_status(
    application: Application,
    new_status: str,
    *,
    user: Any,
    notify: bool = True,
    email: EmailText | None = None,
    comment: str = "",
) -> StatusChange:
    """Move the application to `new_status`; raise `TransitionError` if that is not allowed.

    `email` is the text edited in the decision window; without it the template is used.
    """
    _check_transition(application, new_status)
    old_status = application.status
    with transaction.atomic():
        application.status = new_status
        application.is_seen = True
        if new_status == Status.WAITLISTED:
            application.waitlist_position = _next_position(application)
        else:
            application.waitlist_position = None
        application.save(update_fields=["status", "is_seen", "waitlist_position", "updated_at"])
        if old_status == Status.WAITLISTED:
            _renumber(application.workshop_id, application.level_id)
        notified = notify and _queue_decision_email(application, new_status, email, user)
        change = StatusChange.objects.create(
            application=application,
            old_status=old_status,
            new_status=new_status,
            comment=comment,
            notified=notified,
            changed_by=user,
        )
        audit.record(
            user,
            AUDIT_ACTIONS[new_status],
            application,
            details=f"{Status(old_status).label} → {Status(new_status).label}"
            + (" (wysłano e-mail)" if notified else ""),
        )
    return change


def bulk_change_status(
    applications: list[Application], new_status: str, *, user: Any, notify: bool
) -> tuple[int, list[str]]:
    """Apply one decision to many; returns (changed, names skipped because not allowed)."""
    changed, skipped = 0, []
    for application in applications:
        try:
            change_status(application, new_status, user=user, notify=notify)
        except TransitionError:
            skipped.append(application.full_name)
        else:
            changed += 1
    return changed, skipped


def freed_place_hint(application: Application, old_status: str) -> Application | None:
    """After an accepted person leaves: the first person waiting on the same level, if any.

    Only a hint — the administrator decides (client's answer; no automatic promotion).
    """
    if old_status != Status.ACCEPTED or application.status == Status.ACCEPTED:
        return None
    return first_waitlisted(application.level)


# --- Corrections -------------------------------------------------------------------------------


def change_level(application: Application, level: Any, *, user: Any) -> None:
    if level.pk == application.level_id:
        return
    if level.workshop_id != application.workshop_id:
        raise TransitionError("Poziom należy do innego warsztatu.")
    old_level = application.level
    with transaction.atomic():
        application.level = level
        if application.status == Status.WAITLISTED:
            application.waitlist_position = _next_position(application)
        application.save(update_fields=["level", "waitlist_position", "updated_at"])
        if application.status == Status.WAITLISTED:
            _renumber(application.workshop_id, old_level.pk)
        comment = f"Zmiana poziomu: {old_level.name} → {level.name}"
        StatusChange.objects.create(
            application=application,
            old_status=application.status,
            new_status=application.status,
            comment=comment,
            changed_by=user,
        )
        audit.record(user, "Zmieniono poziom zgłoszenia", application, details=comment)


def record_correction(
    application: Application, changed: dict[str, tuple[str, str]], *, user: Any
) -> None:
    """History entry for edited contact data: {field label: (before, after)}."""
    if not changed:
        return
    comment = "Poprawiono dane: " + "; ".join(
        f"{label}: „{before}” → „{after}”" for label, (before, after) in changed.items()
    )
    StatusChange.objects.create(
        application=application,
        old_status=application.status,
        new_status=application.status,
        comment=comment,
        changed_by=user,
    )
    audit.record(user, "Poprawiono dane zgłoszenia", application, details=comment)
