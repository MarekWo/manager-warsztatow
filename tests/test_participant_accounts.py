"""Participant accounts: sign-in of past applicants, the one-click link, "Moje warsztaty",
withdrawing (PRD §6.4, §6.5)."""

import re
from datetime import date, timedelta

import pytest
import time_machine
from allauth.account.models import EmailAddress
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from tests.factories import (
    ApplicationFactory,
    LevelFactory,
    ParticipantFactory,
    SessionFactory,
    UserFactory,
    WorkshopFactory,
)
from workshop_manager.accounts.models import User
from workshop_manager.accounts.services import login_link_path
from workshop_manager.applications.models import Status, StatusChange
from workshop_manager.applications.tokens import withdraw_path
from workshop_manager.communications.models import EmailMessage, TemplateKey
from workshop_manager.communications.rendering import application_context
from workshop_manager.core.models import SiteSettings

CODE = re.compile(r"\b(\d{6})\b")
LINK = re.compile(r"https?://\S+/konto/link/\S+/")


@pytest.fixture
def level(db):
    workshop = WorkshopFactory(title="Rekolekcje z ikoną", publish_at=timezone.now())
    SessionFactory(workshop=workshop, date=timezone.localdate() + timedelta(days=30))
    return LevelFactory(workshop=workshop, name="Początkujący")


@pytest.fixture
def site(db):
    site = SiteSettings.load()
    site.contact_email = "organizator@example.com"
    site.save()
    return site


def request_code(client, email):
    return client.post(reverse("account_request_login_code"), {"email": email, "remember": "on"})


# --- Signing in ---------------------------------------------------------------------------------


def test_a_past_applicant_gets_an_account_and_sees_their_applications(client, level):
    application = ApplicationFactory(level=level)
    email = application.email
    assert not User.objects.exists()

    request_code(client, email.upper())
    user = User.objects.get()
    assert user.email == email
    assert user.first_name == application.first_name

    code = CODE.search(mail.outbox[-1].body).group(1)
    response = client.post(reverse("account_confirm_login_code"), {"code": code})
    assert response.status_code == 302
    assert EmailAddress.objects.get(user=user).verified
    application.participant.refresh_from_db()
    assert application.participant.user == user

    page = client.get(reverse("public:my_workshops")).content.decode()
    assert "Rekolekcje z ikoną" in page
    assert "oczekuje na decyzję" in page


def test_an_unknown_address_gets_no_account_and_the_page_looks_the_same(client, db):
    known = request_code(client, "nikt@example.com")
    assert known["Location"] == reverse("account_confirm_login_code")
    assert not User.objects.exists()
    assert "nie wysłano jeszcze żadnego zgłoszenia" in mail.outbox[-1].body


def test_the_one_click_link_signs_in_on_post_and_only_once(client, level):
    user = UserFactory()
    request_code(client, user.email)
    link = LINK.search(mail.outbox[-1].body).group(0)
    path = "/" + link.split("/", 3)[3]

    fresh = client.__class__()
    page = fresh.get(path)
    assert "Zaloguj się" in page.content.decode()
    assert "_auth_user_id" not in fresh.session  # a link checker opening it signs nobody in

    response = fresh.post(path, {"remember": "on"})
    assert response["Location"] == reverse("public:my_workshops")
    assert fresh.session["_auth_user_id"] == str(user.pk)

    again = client.__class__().post(path, {"remember": "on"})
    assert "już nie działa" in again.content.decode()


def test_the_link_expires_with_the_code(client, db):
    user = UserFactory()
    path = login_link_path(user)
    with time_machine.travel(timezone.now() + timedelta(minutes=16)):
        response = client.post(path)
    assert "już nie działa" in response.content.decode()
    assert "_auth_user_id" not in client.session


def test_thank_you_page_offers_to_remember_the_details(client, level):
    from tests.test_applications_form import started

    workshop = level.workshop
    data = {
        "level": level.pk,
        "first_name": "Anna",
        "last_name": "Nowak",
        "email": "anna.nowak@example.com",
        "phone": "600 100 200",
        "adult": "on",
        "privacy": "on",
        "started": started(),
    }
    response = client.post(reverse("public:apply", args=[workshop.slug]), data, follow=True)
    page = response.content.decode()
    assert "Zapamiętaj moje dane" in page
    assert reverse("account_request_login_code") in page


# --- Moje warsztaty ------------------------------------------------------------------------------


