"""The participant's own pages (PRD §6.5, §8): "Moje warsztaty", their data, withdrawing,
a copy of their data and deleting the account.

Everything here is reached by signing in, except the withdrawal and unsubscribe links from
e-mails, which work for guests without an account (the signed token is the proof).
"""

import json
from typing import Any

from django import forms
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from workshop_manager.applications import decisions, gdpr
from workshop_manager.applications.models import Application, ConsentChannel, Participant
from workshop_manager.applications.tokens import (
    application_pk_from_token,
    participant_pk_from_token,
)
from workshop_manager.core.forms import BootstrapFormMixin
from workshop_manager.core.models import SiteSettings

signed_in = login_required(login_url="account_request_login_code")


def _own_applications(user: Any) -> Any:
    return (
        Application.objects.filter(
            Q(participant__user=user) | Q(participant__email=user.email.lower())
        )
        .select_related("workshop", "level", "workshop__location")
        .prefetch_related("workshop__sessions")
    )


class WithdrawForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(
        label="Powód (nieobowiązkowo)",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Organizator zobaczy go razem z rezygnacją.",
    )


class MyDataForm(BootstrapFormMixin, forms.Form):
    first_name = forms.CharField(label="Imię", max_length=100)
    last_name = forms.CharField(label="Nazwisko", max_length=100)
    phone = forms.CharField(label="Telefon", max_length=32, required=False)
    marketing = forms.BooleanField(required=False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["marketing"].label = SiteSettings.load().marketing_text


@signed_in
def my_workshops(request: HttpRequest) -> HttpResponse:
    applications = list(_own_applications(request.user).order_by("-submitted_at"))
    today = timezone.localdate()
    current: list[Application] = []
    past: list[Application] = []
    for application in applications:
        last = application.workshop.last_session_date()
        (past if last is not None and last < today else current).append(application)
    return render(request, "public/my_workshops.html", {"current": current, "past": past})


@signed_in
def my_application(request: HttpRequest, pk: int) -> HttpResponse:
    application = get_object_or_404(
        _own_applications(request.user).prefetch_related("answers"), pk=pk
    )
    form = WithdrawForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            decisions.withdraw_by_participant(
                application, reason=form.cleaned_data["reason"], user=request.user
            )
        except decisions.TransitionError as error:
            messages.error(request, str(error))
        else:
            messages.success(
                request, "Zapisaliśmy Twoją rezygnację. Potwierdzenie wysłaliśmy e-mailem."
            )
        return redirect("public:my_application", pk=pk)
    context = {
        "application": application,
        "form": form,
        "can_withdraw": decisions.can_withdraw(application),
    }
    return render(request, "public/my_application.html", context)


@signed_in
def my_data(request: HttpRequest) -> HttpResponse:
    user: Any = request.user
    participant = gdpr.participant_for_user(user)
    initial = {
        "first_name": user.first_name or (participant.first_name if participant else ""),
        "last_name": user.last_name or (participant.last_name if participant else ""),
        "phone": user.phone or (participant.phone if participant else ""),
        "marketing": bool(participant and participant.marketing_consent),
    }
    form = MyDataForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            user.first_name, user.last_name, user.phone = (
                data["first_name"],
                data["last_name"],
                data["phone"],
            )
            user.save(update_fields=["first_name", "last_name", "phone"])
            if participant is not None:
                participant.first_name = data["first_name"]
                participant.last_name = data["last_name"]
                participant.phone = data["phone"]
                participant.save()
                gdpr.set_marketing_consent(
                    participant, data["marketing"], channel=ConsentChannel.ACCOUNT
                )
        messages.success(request, "Zapisano Twoje dane.")
        return redirect("public:my_data")
    return render(
        request, "public/my_data.html", {"form": form, "has_participant": bool(participant)}
    )


def withdraw(request: HttpRequest, token: str) -> HttpResponse:
    """The withdrawal link from e-mails — for guests too."""
    pk = application_pk_from_token(token)
    if pk is None:
        raise Http404
    application = get_object_or_404(Application.objects.select_related("workshop", "level"), pk=pk)
    form = WithdrawForm(request.POST or None)
    done = False
    if request.method == "POST" and form.is_valid() and decisions.can_withdraw(application):
        user = request.user if request.user.is_authenticated else None
        decisions.withdraw_by_participant(
            application, reason=form.cleaned_data["reason"], user=user
        )
        done = True
    context = {
        "application": application,
        "form": form,
        "can_withdraw": decisions.can_withdraw(application),
        "done": done,
    }
    return render(request, "public/withdraw.html", context)


@signed_in
def my_data_download(request: HttpRequest) -> HttpResponse:
    """A copy of everything stored about the signed-in person, as a JSON file (PRD §8)."""
    participant = gdpr.participant_for_user(request.user)
    if participant is None:
        raise Http404
    data = gdpr.export_data(participant)
    response = HttpResponse(
        json.dumps(data, ensure_ascii=False, indent=2), content_type="application/json"
    )
    stamp = timezone.localdate().isoformat()
    response["Content-Disposition"] = f'attachment; filename="moje-dane-{stamp}.json"'
    return response


class DeleteAccountForm(BootstrapFormMixin, forms.Form):
    confirm = forms.BooleanField(
        label="Rozumiem, że moje dane zostaną usunięte na zawsze i nie da się tego cofnąć."
    )


@signed_in
def delete_account(request: HttpRequest) -> HttpResponse:
    """ "Usuń moje konto" (PRD §6.5, §8): anonymise the person and sign them out."""
    user: Any = request.user
    if user.is_staff:
        messages.error(request, "Konta administratora nie usuwa się tutaj.")
        return redirect("public:my_data")
    participant = gdpr.participant_for_user(user)
    blocking = gdpr.blocking_applications(participant) if participant else []
    form = DeleteAccountForm(request.POST or None)
    if request.method == "POST" and form.is_valid() and not blocking:
        if participant is not None:
            gdpr.anonymise(participant, user=user, self_service=True)
        else:
            user.delete()  # an account that never applied: nothing else to remove
        logout(request)
        return redirect("public:account_deleted")
    context = {"form": form, "blocking": blocking, "participant": participant}
    return render(request, "public/delete_account.html", context)


def account_deleted(request: HttpRequest) -> HttpResponse:
    return render(request, "public/account_deleted.html")


@csrf_exempt  # the signed token is the proof; mail programs post here for one-click unsubscribe
def unsubscribe(request: HttpRequest, token: str) -> HttpResponse:
    """The link in e-mails that withdraws the consent to news about workshops (PRD §8).

    Opening the link only shows a button — mail scanners open links on their own — and the
    button (or a mail program's one-click request) withdraws the consent.
    """
    pk = participant_pk_from_token(token)
    if pk is None:
        raise Http404
    participant = get_object_or_404(Participant, pk=pk)
    done = False
    if request.method == "POST":
        gdpr.set_marketing_consent(participant, False, channel=ConsentChannel.LINK)
        done = True
    context = {"participant": participant, "done": done}
    return render(request, "public/unsubscribe.html", context)
