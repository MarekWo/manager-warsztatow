"""Panel: Settings, e-mail templates and the e-mail log (PRD §7.5, §7.8)."""

import io
import smtplib

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from tests.factories import AdminFactory
from workshop_manager.communications import mailer, services
from workshop_manager.communications.models import (
    EmailMessage,
    EmailTemplate,
    MessageStatus,
    TemplateKey,
)
from workshop_manager.core.models import SiteSettings


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 20), "navy").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def admin_client(client, db):
    client.force_login(AdminFactory(email="admin@example.com"))
    return client


def settings_payload(**overrides) -> dict:
    site = SiteSettings.load()
    data = {
        "org_name": site.org_name,
        "org_short_name": site.org_short_name,
        "contact_email": "organizator@example.com",
        "privacy_policy_url": site.privacy_policy_url,
        "privacy_text": site.privacy_text,
        "marketing_text": site.marketing_text,
        "smtp_port": 587,
        "smtp_security": "starttls",
        "admin_notifications": "immediate",
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize(
    "url",
    [
        reverse("panel:settings"),
        reverse("panel:email_template_list"),
        reverse("panel:email_log"),
        reverse("panel:email_template_preview", args=["application_received"]),
    ],
)
def test_pages_need_a_staff_account(client, db, url):
    assert client.get(url).status_code == 302


def test_settings_page_renders(admin_client):
    content = admin_client.get(reverse("panel:settings")).content.decode()
    assert "Poczta wychodząca" in content
    assert "Wyślij e-mail testowy" in content
    assert 'value="admin@example.com"' in content


def test_saving_settings_keeps_the_password_unless_changed(admin_client):
    url = reverse("panel:settings")
    smtp = {
        "smtp_enabled": "on",
        "smtp_host": "smtp.example.com",
        "smtp_username": "ikona@example.com",
    }
    response = admin_client.post(url, settings_payload(**smtp, smtp_password="tajne"))
    assert response.status_code == 302
    assert SiteSettings.load().smtp_password == "tajne"

    page = admin_client.get(url).content.decode()
    assert "tajne" not in page
    assert "Hasło jest zapisane" in page

    admin_client.post(url, settings_payload(**{**smtp, "smtp_host": "smtp2.example.com"}))
    site = SiteSettings.load()
    assert (site.smtp_host, site.smtp_password) == ("smtp2.example.com", "tajne")

    admin_client.post(url, settings_payload(**smtp, smtp_password_clear="on"))
    assert not SiteSettings.load().has_smtp_password


def test_own_smtp_needs_a_host(admin_client):
    response = admin_client.post(reverse("panel:settings"), settings_payload(smtp_enabled="on"))
    assert response.status_code == 200
    assert "Podaj adres serwera SMTP" in response.content.decode()


def test_logo_upload_shows_in_the_header(admin_client):
    logo = SimpleUploadedFile("logo.png", png(), content_type="image/png")
    admin_client.post(reverse("panel:settings"), settings_payload(logo=logo))
    assert SiteSettings.load().logo
    page = admin_client.get(reverse("public:home")).content.decode()
    assert 'class="site-logo"' in page


def test_fixing_smtp_settings_retries_waiting_emails(
    admin_client, monkeypatch, django_capture_on_commit_callbacks
):
    def refuse(message, connection):
        raise smtplib.SMTPConnectError(421, "down")

    monkeypatch.setattr(mailer, "send_now", refuse)
    with django_capture_on_commit_callbacks(execute=True):
        message = services.queue_email(to_email="a@example.com", subject="Temat", text="Treść")
    message.refresh_from_db()
    assert message.is_retrying

    monkeypatch.undo()
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(
            reverse("panel:settings"),
            settings_payload(
                smtp_enabled="on", smtp_host="smtp.example.com", smtp_username="u@example.com"
            ),
            follow=True,
        )
    assert "zostaną wysłane ponownie" in response.content.decode()


def test_test_email(admin_client, monkeypatch):
    url = reverse("panel:settings_test_email")
    response = admin_client.post(url, {"to_email": "test@example.com"}, follow=True)
    assert "Wysłano wiadomość testową" in response.content.decode()
    assert mail.outbox[0].to == ["test@example.com"]

    def refuse(message, connection):
        raise smtplib.SMTPAuthenticationError(535, b"Bad credentials")

    monkeypatch.setattr(mailer, "send_now", refuse)
    response = admin_client.post(url, {"to_email": "test@example.com"}, follow=True)
    assert "Bad credentials" in response.content.decode()


# --- Templates ----------------------------------------------------------------------------------


def test_template_list_and_edit(admin_client):
    content = admin_client.get(reverse("panel:email_template_list")).content.decode()
    assert "Potwierdzenie otrzymania zgłoszenia" in content

    url = reverse("panel:email_template_edit", args=["application_received"])
    assert "{imie}" in admin_client.get(url).content.decode()
    response = admin_client.post(url, {"subject": "Dzięki, {imie}", "body": "Treść {warsztat}"})
    assert response.status_code == 302
    template = EmailTemplate.objects.get(key=TemplateKey.APPLICATION_RECEIVED)
    assert template.subject == "Dzięki, {imie}"

    admin_client.post(reverse("panel:email_template_reset", args=["application_received"]))
    template.refresh_from_db()
    assert template.subject == "Otrzymaliśmy Twoje zgłoszenie: {warsztat}"


def test_template_rejects_unknown_placeholders(admin_client):
    url = reverse("panel:email_template_edit", args=["application_received"])
    response = admin_client.post(url, {"subject": "Hej {imię}", "body": "{link_do_panelu}"})
    content = response.content.decode()
    assert response.status_code == 200
    assert "Nieznane pola: {imię}" not in content  # not a placeholder name at all
    assert "Nieznane pola: {link_do_panelu}" in content


def test_unknown_template_is_404(admin_client):
    assert admin_client.get(reverse("panel:email_template_edit", args=["nope"])).status_code == 404


def test_preview_shows_the_draft_in_a_frame(admin_client):
    url = reverse("panel:email_template_preview", args=["application_received"])
    response = admin_client.post(url, {"subject": "Temat {imie}", "body": "Witaj {imie}!"})
    content = response.content.decode()
    assert "Temat Anna" in content
    assert "Witaj Anna!" in content
    assert response["X-Frame-Options"] == "SAMEORIGIN"
    policy = response["Content-Security-Policy"]
    assert "'unsafe-inline'" in policy
    assert "frame-ancestors 'self'" in policy


# --- Log ----------------------------------------------------------------------------------------


def test_log_lists_filters_and_resends(admin_client):
    sent = EmailMessage.objects.create(
        to_email="a@example.com", subject="Wysłany", body_text="x", status=MessageStatus.SENT
    )
    failed = EmailMessage.objects.create(
        to_email="b@example.com",
        subject="Nieudany",
        body_text="y",
        status=MessageStatus.FAILED,
        attempts=services.MAX_ATTEMPTS,
        last_error="SMTPAuthenticationError: bad",
    )
    content = admin_client.get(reverse("panel:email_log")).content.decode()
    assert "Wysłany" in content
    assert "Nieudany" in content
    assert "Wyślij ponownie nieudane (1)" in content

    problems = admin_client.get(reverse("panel:email_log") + "?status=problems").content.decode()
    assert "Nieudany" in problems
    assert "Wysłany" not in problems

    detail = admin_client.get(reverse("panel:email_detail", args=[failed.pk])).content.decode()
    assert "SMTPAuthenticationError: bad" in detail
    assert admin_client.get(reverse("panel:email_html", args=[sent.pk])).status_code == 200

    admin_client.post(reverse("panel:email_resend", args=[failed.pk]))
    failed.refresh_from_db()
    assert (failed.status, failed.attempts) == (MessageStatus.QUEUED, 0)

    admin_client.post(reverse("panel:email_resend", args=[sent.pk]))
    assert EmailMessage.objects.filter(subject="Wysłany").count() == 2


def test_resend_all_failed(admin_client):
    EmailMessage.objects.create(
        to_email="b@example.com", subject="N", body_text="y", status=MessageStatus.FAILED
    )
    admin_client.post(reverse("panel:email_resend_failed"))
    assert EmailMessage.objects.get().status == MessageStatus.QUEUED


def test_sign_in_codes_use_the_settings_transport(client, db):
    site = SiteSettings.load()
    site.reply_to = "odpowiedzi@example.com"
    site.save()
    AdminFactory(email="kod@example.com")
    client.post(reverse("account_request_login_code"), {"email": "kod@example.com"})
    assert mail.outbox[-1].reply_to == ["odpowiedzi@example.com"]


def test_login_page_title_uses_the_organisation_name(client, db):
    """allauth puts its own `site` in the context; ours is `site_settings`."""
    content = client.get(reverse("account_request_login_code")).content.decode()
    assert "— Stowarzyszenie Ecclesia</title>" in content
