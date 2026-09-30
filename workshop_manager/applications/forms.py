"""The public application form, built from a workshop's configuration (PRD §6.3)."""

import time
from typing import Any

from django import forms
from django.core import signing
from django.utils.html import format_html

from workshop_manager.core.forms import BootstrapFormMixin
from workshop_manager.core.models import SiteSettings
from workshop_manager.forms_builder.models import Question, QuestionKind
from workshop_manager.workshops.models import FieldMode, Level, Workshop

#: A person needs longer than this to fill the form in; a bot does not.
MIN_FILL_SECONDS = 4
#: A form left open longer than this is refused (the page must be reloaded).
MAX_FILL_SECONDS = 24 * 60 * 60
_STAMP_SALT = "applications.form-started"

YES_NO = [("Tak", "Tak"), ("Nie", "Nie")]


def question_field_name(question: Question) -> str:
    return f"q_{question.pk}"


def _question_field(question: Question) -> forms.Field:
    common: dict[str, Any] = {
        "label": question.label,
        "help_text": question.help_text,
        # Level-bound questions are checked in `clean()`, only for the level chosen.
        "required": question.required and question.level_id is None,
    }
    kind = question.kind
    if kind == QuestionKind.SHORT_TEXT:
        return forms.CharField(max_length=500, **common)
    if kind == QuestionKind.LONG_TEXT:
        return forms.CharField(max_length=5000, widget=forms.Textarea(attrs={"rows": 4}), **common)
    if kind == QuestionKind.YES_NO:
        return forms.ChoiceField(choices=YES_NO, widget=forms.RadioSelect, **common)
    choices = [(choice, choice) for choice in question.choice_list()]
    if kind == QuestionKind.MULTI_CHOICE:
        return forms.MultipleChoiceField(
            choices=choices, widget=forms.CheckboxSelectMultiple, **common
        )
    return forms.ChoiceField(choices=choices, widget=forms.RadioSelect, **common)


class LevelChoiceField(forms.ModelChoiceField):
    def __init__(self, *args: Any, show_capacity_notice: bool, **kwargs: Any) -> None:
        self.show_capacity_notice = show_capacity_notice
        super().__init__(*args, **kwargs)

    def label_from_instance(self, obj: Any) -> str:
        level: Level = obj
        parts = [level.name]
        if level.price_display:
            parts.append(f"— {level.price_display}")
        label = " ".join(parts)
        if self.show_capacity_notice and level.is_over_capacity():
            label += " (zgłoszeń jest już więcej niż miejsc — możesz trafić na listę rezerwową)"
        return label


