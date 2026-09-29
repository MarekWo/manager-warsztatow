from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest
import time_machine
from django.urls import reverse

from tests.factories import AdminFactory, LevelFactory, SessionFactory, WorkshopFactory

WARSAW = ZoneInfo("Europe/Warsaw")
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=WARSAW)


def published(**kwargs):
    workshop = WorkshopFactory(publish_at=datetime(2026, 10, 20, 9, tzinfo=WARSAW), **kwargs)
    SessionFactory(
        workshop=workshop, date=date(2026, 11, 28), start_time=time(10), end_time=time(16)
    )
    SessionFactory(
        workshop=workshop, date=date(2026, 12, 12), start_time=time(10), end_time=time(16)
    )
    LevelFactory(workshop=workshop, name="Początkujący", price=600, price_note="deska osobno")
    return workshop


@pytest.fixture(autouse=True)
def _clock():
    with time_machine.travel(NOW, tick=False):
        yield


@pytest.mark.django_db
def test_home_lists_published_workshops_only(client):
    published(title="Rekolekcje z ikoną")
    WorkshopFactory(title="Szkic mozaiki")
    content = client.get(reverse("public:home")).content.decode()
    assert "Rekolekcje z ikoną" in content
    assert "28.11–12.12.2026 · 2 spotkania" in content
    assert "Zapisy otwarte" in content
    assert "Szkic mozaiki" not in content
    assert "Obecnie nie są planowane" not in content


@pytest.mark.django_db
def test_workshop_page_shows_dates_levels_and_sections(client):
    workshop = published(notes="Wpłaty po 1 stycznia.", program="Dzień 1: rysunek")
    content = client.get(workshop.get_absolute_url()).content.decode()
    assert "sobota, 28 listopada 2026" in content
    assert "10:00–16:00" in content
    assert "600 zł" in content
    assert "deska osobno" in content
    assert "Wpłaty po 1 stycznia." in content
    assert "Dzień 1: rysunek" not in content  # the programme section is off by default


@pytest.mark.django_db
def test_drafts_are_hidden_from_visitors_but_previewable_by_staff(client):
    draft = WorkshopFactory()
    assert client.get(draft.get_absolute_url()).status_code == 404
    client.force_login(AdminFactory())
    response = client.get(draft.get_absolute_url())
    assert response.status_code == 200
    assert "Podgląd." in response.content.decode()


@pytest.mark.django_db
def test_cancelled_workshop_says_so(client):
    workshop = published(is_cancelled=True, cancellation_note="Choroba prowadzącego.")
    content = client.get(workshop.get_absolute_url()).content.decode()
    assert "Warsztat został odwołany." in content
    assert "Choroba prowadzącego." in content


@pytest.mark.django_db
def test_description_is_escaped_and_links_are_clickable(client):
    workshop = published(description="<script>alert(1)</script>\n\nZobacz https://example.com")
    content = client.get(workshop.get_absolute_url()).content.decode()
    assert "<script>alert(1)</script>" not in content
    assert '<a href="https://example.com"' in content
