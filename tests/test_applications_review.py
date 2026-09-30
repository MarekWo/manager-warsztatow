"""Reviewing applications: decisions, the waiting list, history and the event log (PRD §7.3)."""

import pytest

from tests.factories import AdminFactory, ApplicationFactory, LevelFactory, WorkshopFactory
from workshop_manager.applications import decisions
from workshop_manager.applications.models import Status, StatusChange
from workshop_manager.applications.summary import level_summaries
from workshop_manager.communications.models import EmailMessage, TemplateKey
from workshop_manager.core.models import AuditEvent


@pytest.fixture
def admin(db):
    return AdminFactory(email="admin@example.com")


@pytest.fixture
def level(db):
    workshop = WorkshopFactory(title="Rekolekcje z ikoną")
    return LevelFactory(workshop=workshop, name="Początkujący", capacity=2)


def statuses(*applications):
    return [type(a).objects.get(pk=a.pk).status for a in applications]


# --- Status machine -------------------------------------------------------------------------------


def test_accepting_writes_history_event_and_the_decision_email(level, admin):
    application = ApplicationFactory(level=level, first_name="Anna")
    decisions.change_status(application, Status.ACCEPTED, user=admin, comment="Stała bywalczyni")

    application.refresh_from_db()
    assert application.status == Status.ACCEPTED
    assert application.is_seen
    change = StatusChange.objects.get()
    assert (change.old_status, change.new_status, change.notified) == ("new", "accepted", True)
    assert change.changed_by == admin
    assert change.comment == "Stała bywalczyni"
    email = EmailMessage.objects.get()
    assert email.template_key == TemplateKey.DECISION_ACCEPTED
    assert email.to_email == application.email
    assert "Dzień dobry Anna" in email.body_text
    assert "Rekolekcje z ikoną" in email.subject
    event = AuditEvent.objects.get()
    assert event.action == "Przyjęto zgłoszenie"
    assert event.actor_email == "admin@example.com"
    assert event.url == application.get_panel_url()


def test_decision_without_notification_sends_nothing(level, admin):
    application = ApplicationFactory(level=level)
    decisions.change_status(application, Status.REJECTED, user=admin, notify=False)
    assert not EmailMessage.objects.exists()
    assert StatusChange.objects.get().notified is False


def test_the_edited_email_is_sent_as_edited(level, admin):
    application = ApplicationFactory(level=level, first_name="Anna")
    preview = decisions.decision_email(application, Status.ACCEPTED)
    assert preview is not None
    assert "{imie}" not in preview.body
    edited = decisions.EmailText(
        subject=preview.subject, body=preview.body + "\n\nCzekamy na Ciebie, {imie}!"
    )
    decisions.change_status(application, Status.ACCEPTED, user=admin, email=edited)
    assert "Czekamy na Ciebie, Anna!" in EmailMessage.objects.get().body_text


@pytest.mark.parametrize(
    ("start", "target"),
    [
        (Status.NEW, Status.CANCELLED),
        (Status.ACCEPTED, Status.REJECTED),
        (Status.WAITLISTED, Status.NEW),
        (Status.REJECTED, Status.CANCELLED),
    ],
)
def test_transitions_outside_the_map_are_refused(level, admin, start, target):
    application = ApplicationFactory(level=level, status=start)
    with pytest.raises(decisions.TransitionError):
        decisions.change_status(application, target, user=admin)
    assert not StatusChange.objects.exists()


def test_reactivation_is_refused_while_another_application_is_active(level, admin):
    old = ApplicationFactory(level=level, status=Status.WITHDRAWN)
    ApplicationFactory(level=level, participant=old.participant)
    with pytest.raises(decisions.TransitionError, match="inne aktywne zgłoszenie"):
        decisions.change_status(old, Status.ACCEPTED, user=admin)


def test_bulk_decision_skips_what_is_not_allowed(level, admin):
    fresh = ApplicationFactory(level=level)
    rejected = ApplicationFactory(level=level, status=Status.REJECTED, first_name="Ewa")
    cancelled = ApplicationFactory(level=level, status=Status.CANCELLED)
    changed, skipped = decisions.bulk_change_status(
        [fresh, rejected, cancelled], Status.REJECTED, user=admin, notify=True
    )
    assert changed == 1
    assert len(skipped) == 2
    assert EmailMessage.objects.count() == 1


# --- Waiting list ---------------------------------------------------------------------------------


def test_waiting_list_positions_follow_the_order_of_decisions(level, admin):
    first, second, third = (ApplicationFactory(level=level) for _ in range(3))
    for application in (first, second, third):
        decisions.change_status(application, Status.WAITLISTED, user=admin, notify=False)
    positions = [type(a).objects.get(pk=a.pk).waitlist_position for a in (first, second, third)]
    assert positions == [1, 2, 3]

    decisions.change_status(first, Status.ACCEPTED, user=admin, notify=False)
    second.refresh_from_db()
    third.refresh_from_db()
    assert (second.waitlist_position, third.waitlist_position) == (1, 2)

    decisions.move_on_waitlist(third, "up")
    second.refresh_from_db()
    third.refresh_from_db()
    assert (third.waitlist_position, second.waitlist_position) == (1, 2)


def test_waitlist_email_tells_the_place(level, admin):
    ApplicationFactory(level=level, status=Status.WAITLISTED, waitlist_position=1)
    application = ApplicationFactory(level=level)
    decisions.change_status(application, Status.WAITLISTED, user=admin)
    assert "miejsce na liście: 2" in EmailMessage.objects.get().body_text


def test_a_freed_place_suggests_the_first_waiting_person(level, admin):
    accepted = ApplicationFactory(level=level, status=Status.ACCEPTED)
    waiting = ApplicationFactory(level=level, status=Status.WAITLISTED, waitlist_position=1)
    decisions.change_status(accepted, Status.WITHDRAWN, user=admin, notify=False)
    assert decisions.freed_place_hint(accepted, Status.ACCEPTED) == waiting
    # Nobody is promoted automatically.
    waiting.refresh_from_db()
    assert waiting.status == Status.WAITLISTED


def test_changing_level_moves_the_person_to_the_end_of_the_other_list(level, admin):
    other = LevelFactory(workshop=level.workshop, name="Zaawansowani")
    ApplicationFactory(level=other, status=Status.WAITLISTED, waitlist_position=1)
    moving = ApplicationFactory(level=level, status=Status.WAITLISTED, waitlist_position=1)
    staying = ApplicationFactory(level=level, status=Status.WAITLISTED, waitlist_position=2)
    decisions.change_level(moving, other, user=admin)
    moving.refresh_from_db()
    staying.refresh_from_db()
    assert (moving.level, moving.waitlist_position) == (other, 2)
    assert staying.waitlist_position == 1
    assert "Początkujący → Zaawansowani" in StatusChange.objects.get().comment


def test_level_summary_counts_against_the_limit(level):
    for status in [Status.ACCEPTED] * 3 + [Status.NEW, Status.WAITLISTED, Status.WITHDRAWN]:
        ApplicationFactory(level=level, status=status)
    workshop = level.workshop
    summary = level_summaries([workshop])[workshop.pk][0]
    assert (summary.accepted, summary.new, summary.waitlisted, summary.left) == (3, 1, 1, 1)
    assert summary.over_capacity
    assert summary.free == -1
    assert not summary.place_for_waitlisted
