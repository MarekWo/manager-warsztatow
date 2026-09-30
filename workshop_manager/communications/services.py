"""The e-mail queue: writing messages, sending them in the worker, retrying failures.

`queue_email()` writes an `EmailMessage` in the caller's transaction and hands it to the worker
after the commit. The worker claims a message by switching it to "sending" in one UPDATE, so
the immediate task and the periodic sweep can never send the same message twice. A failure puts
the message back in the queue with a growing delay (`RETRY_DELAYS`); after the last attempt it is
marked failed and waits for "Wyślij ponownie" in the panel.
"""

import logging
import mimetypes
from datetime import timedelta
from typing import Any

from django.db.models import Q
from django.utils import timezone

from workshop_manager.communications import mailer
from workshop_manager.communications.defaults import DEFAULTS
from workshop_manager.communications.models import (
    EmailMessage,
    EmailTemplate,
    MessageStatus,
)
from workshop_manager.communications.rendering import render, site_context
from workshop_manager.core.models import SiteSettings
from workshop_manager.core.tasks import enqueue, enqueue_on_commit

logger = logging.getLogger(__name__)

#: Minutes to wait after the 1st, 2nd, … failed attempt: about ten hours in all.
RETRY_DELAYS = [1, 5, 15, 60, 180, 360]
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1

#: A message stuck in "sending" this long belongs to a worker that died mid-send.
STALE_SENDING = timedelta(minutes=10)

#: How many due messages one sweep sends (a sweep must finish within the task timeout).
SWEEP_BATCH = 20

SEND_TASK = "workshop_manager.communications.services.send_email_message"


def queue_email(
    *,
    to_email: str,
    subject: str,
    text: str,
    html: str = "",
    to_name: str = "",
    reply_to: str = "",
    template_key: str = "",
    application: Any = None,
    created_by: Any = None,
    broadcast: Any = None,
) -> EmailMessage:
    message = EmailMessage.objects.create(
        to_email=to_email,
        to_name=to_name,
        subject=subject,
        body_text=text,
        body_html=html,
        reply_to=reply_to,
        template_key=template_key,
        application=application,
        created_by=created_by,
        broadcast=broadcast,
    )
    enqueue_on_commit(SEND_TASK, message.pk)
    return message


def get_template(key: str) -> EmailTemplate:
    """The administrator's wording, or the default one if the template was never created."""
    template = EmailTemplate.objects.filter(key=key).first()
    if template is None:
        subject, body = DEFAULTS[key]
        template = EmailTemplate(key=key, subject=subject, body=body)
    return template


def queue_from_template(
    key: str,
    *,
    to_email: str,
    context: dict[str, str],
    to_name: str = "",
    application: Any = None,
    created_by: Any = None,
) -> EmailMessage:
    site = SiteSettings.load()
    template = get_template(key)
    rendered = render(template.subject, template.body, site_context(site) | context, site)
    return queue_email(
        to_email=to_email,
        to_name=to_name,
        subject=rendered.subject,
        text=rendered.text,
        html=rendered.html,
        template_key=key,
        application=application,
        created_by=created_by,
    )


# --- Worker side ---------------------------------------------------------------------------


def send_email_message(message_id: int) -> str:
    """Send one queued message (worker task). Never raises: failures are recorded instead."""
    now = timezone.now()
    claimed = EmailMessage.objects.filter(
        pk=message_id,
        status=MessageStatus.QUEUED,
        next_attempt_at__lte=now,
        # `next_attempt_at` doubles as "claimed at" while sending — what the stale check reads.
    ).update(status=MessageStatus.SENDING, next_attempt_at=now)
    if not claimed:
        return "skipped"
    message = EmailMessage.objects.get(pk=message_id)
    try:
        transport = mailer.transport()
        email = mailer.build(
            to_email=message.to_email,
            to_name=message.to_name,
            subject=message.subject,
            text=message.body_text,
            html=message.body_html,
            reply_to=message.reply_to or transport.reply_to,
            from_email=transport.from_email,
        )
        _attach(email, message)
        mailer.send_now(email, transport.connection)
    except Exception as error:  # any SMTP, network or configuration error
        _record_failure(message, error)
        return "failed"
    message.status = MessageStatus.SENT
    message.attempts += 1
    message.sent_at = timezone.now()
    message.last_error = ""
    message.save(update_fields=["status", "attempts", "sent_at", "last_error"])
    return "sent"


