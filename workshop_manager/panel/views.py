from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


@staff_member_required(login_url="account_request_login_code")
def dashboard(request: HttpRequest) -> HttpResponse:
    """The administrator's start page (PRD §7.1); filled in from Stage 1 on."""
    return render(request, "panel/dashboard.html")
