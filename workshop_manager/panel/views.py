"""The administrator's panel (PRD §7). Every view requires a staff account."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Max, Prefetch
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from workshop_manager.applications.models import Application
from workshop_manager.applications.summary import level_summaries
from workshop_manager.communications.services import failed_or_retrying
from workshop_manager.core import audit
from workshop_manager.core.models import SiteSettings
from workshop_manager.forms_builder.models import Question, copy_template
from workshop_manager.panel import ordering
from workshop_manager.panel.forms import (
    AddTemplateForm,
    DuplicateForm,
    LevelFormSet,
    LocationForm,
    QuestionForm,
    SessionFormSet,
    StandardFieldsForm,
    WorkshopCreateForm,
    WorkshopForm,
)
from workshop_manager.workshops.models import Location, Session, Workshop
from workshop_manager.workshops.services import create_workshop, duplicate_workshop

staff_required: Callable[..., Any] = staff_member_required(login_url="account_request_login_code")

TABS = [
    ("published", "Opublikowane"),
    ("scheduled", "Zaplanowane"),
    ("draft", "Szkice"),
    ("finished", "Zakończone"),
    ("archived", "Archiwum"),
]


def _workshops() -> Any:
    return Workshop.objects.select_related("type", "location").prefetch_related(
        Prefetch("sessions", queryset=Session.objects.order_by("date", "start_time")), "levels"
    )


# --- Dashboard ------------------------------------------------------------------------------


@staff_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Start page (PRD §7.1): applications per level, what needs attention, what is coming."""
    now = timezone.now()
    published = list(_workshops().in_tab("published", now))
    scheduled = list(_workshops().in_tab("scheduled", now))
    summaries = level_summaries(published + scheduled)
    site = SiteSettings.load()
    default_backend = settings.MAILERS.get("default", {}).get("BACKEND", "")
    context = {
        "published": [(w, summaries[w.pk]) for w in published],
        "scheduled": [(w, summaries[w.pk]) for w in scheduled],
        "drafts": _workshops().in_tab("draft", now)[:5],
        "unseen": Application.objects.filter(is_seen=False).count(),
        "failed_emails": failed_or_retrying().count(),
        "publishing_soon": [w for w in scheduled if w.publish_at <= now + timedelta(days=7)],
        "no_smtp": not site.uses_own_smtp()
        and any(name in default_backend for name in ("console", "dummy")),
    }
    return render(request, "panel/dashboard.html", context)


# --- Workshops ------------------------------------------------------------------------------


@staff_required
def workshop_list(request: HttpRequest) -> HttpResponse:
    tab = request.GET.get("tab", "published")
    if tab not in dict(TABS):
        tab = "published"
    workshops = _workshops().in_tab(tab)
    return render(
        request, "panel/workshop_list.html", {"workshops": workshops, "tabs": TABS, "tab": tab}
    )


@staff_required
def workshop_create(request: HttpRequest) -> HttpResponse:
    form = WorkshopCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        workshop = create_workshop(
            workshop_type=form.cleaned_data["type"],
            title=form.cleaned_data["title"],
            template=form.chosen_template(),
            location=form.cleaned_data["location"],
            user=request.user,
        )
        audit.record(request.user, "Utworzono warsztat", workshop)
        messages.success(
            request,
            "Utworzono szkic warsztatu. Uzupełnij terminy spotkań, poziomy i datę publikacji.",
        )
        return redirect("panel:workshop_edit", pk=workshop.pk)
    return render(request, "panel/workshop_create.html", {"form": form})


@staff_required
def workshop_edit(request: HttpRequest, pk: int) -> HttpResponse:
    workshop = get_object_or_404(_workshops(), pk=pk)
    data = request.POST if request.method == "POST" else None
    files = request.FILES if request.method == "POST" else None
    form = WorkshopForm(data, files, instance=workshop)
    sessions = SessionFormSet(data, instance=workshop, prefix="sessions")
    levels = LevelFormSet(data, instance=workshop, prefix="levels")
    if request.method == "POST":
        if form.is_valid() and sessions.is_valid() and levels.is_valid():
            with transaction.atomic():
                form.save()
                sessions.save()
                levels.save()
                for order, level in enumerate(workshop.levels.order_by("order", "pk")):
                    if level.order != order:
                        level.order = order
                        level.save(update_fields=["order"])
                changed = [
                    str(f.fields[name].label)
                    for f in [form, *sessions.forms, *levels.forms]
                    for name in f.changed_data
                    if name in f.fields and name not in ("id", "workshop")
                ]
                audit.record(
                    request.user,
                    "Zmieniono warsztat",
                    workshop,
                    details=", ".join(dict.fromkeys(changed)),
                )
            messages.success(request, "Zapisano zmiany.")
            return redirect("panel:workshop_edit", pk=workshop.pk)
        messages.error(request, "Popraw zaznaczone pola i zapisz ponownie.")
    context = {"workshop": workshop, "form": form, "sessions": sessions, "levels": levels}
    return render(request, "panel/workshop_edit.html", context)


