"""The public application form (PRD §6.3)."""

import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
import time_machine
from django.core import signing
from django.urls import reverse

from tests.factories import (
    AdminFactory,
    LevelFactory,
    QuestionFactory,
    SessionFactory,
    UserFactory,
    WorkshopFactory,
)
from workshop_manager.applications.forms import _STAMP_SALT
from workshop_manager.applications.models import Application, Participant, Status
from workshop_manager.forms_builder.models import QuestionKind

WARSAW = ZoneInfo("Europe/Warsaw")
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=WARSAW)


@pytest.fixture(autouse=True)
def _clock():
    with time_machine.travel(NOW, tick=False):
        yield


@pytest.fixture
def workshop(db):
    workshop = WorkshopFactory(publish_at=datetime(2026, 10, 20, 9, tzinfo=WARSAW))
    SessionFactory(workshop=workshop, date=date(2026, 11, 28))
    beginners = LevelFactory(workshop=workshop, name="Początkujący", order=0, capacity=2)
    advanced = LevelFactory(workshop=workshop, name="Zaawansowani", order=1)
    QuestionFactory(
        workshop=workshop,
        label="Deska 26×26",
        kind=QuestionKind.MATERIAL,
        choices="Tak, zamawiam\nMam własną",
        level=beginners,
        order=1,
    )
    QuestionFactory(
        workshop=workshop,
        label="Deska 30×42",
        kind=QuestionKind.MATERIAL,
        choices="Tak, zamawiam\nMam własną",
        level=advanced,
        order=2,
    )
    QuestionFactory(workshop=workshop, label="Doświadczenie", kind=QuestionKind.LONG_TEXT, order=3)
    QuestionFactory(
        workshop=workshop, label="Dodatkowo", kind=QuestionKind.SHORT_TEXT, required=False, order=4
    )
    QuestionFactory(
        workshop=workshop,
        label="Skąd wiesz?",
        kind=QuestionKind.MULTI_CHOICE,
        choices="Strona\nZnajomi\nParafia",
        order=5,
    )
    return workshop


def started(seconds_ago: float = 60) -> str:
    return signing.dumps(time.time() - seconds_ago, salt=_STAMP_SALT)


def payload(workshop, **overrides) -> dict:
    questions = {q.label: f"q_{q.pk}" for q in workshop.questions.all()}
    beginners = workshop.levels.get(name="Początkujący")
    data = {
        "level": beginners.pk,
        "first_name": "Anna",
        "last_name": "Nowak",
        "email": "Anna.Nowak@Example.com",
        "phone": "600 100 200",
        "adult": "on",
        "privacy": "on",
        "started": started(),
        questions["Deska 26×26"]: "Tak, zamawiam",
        questions["Doświadczenie"]: "Malowałam akwarelą.",
        questions["Skąd wiesz?"]: ["Strona", "Parafia"],
    }
    data.update(overrides)
    return data


def apply_url(workshop) -> str:
    return reverse("public:apply", args=[workshop.slug])


def test_form_page_shows_levels_questions_and_consents(client, workshop):
    content = client.get(apply_url(workshop)).content.decode()
    assert "Wybierz poziom" in content
    assert "Deska 26×26" in content
    assert 'data-level="' in content
    assert "Polityka prywatności" in content
    assert 'name="website"' in content


def test_question_fields_are_styled_like_the_others(client, workshop):
    # Added after the form's own fields; unstyled, a text area overflowed a phone's screen.
    form = client.get(apply_url(workshop)).context["form"]
    for question, field in form.question_rows():
        if question.kind in (QuestionKind.LONG_TEXT, QuestionKind.SHORT_TEXT):
            assert "form-control" in field.field.widget.attrs["class"]


def test_valid_application_is_stored_with_answers(client, workshop):
    response = client.post(apply_url(workshop), payload(workshop))
    assert response.status_code == 302
    assert response["Location"] == reverse("public:application_sent", args=[workshop.slug])

    application = Application.objects.get()
    assert application.status == Status.NEW
    assert application.email == "anna.nowak@example.com"
    assert application.level.name == "Początkujący"
    assert application.privacy_consent_version
    answers = {a.label: a.value for a in application.answers.all()}
    assert answers == {
        "Deska 26×26": "Tak, zamawiam",
        "Doświadczenie": "Malowałam akwarelą.",
        "Dodatkowo": "",
        "Skąd wiesz?": "Strona; Parafia",
    }
    assert Participant.objects.get().full_name == "Anna Nowak"

    summary = client.get(response["Location"]).content.decode()
    assert "Dziękujemy" in summary
    assert "Malowałam akwarelą." in summary


def test_question_of_the_other_level_is_ignored(client, workshop):
    other = workshop.questions.get(label="Deska 30×42")
    client.post(apply_url(workshop), payload(workshop, **{f"q_{other.pk}": "Mam własną"}))
    labels = list(Application.objects.get().answers.values_list("label", flat=True))
    assert "Deska 30×42" not in labels


def test_question_of_the_chosen_level_is_required(client, workshop):
    board = workshop.questions.get(label="Deska 26×26")
    data = payload(workshop)
    del data[f"q_{board.pk}"]
    response = client.post(apply_url(workshop), data)
    assert response.status_code == 200
    assert "wymagane dla wybranego poziomu" in response.content.decode()
    assert not Application.objects.exists()


def test_required_fields_and_consent(client, workshop):
    data = payload(workshop)
    del data["privacy"]
    del data["adult"]
    response = client.post(apply_url(workshop), data)
    content = response.content.decode()
    assert "Nie udało się wysłać zgłoszenia" in content
    assert not Application.objects.exists()


