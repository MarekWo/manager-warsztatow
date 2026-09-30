"""Panel pages for applications, the dashboard counters and the event log (PRD §7.1, §7.3)."""

import pytest
from django.urls import reverse

from tests.factories import (
    AdminFactory,
    ApplicationFactory,
    LevelFactory,
    QuestionFactory,
    UserFactory,
    WorkshopFactory,
)
from workshop_manager.applications.models import Application, Source, Status, StatusChange
from workshop_manager.communications.models import EmailMessage, TemplateKey
from workshop_manager.core.models import AuditEvent, SiteSettings


@pytest.fixture
def admin(db):
    return AdminFactory(email="admin@example.com")


@pytest.fixture
def admin_client(client, admin):
    client.force_login(admin)
    return client


@pytest.fixture
def level(db):
    workshop = WorkshopFactory(title="Rekolekcje z ikoną")
    return LevelFactory(workshop=workshop, name="Początkujący", capacity=12)


def test_pages_need_a_staff_account(client, level):
    application = ApplicationFactory(level=level)
    client.force_login(UserFactory())
    for url in [
        reverse("panel:application_list"),
        application.get_panel_url(),
        reverse("panel:audit_log"),
    ]:
        response = client.get(url)
        assert response.status_code == 302
        assert "/konto/" in response["Location"]


def test_lists_filter_and_search(admin_client, level):
    ApplicationFactory(level=level, last_name="Kowalska", status=Status.ACCEPTED)
    ApplicationFactory(level=level, last_name="Zielińska")
    page = admin_client.get(reverse("panel:application_list"), {"q": "zieli"}).content.decode()
    assert "Zielińska" in page
    assert "Kowalska" not in page
    url = reverse("panel:workshop_applications", args=[level.workshop.pk])
    page = admin_client.get(url, {"status": "accepted"}).content.decode()
    assert "Kowalska" in page
    assert "Zielińska" not in page
    assert "Przyjęte / limit" in page


def test_opening_an_application_marks_it_seen(admin_client, level):
    application = ApplicationFactory(level=level)
    QuestionFactory(workshop=level.workshop)
    application.answers.create(label="Doświadczenie", value="Maluję akwarelą")
    page = admin_client.get(application.get_panel_url()).content.decode()
    assert "Maluję akwarelą" in page
    assert "To pierwsze zgłoszenie tej osoby." in page
    application.refresh_from_db()
    assert application.is_seen


def test_detail_shows_the_persons_other_workshops(admin_client, level):
    earlier = ApplicationFactory(
        level=LevelFactory(workshop=WorkshopFactory(title="Mozaika jesienna")),
        status=Status.ACCEPTED,
    )
    application = ApplicationFactory(level=level, participant=earlier.participant)
    page = admin_client.get(application.get_panel_url()).content.decode()
    assert "Mozaika jesienna" in page


def test_decision_window_shows_the_email_and_applies_the_decision(admin_client, level):
    application = ApplicationFactory(level=level, first_name="Anna")
    url = reverse("panel:application_decide", args=[application.pk, "accepted"])
    page = admin_client.get(url).content.decode()
    assert "Dzień dobry Anna" in page

    response = admin_client.post(
        url,
        {
            "notify": "on",
            "subject": "Przyjęta!",
            "body": "Dzień dobry Anna, do zobaczenia.",
            "comment": "",
        },
    )
    assert response.status_code == 302
    application.refresh_from_db()
    assert application.status == Status.ACCEPTED
    email = EmailMessage.objects.get()
    assert (email.subject, email.template_key) == ("Przyjęta!", TemplateKey.DECISION_ACCEPTED)


def test_decision_window_refuses_an_impossible_change(admin_client, level):
    application = ApplicationFactory(level=level, status=Status.REJECTED)
    url = reverse("panel:application_decide", args=[application.pk, "cancelled"])
    assert admin_client.post(url, {}).status_code == 302
    application.refresh_from_db()
    assert application.status == Status.REJECTED


def test_withdrawal_of_an_accepted_person_suggests_the_waiting_list(admin_client, level):
    accepted = ApplicationFactory(level=level, status=Status.ACCEPTED)
    waiting = ApplicationFactory(
        level=level, status=Status.WAITLISTED, waitlist_position=1, last_name="Rezerwowa"
    )
    url = reverse("panel:application_decide", args=[accepted.pk, "withdrawn"])
    response = admin_client.post(url, {"comment": "Zadzwoniła"}, follow=True)
    page = response.content.decode()
    assert "Zwolniło się miejsce" in page
    assert waiting.get_panel_url() in page


def test_bulk_accept_with_template_emails(admin_client, level):
    first, second = ApplicationFactory(level=level), ApplicationFactory(level=level)
    response = admin_client.post(
        reverse("panel:application_bulk"),
        {"ids": [first.pk, second.pk], "action": "accepted", "notify": "1", "next": "/panel/"},
    )
    assert response["Location"] == "/panel/"
    assert set(Application.objects.values_list("status", flat=True)) == {Status.ACCEPTED}
    assert EmailMessage.objects.count() == 2


