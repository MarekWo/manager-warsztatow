"""Messages to a workshop's participants (PRD §7.5): recipients, preview, sending.

Each person gets their own e-mail (nobody sees the other addresses), personalised with the
same placeholders as the application e-mails, and each one is an ordinary row in the e-mail
log — queued, retried and resendable like any other. The attachment stays in private storage
and is added by the worker when it sends.
"""

from typing import Any

from django.db import transaction
from django.utils import timezone

from workshop_manager.applications.models import ACTIVE_STATUSES, Application, Status
from workshop_manager.communications.models import Broadcast, Group
from workshop_manager.communications.rendering import application_context, render, site_context
from workshop_manager.communications.services import queue_email
from workshop_manager.core import audit
from workshop_manager.core.models import SiteSettings


def recipients(broadcast: Broadcast) -> list[Application]:
    """The applications the message goes to, one per e-mail address, by surname."""
    qs = Application.objects.filter(workshop=broadcast.workshop).select_related(
        "workshop", "level", "workshop__location"
    )
    group = broadcast.group
    if group == Group.ACCEPTED:
        qs = qs.filter(status=Status.ACCEPTED)
    elif group == Group.WAITLISTED:
        qs = qs.filter(status=Status.WAITLISTED)
    elif group == Group.ACTIVE:
        qs = qs.filter(status__in=ACTIVE_STATUSES)
    elif group == Group.LEVEL:
        qs = qs.filter(status=Status.ACCEPTED, level=broadcast.level)
    else:
        qs = qs.filter(pk__in=broadcast.selected.values("pk"))
    seen: set[str] = set()
    result = []
    for application in qs.order_by("last_name", "first_name", "pk"):
        if application.email not in seen:
            seen.add(application.email)
            result.append(application)
    return result


def personal_email(broadcast: Broadcast, application: Application) -> Any:
    site = SiteSettings.load()
    context = site_context(site) | application_context(application)
    return render(broadcast.subject, broadcast.body, context, site)


def send(broadcast: Broadcast, *, user: Any) -> int:
    """Queue one e-mail per recipient; returns how many. A sent message is never sent twice."""
    with transaction.atomic():
        locked = Broadcast.objects.select_for_update().get(pk=broadcast.pk)
        if locked.sent_at is not None:
            return 0
        people = recipients(locked)
        for application in people:
            rendered = personal_email(locked, application)
            queue_email(
                to_email=application.email,
                to_name=application.full_name,
                subject=rendered.subject,
                text=rendered.text,
                html=rendered.html,
                application=application,
                broadcast=locked,
                created_by=user,
            )
        locked.sent_at = timezone.now()
        locked.recipient_count = len(people)
        locked.save(update_fields=["sent_at", "recipient_count"])
        audit.record(
            user,
            "Wysłano wiadomość do uczestników",
            locked.workshop,
            details=f"„{locked.subject}” — {locked.get_group_display()}, odbiorców: {len(people)}",
        )
    broadcast.refresh_from_db()
    return len(people)
