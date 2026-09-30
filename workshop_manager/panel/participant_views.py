"""Panel pages about people (PRD §7.4, §8): the register, one person's card, GDPR actions.

A person's card gathers their applications from every workshop, their consents with the
wording they agreed to, and the two actions a data request needs: a copy of the data and
anonymisation.
"""

import json

from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from workshop_manager.applications import gdpr
from workshop_manager.applications.models import Participant
from workshop_manager.core import audit
from workshop_manager.core.forms import BootstrapFormMixin
from workshop_manager.panel.views import staff_required

PAGE_SIZE = 50


@staff_required
def participant_list(request: HttpRequest) -> HttpResponse:
    qs = Participant.objects.annotate(application_count=Count("applications")).order_by(
        "last_name", "first_name", "pk"
    )
    query = request.GET.get("q", "").strip()
    if query:
        for word in query.split():
            qs = qs.filter(
                Q(first_name__icontains=word)
                | Q(last_name__icontains=word)
                | Q(email__icontains=word)
                | Q(phone__icontains=word)
            )
    marketing = request.GET.get("zgoda") == "1"
    if marketing:
        qs = qs.filter(marketing_consent=True)
    show_anonymised = request.GET.get("anonimowi") == "1"
    if not show_anonymised:
        qs = qs.filter(anonymised_at__isnull=True)
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    context = {
        "page": page,
        "query": query,
        "marketing": marketing,
        "show_anonymised": show_anonymised,
    }
    return render(request, "panel/participant_list.html", context)


@staff_required
def participant_detail(request: HttpRequest, pk: int) -> HttpResponse:
    participant = get_object_or_404(Participant, pk=pk)
    applications = participant.applications.select_related("workshop", "level").order_by(
        "-submitted_at"
    )
    context = {
        "participant": participant,
        "applications": applications,
        "consents": participant.consents.select_related("application__workshop").order_by(
            "-created_at", "-pk"
        ),
        "blocking": gdpr.blocking_applications(participant),
    }
    return render(request, "panel/participant_detail.html", context)


@staff_required
def participant_export(request: HttpRequest, pk: int) -> HttpResponse:
    """A copy of the person's data for a request under GDPR art. 15 (with the organiser's notes)."""
    participant = get_object_or_404(Participant, pk=pk, anonymised_at__isnull=True)
    data = gdpr.export_data(participant, for_organiser=True)
    audit.record(request.user, "Pobrano kopię danych osoby", participant)
    response = HttpResponse(
        json.dumps(data, ensure_ascii=False, indent=2), content_type="application/json"
    )
    stamp = timezone.localdate().isoformat()
    response["Content-Disposition"] = f'attachment; filename="dane-osoby-{pk}-{stamp}.json"'
    return response


class AnonymiseForm(BootstrapFormMixin, forms.Form):
    confirm = forms.BooleanField(
        label="Rozumiem, że dane tej osoby zostaną usunięte na zawsze i nie da się tego cofnąć."
    )


@staff_required
def participant_anonymise(request: HttpRequest, pk: int) -> HttpResponse:
    participant = get_object_or_404(Participant, pk=pk, anonymised_at__isnull=True)
    blocking = gdpr.blocking_applications(participant)
    form = AnonymiseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            gdpr.anonymise(participant, user=request.user)
        except gdpr.CannotAnonymise as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Dane osoby zostały usunięte (zanonimizowane).")
            return redirect("panel:participant_detail", pk=pk)
    context = {"participant": participant, "blocking": blocking, "form": form}
    return render(request, "panel/participant_anonymise.html", context)
