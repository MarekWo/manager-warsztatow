"""Create the data every installation needs (idempotent; run by the entrypoint on every start).

Rows are matched by name and never overwritten, so an administrator's edits survive restarts;
a template's questions are only created together with the template.
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from workshop_manager.forms_builder.models import FormTemplate, QuestionKind, TemplateQuestion
from workshop_manager.workshops.models import Location, WorkshopType

ICON_TEMPLATE = "Ikonopisanie (standard)"
BASIC_TEMPLATE = "Podstawowy"

BEGINNERS = "Początkujący"
ADVANCED = "Zaawansowani"

#: The questions of the Word form used until now (materiały/Formularz_standardowy.doc).
ICON_QUESTIONS: list[dict[str, Any]] = [
    {
        "label": "Zamawiam deskę zagruntowaną 26×26 cm",
        "kind": QuestionKind.MATERIAL,
        "choices": "Tak, zamawiam\nMam własną",
        "level_name": BEGINNERS,
    },
    {
        "label": "Zamawiam deskę zagruntowaną 30×42 cm",
        "kind": QuestionKind.MATERIAL,
        "choices": "Tak, zamawiam\nMam własną",
        "level_name": ADVANCED,
    },
    {
        "label": "Opisz ikonę, którą chcesz namalować",
        "kind": QuestionKind.LONG_TEXT,
        "required": False,
    },
    {
        "label": "Czy uczestniczyłaś/eś już w warsztatach ikonopisania organizowanych przez "
        "Stowarzyszenie lub inne organizacje, pracownie? Napisz w jakich.",
        "kind": QuestionKind.LONG_TEXT,
    },
    {
        "label": "Jakie masz oczekiwania w związku z uczestnictwem w rekolekcjach/warsztatach?",
        "kind": QuestionKind.LONG_TEXT,
    },
    {
        "label": "Jakie znaczenie ma dla Ciebie ikona jako fenomen sztuki chrześcijańskiej?",
        "kind": QuestionKind.LONG_TEXT,
    },
    {"label": "Opisz dotychczasowe doświadczenia malarskie.", "kind": QuestionKind.LONG_TEXT},
    {"label": "W jaki sposób dowiedziałaś/eś się o warsztatach?", "kind": QuestionKind.SHORT_TEXT},
]

BASIC_QUESTIONS: list[dict[str, Any]] = [
    {
        "label": "Czy masz doświadczenie w tej dziedzinie? Opisz krótko.",
        "kind": QuestionKind.LONG_TEXT,
    },
    {
        "label": "Jakie masz oczekiwania w związku z uczestnictwem w warsztatach?",
        "kind": QuestionKind.LONG_TEXT,
        "required": False,
    },
    {"label": "W jaki sposób dowiedziałaś/eś się o warsztatach?", "kind": QuestionKind.SHORT_TEXT},
]

#: (name, default levels, template name)
TYPES: list[tuple[str, list[str], str]] = [
    ("Ikonopisanie", [BEGINNERS, ADVANCED], ICON_TEMPLATE),
    ("Pozłotnictwo", [], BASIC_TEMPLATE),
    ("Mozaika", [], BASIC_TEMPLATE),
    ("Witraż", [], BASIC_TEMPLATE),
    ("Rysunek artystyczny", [], BASIC_TEMPLATE),
    ("Malarstwo według dawnych mistrzów", [], BASIC_TEMPLATE),
]


def _template(name: str, description: str, questions: list[dict[str, Any]]) -> FormTemplate:
    template, created = FormTemplate.objects.get_or_create(
        name=name, defaults={"description": description}
    )
    if created:
        for order, spec in enumerate(questions):
            TemplateQuestion.objects.create(template=template, order=order, **spec)
    return template


class Command(BaseCommand):
    help = "Create default data that does not exist yet."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        templates = {
            ICON_TEMPLATE: _template(
                ICON_TEMPLATE, "Pytania z dotychczasowego formularza Word.", ICON_QUESTIONS
            ),
            BASIC_TEMPLATE: _template(
                BASIC_TEMPLATE, "Krótki zestaw pytań dla innych warsztatów.", BASIC_QUESTIONS
            ),
        }
        for order, (name, levels, template_name) in enumerate(TYPES):
            WorkshopType.objects.get_or_create(
                name=name,
                defaults={
                    "order": order,
                    "default_levels": "\n".join(levels),
                    "default_form_template": templates[template_name],
                },
            )
        if not Location.objects.exists():
            Location.objects.create(
                name="Pracownia Stowarzyszenia Ecclesia", address="ul. Kopernika 26, Kraków"
            )
        self.stdout.write("Default data in place.")
