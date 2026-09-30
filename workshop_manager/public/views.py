from django.contrib import messages
from django.db.models import Prefetch
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from workshop_manager.applications.forms import ApplicationForm
from workshop_manager.applications.models import ACTIVE_STATUSES, Application
from workshop_manager.applications.services import DuplicateApplication, submit_application
from workshop_manager.core import ratelimit
from workshop_manager.public.account_views import own_applications
from workshop_manager.workshops.models import Session, Workshop, WorkshopQuerySet


def _workshops() -> WorkshopQuerySet:
    return Workshop.objects.select_related("type", "location").prefetch_related(
        Prefetch("sessions", queryset=Session.objects.order_by("date", "start_time")), "levels"
    )


def home(request: HttpRequest) -> HttpResponse:
    """The list of current workshops, or a notice that none are planned (PRD §6.1).

    A signed-in participant sees which of them they have already applied for.
    """
    workshops = list(_workshops().public())
    mine: dict[int, Application] = {}
    if request.user.is_authenticated:
        mine = {
            application.workshop_id: application
            for application in own_applications(request.user).filter(
                workshop__in=workshops, status__in=ACTIVE_STATUSES
            )
        }
    cards = [(workshop, mine.get(workshop.pk)) for workshop in workshops]
    return render(request, "public/home.html", {"cards": cards})


def _active_own_application(request: HttpRequest, workshop: Workshop) -> Application | None:
    """The signed-in person's live application for this workshop, if they have one."""
    if not request.user.is_authenticated:
        return None
    return (
        own_applications(request.user).filter(workshop=workshop, status__in=ACTIVE_STATUSES).first()
    )


def workshop_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """A workshop's page (PRD §6.2). Administrators may preview drafts and scheduled ones."""
    workshop = get_object_or_404(_workshops(), slug=slug)
    is_preview = not workshop.is_public()
    if is_preview and not request.user.is_staff:
        raise Http404
    context = {
        "workshop": workshop,
        "is_preview": is_preview,
        "own_application": _active_own_application(request, workshop),
    }
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

    own_application = _active_own_application(request, workshop)
    if own_application is not None:
        messages.info(request, "Masz już zgłoszenie na te warsztaty — oto jego szczegóły.")
        return redirect("public:my_application", pk=own_application.pk)

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
    duplicate_email = ""
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
                duplicate_email = form.cleaned_data["email"]
                form.add_error(
                    "email",
                    "Z tego adresu jest już zgłoszenie na te warsztaty. Jeśli chcesz coś w nim "
                    "zmienić, napisz do organizatora.",
                )
            else:
                request.session[LAST_APPLICATION_KEY] = application.pk
                return redirect("public:application_sent", slug=workshop.slug)
    context = {"workshop": workshop, "form": form, "duplicate_email": duplicate_email}
    return render(request, "public/apply.html", context)


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
