"""E-mail: settings, rendering, the queue with retries, and the application e-mails (PRD §7.5)."""

import smtplib
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import time_machine
from django.core import mail
from django.core.mail.backends.smtp import EmailBackend as SmtpBackend
from django.urls import reverse

from tests.factories import LevelFactory, QuestionFactory, SessionFactory, WorkshopFactory
from tests.test_applications_form import started
from workshop_manager.applications.models import Application
from workshop_manager.communications import mailer, services
from workshop_manager.communications.models import (
    EmailMessage,
    EmailTemplate,
    MessageStatus,
    TemplateKey,
)
from workshop_manager.communications.notifications import send_admin_digest
from workshop_manager.communications.rendering import fill, render, text_to_html
from workshop_manager.core import crypto
from workshop_manager.core.models import AdminNotifications, SiteSettings, SmtpSecurity

WARSAW = ZoneInfo("Europe/Warsaw")
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=WARSAW)


@pytest.fixture(autouse=True)
def clock():
    with time_machine.travel(NOW, tick=False) as traveller:
        yield traveller


@pytest.fixture
def site(db):
    site = SiteSettings.load()
    site.contact_email = "organizator@example.com"
    site.save()
    return site


@pytest.fixture
def workshop(db):
    workshop = WorkshopFactory(
        title="Rekolekcje z ikoną", publish_at=datetime(2026, 10, 20, 9, tzinfo=WARSAW)
    )
    SessionFactory(workshop=workshop, date=date(2026, 11, 28))
    LevelFactory(workshop=workshop, name="Początkujący", order=0, price=450)
    QuestionFactory(workshop=workshop, label="Doświadczenie", order=1)
    return workshop


def apply(client, workshop):
    data = {
        "level": workshop.levels.get().pk,
        "first_name": "Anna",
        "last_name": "Nowak",
        "email": "anna.nowak@example.com",
        "phone": "600 100 200",
        "adult": "on",
        "privacy": "on",
        "started": started(),
        f"q_{workshop.questions.get().pk}": "Maluję <b>akwarelą</b>.",
    }
    return client.post(reverse("public:apply", args=[workshop.slug]), data)


def smtp_down(monkeypatch):
    def refuse(message, connection):
        raise smtplib.SMTPConnectError(421, "Service not available")

    monkeypatch.setattr(mailer, "send_now", refuse)


# --- Encryption and settings --------------------------------------------------------------------


def test_encryption_round_trip_and_a_changed_key(settings):
    token = crypto.encrypt("hasło-aplikacji")
    assert token != "hasło-aplikacji"
    assert crypto.decrypt(token) == "hasło-aplikacji"
    settings.SECRET_KEY = "another-secret-key-another-secret-key-0123456789"
    assert crypto.decrypt(token) == ""
    assert crypto.encrypt("") == ""


def test_smtp_password_is_stored_encrypted(site):
    site.set_smtp_password("tajne")
    site.save()
    stored = SiteSettings.objects.values_list("smtp_password_encrypted", flat=True).get()
    assert "tajne" not in stored
    assert SiteSettings.load().smtp_password == "tajne"


def test_new_consent_wording_is_a_new_version(site):
    first = site.privacy_version
    site.org_name = "Inna nazwa"
    site.save()
    assert SiteSettings.load().privacy_version == first
    site.privacy_text = "Nowa treść zgody."
    site.save()
    assert SiteSettings.load().privacy_version == "2026-10-25 12:00"


def test_application_records_the_current_consent_version(client, workshop, site):
    site.privacy_text = "Zgoda w nowym brzmieniu."
    site.save()
    page = client.get(reverse("public:apply", args=[workshop.slug])).content.decode()
    assert "Zgoda w nowym brzmieniu." in page
    apply(client, workshop)
    assert Application.objects.get().privacy_consent_version == "2026-10-25 12:00"


# --- Transport ----------------------------------------------------------------------------------


