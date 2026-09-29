from django.contrib import messages
from django.db.models import Prefetch
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from workshop_manager.applications.forms import ApplicationForm
from workshop_manager.applications.models import Application
from workshop_manager.applications.services import DuplicateApplication, submit_application
from workshop_manager.core import ratelimit
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


#: Applications one address may send per hour: a family on one connection is fine, a script is not.
APPLICATIONS_PER_HOUR = 10
LAST_APPLICATION_KEY = "last_application_id"


def apply(request: HttpRequest, slug: str) -> HttpResponse:
    """The application form (PRD §6.3), open only within the registration window."""
    workshop = get_object_or_404(_workshops(), slug=slug)
    if not workshop.is_registration_open():
        if not workshop.is_public() and not request.user.is_staff:
            raise Http404
        messages.info(request, "Zapisy na ten warsztat nie są teraz prowadzone.")
        return redirect(workshop.get_absolute_url())

    initial = {}
    if request.user.is_authenticated:
        user = request.user
        initial = {
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": getattr(user, "phone", ""),
        }
    form = ApplicationForm(request.POST or None, workshop=workshop, initial=initial)
    if request.method == "POST":
        client_ip = getattr(request, "client_ip", "") or "unknown"
        if not ratelimit.hit(
            f"apply:{client_ip}", limit=APPLICATIONS_PER_HOUR, window_seconds=3600
        ):
            form.add_error(
                None,
                "Z tego połączenia wysłano w ostatniej godzinie zbyt wiele zgłoszeń. "
                "Spróbuj ponownie później lub napisz do organizatora.",
            )
        elif form.is_valid():
            try:
                application = submit_application(form, user=request.user)
            except DuplicateApplication:
                form.add_error(
                    "email",
                    "Z tego adresu jest już zgłoszenie na te warsztaty. Jeśli chcesz coś w nim "
                    "zmienić, napisz do organizatora.",
                )
            else:
                request.session[LAST_APPLICATION_KEY] = application.pk
                return redirect("public:application_sent", slug=workshop.slug)
    return render(request, "public/apply.html", {"workshop": workshop, "form": form})


def application_sent(request: HttpRequest, slug: str) -> HttpResponse:
    """Thank-you page with a summary — only for the browser that just sent the application."""
    application_id = request.session.get(LAST_APPLICATION_KEY)
    if application_id is None:
        return redirect("public:workshop", slug=slug)
    application = (
        Application.objects.select_related("workshop", "level")
        .prefetch_related("answers")
        .filter(pk=application_id, workshop__slug=slug)
        .first()
    )
    if application is None:
        return redirect("public:workshop", slug=slug)
    return render(request, "public/application_sent.html", {"application": application})
