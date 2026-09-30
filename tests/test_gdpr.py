"""A person's rights over their data (PRD §8): the consent register, a copy of the data,
anonymisation by the person or the organiser, the unsubscribe link."""

import json
from datetime import date, timedelta

import pytest
from allauth.account.models import EmailAddress
from django.urls import reverse
from django.utils import timezone

from tests.factories import (
    AdminFactory,
    ApplicationFactory,
    LevelFactory,
    ParticipantFactory,
    SessionFactory,
    UserFactory,
    WorkshopFactory,
)
from workshop_manager.accounts.models import User
from workshop_manager.applications import decisions, gdpr
from workshop_manager.applications.models import (
    Answer,
    ConsentChannel,
    ConsentKind,
    ConsentRecord,
    Participant,
    Status,
)
from workshop_manager.applications.tokens import unsubscribe_path
from workshop_manager.communications.models import EmailMessage, MessageStatus
from workshop_manager.communications.rendering import application_context
from workshop_manager.core.models import AuditEvent


@pytest.fixture
def level(db):
    workshop = WorkshopFactory(title="Rekolekcje z ikoną", publish_at=timezone.now())
    SessionFactory(workshop=workshop, date=timezone.localdate() + timedelta(days=30))
    return LevelFactory(workshop=workshop, name="Początkujący")


@pytest.fixture
def past_level(db):
    workshop = WorkshopFactory(title="Ikona Pantokratora", publish_at=timezone.now())
    SessionFactory(workshop=workshop, date=date(2025, 5, 10))
    return LevelFactory(workshop=workshop, name="Zaawansowani")


@pytest.fixture
def anna(past_level):
    """A past participant with an account, an answer, notes, e-mails and log entries."""
    user = UserFactory(email="anna@example.com")
    participant = ParticipantFactory(
        email="anna@example.com", first_name="Anna", last_name="Nowak", phone="600 1", user=user
    )
    application = ApplicationFactory(
        level=past_level,
        participant=participant,
        status=Status.ACCEPTED,
        phone="600 1",
        remarks="Proszę o fakturę",
        admin_notes="Dzwoniła w sprawie noclegu",
    )
    Answer.objects.create(application=application, label="Doświadczenie", value="akwarela")
    decisions.record_correction(application, {"Telefon": ("600", "600 1")}, user=AdminFactory())
    EmailMessage.objects.create(
        to_email="anna@example.com",
        to_name="Anna Nowak",
        subject="Przyjęcie: Anna Nowak",
        body_text="Dzień dobry, Anno",
        application=application,
        status=MessageStatus.SENT,
    )
    gdpr.record_consent(
        participant, ConsentKind.PRIVACY, channel=ConsentChannel.FORM, application=application
    )
    return participant


# --- Consents --------------------------------------------------------------------------------


def test_the_form_records_consents_with_their_wording(client, level):
    from tests.test_applications_form import started

    response = client.post(
        reverse("public:apply", args=[level.workshop.slug]),
        {
            "level": level.pk,
            "first_name": "Ewa",
            "last_name": "Zielińska",
            "email": "ewa@example.com",
            "phone": "600 200 300",
            "adult": "on",
            "privacy": "on",
            "marketing": "on",
            "started": started(),
        },
    )
    assert response.status_code == 302, response.context["form"].errors
    consents = ConsentRecord.objects.filter(participant__email="ewa@example.com")
    assert {c.kind for c in consents} == {ConsentKind.PRIVACY, ConsentKind.MARKETING}
    privacy = consents.get(kind=ConsentKind.PRIVACY)
    assert privacy.channel == ConsentChannel.FORM
    assert privacy.version
    assert privacy.text


def test_changing_the_consent_in_my_data_is_recorded(client, anna):
    client.force_login(anna.user)
    data = {"first_name": "Anna", "last_name": "Nowak", "phone": "", "marketing": "on"}
    client.post(reverse("public:my_data"), data)
    client.post(reverse("public:my_data"), data | {"marketing": ""})
    marketing = anna.consents.filter(kind=ConsentKind.MARKETING)
    assert [c.given for c in marketing] == [True, False]
    assert {c.channel for c in marketing} == {ConsentChannel.ACCOUNT}


def test_the_unsubscribe_link_withdraws_the_consent_on_post_only(client, level):
    application = ApplicationFactory(level=level, marketing_consent=True)
    participant = application.participant
    gdpr.set_marketing_consent(participant, True, channel=ConsentChannel.FORM)
    url = unsubscribe_path(participant.pk)
    assert url in application_context(application)["link_wypisu"]

    assert "Tak, wypisz mnie" in client.get(url).content.decode()
    participant.refresh_from_db()
    assert participant.marketing_consent  # opening the link changes nothing

    response = client.post(url)  # also what a mail program's one-click request does
    assert "nie będziemy już wysyłać" in response.content.decode()
    participant.refresh_from_db()
    assert not participant.marketing_consent
    assert participant.consents.last().channel == ConsentChannel.LINK


def test_a_forged_unsubscribe_link_is_not_found(client, db):
    assert client.get(reverse("public:unsubscribe", args=["1:forged"])).status_code == 404


# --- A copy of the data ----------------------------------------------------------------------


