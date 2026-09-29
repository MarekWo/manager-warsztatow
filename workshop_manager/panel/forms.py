from typing import Any

from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from workshop_manager.core.forms import BootstrapFormMixin, DateInput, DateTimeInput, TimeInput
from workshop_manager.forms_builder.models import CHOICE_KINDS, FormTemplate, Question
from workshop_manager.workshops.models import Level, Location, Session, Workshop, WorkshopType


class WorkshopCreateForm(BootstrapFormMixin, forms.Form):
    """Step one of a new workshop: what kind, what title, which questions to start with."""

    type = forms.ModelChoiceField(
        label="Rodzaj warsztatów",
        queryset=WorkshopType.objects.filter(is_active=True),
        empty_label=None,
    )
    title = forms.CharField(label="Tytuł", max_length=200)
    template = forms.ModelChoiceField(
        label="Pytania w formularzu zgłoszeniowym",
        queryset=FormTemplate.objects.all(),
        required=False,
        empty_label="Domyślne dla wybranego rodzaju",
        help_text="Pytania można potem dowolnie zmieniać.",
    )
    location = forms.ModelChoiceField(
        label="Miejsce",
        queryset=Location.objects.filter(is_active=True),
        required=False,
        empty_label="— wybiorę później —",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        locations = self.fields["location"].queryset  # type: ignore[attr-defined]
        if locations.count() == 1:
            self.fields["location"].initial = locations.first()

    def chosen_template(self) -> FormTemplate | None:
        template = self.cleaned_data.get("template")
        return template or self.cleaned_data["type"].default_form_template


class WorkshopForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Workshop
        fields = [
            "type",
            "title",
            "subtitle",
            "description",
            "leader",
            "show_leader",
            "location",
            "show_location",
            "cover_image",
            "show_cover_image",
            "program",
            "show_program",
            "what_to_bring",
            "show_what_to_bring",
            "accommodation",
            "show_accommodation",
            "notes",
            "show_notes",
            "publish_at",
            "registration_opens_at",
            "registration_closes_at",
            "registration_closed",
            "show_capacity_notice",
            "is_cancelled",
            "cancellation_note",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "program": forms.Textarea(attrs={"rows": 5}),
            "what_to_bring": forms.Textarea(attrs={"rows": 4}),
            "accommodation": forms.Textarea(attrs={"rows": 4}),
            "notes": forms.Textarea(attrs={"rows": 4}),
            "publish_at": DateTimeInput(),
            "registration_opens_at": DateTimeInput(),
            "registration_closes_at": DateTimeInput(),
            "cover_image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["location"].queryset = Location.objects.filter(is_active=True)  # type: ignore[attr-defined]
        self.fields["type"].queryset = WorkshopType.objects.filter(is_active=True)  # type: ignore[attr-defined]
        self.fields["type"].empty_label = None  # type: ignore[attr-defined]
        self.fields["location"].empty_label = "— bez miejsca —"  # type: ignore[attr-defined]

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        opens, closes = data.get("registration_opens_at"), data.get("registration_closes_at")
        if opens and closes and closes <= opens:
            self.add_error("registration_closes_at", "Koniec zapisów musi być po ich otwarciu.")
        if data.get("is_cancelled") and not data.get("cancellation_note"):
            self.add_error("cancellation_note", "Napisz krótko, dlaczego warsztat jest odwołany.")
        return data


class SessionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Session
        fields = ["date", "start_time", "end_time", "note"]
        widgets = {"date": DateInput(), "start_time": TimeInput(), "end_time": TimeInput()}

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        start, end = data.get("start_time"), data.get("end_time")
        if start and end and end <= start:
            self.add_error("end_time", "Koniec spotkania musi być po jego rozpoczęciu.")
        return data


class LevelForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Level
        fields = ["name", "description", "capacity", "price", "price_note"]


SessionFormSet = inlineformset_factory(
    Workshop,
    Session,
    form=SessionForm,
    extra=0,
    min_num=1,
    validate_min=True,
    can_delete=True,
)


class BaseLevelFormSet(BaseInlineFormSet):
    def clean(self) -> None:
        super().clean()
        for form in self.deleted_forms:
            level = form.instance
            if level.pk and level.applications.exists():
                raise forms.ValidationError(
                    f"Poziomu „{level.name}” nie można usunąć — są na niego zgłoszenia."
                )


LevelFormSet = inlineformset_factory(
    Workshop,
    Level,
    form=LevelForm,
    formset=BaseLevelFormSet,
    extra=0,
    min_num=1,
    validate_min=True,
    can_delete=True,
)


class StandardFieldsForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Workshop
        fields = ["phone_mode", "adult_confirmation_mode", "remarks_mode"]


class QuestionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Question
        fields = ["label", "help_text", "kind", "choices", "required", "level", "is_active"]
        widgets = {"choices": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args: Any, workshop: Workshop, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["level"].queryset = workshop.levels.all()  # type: ignore[attr-defined]
        self.fields["level"].empty_label = "Wszystkie poziomy"  # type: ignore[attr-defined]

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        kind, choices = data.get("kind"), data.get("choices", "")
        lines = [line for line in choices.splitlines() if line.strip()]
        if kind in CHOICE_KINDS and len(lines) < 2:
            self.add_error("choices", "Podaj co najmniej dwie odpowiedzi, każdą w osobnym wierszu.")
        if kind not in CHOICE_KINDS:
            data["choices"] = ""
        return data


class AddTemplateForm(BootstrapFormMixin, forms.Form):
    template = forms.ModelChoiceField(
        label="Dodaj pytania z szablonu", queryset=FormTemplate.objects.all()
    )


class DuplicateForm(BootstrapFormMixin, forms.Form):
    title = forms.CharField(label="Tytuł nowego warsztatu", max_length=200)
    first_date = forms.DateField(
        label="Data pierwszego spotkania",
        required=False,
        widget=DateInput(),
        help_text="Pozostałe spotkania przesuną się o tyle samo dni. Puste = daty bez zmian.",
    )


class LocationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Location
        fields = ["name", "address", "map_url", "directions", "is_active"]
        widgets = {"directions": forms.Textarea(attrs={"rows": 4})}
