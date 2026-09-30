"""Create or update the worker's periodic jobs.

Idempotent — `core.tasks.schedule()` matches jobs by name — so the container entrypoint runs it
on every start, after the migrations.
"""

from typing import Any

from django.core.management.base import BaseCommand

from workshop_manager.core.tasks import schedule

#: (name, dotted path, cron). Cron times are in `TIME_ZONE`; nightly jobs pick a quiet hour and
#: are spread out so they never run at once. The heartbeat is what `/healthz` listens for.
SCHEDULES: list[tuple[str, str, str]] = [
    ("heartbeat", "workshop_manager.core.tasks.heartbeat", "* * * * *"),
    ("send-due-emails", "workshop_manager.communications.services.send_due_emails", "* * * * *"),
    (
        "admin-daily-digest",
        "workshop_manager.communications.notifications.send_admin_digest",
        "0 19 * * *",
    ),
    ("clear-sessions", "workshop_manager.core.tasks.clear_sessions", "10 3 * * *"),
    ("prune-task-results", "workshop_manager.core.tasks.prune_task_results", "20 3 * * *"),
]


class Command(BaseCommand):
    help = "Create or update the periodic background jobs."

    def handle(self, *args: Any, **options: Any) -> None:
        for name, func, cron in SCHEDULES:
            schedule(func, name=name, cron=cron)
        self.stdout.write(f"{len(SCHEDULES)} periodic job(s) in place.")