def test_second_application_from_the_same_address_is_refused(client, workshop):
    client.post(apply_url(workshop), payload(workshop))
    response = client.post(apply_url(workshop), payload(workshop, email="anna.nowak@example.com"))
    assert "jest już zgłoszenie na te warsztaty" in response.content.decode()
    assert Application.objects.count() == 1


def test_withdrawn_application_allows_a_new_one(client, workshop):
    client.post(apply_url(workshop), payload(workshop))
    Application.objects.update(status=Status.WITHDRAWN)
    client.post(apply_url(workshop), payload(workshop))
    assert Application.objects.count() == 2


def test_honeypot_and_too_fast_submissions_are_refused(client, workshop):
    client.post(apply_url(workshop), payload(workshop, website="http://spam.example"))
    client.post(apply_url(workshop), payload(workshop, started=started(seconds_ago=1)))
    client.post(apply_url(workshop), payload(workshop, started="forged"))
    assert not Application.objects.exists()


def test_rate_limit_per_address(client, workshop, settings):
    from workshop_manager.public import views

    for n in range(views.APPLICATIONS_PER_HOUR):
        client.post(apply_url(workshop), payload(workshop, email=f"osoba{n}@example.com"))
    assert Application.objects.count() == views.APPLICATIONS_PER_HOUR
    response = client.post(apply_url(workshop), payload(workshop, email="kolejna@example.com"))
    assert "zbyt wiele zgłoszeń" in response.content.decode()


def test_hidden_standard_fields_are_not_asked(client, workshop):
    workshop.phone_mode = "hidden"
    workshop.adult_confirmation_mode = "hidden"
    workshop.remarks_mode = "hidden"
    workshop.save()
    content = client.get(apply_url(workshop)).content.decode()
    assert 'name="phone"' not in content
    assert 'name="adult"' not in content
    assert 'name="remarks"' not in content
    data = payload(workshop)
    del data["phone"]
    del data["adult"]
    client.post(apply_url(workshop), data)
    assert Application.objects.get().phone == ""


def test_single_level_is_chosen_silently(client, workshop):
    workshop.levels.filter(name="Zaawansowani").delete()
    content = client.get(apply_url(workshop)).content.decode()
    assert 'type="hidden" name="level"' in content


def test_capacity_notice_after_the_limit(client, workshop):
    for n in range(2):
        client.post(apply_url(workshop), payload(workshop, email=f"osoba{n}@example.com"))
    content = client.get(apply_url(workshop)).content.decode()
    assert "możesz trafić na listę rezerwową" in content
    workshop.show_capacity_notice = False
    workshop.save()
    assert "listę rezerwową" not in client.get(apply_url(workshop)).content.decode()


def test_closed_registration_redirects_to_the_workshop(client, workshop):
    workshop.registration_closed = True
    workshop.save()
    response = client.get(apply_url(workshop))
    assert response["Location"] == workshop.get_absolute_url()


def test_draft_form_is_not_found(client, db):
    draft = WorkshopFactory()
    assert client.get(reverse("public:apply", args=[draft.slug])).status_code == 404


def test_thank_you_page_only_for_the_sender(client, workshop):
    client.post(apply_url(workshop), payload(workshop))
    other = client.__class__()
    response = other.get(reverse("public:application_sent", args=[workshop.slug]))
    assert response["Location"] == workshop.get_absolute_url()


def test_signed_in_user_gets_prefilled_details(client, workshop):
    user = UserFactory(first_name="Jan", last_name="Kowalski", phone="500 600 700")
    client.force_login(user)
    content = client.get(apply_url(workshop)).content.decode()
    assert f'value="{user.email}"' in content
    assert 'value="Kowalski"' in content
    client.post(apply_url(workshop), payload(workshop, email=user.email))
    assert Participant.objects.get(email=user.email).user == user


def test_participant_with_account_keeps_their_own_details(client, workshop):
    user = UserFactory()
    Participant.objects.create(
        email=user.email, first_name="Prawdziwe", last_name="Nazwisko", user=user
    )
    client.post(apply_url(workshop), payload(workshop, email=user.email, first_name="Obcy"))
    participant = Participant.objects.get(email=user.email)
    assert participant.first_name == "Prawdziwe"
    assert Application.objects.get().first_name == "Obcy"  # the application keeps what was sent


def test_marketing_consent_is_recorded_with_its_date(client, workshop):
    client.post(apply_url(workshop), payload(workshop, marketing="on"))
    participant = Participant.objects.get()
    assert participant.marketing_consent
    assert participant.marketing_consent_at is not None


# --- Guards in the panel -----------------------------------------------------------------------


def test_level_with_applications_cannot_be_deleted(client, workshop):
    from tests.test_panel_workshops import edit_payload

    client.post(apply_url(workshop), payload(workshop))
    client.force_login(AdminFactory())
    levels = list(workshop.levels.all())
    index = levels.index(workshop.levels.get(name="Początkujący"))
    data = edit_payload(workshop, **{f"levels-{index}-DELETE": "on"})
    response = client.post(reverse("panel:workshop_edit", args=[workshop.pk]), data)
    assert "nie można usunąć" in response.content.decode()
    assert workshop.levels.count() == 2


def test_answered_question_cannot_be_deleted(client, workshop):
    client.post(apply_url(workshop), payload(workshop))
    client.force_login(AdminFactory())
    question = workshop.questions.get(label="Doświadczenie")
    client.post(reverse("panel:question_delete", args=[workshop.pk, question.pk]))
    assert workshop.questions.filter(pk=question.pk).exists()