def test_bulk_mark_as_seen(admin_client, level):
    application = ApplicationFactory(level=level)
    admin_client.post(
        reverse("panel:application_bulk"), {"ids": [application.pk], "action": "seen"}
    )
    application.refresh_from_db()
    assert application.is_seen
    assert not StatusChange.objects.exists()


def test_bulk_next_must_stay_on_this_site(admin_client, level):
    application = ApplicationFactory(level=level)
    response = admin_client.post(
        reverse("panel:application_bulk"),
        {"ids": [application.pk], "action": "seen", "next": "https://evil.example.com/"},
    )
    assert response["Location"] == reverse("panel:application_list")


def test_waitlist_reordering(admin_client, level):
    first = ApplicationFactory(level=level, status=Status.WAITLISTED, waitlist_position=1)
    second = ApplicationFactory(level=level, status=Status.WAITLISTED, waitlist_position=2)
    admin_client.post(reverse("panel:application_waitlist_move", args=[second.pk, "up"]))
    first.refresh_from_db()
    second.refresh_from_db()
    assert (second.waitlist_position, first.waitlist_position) == (1, 2)


def test_correcting_data_goes_to_history(admin_client, level):
    application = ApplicationFactory(level=level, phone="600 100 200")
    response = admin_client.post(
        reverse("panel:application_edit", args=[application.pk]),
        {
            "first_name": application.first_name,
            "last_name": application.last_name,
            "phone": "600 999 999",
            "remarks": "",
        },
    )
    assert response.status_code == 302
    comment = StatusChange.objects.get().comment
    assert "600 100 200" in comment
    assert "600 999 999" in comment


def test_level_change_in_the_panel(admin_client, level):
    other = LevelFactory(workshop=level.workshop, name="Zaawansowani")
    application = ApplicationFactory(level=level)
    admin_client.post(
        reverse("panel:application_level", args=[application.pk]), {"level": other.pk}
    )
    application.refresh_from_db()
    assert application.level == other


def test_notes_are_saved(admin_client, level):
    application = ApplicationFactory(level=level)
    admin_client.post(
        application.get_panel_url(), {"notes-admin_notes": "Prosi o miejsce przy oknie"}
    )
    application.refresh_from_db()
    assert application.admin_notes == "Prosi o miejsce przy oknie"


# --- Manual application ---------------------------------------------------------------------------


def manual_payload(level, **overrides):
    data = {
        "level": level.pk,
        "first_name": "Maria",
        "last_name": "Telefoniczna",
        "email": "maria@example.com",
        "privacy": "on",
    }
    data.update(overrides)
    return data


def test_manual_application_without_confirmation(admin_client, level, admin):
    site = SiteSettings.load()
    site.contact_email = "organizator@example.com"
    site.save()
    QuestionFactory(workshop=level.workshop, required=True)
    url = reverse("panel:application_add", args=[level.workshop.pk])
    response = admin_client.post(url, manual_payload(level))
    assert response.status_code == 302
    application = Application.objects.get()
    assert (application.source, application.created_by, application.is_seen) == (
        Source.PANEL,
        admin,
        True,
    )
    # Neither the participant (not asked for) nor the organiser (they typed it) gets an e-mail.
    assert not EmailMessage.objects.exists()
    assert AuditEvent.objects.filter(action="Dodano zgłoszenie w panelu").exists()


def test_manual_application_with_confirmation_and_duplicate(admin_client, level):
    url = reverse("panel:application_add", args=[level.workshop.pk])
    admin_client.post(url, manual_payload(level, send_confirmation="on"))
    assert EmailMessage.objects.get().template_key == TemplateKey.APPLICATION_RECEIVED
    response = admin_client.post(url, manual_payload(level))
    assert response.status_code == 200
    assert "ma już aktywne zgłoszenie" in response.content.decode()


def test_manual_application_needs_the_consent(admin_client, level):
    url = reverse("panel:application_add", args=[level.workshop.pk])
    response = admin_client.post(url, manual_payload(level, privacy=""))
    assert response.status_code == 200
    assert not Application.objects.exists()


# --- Dashboard, event log, e-mail link ------------------------------------------------------------


def test_dashboard_shows_counters_and_unseen(admin_client, level):
    from django.utils import timezone

    level.workshop.publish_at = timezone.now()
    level.workshop.save()
    for _ in range(13):
        ApplicationFactory(level=level, status=Status.ACCEPTED, is_seen=True)
    ApplicationFactory(level=level)
    page = admin_client.get(reverse("panel:dashboard")).content.decode()
    assert "13 / 12" in page
    assert "ponad limit" in page
    assert "nieprzejrzane zgłoszenia: <strong>1</strong>" in page


def test_event_log_lists_panel_changes(admin_client, level):
    ApplicationFactory(level=level)
    admin_client.post(reverse("panel:workshop_action", args=[level.workshop.pk, "archive"]))
    page = admin_client.get(reverse("panel:audit_log")).content.decode()
    assert "Warsztat przeniesiono do archiwum" in page
    assert "admin@example.com" in page


def test_admin_notification_links_to_the_panel(level):
    from workshop_manager.communications.rendering import application_context

    application = ApplicationFactory(level=level)
    assert application_context(application)["link_do_zgloszenia"].endswith(
        f"/panel/zgloszenia/{application.pk}/"
    )