def test_participant_downloads_their_data_without_organiser_notes(client, anna):
    client.force_login(anna.user)
    response = client.get(reverse("public:my_data_download"))
    assert response["Content-Disposition"].startswith("attachment;")
    data = json.loads(response.content)
    assert data["osoba"]["adres_email"] == "anna@example.com"
    entry = data["zgloszenia"][0]
    assert entry["uwagi"] == "Proszę o fakturę"
    assert entry["odpowiedzi"] == [{"pytanie": "Doświadczenie", "odpowiedz": "akwarela"}]
    assert "notatki_organizatora" not in entry
    assert data["e_maile"][0]["temat"] == "Przyjęcie: Anna Nowak"
    assert data["zgody"][0]["sposob"] == "formularz zgłoszenia"


def test_organiser_downloads_the_full_copy_and_it_is_logged(client, anna):
    client.force_login(AdminFactory())
    response = client.get(reverse("panel:participant_export", args=[anna.pk]))
    data = json.loads(response.content)
    assert data["zgloszenia"][0]["notatki_organizatora"] == "Dzwoniła w sprawie noclegu"
    assert AuditEvent.objects.filter(action="Pobrano kopię danych osoby").exists()


# --- Anonymisation ---------------------------------------------------------------------------


def test_anonymisation_removes_every_trace(anna):
    application = anna.applications.get()
    admin = AdminFactory()
    gdpr.anonymise(anna, user=admin)

    anna.refresh_from_db()
    assert anna.is_anonymised
    assert anna.first_name == "Anonim"
    assert "anna" not in anna.email
    assert anna.phone == ""
    assert anna.user is None
    application.refresh_from_db()
    assert (application.first_name, application.email) == ("Anonim", anna.email)
    assert application.status == Status.ACCEPTED  # the numbers still add up
    assert (application.phone, application.remarks, application.admin_notes) == ("", "", "")
    assert Answer.objects.get().value == ""
    assert all(change.comment == "" for change in application.history.all())
    email = EmailMessage.objects.get()
    assert "anna" not in email.to_email
    assert "Anna" not in email.subject + email.body_text + email.to_name
    assert not User.objects.filter(email="anna@example.com").exists()
    assert not EmailAddress.objects.filter(email="anna@example.com").exists()
    for event in AuditEvent.objects.all():
        assert "Nowak" not in event.target + event.details
        assert event.actor_email != "anna@example.com"
    assert ConsentRecord.objects.filter(participant=anna).exists()


def test_no_anonymisation_while_holding_a_place(anna, level):
    ApplicationFactory(level=level, participant=anna, status=Status.WAITLISTED)
    with pytest.raises(gdpr.CannotAnonymise, match="Rekolekcje z ikoną"):
        gdpr.anonymise(anna, user=AdminFactory())
    anna.refresh_from_db()
    assert not anna.is_anonymised


def test_unsent_emails_are_not_sent_after_anonymisation(anna):
    EmailMessage.objects.create(
        to_email="anna@example.com", subject="Wkrótce", body_text="…", status=MessageStatus.QUEUED
    )
    gdpr.anonymise(anna, user=AdminFactory())
    assert not EmailMessage.objects.filter(status=MessageStatus.QUEUED).exists()


def test_an_administrator_address_cannot_be_anonymised(db):
    admin = AdminFactory(email="szef@example.com")
    participant = ParticipantFactory(email="szef@example.com", user=admin)
    with pytest.raises(gdpr.CannotAnonymise):
        gdpr.anonymise(participant, user=admin)


def test_participant_deletes_their_account(client, anna):
    client.force_login(anna.user)
    url = reverse("public:delete_account")
    assert "Usuń moje konto i dane" in client.get(url).content.decode()
    response = client.post(url, {"confirm": "on"})
    assert response["Location"] == reverse("public:account_deleted")
    anna.refresh_from_db()
    assert anna.is_anonymised
    assert "_auth_user_id" not in client.session
    event = AuditEvent.objects.get(action="Usunięto dane osoby (anonimizacja)")
    assert "na prośbę osoby" in event.details


def test_deleting_the_account_asks_to_withdraw_first(client, anna, level):
    ApplicationFactory(level=level, participant=anna, status=Status.ACCEPTED)
    client.force_login(anna.user)
    url = reverse("public:delete_account")
    content = client.get(url).content.decode()
    assert "Najpierw zrezygnuj" in content
    client.post(url, {"confirm": "on"})
    anna.refresh_from_db()
    assert not anna.is_anonymised


def test_organiser_anonymises_from_the_persons_card(client, anna):
    client.force_login(AdminFactory())
    card = client.get(reverse("panel:participant_detail", args=[anna.pk])).content.decode()
    assert "Ikona Pantokratora" in card
    assert "anna@example.com" in card
    url = reverse("panel:participant_anonymise", args=[anna.pk])
    assert client.post(url, {}).status_code == 200  # the box must be ticked
    client.post(url, {"confirm": "on"})
    anna.refresh_from_db()
    assert anna.is_anonymised
    card = client.get(reverse("panel:participant_detail", args=[anna.pk])).content.decode()
    assert "anna@example.com" not in card


def test_register_searches_and_hides_anonymised_people(client, anna, db):
    other = ParticipantFactory(first_name="Ewa", last_name="Zielińska")
    client.force_login(AdminFactory())
    url = reverse("panel:participant_list")
    content = client.get(url, {"q": "zielińska"}).content.decode()
    assert other.email in content
    assert "anna@example.com" not in content
    gdpr.anonymise(anna, user=None)
    assert "Anonim" not in client.get(url).content.decode()
    assert "Anonim" in client.get(url, {"anonimowi": "1"}).content.decode()
    assert Participant.objects.count() == 2


def test_register_needs_staff(client, anna):
    client.force_login(anna.user)
    assert client.get(reverse("panel:participant_list")).status_code in (302, 403)
