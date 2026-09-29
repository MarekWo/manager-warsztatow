"""Bootstrap-styled rendering for every Django form in the project.

`FORM_RENDERER` points at `BootstrapRenderer`, whose field template draws label, widget, help
text and errors with Bootstrap markup; `BootstrapFormMixin` puts the matching CSS classes on the
widgets. Forms only need to inherit the mixin.
"""

from typing import Any

from django import forms
from django.db.models.fields import BLANK_CHOICE_LABEL
from django.forms.renderers import TemplatesSetting


class BootstrapRenderer(TemplatesSetting):
    form_template_name = "forms/form.html"
    field_template_name = "forms/field.html"
    formset_template_name = "forms/formset.html"


def widget_class(widget: forms.Widget) -> str:
    if isinstance(widget, forms.CheckboxInput):
        return "form-check-input"
    if isinstance(widget, (forms.RadioSelect, forms.CheckboxSelectMultiple)):
        return ""
    if isinstance(widget, forms.Select):
        return "form-select"
    return "form-control"


#: Django 6.1's new blank-choice label has no Polish translation yet.
BLANK_LABEL = "— wybierz —"


def polish_blank_choice(field: forms.Field) -> None:
    if isinstance(field, forms.ModelChoiceField):
        if field.empty_label is not None and str(field.empty_label) == str(BLANK_CHOICE_LABEL):
            field.empty_label = BLANK_LABEL
    elif isinstance(field, forms.ChoiceField):
        choices: Any = field.choices  # a list of pairs once the field is built
        field.choices = [
            ("", BLANK_LABEL)
            if value == "" and str(label) == str(BLANK_CHOICE_LABEL)
            else (value, label)
            for value, label in choices
        ]


class BootstrapFormMixin:
    fields: dict[str, forms.Field]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            polish_blank_choice(field)
            css = widget_class(field.widget)
            if css:
                existing = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = f"{existing} {css}".strip()


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        super().__init__(attrs=attrs, format="%Y-%m-%d")


class TimeInput(forms.TimeInput):
    input_type = "time"

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        super().__init__(attrs=attrs, format="%H:%M")


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        super().__init__(attrs=attrs, format="%Y-%m-%dT%H:%M")
