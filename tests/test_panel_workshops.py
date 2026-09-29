"""The administrator's workshop screens (PRD §7.2) and the form editor (PRD §6.3)."""

from datetime import date, time

import pytest
from django.core.management import call_command
from django.urls import reverse

from tests.factories import (
    AdminFactory,
    LevelFactory,
    QuestionFactory,
    SessionFactory,
    UserFactory,
    WorkshopFactory,
)
from workshop_manager.forms_builder.models import Question, QuestionKind
from workshop_manager.workshops.models import Workshop, WorkshopType


@pytest.fixture
def admin_client(client, db):
    client.force_login(AdminFactory())
    return client


def edit_payload(workshop: Workshop, **overrides) -> dict:
    """The edit form as the browser would post it, with every session and level unchanged."""
    data = {
        "type": workshop.type_id,
        "title": workshop.title,
        "subtitle": workshop.subtitle,
        "description": workshop.description,
        "leader": workshop.leader,
        "location": workshop.location_id or "",
        "show_location": "on",
        "notes": workshop.notes,
        "show_notes": "on",
        "publish_at": "",
        "registration_opens_at": "",
        "registration_closes_at": "",
        "cancellation_note": "",
    }
    sessions = list(workshop.sessions.all())
    data |= {
        "sessions-TOTAL_FORMS": str(len(sessions)),
        "sessions-INITIAL_FORMS": str(len(sessions)),
        "sessions-MIN_NUM_FORMS": "1",
        "sessions-MAX_NUM_FORMS": "1000",
    }
    for i, session in enumerate(sessions):
        data |= {
            f"sessions-{i}-id": session.pk,
            f"sessions-{i}-date": session.date.isoformat(),
            f"sessions-{i}-start_time": session.start_time.strftime("%H:%M"),
            f"sessions-{i}-end_time": session.end_time.strftime("%H:%M"),
            f"sessions-{i}-note": session.note,
        }
    levels = list(workshop.levels.all())
    data |= {
        "levels-TOTAL_FORMS": str(len(levels)),
        "levels-INITIAL_FORMS": str(len(levels)),
        "levels-MIN_NUM_FORMS": "1",
        "levels-MAX_NUM_FORMS": "1000",
    }
    for i, level in enumerate(levels):
        data |= {
            f"levels-{i}-id": level.pk,
            f"levels-{i}-name": level.name,
            f"levels-{i}-capacity": level.capacity or "",
            f"levels-{i}-price": level.price or "",
        }
    return data | overrides


def full_workshop(**kwargs) -> Workshop:
    workshop = WorkshopFactory(**kwargs)
    SessionFactory(workshop=workshop)
    LevelFactory(workshop=workshop)
    return workshop


# --- Access -----------------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name", ["panel:dashboard", "panel:workshop_list", "panel:workshop_create"]
)
def test_panel_needs_a_staff_account(client, name):
    assert client.get(reverse(name)).status_code == 302
    client.force_login(UserFactory())
    response = client.get(reverse(name))
    assert response.status_code == 302
    assert "/konto/login/code/" in response["Location"]


@pytest.mark.django_db
def test_dashboard_and_list_render(admin_client):
    full_workshop(title="Mozaika jesienna")
    assert admin_client.get(reverse("panel:dashboard")).status_code == 200
    response = admin_client.get(reverse("panel:workshop_list") + "?tab=draft")
    assert "Mozaika jesienna" in response.content.decode()


# --- Create, edit -----------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_makes_a_draft_from_the_type_defaults(admin_client):
    call_command("seed_defaults")
    icon = WorkshopType.objects.get(name="Ikonopisanie")
    response = admin_client.post(
        reverse("panel:workshop_create"), {"type": icon.pk, "title": "Rekolekcje z ikoną"}
    )
    workshop = Workshop.objects.get(title="Rekolekcje z ikoną")
    assert response["Location"] == reverse("panel:workshop_edit", args=[workshop.pk])
    assert workshop.levels.count() == 2
    assert workshop.questions.count() == 8
    assert workshop.created_by is not None


@pytest.mark.django_db
def test_edit_saves_workshop_sessions_and_levels(admin_client):
    workshop = full_workshop()
    data = edit_payload(workshop, title="Nowy tytuł", publish_at="2026-10-20T09:00")
    data |= {
        "sessions-TOTAL_FORMS": "2",
        "sessions-1-date": "2026-12-12",
        "sessions-1-start_time": "10:00",
        "sessions-1-end_time": "16:00",
        "levels-0-price": "650",
    }
    response = admin_client.post(reverse("panel:workshop_edit", args=[workshop.pk]), data)
    assert response.status_code == 302
    workshop.refresh_from_db()
    assert workshop.title == "Nowy tytuł"
    assert workshop.sessions.count() == 2
    assert workshop.levels.get().price == 650
    assert workshop.publish_at.hour == 7  # 09:00 in Warsaw is 07:00 UTC in October (CEST)