def test_fallback_transport_uses_the_installation_sender(site, settings):
    transport = mailer.transport(site)
    assert transport.from_email == settings.DEFAULT_FROM_EMAIL
    assert transport.reply_to == "organizator@example.com"


def test_own_smtp_transport_from_settings(site):
    site.smtp_enabled = True
    site.smtp_host = "smtp.example.com"
    site.smtp_port = 465
    site.smtp_security = SmtpSecurity.SSL
    site.smtp_username = "ikona@example.com"
    site.set_smtp_password("tajne")
    site.from_name = "Warsztaty, Ecclesia"
    site.reply_to = "odpowiedzi@example.com"
    site.save()
    transport = mailer.transport(SiteSettings.load())
    connection = transport.connection
    assert isinstance(connection, SmtpBackend)
    assert (connection.host, connection.port, connection.use_ssl, connection.use_tls) == (
        "smtp.example.com",
        465,
        True,
        False,
    )
    assert connection.password == "tajne"
    assert transport.from_email == '"Warsztaty, Ecclesia" <ikona@example.com>'
    assert transport.reply_to == "odpowiedzi@example.com"


# --- Rendering ----------------------------------------------------------------------------------


def test_placeholders_and_html(site):
    assert (
        fill("Dzień dobry {imie}, {nieznane}", {"imie": "Anna"}) == "Dzień dobry Anna, {nieznane}"
    )
    html = text_to_html("Akapit <b>1</b>\nlinia 2\n\nhttps://example.com/")
    assert "&lt;b&gt;1&lt;/b&gt;<br>" in html
    assert '<a href="https://example.com/"' in html
    rendered = render("Terminy: {terminy}", "Treść", {"terminy": "sobota\nniedziela"}, site)
    assert rendered.subject == "Terminy: sobota niedziela"
    assert "Stowarzyszenie Ecclesia" in rendered.html


# --- Application e-mails ------------------------------------------------------------------------


