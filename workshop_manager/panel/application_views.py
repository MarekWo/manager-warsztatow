"""Panel pages for reviewing applications (PRD §7.3) and the event log (PRD §7.9)."""

from typing import Any

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from workshop_manager.applications import decisions
from workshop_manager.applications.forms import PanelApplicationForm
from workshop_manager.applications.models import (
    ACTION_LABELS,
    TRANSITIONS,
    Application,
    Status,
    StatusChange,
)
from workshop_manager.applications.services import DuplicateApplication, submit_application
from workshop_manager.applications.summary import level_summaries
from workshop_manager.core import audit
from workshop_manager.core.models import AuditEvent
from workshop_manager.exports.reports import material_choices
from workshop_manager.panel.forms import (
    ApplicationEditForm,
    DecisionForm,
    LevelChangeForm,
    NotesForm,
)
from workshop_manager.panel.views import staff_required
from workshop_manager.workshops.models import Workshop

PAGE_SIZE = 50

#: Bulk actions under the list: decision statuses plus "mark as seen".
BULK_ACTIONS = [
    (Status.ACCEPTED, "Przyjmij zaznaczone"),
    (Status.WAITLISTED, "Wpisz zaznaczone na listę rezerwową"),
    (Status.REJECTED, "Odrzuć zaznaczone"),
    ("seen", "Oznacz zaznaczone jako przejrzane"),
    ("message", "Napisz wiadomość do zaznaczonych"),
]


def _safe_next(request: HttpRequest, default: str) -> str:
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}):
        return target
    return default


def _hint_message(request: HttpRequest, application: Application, old_status: str) -> None:
    waiting = decisions.freed_place_hint(application, old_status)
    if waiting is not None:
        messages.info(
            request,
            format_html(
                "Zwolniło się miejsce na poziomie „{}”. Pierwsza osoba z listy rezerwowej: "
                '<a href="{}">{}</a>.',
                application.level.name,
                waiting.get_panel_url(),
                waiting.full_name,
            ),
        )


# --- Lists --------------------------------------------------------------------------------------


def _filtered(request: HttpRequest, workshop: Workshop | None) -> tuple[Any, dict[str, Any]]:
    qs = Application.objects.select_related("workshop", "level")
    if workshop is not None:
        qs = qs.filter(workshop=workshop)
    status = request.GET.get("status", "")
    if status == "active":
        qs = qs.filter(status__in=[Status.NEW, Status.ACCEPTED, Status.WAITLISTED])
    elif status in Status.values:
        qs = qs.filter(status=status)
    else:
        status = ""
    level = request.GET.get("level", "")
    if workshop is not None and level.isdigit():
        qs = qs.filter(level_id=int(level))
    else:
        level = ""
    material = request.GET.get("material", "")
    if workshop is not None and "|" in material:
        question_id, _sep, choice = material.partition("|")
        if question_id.isdigit():
            qs = qs.filter(answers__question_id=int(question_id), answers__value=choice)
    else:
        material = ""
    query = request.GET.get("q", "").strip()
    if query:
        for word in query.split():
            qs = qs.filter(
                Q(first_name__icontains=word)
                | Q(last_name__icontains=word)
                | Q(email__icontains=word)
            )
    unseen = request.GET.get("unseen") == "1"
    if unseen:
        qs = qs.filter(is_seen=False)
    order = "-submitted_at" if request.GET.get("order") == "newest" else "submitted_at"
    qs = qs.order_by(order, "pk")
    filters = {
        "status": status,
        "level": level,
        "q": query,
        "unseen": unseen,
        "order": request.GET.get("order", ""),
        "material": material,
    }
    return qs, filters


def _list_context(request: HttpRequest, workshop: Workshop | None) -> dict[str, Any]:
    qs, filters = _filtered(request, workshop)
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return {
        "page": page,
        "filters": filters,
        "query_string": query.urlencode(),
        "statuses": Status.choices,
        "bulk_actions": BULK_ACTIONS,
        "workshop": workshop,
        "total": qs.count(),
    }


@staff_required
def application_list(request: HttpRequest) -> HttpResponse:
    """Applications to every workshop — mostly for "nieprzejrzane" and searching a person."""
    context = _list_context(request, None)
    return render(request, "panel/application_list.html", context)


