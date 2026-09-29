"""The configurable application form (PRD §6.3).

A `FormTemplate` holds the usual questions. Creating a workshop copies them into the workshop's
own `Question`s, which the administrator can then change freely — editing a template never
changes workshops that already exist.
"""

from typing import Any

from django.db import models


class QuestionKind(models.TextChoices):
    SHORT_TEXT = "short_text", "krótki tekst"
    LONG_TEXT = "long_text", "dłuższa odpowiedź"
    YES_NO = "yes_no", "tak / nie"
    SINGLE_CHOICE = "single_choice", "wybór jednej odpowiedzi"
    MULTI_CHOICE = "multi_choice", "wybór wielu odpowiedzi"
    MATERIAL = "material", "zamówienie materiału"


#: Kinds whose answers come from `choices`.
CHOICE_KINDS = {QuestionKind.SINGLE_CHOICE, QuestionKind.MULTI_CHOICE, QuestionKind.MATERIAL}


class QuestionBase(models.Model):
    label = models.CharField("treść pytania", max_length=300)
    help_text = models.CharField("podpowiedź", max_length=300, blank=True)
    kind = models.CharField(
        "rodzaj odpowiedzi",
        max_length=20,
        choices=QuestionKind.choices,
        default=QuestionKind.LONG_TEXT,
    )
    choices = models.TextField(
        "możliwe odpowiedzi",
        blank=True,
        help_text="Jedna odpowiedź w wierszu (dla pytań z wyborem i zamówień materiałów).",
    )
    required = models.BooleanField("wymagane", default=True)
    order = models.PositiveSmallIntegerField("kolejność", default=0)

    class Meta:
        abstract = True
        ordering = ["order", "pk"]

    def __str__(self) -> str:
        return self.label

    def choice_list(self) -> list[str]:
        return [line.strip() for line in self.choices.splitlines() if line.strip()]

    @property
    def has_choices(self) -> bool:
        return self.kind in CHOICE_KINDS

    def copy_fields(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "help_text": self.help_text,
            "kind": self.kind,
            "choices": self.choices,
            "required": self.required,
            "order": self.order,
        }


class FormTemplate(models.Model):
    name = models.CharField("nazwa", max_length=150, unique=True)
    description = models.CharField("opis", max_length=250, blank=True)

    class Meta:
        verbose_name = "szablon formularza"
        verbose_name_plural = "szablony formularzy"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class TemplateQuestion(QuestionBase):
    template = models.ForeignKey(
        FormTemplate, verbose_name="szablon", on_delete=models.CASCADE, related_name="questions"
    )
    level_name = models.CharField(
        "tylko dla poziomu",
        max_length=100,
        blank=True,
        help_text="Nazwa poziomu, np. „Początkujący”. Puste = pytanie dla wszystkich.",
    )

    class Meta(QuestionBase.Meta):
        verbose_name = "pytanie szablonu"
        verbose_name_plural = "pytania szablonu"


class Question(QuestionBase):
    workshop = models.ForeignKey(
        "workshops.Workshop",
        verbose_name="warsztat",
        on_delete=models.CASCADE,
        related_name="questions",
    )
    level = models.ForeignKey(
        "workshops.Level",
        verbose_name="tylko dla poziomu",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="questions",
        help_text="Puste = pytanie dla wszystkich poziomów.",
    )
    is_active = models.BooleanField(
        "widoczne w formularzu",
        default=True,
        help_text="Pytań, na które ktoś już odpowiedział, nie usuwamy — można je ukryć.",
    )

    class Meta(QuestionBase.Meta):
        verbose_name = "pytanie"
        verbose_name_plural = "pytania"


def copy_template(template: FormTemplate, workshop: Any) -> list[Question]:
    """Copy a template's questions into a workshop, matching level-only questions by name.

    A question for a level the workshop does not have (say, "Zaawansowani" on a beginners-only
    workshop) is copied hidden, so the administrator sees it and can decide.
    """
    levels = {level.name.strip().lower(): level for level in workshop.levels.all()}
    start = (workshop.questions.aggregate(models.Max("order"))["order__max"] or 0) + 1
    created = []
    for offset, source in enumerate(template.questions.all()):
        level = None
        active = True
        if source.level_name.strip():
            level = levels.get(source.level_name.strip().lower())
            active = level is not None
        fields = source.copy_fields() | {"order": start + offset}
        created.append(
            Question.objects.create(workshop=workshop, level=level, is_active=active, **fields)
        )
    return created
