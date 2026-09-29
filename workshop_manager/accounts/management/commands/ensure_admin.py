"""Create the first administrator from `ADMIN_EMAIL` (idempotent; run by the entrypoint).

The account has no password: the administrator signs in with a code sent to that address, so
the address is marked as verified — it is the operator who vouches for it.
"""

from typing import Any

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.management.base import BaseCommand

from workshop_manager.accounts.models import User


class Command(BaseCommand):
    help = "Create the administrator named by ADMIN_EMAIL unless it exists."

    def handle(self, *args: Any, **options: Any) -> None:
        email = settings.ADMIN_EMAIL.strip().lower()
        if not email:
            self.stdout.write("ADMIN_EMAIL is empty; no administrator created.")
            return
        user, created = User.objects.get_or_create(
            email=email, defaults={"is_staff": True, "is_superuser": True}
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        EmailAddress.objects.update_or_create(
            user=user, email=email, defaults={"verified": True, "primary": True}
        )
        self.stdout.write(f"Administrator {email} {'created' if created else 'already exists'}.")