@staff_required
def workshop_applications(request: HttpRequest, pk: int) -> HttpResponse:
    workshop = get_object_or_404(
        Workshop.objects.prefetch_related("levels").select_related("type"), pk=pk
    )
    context = _list_context(request, workshop)
    context["summaries"] = level_summaries([workshop])[workshop.pk]
    context["material_choices"] = material_choices(workshop)
    context["waitlists"] = [
        (
            level,
            list(
                workshop.applications.filter(level=level, status=Status.WAITLISTED).order_by(
                    "waitlist_position", "submitted_at"
                )
            ),
        )
        for level in workshop.levels.all()
    ]
    context["has_waitlist"] = any(waiting for _level, waiting in context["waitlists"])
    return render(request, "panel/workshop_applications.html", context)


@staff_required
@require_POST
def application_bulk(request: HttpRequest) -> HttpResponse:
    back = _safe_next(request, reverse("panel:application_list"))
    action = request.POST.get("action", "")
    ids = [int(i) for i in request.POST.getlist("ids") if i.isdigit()]
    applications = list(
        Application.objects.filter(pk__in=ids).select_related("workshop", "level", "participant")
    )
    if not applications:
        messages.error(request, "Zaznacz co najmniej jedno zgłoszenie.")
        return redirect(back)
    if action == "message":
        from workshop_manager.panel.report_views import broadcast_to_selected

        return broadcast_to_selected(request, applications)
    if action == "seen":
        count = Application.objects.filter(pk__in=ids).update(is_seen=True)
        messages.success(request, f"Oznaczono jako przejrzane: {count}.")
        return redirect(back)
    if action not in ACTION_LABELS:
        raise Http404
    notify = request.POST.get("notify") == "1"
    changed, skipped = decisions.bulk_change_status(
        applications, action, user=request.user, notify=notify
    )
    label = Status(action).label
    if changed:
        sent = " Powiadomienia e-mail są w drodze." if notify else ""
        messages.success(request, f"Zmieniono status na „{label}”: {changed}.{sent}")
    if skipped:
        messages.warning(
            request,
            "Pominięto (ta zmiana nie jest możliwa dla ich obecnego statusu): "
            + ", ".join(skipped)
            + ".",
        )
    return redirect(back)


# --- One application ----------------------------------------------------------------------------


def _application(pk: int) -> Application:
    return get_object_or_404(
        Application.objects.select_related("workshop", "level", "participant").prefetch_related(
            "answers",
            Prefetch(
                "history",
                queryset=StatusChange.objects.select_related("changed_by"),
                to_attr="history_entries",
            ),
        ),
        pk=pk,
    )


@staff_required
def application_detail(request: HttpRequest, pk: int) -> HttpResponse:
    application = _application(pk)
    notes_form = NotesForm(request.POST or None, instance=application, prefix="notes")
    if request.method == "POST":
        if notes_form.is_valid():
            notes_form.save()
            messages.success(request, "Zapisano notatkę.")
            return redirect(application.get_panel_url())
    elif not application.is_seen:
        application.is_seen = True
        application.save(update_fields=["is_seen"])
    others = (
        application.participant.applications.exclude(pk=application.pk)
        .select_related("workshop", "level")
        .order_by("-submitted_at")
    )
    context = {
        "application": application,
        "workshop": application.workshop,
        "notes_form": notes_form,
        "level_form": LevelChangeForm(
            workshop=application.workshop, initial={"level": application.level_id}
        ),
        "others": others,
        "history": application.history_entries,  # type: ignore[attr-defined]
        "emails": application.emails.order_by("-created_at")[:20],
        "transitions": application.allowed_transitions(),
    }
    return render(request, "panel/application_detail.html", context)


