"""Participant accounts (PRD §6.4, §6.5): who may sign in, and the one-click sign-in link.

An account is a verified e-mail address. Anyone who has ever applied may sign in: their account
is created when they ask for a code, and signing in with it proves they own the address — so
every application ever sent from it becomes theirs. A person who never applied gets no account
(and the page says the same either way, so nobody learns which addresses are known).

The one-click link in the code e-mail cannot reuse allauth's code, which is bound to the browser
session that asked for it (ADR-0001): a link opened in a mail app is another session. It is our
own signed token instead, valid for the code's lifetime and only until the account's next
sign-in (it carries `last_login`), so it works once.
"""

from typing import Any

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import login
from django.core import signing
from django.http import HttpRequest
from django.urls import reverse

from workshop_manager.accounts.models import User
from workshop_manager.accounts.sessions import set_session_expiry

LOGIN_LINK_SALT = "accounts.login-link"


def ensure_account(email: str) -> User | None:
    """The account for `email`, created from the applications if the person has applied."""
    from workshop_manager.applications.models import Participant

    email = email.strip().lower()
    user = User.objects.filter(email__iexact=email).first()
    if user is not None:
        return user
    participant = Participant.objects.filter(email=email).first()
    if participant is None:
        return None
    user = User.objects.create_user(
        email=email,
        first_name=participant.first_name,
        last_name=participant.last_name,
        phone=participant.phone,
    )
    EmailAddress.objects.create(user=user, email=email, verified=False, primary=True)
    return user


def link_participant(user: Any) -> None:
    """After a sign-in: the applications sent from this address belong to the account."""
    from workshop_manager.applications.models import Participant

    Participant.objects.filter(email=user.email.lower(), user__isnull=True).update(user=user)


# --- One-click sign-in link -------------------------------------------------------------------


def _last_login_stamp(user: Any) -> str:
    return user.last_login.isoformat() if user.last_login else ""


def login_link_token(user: Any) -> str:
    return signing.dumps({"u": user.pk, "l": _last_login_stamp(user)}, salt=LOGIN_LINK_SALT)


def login_link_path(user: Any) -> str:
    return reverse("account_login_link", args=[login_link_token(user)])


def user_from_login_token(token: str) -> User | None:
    """The account a still valid, unused link belongs to; None otherwise."""
    try:
        data = signing.loads(
            token, salt=LOGIN_LINK_SALT, max_age=settings.ACCOUNT_LOGIN_BY_CODE_TIMEOUT
        )
    except signing.BadSignature:
        return None
    user = User.objects.filter(pk=data.get("u"), is_active=True).first()
    if user is None or _last_login_stamp(user) != data.get("l"):
        return None
    return user


def login_with_link(request: HttpRequest, user: User, *, remember: bool) -> None:
    """Sign in as allauth would after a correct code: the address counts as verified."""
    EmailAddress.objects.filter(user=user, email__iexact=user.email).update(verified=True)
    if not EmailAddress.objects.filter(user=user).exists():
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    login(request, user, backend="allauth.account.auth_backends.AuthenticationBackend")
    set_session_expiry(request, user, remember=remember)
    link_participant(user)
