"""Links in e-mails that work without signing in, each a signed number.

The withdrawal link (PRD §6.5): a guest without an account can withdraw too. The token is the
application's number; it does not expire — it stops working once the application is no longer
active or the workshop is over, which `decisions.can_withdraw` checks.

The unsubscribe link (PRD §8): the consent to news about workshops is withdrawn with one click.
The token is the participant's number and does not expire either.
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


UNSUBSCRIBE_SALT = "applications.unsubscribe"


def unsubscribe_path(participant_pk: int) -> str:
    return reverse(
        "public:unsubscribe", args=[signing.dumps(participant_pk, salt=UNSUBSCRIBE_SALT)]
    )


def participant_pk_from_token(token: str) -> int | None:
    try:
        value = signing.loads(token, salt=UNSUBSCRIBE_SALT)
    except signing.BadSignature:
        return None
    return value if isinstance(value, int) else None
