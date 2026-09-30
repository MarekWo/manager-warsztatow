"""Dictionaries in Settings: workshop types and form templates with their questions (PRD §7.8).

Editing a template never changes existing workshops — they have their own copies of the
questions (`forms_builder.copy_template`). Types are never deleted, only switched off, because
workshops refer to them.
"""

from django.contrib import messages
from django.db.models import Count, Max
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from workshop_manager.forms_builder.models import FormTemplate, TemplateQuestion
from workshop_manager.panel import ordering
from workshop_manager.panel.forms import FormTemplateForm, TemplateQuestionForm, WorkshopTypeForm
from workshop_manager.panel.views import staff_required
from workshop_manager.workshops.models import WorkshopType

# --- Workshop types -----------------------------------------------------------------------------


@staff_required
def type_list(request: HttpRequest) -> HttpResponse:
    types = (
        WorkshopType.objects.select_related("default_form_template")
        .annotate(workshop_count=Count("workshops"))
        .order_by("-is_active", "order", "name")
    )
    return render(request, "panel/dictionary_type_list.html", {"types": types})


@staff_required
def type_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    workshop_type = get_object_or_404(WorkshopType, pk=pk) if pk is not None else None
    form = WorkshopTypeForm(request.POST or None, instance=workshop_type)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Zapisano rodzaj warsztatów.")
        return redirect("panel:dictionary_type_list")
    return render(
        request, "panel/dictionary_type_edit.html", {"form": form, "workshop_type": workshop_type}
    )


# --- Form templates -----------------------------------------------------------------------------


def _types_using(template: FormTemplate) -> list[str]:
    """Names of the workshop types that start new workshops with this template."""
    return list(
        WorkshopType.objects.filter(default_form_template=template).values_list("name", flat=True)
    )


@staff_required
def template_list(request: HttpRequest) -> HttpResponse:
    templates = FormTemplate.objects.annotate(question_count=Count("questions")).order_by("name")
    return render(request, "panel/dictionary_template_list.html", {"templates": templates})


@staff_required
def template_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    template = get_object_or_404(FormTemplate, pk=pk) if pk is not None else None
    form = FormTemplateForm(request.POST or None, instance=template)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(request, "Zapisano szablon.")
        return redirect("panel:dictionary_template_edit", pk=saved.pk)
    context = {
        "form": form,
        "template": template,
        "questions": template.questions.order_by("order", "pk") if template else [],
        "used_by": _types_using(template) if template else [],
    }
    return render(request, "panel/dictionary_template_edit.html", context)


@staff_required
def template_delete(request: HttpRequest, pk: int) -> HttpResponse:
    template = get_object_or_404(FormTemplate, pk=pk)
    if request.method == "POST":
        template.delete()
        messages.success(request, f"Usunięto szablon „{template.name}”.")
        return redirect("panel:dictionary_template_list")
    context = {"template": template, "used_by": _types_using(template)}
    return render(request, "panel/dictionary_template_delete.html", context)


@staff_required
def template_question_edit(
    request: HttpRequest, pk: int, question_pk: int | None = None
) -> HttpResponse:
    template = get_object_or_404(FormTemplate, pk=pk)
    question = None
    if question_pk is not None:
        question = get_object_or_404(TemplateQuestion, pk=question_pk, template=template)
    form = TemplateQuestionForm(request.POST or None, instance=question)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.template = template
        if question is None:
            last = template.questions.aggregate(Max("order"))["order__max"]
            saved.order = (last or 0) + 1
        saved.save()
        messages.success(request, "Zapisano pytanie szablonu.")
        return redirect("panel:dictionary_template_edit", pk=pk)
    context = {"template": template, "question": question, "form": form}
    return render(request, "panel/dictionary_question_edit.html", context)


@staff_required
@require_POST
def template_question_move(
    request: HttpRequest, pk: int, question_pk: int, direction: str
) -> HttpResponse:
    template = get_object_or_404(FormTemplate, pk=pk)
    if not ordering.move(list(template.questions.order_by("order", "pk")), question_pk, direction):
        raise Http404
    return redirect(reverse("panel:dictionary_template_edit", args=[pk]) + f"#q{question_pk}")


@staff_required
def template_question_delete(request: HttpRequest, pk: int, question_pk: int) -> HttpResponse:
    question = get_object_or_404(
        TemplateQuestion.objects.select_related("template"), pk=question_pk, template_id=pk
    )
    if request.method == "POST":
        question.delete()
        messages.success(request, "Usunięto pytanie z szablonu.")
        return redirect("panel:dictionary_template_edit", pk=pk)
    return render(request, "panel/dictionary_question_delete.html", {"question": question})