def _attach(email: Any, message: EmailMessage) -> None:
    """A message to participants carries its attachment, read from private storage."""
    broadcast = message.broadcast
    if broadcast is None or not broadcast.attachment:
        return
    with broadcast.attachment.open("rb") as file:
        content = file.read()
    mimetype = mimetypes.guess_type(broadcast.attachment_name)[0] or "application/octet-stream"
    email.attach(broadcast.attachment_name, content, mimetype)


def _record_failure(message: EmailMessage, error: Exception) -> None:
    message.attempts += 1
    message.last_error = f"{type(error).__name__}: {error}"[:2000]
    if message.attempts >= MAX_ATTEMPTS:
        message.status = MessageStatus.FAILED
    else:
        message.status = MessageStatus.QUEUED
        delay = RETRY_DELAYS[message.attempts - 1]
        message.next_attempt_at = timezone.now() + timedelta(minutes=delay)
    message.save(update_fields=["status", "attempts", "last_error", "next_attempt_at"])
    logger.warning("E-mail %s to %s failed: %s", message.pk, message.to_email, message.last_error)


def send_due_emails() -> int:
    """Periodic sweep (every minute): retries that are due, and messages a dead worker left."""
    now = timezone.now()
    EmailMessage.objects.filter(
        status=MessageStatus.SENDING, next_attempt_at__lt=now - STALE_SENDING
    ).update(status=MessageStatus.QUEUED)
    due = list(
        EmailMessage.objects.filter(status=MessageStatus.QUEUED, next_attempt_at__lte=now)
        .order_by("next_attempt_at", "pk")
        .values_list("pk", flat=True)[:SWEEP_BATCH]
    )
    return sum(send_email_message(pk) == "sent" for pk in due)


# --- Panel actions -------------------------------------------------------------------------


def retry_now(message: EmailMessage) -> EmailMessage:
    """ "Wyślij ponownie": a failed or waiting message is tried at once; a sent one is copied."""
    if message.status == MessageStatus.SENT:
        message = queue_email(
            to_email=message.to_email,
            to_name=message.to_name,
            subject=message.subject,
            text=message.body_text,
            html=message.body_html,
            reply_to=message.reply_to,
            template_key=message.template_key,
            application=message.application,
            broadcast=message.broadcast,
        )
        return message
    if message.status == MessageStatus.FAILED:
        message.attempts = 0
    message.status = MessageStatus.QUEUED
    message.next_attempt_at = timezone.now()
    message.save(update_fields=["status", "attempts", "next_attempt_at"])
    enqueue_on_commit(SEND_TASK, message.pk)
    return message


def retry_all_waiting(*, include_failed: bool = False) -> int:
    """Try every waiting message now — after the SMTP settings were corrected, say."""
    statuses = [MessageStatus.QUEUED]
    if include_failed:
        statuses.append(MessageStatus.FAILED)
    waiting = EmailMessage.objects.filter(status__in=statuses)
    count = waiting.update(status=MessageStatus.QUEUED, next_attempt_at=timezone.now(), attempts=0)
    if count:
        enqueue_on_commit("workshop_manager.communications.services.send_due_emails")
    return count


def failed_or_retrying() -> Any:
    return EmailMessage.objects.filter(
        Q(status=MessageStatus.FAILED) | Q(status=MessageStatus.QUEUED, attempts__gt=0)
    )


def send_test_email(to_email: str, site: SiteSettings | None = None) -> str:
    """Send a test message right now (not queued); return the error text, or "" on success."""
    site = site or SiteSettings.load()
    try:
        transport = mailer.transport(site)
        rendered = render(
            "Wiadomość testowa — {organizacja}",
            "To jest wiadomość testowa z systemu zapisów na warsztaty.\n\n"
            "Skoro dotarła, ustawienia poczty są poprawne.",
            site_context(site),
            site,
        )
        email = mailer.build(
            to_email=to_email,
            subject=rendered.subject,
            text=rendered.text,
            html=rendered.html,
            reply_to=transport.reply_to,
            from_email=transport.from_email,
        )
        mailer.send_now(email, transport.connection)
    except Exception as error:  # shown to the administrator as is
        return f"{type(error).__name__}: {error}"
    return ""


def kick_worker() -> None:
    """Ask the worker for a sweep now instead of at the next minute (outside transactions)."""
    enqueue("workshop_manager.communications.services.send_due_emails")
