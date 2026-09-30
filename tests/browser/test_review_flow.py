"""The organiser reviews an application in the panel; its pages pass the accessibility check."""

import pytest
from django.conf import settings
from django.test import Client

from tests.browser.test_application_flow import serious_violations
from tests.factories import AdminFactory, ApplicationFactory, LevelFactory, WorkshopFactory
from workshop_manager.applications.models import Application, Status
from workshop_manager.communications.models import EmailMessage

pytestmark = [pytest.mark.browser, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def application():
    workshop = WorkshopFactory(title="Rekolekcje z ikoną")
    level = LevelFactory(workshop=workshop, name="Początkujący", capacity=1)
    ApplicationFactory(level=level, status=Status.WAITLISTED, waitlist_position=1)
    return ApplicationFactory(level=level, first_name="Anna", last_name="Przykładowa")


@pytest.fixture
def panel_page(live_server, page):
    client = Client()
    client.force_login(AdminFactory())
    page.context.add_cookies(
        [
            {
                "name": settings.SESSION_COOKIE_NAME,
                "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
                "url": live_server.url,
            }
        ]
    )
    return page


def test_accept_with_an_edited_email(live_server, panel_page, application):
    page = panel_page
    page.goto(f"{live_server.url}/panel/warsztaty/{application.workshop_id}/zgloszenia/")
    page.get_by_role("link", name="Przykładowa Anna").click()
    page.get_by_role("link", name="Przyjmij").click()
    body = page.get_by_label("Treść")
    assert "Dzień dobry Anna" in body.input_value()
    body.fill(body.input_value() + "\n\nDo zobaczenia w sobotę!")
    page.get_by_role("button", name="Przyjmij").click()
    page.get_by_text("Status zmieniono na „przyjęte”").wait_for()

    application.refresh_from_db()
    assert application.status == Status.ACCEPTED
    assert "Do zobaczenia w sobotę!" in EmailMessage.objects.get().body_text


@pytest.mark.parametrize(
    "path",
    [
        "/panel/zgloszenia/",
        "/panel/warsztaty/{workshop}/zgloszenia/",
        "/panel/warsztaty/{workshop}/zgloszenia/nowe/",
        "/panel/zgloszenia/{pk}/",
        "/panel/zgloszenia/{pk}/decyzja/accepted/",
        "/panel/zgloszenia/{pk}/dane/",
        "/panel/dziennik/",
    ],
)
def test_review_pages_accessibility(live_server, panel_page, application, path):
    url = path.format(workshop=application.workshop_id, pk=application.pk)
    panel_page.goto(live_server.url + url)
    assert serious_violations(panel_page) == []
    assert Application.objects.count() == 2