@pytest.mark.django_db
def test_edit_rejects_a_session_ending_before_it_starts(admin_client):
    workshop = full_workshop()
    data = edit_payload(workshop, **{"sessions-0-end_time": "09:00"})
    response = admin_client.post(reverse("panel:workshop_edit", args=[workshop.pk]), data)
    assert response.status_code == 200
    assert "Koniec spotkania musi być po jego rozpoczęciu." in response.content.decode()


@pytest.mark.django_db
def test_edit_needs_at_least_one_session(admin_client):
    workshop = full_workshop()
    data = edit_payload(workshop, **{"sessions-0-DELETE": "on"})
    response = admin_client.post(reverse("panel:workshop_edit", args=[workshop.pk]), data)
    assert response.status_code == 200
    assert workshop.sessions.count() == 1


@pytest.mark.django_db
def test_cancelling_needs_a_reason(admin_client):
    workshop = full_workshop()
    data = edit_payload(workshop, is_cancelled="on")
    response = admin_client.post(reverse("panel:workshop_edit", args=[workshop.pk]), data)
    assert "dlaczego warsztat jest odwołany" in response.content.decode()


@pytest.mark.django_db
def test_extra_row_raises_total_forms_out_of_band(admin_client):
    response = admin_client.get(
        reverse("panel:formset_row", args=["sessions"]), {"sessions-TOTAL_FORMS": "3"}
    )
    content = response.content.decode()
    assert 'name="sessions-3-date"' in content
    assert 'name="sessions-TOTAL_FORMS" value="4"' in content
    assert 'hx-swap-oob="true"' in content
    assert admin_client.get(reverse("panel:formset_row", args=["nope"])).status_code == 404


# --- Actions ----------------------------------------------------------------------------------


@pytest.mark.django_db
def test_publish_now_and_back_to_draft(admin_client):
    workshop = full_workshop()
    url = reverse("panel:workshop_action", args=[workshop.pk, "publish_now"])
    admin_client.post(url)
    workshop.refresh_from_db()
    assert workshop.state() == "published"
    admin_client.post(reverse("panel:workshop_action", args=[workshop.pk, "unpublish"]))
    workshop.refresh_from_db()
    assert workshop.state() == "draft"


@pytest.mark.django_db
def test_cannot_publish_without_sessions(admin_client):
    workshop = WorkshopFactory()
    admin_client.post(reverse("panel:workshop_action", args=[workshop.pk, "publish_now"]))
    workshop.refresh_from_db()
    assert workshop.publish_at is None


@pytest.mark.django_db
def test_actions_need_post(admin_client):
    workshop = full_workshop()
    url = reverse("panel:workshop_action", args=[workshop.pk, "archive"])
    assert admin_client.get(url).status_code == 405


@pytest.mark.django_db
def test_only_drafts_can_be_deleted(admin_client):
    published = full_workshop(publish_at="2026-01-01T09:00:00+01:00")
    admin_client.post(reverse("panel:workshop_delete", args=[published.pk]))
    assert Workshop.objects.filter(pk=published.pk).exists()
    draft = full_workshop()
    admin_client.post(reverse("panel:workshop_delete", args=[draft.pk]))
    assert not Workshop.objects.filter(pk=draft.pk).exists()


@pytest.mark.django_db
def test_duplicate_view(admin_client):
    source = full_workshop(title="Rekolekcje 2025")
    response = admin_client.post(
        reverse("panel:workshop_duplicate", args=[source.pk]),
        {"title": "Rekolekcje 2026", "first_date": "2026-11-28"},
    )
    copy = Workshop.objects.get(title="Rekolekcje 2026")
    assert response["Location"] == reverse("panel:workshop_edit", args=[copy.pk])
    assert copy.ordered_sessions()[0].date == date(2026, 11, 28)


# --- Form editor ------------------------------------------------------------------------------


@pytest.mark.django_db
def test_form_editor_lists_questions_and_saves_standard_fields(admin_client):
    workshop = full_workshop()
    QuestionFactory(workshop=workshop, label="Skąd wiesz o warsztatach?")
    url = reverse("panel:form_editor", args=[workshop.pk])
    assert "Skąd wiesz o warsztatach?" in admin_client.get(url).content.decode()
    admin_client.post(
        url,
        {
            "fields-phone_mode": "optional",
            "fields-adult_confirmation_mode": "hidden",
            "fields-remarks_mode": "optional",
        },
    )
    workshop.refresh_from_db()
    assert workshop.phone_mode == "optional"
    assert workshop.adult_confirmation_mode == "hidden"