class ApplicationForm(BootstrapFormMixin, forms.Form):
    """Standard fields, the workshop's questions, consents and two quiet anti-spam checks.

    Anti-spam without a CAPTCHA (PRD §6.3): a honeypot field people never see, and a signed
    timestamp — a form sent back within seconds of being shown was not filled in by a person.
    """

    level = LevelChoiceField(
        label="Wybierz poziom", queryset=Level.objects.none(), show_capacity_notice=True
    )
    first_name = forms.CharField(
        label="Imię", max_length=100, widget=forms.TextInput(attrs={"autocomplete": "given-name"})
    )
    last_name = forms.CharField(
        label="Nazwisko",
        max_length=100,
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}),
    )
    email = forms.EmailField(
        label="Adres e-mail",
        help_text="Na ten adres wyślemy potwierdzenie i decyzję organizatora.",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    phone = forms.CharField(
        label="Telefon",
        max_length=32,
        help_text="Przyda się, gdyby trzeba było pilnie przekazać zmianę.",
        widget=forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
    )
    adult = forms.BooleanField(
        label="Potwierdzam, że jestem osobą pełnoletnią (warsztaty są tylko dla dorosłych)."
    )
    remarks = forms.CharField(
        label="Uwagi do zgłoszenia",
        required=False,
        max_length=2000,
        help_text="Np. dane do faktury lub inne informacje dla organizatora.",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    # Labels come from Settings (`__init__`).
    privacy = forms.BooleanField()
    marketing = forms.BooleanField(required=False)
    # Anti-spam: rendered off-screen and labelled for people using screen readers.
    website = forms.CharField(
        label="Nie wypełniaj tego pola",
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )
    started = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args: Any, workshop: Workshop, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.workshop = workshop
        levels = workshop.levels.all()
        level_field: LevelChoiceField = self.fields["level"]  # type: ignore[assignment]
        level_field.queryset = levels
        level_field.show_capacity_notice = workshop.show_capacity_notice
        level_field.widget = forms.RadioSelect()
        level_field.empty_label = None
        level_field.widget.choices = level_field.choices
        if len(levels) == 1:
            level_field.initial = levels[0].pk
            level_field.widget = forms.HiddenInput()

        self._apply_mode("phone", workshop.phone_mode)
        self._apply_mode("adult", workshop.adult_confirmation_mode)
        self._apply_mode("remarks", workshop.remarks_mode)
        site = SiteSettings.load()
        self.privacy_version = site.privacy_version
        self.fields["privacy"].label = site.privacy_text
        self.fields["marketing"].label = site.marketing_text
        self.fields["privacy"].help_text = format_html(
            '<a href="{}" target="_blank" rel="noopener">Polityka prywatności</a>',
            site.privacy_policy_url,
        )
        if not self.is_bound:
            self.fields["started"].initial = signing.dumps(time.time(), salt=_STAMP_SALT)

        self.questions = list(
            workshop.questions.filter(is_active=True).select_related("level").order_by("order")
        )
        for question in self.questions:
            self.fields[question_field_name(question)] = _question_field(question)

    def _apply_mode(self, name: str, mode: str) -> None:
        if mode == FieldMode.HIDDEN:
            del self.fields[name]
        else:
            self.fields[name].required = mode == FieldMode.REQUIRED

    # --- Rendering helpers ---------------------------------------------------------------------

    def question_rows(self) -> list[tuple[Question, forms.BoundField]]:
        return [(q, self[question_field_name(q)]) for q in self.questions]

    def contact_fields(self) -> list[forms.BoundField]:
        names = ["first_name", "last_name", "email", "phone"]
        return [self[name] for name in names if name in self.fields]

    # --- Validation ----------------------------------------------------------------------------

    def clean_email(self) -> str:
        return self.cleaned_data["email"].strip().lower()

    def clean_website(self) -> str:
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("Formularz nie został wysłany. Spróbuj ponownie.")
        return ""

    def clean_started(self) -> float:
        refused = forms.ValidationError(
            "Formularz wygasł lub został wysłany zbyt szybko. Odśwież stronę i spróbuj ponownie."
        )
        try:
            started = float(
                signing.loads(
                    self.cleaned_data["started"], salt=_STAMP_SALT, max_age=MAX_FILL_SECONDS
                )
            )
        except (signing.BadSignature, TypeError, ValueError) as error:
            raise refused from error
        if time.time() - started < MIN_FILL_SECONDS:
            raise refused
        return started

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        level = data.get("level")
        for question in self.questions:
            name = question_field_name(question)
            if question.level_id is None:
                continue
            if level is None or question.level_id != level.pk:
                # A question for another level: whatever the browser sent is ignored.
                data.pop(name, None)
                self.errors.pop(name, None)
            elif question.required and not data.get(name):
                self.add_error(name, "To pole jest wymagane dla wybranego poziomu.")
        return data

    def answers(self) -> list[tuple[Question, str]]:
        """(question, answer text) for every question that applies to the chosen level."""
        result = []
        level = self.cleaned_data.get("level")
        for question in self.questions:
            if question.level_id is not None and (level is None or question.level_id != level.pk):
                continue
            value = self.cleaned_data.get(question_field_name(question))
            if isinstance(value, list):
                value = "; ".join(value)
            result.append((question, (value or "").strip()))
        return result
