"""Create the data every installation needs (idempotent; run by the entrypoint on every start).

Later stages add workshop types, the default location, the default form template and email
templates here. Existing rows are never overwritten, so an administrator's edits survive.
"""

from typing import Any

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create default data that does not exist yet."

    def handle(self, *args: Any, **options: Any) -> None:
        self.stdout.write("Default data in place.")
