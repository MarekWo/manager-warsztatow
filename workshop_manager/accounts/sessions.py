"""How long a sign-in lasts (PRD §6.4): the visitor's "remember me" choice at the code request.

Remembered, a participant stays signed in for `SESSION_REMEMBER_DAYS` (rolling), an
administrator for `STAFF_SESSION_REMEMBER_DAYS`; otherwise the session ends with the browser.
"""

from typing import Any

from allauth.account.signals import user_logged_in
from django.conf import settings
from django.dispatch import receiver
from django.http import HttpRequest

REMEMBER_SESSION_KEY = "wm_remember"


@receiver(user_logged_in)
def apply_remember(sender: Any, request: HttpRequest, user: Any, **kwargs: Any) -> None:
    remember = request.session.pop(REMEMBER_SESSION_KEY, True)
    if not remember:
        request.session.set_expiry(0)
    elif user.is_staff:
        request.session.set_expiry(settings.STAFF_SESSION_REMEMBER_DAYS * 24 * 60 * 60)
    else:
        request.session.set_expiry(settings.SESSION_COOKIE_AGE)
