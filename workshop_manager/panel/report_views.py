"""Panel pages for messages to participants (PRD §7.5) and printouts/exports (PRD §7.6)."""

from pathlib import Path
from typing import Any

from django import forms
from django.contrib import messages
from django.contrib.staticfiles import finders
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from workshop_manager.applications.models import ACTIVE_STATUSES, Status
from workshop_manager.communications import broadcasts
from workshop_manager.communications.defaults import APPLICATION_PLACEHOLDERS, SITE_PLACEHOLDERS
from workshop_manager.communications.models import Broadcast, Group, MessageStatus
from workshop_manager.communications.rendering import unknown_placeholders
from workshop_manager.core import audit
from workshop_manager.core.forms import BootstrapFormMixin
from workshop_manager.core.models import SiteSettings
from workshop_manager.exports import pdf, reports, spreadsheets
from workshop_manager.panel.views import staff_required
from workshop_manager.workshops.models import Session, Workshop

PLACEHOLDERS = APPLICATION_PLACEHOLDERS | SITE_PLACEHOLDERS
MAX_ATTACHMENT = 5 * 1024 * 1024

#: The Excel export's status choices: (value, label, statuses).
EXPORT_SCOPES: list[tuple[str, str, list[str] | None]] = [
    ("accepted", "przyjęci", [str(Status.ACCEPTED)]),
    ("active", "aktywni (nowi, przyjęci, rezerwa)", [str(s) for s in ACTIVE_STATUSES]),
    ("all", "wszystkie zgłoszenia", None),
]


def _workshop(pk: int) -> Workshop:
    return get_object_or_404(
        Workshop.objects.select_related("type", "location").prefetch_related(
            "levels", Prefetch("sessions", queryset=Session.objects.order_by("date", "start_time"))
        ),
        pk=pk,
    )


# --- Messages to participants ------------------------------------------------------------------