def test_application_sends_confirmation_and_notification(
    client, workshop, site, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        response = apply(client, workshop)
    assert response.status_code == 302

    assert len(mail.outbox) == 2
    by_recipient = {m.to[0]: m for m in mail.outbox}
    confirmation = by_recipient["Anna Nowak <anna.nowak@example.com>"]
    notification = by_recipient["organizator@example.com"]
    assert confirmation.to == ["Anna Nowak <anna.nowak@example.com>"]
    assert confirmation.subject == "Otrzymaliśmy Twoje zgłoszenie: Rekolekcje z ikoną"
    assert "Dzień dobry Anna" in confirmation.body
    assert "Doświadczenie: Maluję <b>akwarelą</b>." in confirmation.body
    assert "sobota, 28 listopada 2026, 10:00–16:00" in confirmation.body
    assert confirmation.reply_to == ["organizator@example.com"]
    html = confirmation.alternatives[0].content
    assert "Maluję &lt;b&gt;akwarelą&lt;/b&gt;." in html

    assert notification.to == ["organizator@example.com"]
    assert notification.subject == "Nowe zgłoszenie: Anna Nowak — Rekolekcje z ikoną"

    application = Application.objects.get()
    assert set(application.emails.values_list("status", flat=True)) == {MessageStatus.SENT}


def test_edited_template_is_used(client, workshop, site, django_capture_on_commit_callbacks):
    EmailTemplate.objects.create(
        key=TemplateKey.APPLICATION_RECEIVED, subject="Mamy to, {imie}!", body="Poziom: {poziom}"
    )
    site.admin_notifications = AdminNotifications.OFF
    site.save()
    with django_capture_on_commit_callbacks(execute=True):
        apply(client, workshop)
    [message] = mail.outbox
    assert message.subject == "Mamy to, Anna!"
    assert message.body.strip() == "Poziom: Początkujący"


def test_smtp_failure_keeps_the_application_and_retries_later(
    client, workshop, site, monkeypatch, django_capture_on_commit_callbacks, clock
):
    """PLAN Stage 3 acceptance: SMTP down → the application goes through, the e-mail waits."""
    site.admin_notifications = AdminNotifications.OFF
    site.save()
    smtp_down(monkeypatch)
    with django_capture_on_commit_callbacks(execute=True):
        response = apply(client, workshop)
    assert response.status_code == 302
    assert Application.objects.count() == 1
    message = EmailMessage.objects.get()
    assert message.status == MessageStatus.QUEUED
    assert message.attempts == 1
    assert "Service not available" in message.last_error
    assert message.next_attempt_at == NOW + timedelta(minutes=1)
    assert services.send_due_emails() == 0  # not due yet

    monkeypatch.undo()  # the server is back
    clock.shift(timedelta(minutes=2))
    assert services.send_due_emails() == 1
    message.refresh_from_db()
    assert message.status == MessageStatus.SENT
    assert message.attempts == 2
    assert message.last_error == ""
    assert len(mail.outbox) == 1


def test_gives_up_after_the_last_attempt(site, monkeypatch, clock):
    smtp_down(monkeypatch)
    message = services.queue_email(to_email="a@example.com", subject="Temat", text="Treść")
    for _ in range(services.MAX_ATTEMPTS):
        clock.shift(timedelta(hours=7))
        services.send_email_message(message.pk)
    message.refresh_from_db()
    assert message.status == MessageStatus.FAILED
    assert message.attempts == services.MAX_ATTEMPTS
    assert list(services.failed_or_retrying()) == [message]


def test_a_message_is_never_sent_twice(site):
    message = services.queue_email(to_email="a@example.com", subject="Temat", text="Treść")
    assert services.send_email_message(message.pk) == "sent"
    assert services.send_email_message(message.pk) == "skipped"
    assert len(mail.outbox) == 1


def test_sweep_picks_up_messages_left_by_a_dead_worker(site, clock):
    message = services.queue_email(to_email="a@example.com", subject="Temat", text="Treść")
    EmailMessage.objects.filter(pk=message.pk).update(status=MessageStatus.SENDING)
    assert services.send_due_emails() == 0  # a worker may still be sending it
    clock.shift(timedelta(minutes=11))
    assert services.send_due_emails() == 1


def test_resend(site, monkeypatch):
    smtp_down(monkeypatch)
    message = services.queue_email(to_email="a@example.com", subject="Temat", text="Treść")
    EmailMessage.objects.filter(pk=message.pk).update(
        status=MessageStatus.FAILED, attempts=services.MAX_ATTEMPTS
    )
    monkeypatch.undo()
    message.refresh_from_db()
    services.retry_now(message)
    assert services.send_email_message(message.pk) == "sent"
    message.refresh_from_db()
    copy = services.retry_now(message)
    assert copy.pk != message.pk
    assert copy.status == MessageStatus.QUEUED
    assert copy.subject == "Temat"


# --- Daily digest -------------------------------------------------------------------------------


def test_daily_digest(client, workshop, site, clock):
    site.admin_notifications = AdminNotifications.DAILY
    site.save()
    apply(client, workshop)
    assert not EmailMessage.objects.filter(template_key=TemplateKey.ADMIN_NEW_APPLICATION)
    clock.shift(timedelta(hours=7))
    assert send_admin_digest() == 1
    digest = EmailMessage.objects.get(template_key=TemplateKey.ADMIN_DAILY_DIGEST)
    assert digest.to_email == "organizator@example.com"
    assert "Anna Nowak — Rekolekcje z ikoną (Początkujący)" in digest.body_text
    assert send_admin_digest() == 0  # nothing new since the last one


def test_no_digest_in_immediate_mode(client, workshop, site, clock):
    apply(client, workshop)
    clock.shift(timedelta(hours=7))
    assert send_admin_digest() == 0
    assert not EmailMessage.objects.filter(template_key=TemplateKey.ADMIN_DAILY_DIGEST)
