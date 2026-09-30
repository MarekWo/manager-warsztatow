"""E-mails about applications: the applicant's confirmation and the organiser's notifications."""

from datetime import timedelta
from typing import Any

from django.urls import reverse
from django.utils import timezone

from workshop_manager.communications.models import TemplateKey
from workshop_manager.communications.rendering import application_context
from workshop_manager.communications.services import queue_from_template
from workshop_manager.core.models import AdminNotifications, SiteSettings, absolute_url


def application_submitted(
    application: Any, *, confirm: bool = True, notify_organiser: bool = True
) -> None:
    """Queue the confirmation (with a copy of the answers) and, if wanted, the notification.

    Called inside the transaction that stores the application: the messages are written with
    it and sent after the commit, so an SMTP failure can never lose an application.
    """
    context = application_context(application)
    if confirm:
        queue_from_template(
            TemplateKey.APPLICATION_RECEIVED,
            to_email=application.email,
            to_name=application.full_name,
            context=context,
            application=application,
        )
    site = SiteSettings.load()
    recipient = site.admin_recipient()
    wanted = notify_organiser and site.admin_notifications == AdminNotifications.IMMEDIATE
    if wanted and recipient:
        queue_from_template(
            TemplateKey.ADMIN_NEW_APPLICATION,
            to_email=recipient,
            context=context,
            application=application,
        )


def send_admin_digest() -> int:
    """Evening summary of the day's applications (periodic job); returns how many it listed."""
    from workshop_manager.applications.models import Application, Source

    site = SiteSettings.load()
    now = timezone.now()
    since = site.last_digest_at or now - timedelta(days=1)
    recipient = site.admin_recipient()
    count = 0
    if site.admin_notifications == AdminNotifications.DAILY and recipient:
        applications = list(
            Application.objects.filter(
                submitted_at__gt=since, submitted_at__lte=now, source=Source.FORM
            )
            .select_related("workshop", "level")
            .order_by("submitted_at")
        )
        count = len(applications)
        if applications:
            lines = [f"• {a.full_name} — {a.workshop.title} ({a.level.name})" for a in applications]
            queue_from_template(
                TemplateKey.ADMIN_DAILY_DIGEST,
                to_email=recipient,
                context={
                    "liczba": str(count),
                    "lista_zgloszen": "\n".join(lines),
                    "link_do_panelu": absolute_url(reverse("panel:dashboard")),
                },
            )
    SiteSettings.objects.filter(pk=site.pk).update(last_digest_at=now)
    return count
