"""Pages about a person's data and the error pages pass the accessibility check; a participant
deletes their account on a phone."""

import pytest
from django.conf import settings
from django.test import Client

from tests.browser.test_application_flow import serious_violations
from tests.factories import (
    AdminFactory,
    ApplicationFactory,
    LevelFactory,
    ParticipantFactory,
    UserFactory,
    WorkshopFactory,
)
from workshop_manager.applications.models import Participant, Status
from workshop_manager.applications.tokens import unsubscribe_path

pytestmark = [pytest.mark.browser, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def participant():
    user = UserFactory(email="anna@example.com")
    person = ParticipantFactory(
        email="anna@example.com", first_name="Anna", last_name="Przykładowa", user=user
    )
    level = LevelFactory(workshop=WorkshopFactory(title="Ikona Pantokratora"))
    ApplicationFactory(level=level, participant=person, status=Status.REJECTED)
    person.marketing_consent = True
    person.save()
    return person


def sign_in(page, live_server, user):
    client = Client()
    client.force_login(user)
    page.context.add_cookies(
        [
            {
                "name": settings.SESSION_COOKIE_NAME,
                "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
                "url": live_server.url,
            }
        ]
    )


@pytest.mark.parametrize(
    "path", ["/panel/uczestnicy/", "/panel/uczestnicy/{pk}/", "/panel/uczestnicy/{pk}/usun-dane/"]
)
def test_panel_people_pages_accessibility(live_server, page, participant, path):
    sign_in(page, live_server, AdminFactory())
    page.goto(live_server.url + path.format(pk=participant.pk))
    assert serious_violations(page) == []


@pytest.mark.parametrize("path", ["/moje-dane/", "/moje-dane/usun-konto/", "unsubscribe"])
def test_participant_data_pages_accessibility(live_server, phone_page, participant, path):
    sign_in(phone_page, live_server, participant.user)
    if path == "unsubscribe":
        path = unsubscribe_path(participant.pk)
    phone_page.goto(live_server.url + path)
    assert serious_violations(phone_page) == []


def test_error_page_accessibility(live_server, phone_page, db):
    response = phone_page.goto(live_server.url + "/nie-ma-takiej-strony/")
    assert response is not None
    assert response.status == 404
    assert serious_violations(phone_page) == []


def test_participant_deletes_their_account_on_a_phone(live_server, phone_page, participant):
    page = phone_page
    sign_in(page, live_server, participant.user)
    page.goto(live_server.url + "/moje-dane/")
    page.get_by_role("link", name="Usuń moje konto").click()
    page.get_by_label("Rozumiem, że moje dane zostaną usunięte").check()
    page.get_by_role("button", name="Usuń moje konto i dane").click()
    page.get_by_role("heading", name="Konto zostało usunięte").wait_for()
    assert Participant.objects.get(pk=participant.pk).is_anonymised
    assert serious_violations(page) == []