@staff_required
def application_decide(request: HttpRequest, pk: int, status: str) -> HttpResponse:
    """The decision window: preview (and edit) the e-mail, then confirm."""
    application = _application(pk)
    if status not in ACTION_LABELS:
        raise Http404
    if status not in TRANSITIONS[application.status]:
        messages.error(request, "Ta zmiana nie jest możliwa dla obecnego statusu zgłoszenia.")
        return redirect(application.get_panel_url())
    preview = decisions.decision_email(application, status)
    initial: dict[str, Any] = {"notify": True}
    if preview is not None:
        initial |= {"subject": preview.subject, "body": preview.body}
    form = DecisionForm(request.POST or None, initial=initial, with_email=preview is not None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        old_status = application.status
        notify = bool(data.get("notify"))
        email = decisions.EmailText(subject=data["subject"], body=data["body"]) if notify else None
        try:
            decisions.change_status(
                application,
                status,
                user=request.user,
                notify=notify,
                email=email,
                comment=data.get("comment", ""),
            )
        except decisions.TransitionError as error:
            messages.error(request, str(error))
            return redirect(application.get_panel_url())
        sent = " Powiadomienie e-mail jest w drodze." if notify else ""
        messages.success(
            request, f"Status zmieniono na „{application.get_status_display()}”.{sent}"
        )
        _hint_message(request, application, old_status)
        return redirect(_safe_next(request, application.get_panel_url()))
    context = {
        "application": application,
        "workshop": application.workshop,
        "form": form,
        "target_status": Status(status),
        "action_label": ACTION_LABELS[status],
        "next": _safe_next(request, ""),
    }
    return render(request, "panel/application_decide.html", context)


@staff_required
@require_POST
def application_level(request: HttpRequest, pk: int) -> HttpResponse:
    application = _application(pk)
    form = LevelChangeForm(request.POST, workshop=application.workshop)
    if form.is_valid():
        old_status = application.status
        decisions.change_level(application, form.cleaned_data["level"], user=request.user)
        messages.success(request, f"Zmieniono poziom na „{application.level.name}”.")
        if old_status == Status.ACCEPTED:
            messages.info(
                request,
                "Sprawdź listę rezerwową poprzedniego poziomu — mogło się tam zwolnić miejsce.",
            )
    return redirect(application.get_panel_url())


@staff_required
def application_edit(request: HttpRequest, pk: int) -> HttpResponse:
    application = _application(pk)
    form = ApplicationEditForm(request.POST or None, instance=application)
    if request.method == "POST" and form.is_valid():
        before = {name: str(form.initial.get(name) or "") for name in form.changed_data}
        with transaction.atomic():
            form.save()
            changed = {
                str(form.fields[name].label): (before[name], str(form.cleaned_data[name] or ""))
                for name in form.changed_data
            }
            decisions.record_correction(application, changed, user=request.user)
        messages.success(request, "Zapisano dane zgłoszenia.")
        return redirect(application.get_panel_url())
    return render(
        request,
        "panel/application_edit.html",
        {"application": application, "workshop": application.workshop, "form": form},
    )


@staff_required
@require_POST
def application_waitlist_move(request: HttpRequest, pk: int, direction: str) -> HttpResponse:
    application = get_object_or_404(Application, pk=pk)
    if direction not in ("up", "down"):
        raise Http404
    decisions.move_on_waitlist(application, direction)
    audit.record(
        request.user,
        "Zmieniono kolejność na liście rezerwowej",
        application,
        details="w górę" if direction == "up" else "w dół",
    )
    default = reverse("panel:workshop_applications", args=[application.workshop_id])
    return redirect(_safe_next(request, default) + "#rezerwa")


@staff_required
def application_add(request: HttpRequest, pk: int) -> HttpResponse:
    """An application entered by the administrator (made by phone or in person)."""
    workshop = get_object_or_404(Workshop, pk=pk)
    if not workshop.levels.exists():
        messages.error(request, "Dodaj co najmniej jeden poziom, zanim dodasz zgłoszenie.")
        return redirect("panel:workshop_edit", pk=pk)
    form = PanelApplicationForm(request.POST or None, workshop=workshop)
    if request.method == "POST" and form.is_valid():
        try:
            application = submit_application(
                form,
                added_by=request.user,
                send_confirmation=form.cleaned_data.get("send_confirmation", False),
            )
        except DuplicateApplication:
            form.add_error(
                "email",
                "Ta osoba ma już aktywne zgłoszenie na ten warsztat — znajdziesz je na liście.",
            )
        else:
            messages.success(request, "Dodano zgłoszenie. Możesz teraz podjąć decyzję.")
            return redirect(application.get_panel_url())
    return render(request, "panel/application_add.html", {"workshop": workshop, "form": form})


# --- Event log ------------------------------------------------------------------------------------


@staff_required
def audit_log(request: HttpRequest) -> HttpResponse:
    qs = AuditEvent.objects.all()
    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(action__icontains=query)
            | Q(target__icontains=query)
            | Q(actor_email__icontains=query)
            | Q(details__icontains=query)
        )
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "panel/audit_log.html", {"page": page, "query": query})
