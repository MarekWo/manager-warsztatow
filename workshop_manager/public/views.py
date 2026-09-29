from django.db.models import Prefetch
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from workshop_manager.workshops.models import Session, Workshop, WorkshopQuerySet


def _workshops() -> WorkshopQuerySet:
    return Workshop.objects.select_related("type", "location").prefetch_related(
        Prefetch("sessions", queryset=Session.objects.order_by("date", "start_time")), "levels"
    )


def home(request: HttpRequest) -> HttpResponse:
    """The list of current workshops, or a notice that none are planned (PRD §6.1)."""
    return render(request, "public/home.html", {"workshops": _workshops().public()})


def workshop_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """A workshop's page (PRD §6.2). Administrators may preview drafts and scheduled ones."""
    workshop = get_object_or_404(_workshops(), slug=slug)
    is_preview = not workshop.is_public()
    if is_preview and not request.user.is_staff:
        raise Http404
    context = {"workshop": workshop, "is_preview": is_preview}
    return render(request, "public/workshop_detail.html", context)
