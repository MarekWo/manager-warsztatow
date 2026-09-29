from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def home(request: HttpRequest) -> HttpResponse:
    """The list of current workshops, or a notice that none are planned (PRD §6.1).

    Workshops arrive in Stage 1; until then the list is always empty.
    """
    return render(request, "public/home.html", {"workshops": []})
