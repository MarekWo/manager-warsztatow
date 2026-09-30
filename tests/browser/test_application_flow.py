"""A person applies from a phone; key pages pass an automated accessibility check."""

from datetime import date, timedelta

import pytest
from axe_playwright_python.sync_playwright import Axe
from django.utils import timezone

from tests.factories import LevelFactory, QuestionFactory, SessionFactory, WorkshopFactory
from workshop_manager.applications.models import Application
from workshop_manager.forms_builder.models import QuestionKind

pytestmark = [pytest.mark.browser, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def workshop():
    workshop = WorkshopFactory(
        title="Rekolekcje z ikoną", publish_at=timezone.now() - timedelta(days=1)
    )
    SessionFactory(workshop=workshop, date=date.today() + timedelta(days=30))
    beginners = LevelFactory(workshop=workshop, name="Początkujący", order=0)
    advanced = LevelFactory(workshop=workshop, name="Zaawansowani", order=1)
    QuestionFactory(
        workshop=workshop,
        label="Zamawiam deskę 26×26 cm",
        kind=QuestionKind.MATERIAL,
        choices="Tak, zamawiam\nMam własną",
        level=beginners,
    )
    QuestionFactory(
        workshop=workshop,
        label="Zamawiam deskę 30×42 cm",
        kind=QuestionKind.MATERIAL,
        choices="Tak, zamawiam\nMam własną",
        level=advanced,
    )
    QuestionFactory(
        workshop=workshop, label="Opisz swoje doświadczenie", kind=QuestionKind.LONG_TEXT
    )
    return workshop


def serious_violations(page) -> list[str]:
    results = Axe().run(page)
    return [
        f"{v['id']}: {v['help']}"
        for v in results.response["violations"]
        if v["impact"] in ("serious", "critical")
    ]


def test_apply_from_a_phone(live_server, phone_page, workshop):
    page = phone_page
    page.goto(live_server.url)
    page.get_by_role("link", name="Rekolekcje z ikoną").click()
    page.get_by_role("link", name="Zapisz się").click()

    # Only the chosen level's board question is shown.
    advanced_board = page.get_by_text("Zamawiam deskę 30×42 cm")
    page.get_by_label("Początkujący").check()
    assert not advanced_board.is_visible()
    page.get_by_label("Zaawansowani").check()
    assert advanced_board.is_visible()
    page.get_by_label("Początkujący").check()

    page.get_by_role("textbox", name="Imię", exact=True).fill("Anna")
    page.get_by_role("textbox", name="Nazwisko").fill("Nowak")
    page.get_by_role("textbox", name="Adres e-mail").fill("anna@example.com")
    page.get_by_role("textbox", name="Telefon").fill("600100200")
    page.get_by_label("Tak, zamawiam").first.check()
    page.get_by_role("textbox", name="Opisz swoje doświadczenie").fill("Pierwszy raz.")
    page.get_by_label("Potwierdzam, że jestem osobą pełnoletnią").check()
    page.get_by_label("Wyrażam zgodę na przetwarzanie").check()
    page.get_by_role("button", name="Wyślij zgłoszenie").click()

    page.get_by_role("heading", name="Dziękujemy").wait_for()
    application = Application.objects.get()
    assert application.level.name == "Początkujący"
    labels = list(application.answers.values_list("label", flat=True))
    assert "Zamawiam deskę 30×42 cm" not in labels


def test_errors_are_listed_and_focused(live_server, phone_page, workshop):
    page = phone_page
    page.goto(f"{live_server.url}/warsztaty/{workshop.slug}/zgloszenie/")
    page.get_by_role("button", name="Wyślij zgłoszenie").click()
    summary = page.locator("#form-errors")
    summary.wait_for()
    assert "Nie udało się wysłać zgłoszenia" in summary.inner_text()
    assert page.evaluate("document.activeElement.id") == "form-errors"


@pytest.mark.parametrize(
    "path", ["/", "/warsztaty/{slug}/", "/warsztaty/{slug}/zgloszenie/", "/konto/login/code/"]
)
def test_accessibility(live_server, page, workshop, path):
    page.goto(live_server.url + path.format(slug=workshop.slug))
    assert serious_violations(page) == []


@pytest.mark.parametrize(
    "path",
    [
        "/panel/",
        "/panel/warsztaty/{pk}/",
        "/panel/warsztaty/{pk}/formularz/",
        "/panel/miejsca/",
        "/panel/ustawienia/",
        "/panel/ustawienia/e-maile/application_received/",
        "/panel/ustawienia/rodzaje/",
        "/panel/ustawienia/szablony/",
        "/panel/e-maile/",
    ],
)
def test_panel_accessibility(live_server, page, workshop, path):
    from django.conf import settings
    from django.test import Client

    from tests.factories import AdminFactory

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
    page.goto(live_server.url + path.format(pk=workshop.pk))
    assert serious_violations(page) == []
