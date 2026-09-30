"""Retake the help's screenshots from the demo data: `uv run pytest -m screenshots`.

Not a test of behaviour: it writes `workshop_manager/static/help/<name>.png`, which the help's
`{% help_shot %}` shows. Run it after a visible change in the panel and commit the pictures.
All people in the demo data are made up (`@example.com`).
"""

from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.test import Client

from tests.factories import AdminFactory
from workshop_manager.applications.models import Application, Status
from workshop_manager.communications.models import Broadcast, Group
from workshop_manager.workshops.models import Workshop

pytestmark = [pytest.mark.screenshots, pytest.mark.django_db(transaction=True)]

OUT = Path(settings.BASE_DIR) / "workshop_manager" / "static" / "help"
VIEWPORT = {"width": 1280, "height": 860}


@pytest.fixture
def demo():
    call_command("seed_defaults", verbosity=0)
    call_command("seed_demo", verbosity=0)
    upcoming = Workshop.objects.get(title="Pokaz: Ikona Bożego Narodzenia")
    ongoing = Workshop.objects.get(title="Pokaz: Rekolekcje z ikoną (trwające)")
    broadcast = Broadcast.objects.create(
        workshop=upcoming,
        group=Group.ACCEPTED,
        subject="Co zabrać na warsztaty",
        body="Dzień dobry {imie},\n\nprzypominamy, że warsztaty zaczynają się {terminy}.\n"
        "Prosimy zabrać fartuch i ołówek.\n\nDo zobaczenia!",
    )
    return {"upcoming": upcoming, "ongoing": ongoing, "broadcast": broadcast}


@pytest.fixture
def admin_page(live_server, browser):
    context = browser.new_context(viewport=VIEWPORT, locale="pl-PL", timezone_id="Europe/Warsaw")
    client = Client()
    client.force_login(AdminFactory(email="organizator@example.com"))
    context.add_cookies(
        [
            {
                "name": settings.SESSION_COOKIE_NAME,
                "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
                "url": live_server.url,
            }
        ]
    )
    page = context.new_page()
    yield page
    context.close()


def shoot(page, url: str, name: str) -> None:
    page.goto(url)
    page.wait_for_load_state("networkidle")
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / f"{name}.png"))


def test_take_help_screenshots(live_server, admin_page, demo):
    base = live_server.url
    upcoming, ongoing = demo["upcoming"], demo["ongoing"]
    new = Application.objects.filter(workshop=upcoming, status=Status.NEW).first()
    assert new is not None

    shoot(admin_page, f"{base}/panel/", "pulpit")
    shoot(admin_page, f"{base}/panel/warsztaty/{upcoming.pk}/", "warsztat-edycja")
    shoot(admin_page, f"{base}/panel/warsztaty/{upcoming.pk}/formularz/", "formularz")
    shoot(admin_page, f"{base}/panel/warsztaty/{upcoming.pk}/zgloszenia/", "zgloszenia")
    shoot(admin_page, f"{base}/panel/zgloszenia/{new.pk}/decyzja/accepted/", "decyzja")
    shoot(
        admin_page,
        f"{base}/panel/warsztaty/{upcoming.pk}/wiadomosci/{demo['broadcast'].pk}/",
        "wiadomosc",
    )
    shoot(admin_page, f"{base}/panel/warsztaty/{ongoing.pk}/lista-obecnosci/", "lista-obecnosci")
    for name in ["pulpit", "warsztat-edycja", "formularz", "zgloszenia", "decyzja"]:
        assert (OUT / f"{name}.png").stat().st_size > 10_000