@pytest.fixture
def participant_client(client, level):
    user = UserFactory(email="anna@example.com")
    participant = ParticipantFactory(email="anna@example.com", user=user)
    client.force_login(user)
    client.application = ApplicationFactory(level=level, participant=participant)
    return client


def test_pages_need_signing_in(client, db):
    response = client.get(reverse("public:my_workshops"))
    assert response.status_code == 302
    assert "/konto/login/code/" in response["Location"]


def test_someone_elses_application_is_not_found(participant_client, level):
    other = ApplicationFactory(level=level)
    url = reverse("public:my_application", args=[other.pk])
    assert participant_client.get(url).status_code == 404


def test_withdrawing_from_the_account(participant_client, level, site):
    application = participant_client.application
    application.status = Status.ACCEPTED
    application.is_seen = True
    application.save()
    waiting = ApplicationFactory(level=level, status=Status.WAITLISTED, waitlist_position=1)

    url = reverse("public:my_application", args=[application.pk])
    assert "Rezygnuję z udziału" in participant_client.get(url).content.decode()
    participant_client.post(url, {"reason": "Choroba w rodzinie"})

    application.refresh_from_db()
    assert application.status == Status.WITHDRAWN
    assert not application.is_seen
    assert "Choroba w rodzinie" in StatusChange.objects.get().comment
    keys = set(EmailMessage.objects.values_list("template_key", flat=True))
    assert keys == {TemplateKey.WITHDRAWAL_CONFIRMED, TemplateKey.ADMIN_WITHDRAWAL}
    notice = EmailMessage.objects.get(template_key=TemplateKey.ADMIN_WITHDRAWAL)
    assert notice.to_email == "organizator@example.com"
    assert waiting.full_name in notice.body_text
    # Once is enough.
    assert "Rezygnuję z udziału" not in participant_client.get(url).content.decode()


def test_withdrawing_with_the_link_from_an_email(client, level, site):
    application = ApplicationFactory(level=level)
    assert withdraw_path(application.pk) in application_context(application)["link_rezygnacji"]
    url = withdraw_path(application.pk)
    assert "Rezygnuję z udziału" in client.get(url).content.decode()
    response = client.post(url, {"reason": ""})
    assert "Zapisaliśmy Twoją rezygnację" in response.content.decode()
    application.refresh_from_db()
    assert application.status == Status.WITHDRAWN
    assert "przez link z e-maila" in StatusChange.objects.get().comment


def test_a_forged_withdrawal_link_is_not_found(client, db):
    assert client.get(reverse("public:withdraw", args=["1:forged"])).status_code == 404


def test_no_withdrawal_after_the_workshop(client, level):
    application = ApplicationFactory(level=level, status=Status.ACCEPTED)
    level.workshop.sessions.update(date=date(2020, 1, 1))
    response = client.post(withdraw_path(application.pk), {"reason": ""})
    assert "nie można już zrezygnować" in response.content.decode()
    application.refresh_from_db()
    assert application.status == Status.ACCEPTED


def test_editing_my_data_and_consent(participant_client):
    participant_client.post(
        reverse("public:my_data"),
        {"first_name": "Anna", "last_name": "Nowa", "phone": "600 000 111", "marketing": "on"},
    )
    user = User.objects.get(email="anna@example.com")
    participant = participant_client.application.participant
    participant.refresh_from_db()
    assert (user.last_name, user.phone) == ("Nowa", "600 000 111")
    assert participant.last_name == "Nowa"
    assert participant.marketing_consent
    assert participant.marketing_consent_at is not None


def test_the_form_is_prefilled_for_a_signed_in_participant(participant_client, level):
    user = User.objects.get(email="anna@example.com")
    user.phone = "600 999 888"
    user.save()
    # Another workshop: the one they applied for sends them to their application instead.
    other = WorkshopFactory(publish_at=timezone.now())
    SessionFactory(workshop=other, date=timezone.localdate() + timedelta(days=40))
    LevelFactory(workshop=other)
    page = participant_client.get(reverse("public:apply", args=[other.slug]))
    assert 'value="600 999 888"' in page.content.decode()


def test_codes_to_one_address_are_limited(client, db):
    user = UserFactory()
    request_code(client, user.email)
    sent = len(mail.outbox)
    response = client.__class__().post(reverse("account_request_login_code"), {"email": user.email})
    assert response.status_code == 200  # the form comes back with an error
    assert len(mail.outbox) == sent
