"""The administrator's help (PRD §7.10) and the short help for participants."""

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from workshop_manager.help.chapters import BY_SLUG, CHAPTERS
from workshop_manager.panel.views import staff_required


@staff_required
def index(request: HttpRequest) -> HttpResponse:
    return render(request, "help/index.html", {"chapters": CHAPTERS})


@staff_required
def chapter(request: HttpRequest, slug: str) -> HttpResponse:
    current = BY_SLUG.get(slug)
    if current is None:
        raise Http404
    position = CHAPTERS.index(current)
    context = {
        "chapter": current,
        "chapters": CHAPTERS,
        "previous": CHAPTERS[position - 1] if position > 0 else None,
        "next": CHAPTERS[position + 1] if position + 1 < len(CHAPTERS) else None,
    }
    return render(request, current.template, context)


def participants(request: HttpRequest) -> HttpResponse:
    """How applying, signing in and withdrawing work — for everyone, no sign-in needed."""
    return render(request, "help/participants.html")
