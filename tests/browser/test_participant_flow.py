"""A regular participant signs in on a phone, applies again without typing, sees the history."""

import re
from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from tests.browser.test_application_flow import serious_violations
from tests.factories import ApplicationFactory, LevelFactory, SessionFactory, WorkshopFactory
from workshop_manager.applications.models import Application, Status

pytestmark = [pytest.mark.browser, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def workshops():
    def make(title, days):
        workshop = WorkshopFactory(title=title, publish_at=timezone.now() - timedelta(days=60))
        SessionFactory(workshop=workshop, date=timezone.localdate() + timedelta(days=days))
        return LevelFactory(workshop=workshop, name="Początkujący")

    earlier = make("Ikona Zwiastowania", -30)
    ApplicationFactory(
        level=earlier,
        first_name="Anna",
        last_name="Stała",
        participant__email="anna.stala@example.com",
        participant__first_name="Anna",
        participant__last_name="Stała",
        participant__phone="600100200",
        status=Status.ACCEPTED,
    )
    return make("Ikona Bożego Narodzenia", 30).workshop


def test_regular_participant_on_a_phone(live_server, phone_page, workshops):
    page = phone_page
    page.goto(f"{live_server.url}/konto/login/code/")
    page.get_by_label("Adres e-mail").fill("anna.stala@example.com")
    page.get_by_role("button", name="Wyślij mi kod").click()
    page.get_by_label("Kod").wait_for()
    code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
    page.get_by_label("Kod").fill(code)
    page.get_by_role("button", name=re.compile("Zaloguj|Potwierdź")).click()

    page.goto(f"{live_server.url}/warsztaty/{workshops.slug}/zgloszenie/")
    assert page.get_by_role("textbox", name="Imię", exact=True).input_value() == "Anna"
    assert page.get_by_role("textbox", name="Telefon").input_value() == "600100200"
    page.get_by_label("Potwierdzam, że jestem osobą pełnoletnią").check()
    page.get_by_label("Wyrażam zgodę na przetwarzanie").check()
    page.get_by_role("button", name="Wyślij zgłoszenie").click()
    page.get_by_role("heading", name="Dziękujemy").wait_for()
    assert Application.objects.count() == 2

    page.goto(f"{live_server.url}/moje-warsztaty/")
    page.get_by_text("Ikona Bożego Narodzenia").wait_for()
    assert page.get_by_text("Ikona Zwiastowania").is_visible()
    assert serious_violations(page) == []

    page.get_by_role("link", name="Ikona Bożego Narodzenia").click()
    page.get_by_role("button", name="Rezygnuję z udziału").wait_for()
    assert serious_violations(page) == []

    page.goto(f"{live_server.url}/moje-dane/")
    page.get_by_role("button", name="Zapisz").wait_for()
    assert serious_violations(page) == []


def test_withdrawal_link_page_accessibility(live_server, page, workshops):
    from workshop_manager.applications.tokens import withdraw_path

    application = ApplicationFactory(level=workshops.levels.get())
    page.goto(live_server.url + withdraw_path(application.pk))
    page.get_by_role("button", name="Rezygnuję z udziału").wait_for()
    assert serious_violations(page) == []