@pytest.mark.django_db
def test_add_choice_question_needs_two_answers(admin_client):
    workshop = full_workshop()
    url = reverse("panel:question_add", args=[workshop.pk])
    data = {"label": "Deska", "kind": QuestionKind.MATERIAL, "choices": "Tak", "required": "on"}
    response = admin_client.post(url, data)
    assert "co najmniej dwie odpowiedzi" in response.content.decode()
    data["choices"] = "Tak, zamawiam\nMam własną"
    admin_client.post(url, data | {"is_active": "on"})
    question = workshop.questions.get()
    assert question.choice_list() == ["Tak, zamawiam", "Mam własną"]


@pytest.mark.django_db
def test_text_question_drops_leftover_choices(admin_client):
    workshop = full_workshop()
    admin_client.post(
        reverse("panel:question_add", args=[workshop.pk]),
        {"label": "Opis", "kind": QuestionKind.LONG_TEXT, "choices": "a\nb", "is_active": "on"},
    )
    assert workshop.questions.get().choices == ""


@pytest.mark.django_db
def test_question_level_must_belong_to_the_workshop(admin_client):
    workshop = full_workshop()
    foreign_level = LevelFactory()
    response = admin_client.post(
        reverse("panel:question_add", args=[workshop.pk]),
        {"label": "X", "kind": QuestionKind.SHORT_TEXT, "level": foreign_level.pk},
    )
    assert response.status_code == 200
    assert not workshop.questions.exists()


@pytest.mark.django_db
def test_move_toggle_delete(admin_client):
    workshop = full_workshop()
    first = QuestionFactory(workshop=workshop, label="A", order=0)
    second = QuestionFactory(workshop=workshop, label="B", order=1)
    admin_client.post(reverse("panel:question_move", args=[workshop.pk, second.pk, "up"]))
    assert list(workshop.questions.order_by("order").values_list("label", flat=True)) == ["B", "A"]

    admin_client.post(reverse("panel:question_toggle", args=[workshop.pk, first.pk]))
    first.refresh_from_db()
    assert not first.is_active

    admin_client.post(reverse("panel:question_delete", args=[workshop.pk, first.pk]))
    assert not Question.objects.filter(pk=first.pk).exists()


@pytest.mark.django_db
def test_questions_of_another_workshop_are_out_of_reach(admin_client):
    workshop = full_workshop()
    other = QuestionFactory()
    url = reverse("panel:question_toggle", args=[workshop.pk, other.pk])
    assert admin_client.post(url).status_code == 404


@pytest.mark.django_db
def test_add_questions_from_template(admin_client):
    call_command("seed_defaults")
    workshop = full_workshop()
    from workshop_manager.forms_builder.models import FormTemplate

    template = FormTemplate.objects.get(name="Podstawowy")
    admin_client.post(
        reverse("panel:questions_from_template", args=[workshop.pk]), {"tpl-template": template.pk}
    )
    assert workshop.questions.count() == 3


@pytest.mark.django_db
def test_session_times_render_in_the_edit_form(admin_client):
    workshop = WorkshopFactory()
    SessionFactory(workshop=workshop, start_time=time(9, 30), end_time=time(15, 0))
    LevelFactory(workshop=workshop)
    content = admin_client.get(reverse("panel:workshop_edit", args=[workshop.pk])).content.decode()
    assert 'value="09:30"' in content
    assert 'value="2026-11-28"' in content


@pytest.mark.django_db
def test_no_untranslated_blank_choice(admin_client):
    workshop = full_workshop()
    QuestionFactory(workshop=workshop)
    for url in (
        reverse("panel:workshop_create"),
        reverse("panel:workshop_edit", args=[workshop.pk]),
        reverse("panel:question_add", args=[workshop.pk]),
        reverse("panel:form_editor", args=[workshop.pk]),
    ):
        assert "Select an option" not in admin_client.get(url).content.decode(), url


@pytest.mark.django_db
def test_locations_can_be_added_and_deactivated(admin_client):
    from workshop_manager.workshops.models import Location

    admin_client.post(
        reverse("panel:location_add"),
        {"name": "Dom rekolekcyjny", "address": "ul. Leśna 5, Zakopane", "is_active": "on"},
    )
    location = Location.objects.get(name="Dom rekolekcyjny")
    assert "Dom rekolekcyjny" in admin_client.get(reverse("panel:location_list")).content.decode()
    admin_client.post(
        reverse("panel:location_edit", args=[location.pk]),
        {"name": "Dom rekolekcyjny", "address": "ul. Leśna 5, Zakopane"},
    )
    location.refresh_from_db()
    assert not location.is_active
    create_page = admin_client.get(reverse("panel:workshop_create")).content.decode()
    assert "Dom rekolekcyjny" not in create_page
