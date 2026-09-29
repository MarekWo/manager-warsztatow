"""Publication and registration follow the dates alone (PRD §7.2, PLAN D6)."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest
import time_machine

from tests.factories import SessionFactory, WorkshopFactory
from workshop_manager.core.text import polish_slugify, unique_slug
from workshop_manager.workshops.models import Workshop

WARSAW = ZoneInfo("Europe/Warsaw")


def local(*args: int) -> datetime:
    return datetime(*args, tzinfo=WARSAW)


def workshop_with_sessions(**kwargs):
    workshop = WorkshopFactory(**kwargs)
    SessionFactory(
        workshop=workshop, date=date(2026, 11, 28), start_time=time(10), end_time=time(16)
    )
    SessionFactory(
        workshop=workshop, date=date(2026, 12, 12), start_time=time(10), end_time=time(16)
    )
    return workshop


@pytest.mark.django_db
def test_without_publication_date_it_is_a_draft():
    workshop = workshop_with_sessions()
    assert workshop.state() == "draft"
    assert workshop.registration_status() == "not_published"


@pytest.mark.django_db
def test_publishes_itself_at_the_minute():
    workshop = workshop_with_sessions(publish_at=local(2026, 10, 20, 9, 0))
    assert workshop.state(local(2026, 10, 20, 8, 59)) == "scheduled"
    assert workshop.state(local(2026, 10, 20, 9, 0)) == "published"


@pytest.mark.django_db
def test_home_page_query_follows_the_clock():
    workshop_with_sessions(publish_at=local(2026, 10, 20, 9, 0))
    assert not Workshop.objects.public(local(2026, 10, 20, 8, 59)).exists()
    assert Workshop.objects.public(local(2026, 10, 20, 9, 0)).count() == 1


@pytest.mark.django_db
def test_finished_after_the_last_session_and_off_the_home_page():
    workshop = workshop_with_sessions(publish_at=local(2026, 10, 1, 9, 0))
    assert workshop.state(local(2026, 12, 12, 15, 59)) == "published"
    assert workshop.state(local(2026, 12, 12, 16, 1)) == "finished"
    assert Workshop.objects.public(local(2026, 12, 12, 23, 0)).count() == 1  # still that day
    assert not Workshop.objects.public(local(2026, 12, 13, 0, 1)).exists()


@pytest.mark.django_db
def test_archive_hides_everywhere():
    workshop = workshop_with_sessions(publish_at=local(2026, 10, 1, 9, 0), is_archived=True)
    assert workshop.state(local(2026, 11, 1)) == "archived"
    assert not Workshop.objects.public(local(2026, 11, 1)).exists()


@pytest.mark.django_db
def test_registration_window_defaults_to_publication_until_first_session():
    workshop = workshop_with_sessions(publish_at=local(2026, 10, 20, 9, 0))
    assert workshop.registration_status(local(2026, 10, 20, 9, 0)) == "open"
    assert workshop.registration_status(local(2026, 11, 28, 9, 59)) == "open"
    assert workshop.registration_status(local(2026, 11, 28, 10, 0)) == "over"


@pytest.mark.django_db
def test_registration_window_explicit_dates():
    workshop = workshop_with_sessions(
        publish_at=local(2026, 10, 1, 9, 0),
        registration_opens_at=local(2026, 10, 10, 8, 0),
        registration_closes_at=local(2026, 11, 15, 23, 59),
    )
    assert workshop.registration_status(local(2026, 10, 5)) == "not_yet"
    assert workshop.registration_status(local(2026, 10, 10, 8, 0)) == "open"
    assert workshop.registration_status(local(2026, 11, 16)) == "over"


@pytest.mark.django_db
def test_manual_close_and_cancellation_close_registration():
    workshop = workshop_with_sessions(publish_at=local(2026, 10, 1), registration_closed=True)
    assert workshop.registration_status(local(2026, 10, 2)) == "closed"
    workshop.registration_closed = False
    workshop.is_cancelled = True
    assert workshop.registration_status(local(2026, 10, 2)) == "closed"


@pytest.mark.django_db
def test_session_across_the_autumn_clock_change():
    """25 Oct 2026, 02:00–03:00 happens twice in Warsaw: 01:00–04:00 lasts four real hours.

    Aware datetimes in one zone subtract as wall-clock times, so compare in UTC — as every
    comparison with `timezone.now()` does.
    """
    workshop = WorkshopFactory(publish_at=local(2026, 10, 1))
    session = SessionFactory(
        workshop=workshop, date=date(2026, 10, 25), start_time=time(1, 0), end_time=time(4, 0)
    )
    elapsed = session.ends_at().astimezone(UTC) - session.starts_at().astimezone(UTC)
    assert elapsed.total_seconds() == 4 * 3600


@pytest.mark.django_db
def test_state_uses_the_real_clock_by_default():
    workshop = workshop_with_sessions(publish_at=local(2026, 10, 20, 9, 0))
    with time_machine.travel(local(2026, 10, 20, 8, 0), tick=False):
        assert workshop.state() == "scheduled"
    with time_machine.travel(local(2026, 10, 21, 8, 0), tick=False):
        assert workshop.state() == "published"


def test_polish_slug_keeps_l_with_stroke():
    assert polish_slugify("Złocenie i pozłotnictwo — łączenie technik") == (
        "zlocenie-i-pozlotnictwo-laczenie-technik"
    )


@pytest.mark.django_db
def test_slugs_are_unique():
    first = WorkshopFactory(title="Rekolekcje z ikoną")
    second = WorkshopFactory(title="Rekolekcje z ikoną")
    assert first.slug == "rekolekcje-z-ikona"
    assert second.slug == "rekolekcje-z-ikona-2"
    assert unique_slug(Workshop, "Rekolekcje z ikoną") == "rekolekcje-z-ikona-3"