class BroadcastForm(BootstrapFormMixin, forms.ModelForm):
    remove_attachment = forms.BooleanField(label="Usuń załącznik", required=False)

    class Meta:
        model = Broadcast
        fields = ["group", "level", "subject", "body", "attachment"]  # noqa: RUF012
        widgets = {  # noqa: RUF012 — Django's Meta convention
            "group": forms.RadioSelect,
            "body": forms.Textarea(attrs={"rows": 14}),
        }

    def __init__(self, *args: Any, workshop: Workshop, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        level_field: forms.ModelChoiceField = self.fields["level"]  # type: ignore[assignment]
        level_field.queryset = workshop.levels.all()
        self.fields["level"].help_text = "Tylko dla „przyjęci na wybranym poziomie”."
        choices = list(Group.choices)
        if self.instance.group != Group.SELECTED:
            # "Selected people" is reached from the application list (tick, then "Napisz").
            choices = [c for c in choices if c[0] != Group.SELECTED]
        group_field: forms.ChoiceField = self.fields["group"]  # type: ignore[assignment]
        group_field.choices = choices
        if not self.instance.attachment:
            del self.fields["remove_attachment"]

    def clean_attachment(self) -> Any:
        file = self.cleaned_data.get("attachment")
        if file and getattr(file, "size", 0) > MAX_ATTACHMENT:
            raise forms.ValidationError("Załącznik może mieć najwyżej 5 MB.")
        return file

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        if data.get("group") == Group.LEVEL and not data.get("level"):
            self.add_error("level", "Wybierz poziom.")
        for name in ("subject", "body"):
            unknown = unknown_placeholders(data.get(name, ""), PLACEHOLDERS)
            if unknown:
                listed = ", ".join("{" + u + "}" for u in unknown)
                self.add_error(name, f"Nieznane pola: {listed}. Sprawdź pisownię z listą obok.")
        return data

    def save(self, commit: bool = True) -> Any:
        broadcast = super().save(commit=False)
        if self.cleaned_data.get("remove_attachment"):
            broadcast.attachment.delete(save=False)
            broadcast.attachment = ""
        if broadcast.group != Group.LEVEL:
            broadcast.level = None
        if commit:
            broadcast.save()
        return broadcast


@staff_required
def broadcast_list(request: HttpRequest, pk: int) -> HttpResponse:
    workshop = _workshop(pk)
    items = workshop.broadcasts.annotate(
        failed=Count("emails", filter=Q(emails__status=MessageStatus.FAILED)),
        sent=Count("emails", filter=Q(emails__status=MessageStatus.SENT)),
    )
    return render(request, "panel/broadcast_list.html", {"workshop": workshop, "broadcasts": items})


@staff_required
def broadcast_edit(request: HttpRequest, pk: int, broadcast_pk: int | None = None) -> HttpResponse:
    workshop = _workshop(pk)
    broadcast = None
    if broadcast_pk is not None:
        broadcast = get_object_or_404(Broadcast, pk=broadcast_pk, workshop=workshop)
        if broadcast.sent_at:
            return redirect("panel:broadcast_preview", pk=pk, broadcast_pk=broadcast.pk)
    form = BroadcastForm(
        request.POST or None,
        request.FILES or None,
        instance=broadcast or Broadcast(workshop=workshop, group=Group.ACCEPTED),
        workshop=workshop,
    )
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.created_by = saved.created_by or request.user
        saved.save()
        return redirect("panel:broadcast_preview", pk=pk, broadcast_pk=saved.pk)
    context = {
        "workshop": workshop,
        "form": form,
        "broadcast": broadcast,
        "placeholders": PLACEHOLDERS,
    }
    return render(request, "panel/broadcast_edit.html", context)


@staff_required
def broadcast_preview(request: HttpRequest, pk: int, broadcast_pk: int) -> HttpResponse:
    workshop = _workshop(pk)
    broadcast = get_object_or_404(Broadcast, pk=broadcast_pk, workshop=workshop)
    people = broadcasts.recipients(broadcast) if not broadcast.sent_at else []
    sample = broadcasts.personal_email(broadcast, people[0]) if people else None
    emails = broadcast.emails.select_related("application").order_by("to_email")
    context = {
        "workshop": workshop,
        "broadcast": broadcast,
        "people": people,
        "sample": sample,
        "emails": emails if broadcast.sent_at else [],
    }
    return render(request, "panel/broadcast_preview.html", context)


@staff_required
@require_POST
def broadcast_send(request: HttpRequest, pk: int, broadcast_pk: int) -> HttpResponse:
    broadcast = get_object_or_404(Broadcast, pk=broadcast_pk, workshop_id=pk)
    if not broadcast.subject or not broadcast.body:
        messages.error(request, "Uzupełnij temat i treść wiadomości.")
        return redirect("panel:broadcast_edit", pk=pk, broadcast_pk=broadcast.pk)
    count = broadcasts.send(broadcast, user=request.user)
    if count:
        messages.success(
            request, f"Wiadomość trafiła do kolejki: {count} e-maili. Status każdego widać niżej."
        )
    else:
        messages.info(request, "Ta wiadomość została już wysłana albo nie ma do kogo jej wysłać.")
    return redirect("panel:broadcast_preview", pk=pk, broadcast_pk=broadcast.pk)


@staff_required
@require_POST
def broadcast_delete(request: HttpRequest, pk: int, broadcast_pk: int) -> HttpResponse:
    broadcast = get_object_or_404(Broadcast, pk=broadcast_pk, workshop_id=pk, sent_at__isnull=True)
    if broadcast.attachment:
        broadcast.attachment.delete(save=False)
    broadcast.delete()
    messages.success(request, "Usunięto szkic wiadomości.")
    return redirect("panel:broadcast_list", pk=pk)


def broadcast_to_selected(request: HttpRequest, applications: list[Any]) -> HttpResponse:
    """Bulk action "Napisz wiadomość do zaznaczonych" (application list)."""
    workshops = {a.workshop_id for a in applications}
    if len(workshops) != 1:
        messages.error(request, "Wiadomość można napisać do osób z jednego warsztatu naraz.")
        return redirect(request.POST.get("next") or "panel:application_list")
    workshop_id = workshops.pop()
    broadcast = Broadcast.objects.create(
        workshop_id=workshop_id,
        group=Group.SELECTED,
        created_by=request.user,  # type: ignore[misc]
    )
    broadcast.selected.set(applications)
    return redirect("panel:broadcast_edit", pk=workshop_id, broadcast_pk=broadcast.pk)


# --- Printouts and exports -----------------------------------------------------------------------


@staff_required
def report_index(request: HttpRequest, pk: int) -> HttpResponse:
    workshop = _workshop(pk)
    context = {
        "workshop": workshop,
        "scopes": EXPORT_SCOPES,
        "counts": reports.status_counts(workshop),
        "pdf_available": pdf.available(),
        "has_materials": bool(reports.material_choices(workshop)),
    }
    return render(request, "panel/report_index.html", context)


def _filename(workshop: Workshop, what: str, extension: str) -> str:
    stamp = timezone.localdate().isoformat()
    return f"{slugify(workshop.title)[:60]}-{what}-{stamp}.{extension}"


@staff_required
def export_xlsx(request: HttpRequest, pk: int) -> HttpResponse:
    workshop = _workshop(pk)
    scope = request.GET.get("zakres", "accepted")
    statuses = next(
        (s for value, _label, s in EXPORT_SCOPES if value == scope), [str(Status.ACCEPTED)]
    )
    content = spreadsheets.applications_xlsx(workshop, statuses)
    audit.record(request.user, "Pobrano zgłoszenia do Excela", workshop, details=scope)
    response = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    name = _filename(workshop, "zgloszenia", "xlsx")
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    return response


def _print_css() -> str:
    path = finders.find("css/print.css")
    return Path(str(path)).read_text(encoding="utf-8") if path else ""


def _printout(
    request: HttpRequest, workshop: Workshop, template: str, what: str, context: dict[str, Any]
) -> HttpResponse:
    context = {
        "workshop": workshop,
        "printed_at": timezone.localtime(),
        "site_settings": SiteSettings.load(),  # the PDF is rendered without a request
    } | context
    if request.GET.get("format") == "pdf":
        if not pdf.available():
            raise Http404
        content = pdf.render_pdf(template, context | {"print_css": _print_css()})
        response = HttpResponse(content, content_type="application/pdf")
        name = _filename(workshop, what, "pdf")
        response["Content-Disposition"] = f'inline; filename="{name}"'
        return response
    return render(request, template, context)


@staff_required
def attendance(request: HttpRequest, pk: int) -> HttpResponse:
    """Accepted people per level, a column per session to sign in (A4 landscape)."""
    workshop = _workshop(pk)
    context = {
        "groups": reports.by_level(workshop, [Status.ACCEPTED]),
        "sessions": workshop.ordered_sessions(),
    }
    return _printout(request, workshop, "print/attendance.html", "lista-obecnosci", context)


@staff_required
def contacts(request: HttpRequest, pk: int) -> HttpResponse:
    workshop = _workshop(pk)
    context = {"groups": reports.by_level(workshop, [Status.ACCEPTED])}
    return _printout(request, workshop, "print/contacts.html", "lista-kontaktowa", context)


@staff_required
def materials(request: HttpRequest, pk: int) -> HttpResponse:
    workshop = _workshop(pk)
    context = {"summaries": reports.materials(workshop)}
    return _printout(request, workshop, "print/materials.html", "materialy", context)
