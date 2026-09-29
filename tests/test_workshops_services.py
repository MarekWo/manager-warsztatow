from datetime import date, time
from decimal import Decimal

import pytest
from django.core.management import call_command

from tests.factories import LevelFactory, QuestionFactory, SessionFactory, WorkshopFactory
from workshop_manager.forms_builder.models import FormTemplate, QuestionKind, TemplateQuestion
from workshop_manager.workshops.models import Location, WorkshopType
from workshop_manager.workshops.services import create_workshop, duplicate_workshop


@pytest.fixture
def seeded(db):
    call_command("seed_defaults")


def test_seed_is_idempotent_and_matches_the_word_form(seeded):
    call_command("seed_defaults")
    assert WorkshopType.objects.filter(name="Ikonopisanie").count() == 1
    assert Location.objects.count() == 1
    template = FormTemplate.objects.get(name="Ikonopisanie (standard)")
    assert template.questions.count() == 8
    boards = template.questions.filter(kind=QuestionKind.MATERIAL)
    assert sorted(boards.values_list("level_name", flat=True)) == ["Początkujący", "Zaawansowani"]


def test_seed_never_overwrites_the_administrators_edits(seeded):
    icon = WorkshopType.objects.get(name="Ikonopisanie")
    icon.default_levels = "Jedna grupa"
    icon.save()
    TemplateQuestion.objects.filter(template__name="Ikonopisanie (standard)").first().delete()
    call_command("seed_defaults")
    icon.refresh_from_db()
    assert icon.default_levels == "Jedna grupa"
    assert FormTemplate.objects.get(name="Ikonopisanie (standard)").questions.count() == 7


def test_new_icon_workshop_gets_levels_and_level_bound_questions(seeded):
    icon = WorkshopType.objects.get(name="Ikonopisanie")
    workshop = create_workshop(
        workshop_type=icon, title="Rekolekcje z ikoną", template=icon.default_form_template
    )
    assert [level.name for level in workshop.levels.all()] == ["Początkujący", "Zaawansowani"]
    assert workshop.questions.count() == 8
    board = workshop.questions.get(label__contains="26×26")
    assert board.level.name == "Początkujący"
    assert board.is_active
    assert workshop.state() == "draft"


def test_question_for_a_missing_level_is_copied_hidden(seeded):
    mosaic = WorkshopType.objects.get(name="Mozaika")
    template = FormTemplate.objects.get(name="Ikonopisanie (standard)")
    workshop = create_workshop(workshop_type=mosaic, title="Mozaika", template=template)
    assert [level.name for level in workshop.levels.all()] == ["Wszyscy uczestnicy"]
    boards = workshop.questions.filter(kind=QuestionKind.MATERIAL)
    assert boards.count() == 2
    assert not boards.filter(is_active=True).exists()
    assert not boards.filter(level__isnull=False).exists()


@pytest.mark.django_db
def test_duplicate_moves_sessions_and_copies_levels_and_questions():
    source = WorkshopFactory(
        publish_at="2025-10-01T09:00:00+02:00", notes="Cena 600 zł", subtitle="Dla wszystkich"
    )
    SessionFactory(workshop=source, date=date(2025, 11, 29), start_time=time(10), end_time=time(16))
    SessionFactory(workshop=source, date=date(2025, 12, 13), start_time=time(9), end_time=time(15))
    beginners = LevelFactory(workshop=source, name="Początkujący", price=Decimal("600"))
    QuestionFactory(workshop=source, label="Deska", level=beginners, kind=QuestionKind.MATERIAL)
    QuestionFactory(workshop=source, label="Oczekiwania", is_active=False)

    copy = duplicate_workshop(source, title="Rekolekcje 2026", first_date=date(2026, 11, 28))

    assert copy.state() == "draft"
    assert copy.publish_at is None
    assert copy.slug != source.slug
    assert [s.date for s in copy.ordered_sessions()] == [date(2026, 11, 28), date(2026, 12, 12)]
    assert copy.ordered_sessions()[1].start_time == time(9)
    level = copy.levels.get()
    assert level.price == Decimal("600")
    board = copy.questions.get(label="Deska")
    assert board.level == level
    assert not copy.questions.get(label="Oczekiwania").is_active
    assert copy.notes == "Cena 600 zł"
    assert source.questions.count() == 2  # the source is untouched


@pytest.mark.django_db
def test_duplicate_without_a_date_keeps_the_dates():
    source = WorkshopFactory()
    SessionFactory(workshop=source, date=date(2026, 1, 10))
    copy = duplicate_workshop(source, title="Kopia", first_date=None)
    assert copy.ordered_sessions()[0].date == date(2026, 1, 10)
