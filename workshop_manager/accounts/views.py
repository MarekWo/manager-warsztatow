from allauth.account.views import RequestLoginCodeView as BaseRequestLoginCodeView
from django.http import HttpResponse

from workshop_manager.accounts.sessions import REMEMBER_SESSION_KEY


class RequestLoginCodeView(BaseRequestLoginCodeView):
    """allauth's "send me a code" page, keeping the visitor's "remember me" choice.

    The choice waits in the session until the code is confirmed; `sessions.apply_remember`
    turns it into the session's lifetime at sign-in.
    """

    def form_valid(self, form) -> HttpResponse:
        self.request.session[REMEMBER_SESSION_KEY] = bool(form.cleaned_data.get("remember"))
        return super().form_valid(form)


request_login_code = RequestLoginCodeView.as_view()