_ROW_FORMSETS: dict[str, Any] = {
    "sessions": SessionFormSet,
    "levels": LevelFormSet,
}


@staff_required
def formset_row(request: HttpRequest, prefix: str) -> HttpResponse:
    """One more empty row for the sessions or levels table (HTMX, no JavaScript of our own).

    The response carries the new row and, out of band, the management form's TOTAL_FORMS
    raised by one, so Django accepts the extra row on save.
    """
    formset_class = _ROW_FORMSETS.get(prefix)
    if formset_class is None:
        raise Http404
    try:
        index = int(request.GET.get(f"{prefix}-TOTAL_FORMS", "0"))
    except ValueError:
        index = 0
    formset = formset_class(prefix=prefix)
    form = formset.empty_form
    form.prefix = f"{prefix}-{index}"
    return render(
        request,
        f"panel/partials/{prefix}_row.html",
        {"form": form, "prefix": prefix, "total": index + 1, "oob": True},
    )


@staff_required
@require_POST
def workshop_action(request: HttpRequest, pk: int, action: str) -> HttpResponse:
    """Quick actions from the workshop page: publish now, close/open registration, archive."""
    workshop = get_object_or_404(Workshop, pk=pk)
    if action == "publish_now":
        if not workshop.sessions.exists():
            messages.error(request, "Dodaj co najmniej jedno spotkanie przed publikacją.")
            return redirect("panel:workshop_edit", pk=pk)
        workshop.publish_at = timezone.now()
        message = "Warsztat jest opublikowany."
    elif action == "unpublish":
        workshop.publish_at = None
        message = "Warsztat wrócił do szkiców i nie jest widoczny publicznie."
    elif action == "close_registration":
        workshop.registration_closed = True
        message = "Zapisy zostały zamknięte."
    elif action == "open_registration":
        workshop.registration_closed = False
        message = "Zapisy zostały ponownie otwarte (w ramach ustawionych dat)."
    elif action == "archive":
        workshop.is_archived = True
        message = "Warsztat przeniesiono do archiwum."
    elif action == "unarchive":
        workshop.is_archived = False
        message = "Warsztat przywrócono z archiwum."
    else:
        raise Http404
    workshop.save()
    audit.record(request.user, message.rstrip("."), workshop)
    messages.success(request, message)
    return redirect(request.POST.get("next") or reverse("panel:workshop_edit", args=[pk]))


@staff_required
def workshop_duplicate(request: HttpRequest, pk: int) -> HttpResponse:
    source = get_object_or_404(_workshops(), pk=pk)
    form = DuplicateForm(request.POST or None, initial={"title": source.title})
    if request.method == "POST" and form.is_valid():
        copy = duplicate_workshop(
            source,
            title=form.cleaned_data["title"],
            first_date=form.cleaned_data["first_date"],
            user=request.user,
        )
        audit.record(request.user, "Zduplikowano warsztat", copy, details=f"z „{source.title}”")
        messages.success(
            request, "Utworzono kopię jako szkic. Sprawdź terminy i ustaw datę publikacji."
        )
        return redirect("panel:workshop_edit", pk=copy.pk)
    return render(request, "panel/workshop_duplicate.html", {"source": source, "form": form})


