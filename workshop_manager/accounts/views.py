import logging
import smtplib

from allauth.account.views import RequestLoginCodeView as BaseRequestLoginCodeView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from workshop_manager.accounts.services import login_with_link, user_from_login_token
from workshop_manager.accounts.sessions import REMEMBER_SESSION_KEY

logger = logging.getLogger(__name__)

SEND_FAILED = (
    "Nie udało się teraz wysłać kodu — serwer poczty nie odpowiada. Spróbuj ponownie za kilka "
    "minut. Jeśli problem się powtarza, napisz do organizatora."
)


class RequestLoginCodeView(BaseRequestLoginCodeView):
    """allauth's "send me a code" page, keeping the visitor's "remember me" choice.

    The choice waits in the session until the code is confirmed; `sessions.apply_remember`
    turns it into the session's lifetime at sign-in.
    """

    def form_valid(self, form) -> HttpResponse:
        self.request.session[REMEMBER_SESSION_KEY] = bool(form.cleaned_data.get("remember"))
        try:
            return super().form_valid(form)
        except (OSError, smtplib.SMTPException):
            # The code is sent at once, not queued: a mail server that is down must read as
            # "try again later" on the page, not as a server error.
            logger.exception("Sending a sign-in code failed")
            form.add_error(None, SEND_FAILED)
            return self.form_invalid(form)


request_login_code = RequestLoginCodeView.as_view()


def login_link(request: HttpRequest, token: str) -> HttpResponse:
    """The one-click link from the code e-mail (accounts.services).

    Opening it only shows a button: signing in happens on POST, so a mail program that checks
    links in advance cannot use the link up before the person does.
    """
    user = user_from_login_token(token)
    if request.method == "POST" and user is not None:
        login_with_link(request, user, remember=request.POST.get("remember") == "on")
        return redirect("/panel/" if user.is_staff else reverse("public:my_workshops"))
    return render(request, "account/login_link.html", {"valid": user is not None})
