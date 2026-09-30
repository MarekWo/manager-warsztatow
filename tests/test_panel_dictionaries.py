"""Panel dictionaries: workshop types and form templates (PRD §7.8)."""

import pytest
from django.urls import reverse

from tests.factories import AdminFactory, WorkshopFactory, WorkshopTypeFactory
from workshop_manager.forms_builder.models import FormTemplate, QuestionKind, TemplateQuestion
from workshop_manager.workshops.models import WorkshopType


@pytest.fixture
def admin_client(client, db):
    client.force_login(AdminFactory())
    return client


@pytest.fixture
def template(db):
    template = FormTemplate.objects.create(name="Mozaika (standard)")
    for order, label in enumerate(["Pierwsze", "Drugie", "Trzecie"]):
        TemplateQuestion.objects.create(template=template, label=label, order=order)
    return template


@pytest.mark.parametrize("name", ["panel:dictionary_type_list", "panel:dictionary_template_list"])
def test_dictionaries_need_a_staff_account(client, db, name):
    assert client.get(reverse(name)).status_code == 302


def test_type_list_add_and_edit(admin_client, template):
    WorkshopFactory(type=WorkshopTypeFactory(name="Ikonopisanie"))
    content = admin_client.get(reverse("panel:dictionary_type_list")).content.decode()
    assert "Ikonopisanie" in content
    assert "Warsztatów: 1" in content

    response = admin_client.post(
        reverse("panel:dictionary_type_add"),
        {
            "name": "Mozaika",
            "default_levels": "Początkujący\nŚredniozaawansowani",
            "default_form_template": template.pk,
            "order": 3,
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    mosaic = WorkshopType.objects.get(name="Mozaika")
    assert mosaic.level_names() == ["Początkujący", "Średniozaawansowani"]
    assert mosaic.default_form_template == template

    admin_client.post(
        reverse("panel:dictionary_type_edit", args=[mosaic.pk]),
        {"name": "Mozaika", "default_levels": "", "order": 3},
    )
    mosaic.refresh_from_db()
    assert not mosaic.is_active
    assert mosaic.default_form_template is None


def test_inactive_type_is_not_offered_for_new_workshops(admin_client):
    WorkshopTypeFactory(name="Witraż", is_active=False)
    content = admin_client.get(reverse("panel:workshop_create")).content.decode()
    assert "Witraż" not in content


def test_template_create_and_rename(admin_client):
    response = admin_client.post(
        reverse("panel:dictionary_template_add"), {"name": "Nowy", "description": ""}
    )
    template = FormTemplate.objects.get(name="Nowy")
    assert response["Location"] == reverse("panel:dictionary_template_edit", args=[template.pk])
    admin_client.post(
        reverse("panel:dictionary_template_edit", args=[template.pk]),
        {"name": "Nowy szablon", "description": "Opis"},
    )
    template.refresh_from_db()
    assert (template.name, template.description) == ("Nowy szablon", "Opis")


def test_template_questions_add_edit_move_delete(admin_client, template):
    edit_url = reverse("panel:dictionary_template_edit", args=[template.pk])
    assert "Trzecie" in admin_client.get(edit_url).content.decode()

    admin_client.post(
        reverse("panel:dictionary_question_add", args=[template.pk]),
        {
            "label": "Zamawiam deskę",
            "kind": QuestionKind.MATERIAL,
            "choices": "Tak\nNie",
            "required": "on",
            "level_name": "Początkujący",
        },
    )
    added = template.questions.get(label="Zamawiam deskę")
    assert added.order == 3
    assert added.level_name == "Początkujący"

    response = admin_client.post(
        reverse("panel:dictionary_question_add", args=[template.pk]),
        {"label": "Wybór", "kind": QuestionKind.SINGLE_CHOICE, "choices": "Jedna"},
    )
    assert "co najmniej dwie odpowiedzi" in response.content.decode()

    third = template.questions.get(label="Trzecie")
    admin_client.post(reverse("panel:dictionary_question_move", args=[template.pk, third.pk, "up"]))
    labels = list(template.questions.order_by("order").values_list("label", flat=True))
    assert labels == ["Pierwsze", "Trzecie", "Drugie", "Zamawiam deskę"]

    delete_url = reverse("panel:dictionary_question_delete", args=[template.pk, third.pk])
    assert "Usunąć pytanie" in admin_client.get(delete_url).content.decode()
    admin_client.post(delete_url)
    assert not template.questions.filter(label="Trzecie").exists()


def test_deleting_a_template_keeps_workshop_questions(admin_client, template):
    from workshop_manager.forms_builder.models import copy_template

    workshop_type = WorkshopTypeFactory(name="Mozaika", default_form_template=template)
    workshop = WorkshopFactory(type=workshop_type)
    copy_template(template, workshop)

    url = reverse("panel:dictionary_template_delete", args=[template.pk])
    assert "Mozaika" in admin_client.get(url).content.decode()
    admin_client.post(url)
    assert not FormTemplate.objects.filter(pk=template.pk).exists()
    assert workshop.questions.count() == 3
    workshop_type.refresh_from_db()
    assert workshop_type.default_form_template is None


def test_settings_tabs_link_the_dictionaries(admin_client):
    content = admin_client.get(reverse("panel:settings")).content.decode()
    assert reverse("panel:dictionary_type_list") in content
    assert reverse("panel:dictionary_template_list") in content
