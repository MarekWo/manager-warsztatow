from typing import Any

from allauth.account.adapter import DefaultAccountAdapter
from django.http import HttpRequest


class AccountAdapter(DefaultAccountAdapter):
    """Project-specific allauth behaviour (ADR-0001).

    Sign-up happens implicitly — from the application form or at the first sign-in with a code —
    so allauth's own sign-up page stays closed. Login and verification codes are six digits
    (`ALLAUTH_USER_CODE_FORMAT`).
    """

    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return False

    def format_email_subject(self, subject: str) -> str:
        return f"Manager Warsztatów — {subject}"

    def get_login_redirect_url(self, request: HttpRequest) -> str:
        user: Any = request.user
        if getattr(user, "is_staff", False):
            return "/panel/"
        return super().get_login_redirect_url(request)
