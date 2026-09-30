from typing import Any

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core import context as allauth_context
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpRequest

from workshop_manager.core.models import SiteSettings, absolute_url


class AccountAdapter(DefaultAccountAdapter):
    """Project-specific allauth behaviour (ADR-0001).

    Sign-up happens implicitly — from the application form or at the first sign-in with a code —
    so allauth's own sign-up page stays closed. Login and verification codes are six digits
    (`ALLAUTH_USER_CODE_FORMAT`).
    """

    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return False

    def send_mail(self, template_prefix: str, email: str, context: dict[str, Any]) -> None:
        """Send sign-in codes through the same server as every other e-mail (Settings).

        Directly, not through the queue: a code is needed within seconds and must not be kept
        in the e-mail log.
        """
        from workshop_manager.communications import mailer

        request = allauth_context.request
        context = {
            "request": request,
            "email": email,
            "current_site": get_current_site(request),
        } | context
        if template_prefix == "account/email/login_code":
            context["login_url"] = self._login_url(email)
        context["site_settings"] = SiteSettings.load()
        message = self.render_mail(template_prefix, email, context)
        transport = mailer.transport()
        message.from_email = transport.from_email
        message.reply_to = [transport.reply_to] if transport.reply_to else []
        mailer.send_now(message, transport.connection)

    @staticmethod
    def _login_url(email: str) -> str:
        """The one-click link sent next to the code (accounts.services)."""
        from workshop_manager.accounts.models import User
        from workshop_manager.accounts.services import login_link_path

        user = User.objects.filter(email__iexact=email).first()
        return absolute_url(login_link_path(user)) if user else ""

    def format_email_subject(self, subject: str) -> str:
        return f"{subject} — {SiteSettings.load().org_short_name}"

    def get_login_redirect_url(self, request: HttpRequest) -> str:
        user: Any = request.user
        if getattr(user, "is_staff", False):
            return "/panel/"
        return super().get_login_redirect_url(request)
