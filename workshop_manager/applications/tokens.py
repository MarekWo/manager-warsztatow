"""The withdrawal link in e-mails: a guest without an account can withdraw too (PRD §6.5).

The token is the application's number, signed. It does not expire — it stops working once the
application is no longer active or the workshop is over, which `decisions.can_withdraw` checks.
"""

from django.core import signing
from django.urls import reverse

WITHDRAW_SALT = "applications.withdraw"


def withdraw_token(application_pk: int) -> str:
    return signing.dumps(application_pk, salt=WITHDRAW_SALT)


def withdraw_path(application_pk: int) -> str:
    return reverse("public:withdraw", args=[withdraw_token(application_pk)])


def application_pk_from_token(token: str) -> int | None:
    try:
        value = signing.loads(token, salt=WITHDRAW_SALT)
    except signing.BadSignature:
        return None
    return value if isinstance(value, int) else None