@staff_required
def workshop_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Only drafts may be deleted; anything that was public goes to the archive instead."""
    workshop = get_object_or_404(Workshop, pk=pk)
    if workshop.state() != "draft" or workshop.applications.exists():
        messages.error(
            request,
            "Usunąć można tylko szkic bez zgłoszeń. Ten warsztat przenieś do archiwum.",
        )
        return redirect("panel:workshop_edit", pk=pk)
    if request.method == "POST":
        workshop.delete()
        audit.record(request.user, "Usunięto szkic warsztatu", workshop.title)
        messages.success(request, f"Usunięto szkic „{workshop.title}”.")
        return redirect(reverse("panel:workshop_list") + "?tab=draft")
    return render(request, "panel/workshop_delete.html", {"workshop": workshop})


# --- Application form --------------------------------------------------------------------------


@staff_required
def form_editor(request: HttpRequest, pk: int) -> HttpResponse:
    """Standard fields and the workshop's questions (PRD §6.3)."""
    workshop = get_object_or_404(Workshop, pk=pk)
    fields_form = StandardFieldsForm(request.POST or None, instance=workshop, prefix="fields")
    if request.method == "POST" and fields_form.is_valid():
        fields_form.save()
        messages.success(request, "Zapisano ustawienia pól formularza.")
        return redirect("panel:form_editor", pk=pk)
    questions = workshop.questions.select_related("level").order_by("order", "pk")
    context = {
        "workshop": workshop,
        "fields_form": fields_form,
        "questions": questions,
        "template_form": AddTemplateForm(prefix="tpl"),
    }
    return render(request, "panel/form_editor.html", context)


@staff_required
def question_edit(request: HttpRequest, pk: int, question_pk: int | None = None) -> HttpResponse:
    workshop = get_object_or_404(Workshop, pk=pk)
    question = None
    if question_pk is not None:
        question = get_object_or_404(Question, pk=question_pk, workshop=workshop)
    form = QuestionForm(request.POST or None, instance=question, workshop=workshop)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.workshop = workshop
        if question is None:
            last = workshop.questions.aggregate(Max("order"))["order__max"]
            saved.order = (last or 0) + 1
        saved.save()
        audit.record(request.user, "Zapisano pytanie formularza", workshop, details=saved.label)
        messages.success(request, "Zapisano pytanie.")
        return redirect("panel:form_editor", pk=pk)
    return render(
        request,
        "panel/question_edit.html",
        {"workshop": workshop, "question": question, "form": form},
    )


@staff_required
@require_POST
def question_move(request: HttpRequest, pk: int, question_pk: int, direction: str) -> HttpResponse:
    """Swap a question with its neighbour."""
    workshop = get_object_or_404(Workshop, pk=pk)
    if not ordering.move(list(workshop.questions.order_by("order", "pk")), question_pk, direction):
        raise Http404
    return redirect(reverse("panel:form_editor", args=[pk]) + f"#q{question_pk}")


@staff_required
@require_POST
def question_toggle(request: HttpRequest, pk: int, question_pk: int) -> HttpResponse:
    question = get_object_or_404(Question, pk=question_pk, workshop_id=pk)
    question.is_active = not question.is_active
    question.save(update_fields=["is_active"])
    return redirect(reverse("panel:form_editor", args=[pk]) + f"#q{question_pk}")


@staff_required
def question_delete(request: HttpRequest, pk: int, question_pk: int) -> HttpResponse:
    workshop = get_object_or_404(Workshop, pk=pk)
    question = get_object_or_404(Question, pk=question_pk, workshop=workshop)
    if question.answers.exists():
        messages.error(
            request,
            "Na to pytanie ktoś już odpowiedział, więc nie można go usunąć — możesz je ukryć.",
        )
        return redirect("panel:form_editor", pk=pk)
    if request.method == "POST":
        question.delete()
        audit.record(request.user, "Usunięto pytanie formularza", workshop, details=question.label)
        messages.success(request, "Usunięto pytanie.")
        return redirect("panel:form_editor", pk=pk)
    return render(
        request, "panel/question_delete.html", {"workshop": workshop, "question": question}
    )


@staff_required
@require_POST
def questions_from_template(request: HttpRequest, pk: int) -> HttpResponse:
    workshop = get_object_or_404(Workshop, pk=pk)
    form = AddTemplateForm(request.POST, prefix="tpl")
    if form.is_valid():
        added = copy_template(form.cleaned_data["template"], workshop)
        messages.success(request, f"Dodano pytania z szablonu ({len(added)}).")
    return redirect("panel:form_editor", pk=pk)


# --- Locations --------------------------------------------------------------------------------


@staff_required
def location_list(request: HttpRequest) -> HttpResponse:
    locations = Location.objects.order_by("-is_active", "name")
    return render(request, "panel/location_list.html", {"locations": locations})


@staff_required
def location_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    location = get_object_or_404(Location, pk=pk) if pk is not None else None
    form = LocationForm(request.POST or None, instance=location)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        audit.record(request.user, "Zapisano miejsce", saved)
        messages.success(request, "Zapisano miejsce.")
        return redirect("panel:location_list")
    return render(request, "panel/location_edit.html", {"form": form, "location": location})
