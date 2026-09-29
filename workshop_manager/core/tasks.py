"""The only place in the codebase that talks to the task queue.

Application code calls `enqueue()` for one-off background work and `schedule()` for periodic
jobs. The backend (django-q2 with the ORM broker) can be replaced behind these functions without
touching call sites. With `settings.TASK_SYNC = True` tasks run inline, which is what the test
suite uses.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone
from django_q.models import Failure, Schedule, Success
from django_q.tasks import async_task

TaskFunc = Callable[..., Any] | str

# django-q2 consumes these keyword arguments as queue options even when `q_options` is given,
# so a task parameter with one of these names would silently never reach the task.
RESERVED_KWARGS = frozenset(
    {
        "hook", "group", "save", "sync", "cached", "ack_failure", "iter_count",
        "iter_cached", "chain", "broker", "cluster", "timeout", "task_name", "q_options",
    }
)  # fmt: skip


def enqueue(func: TaskFunc, *args: Any, **kwargs: Any) -> str:
    """Run `func(*args, **kwargs)` in the worker and return the task id.

    `func` may be a callable or a dotted path to a module-level function. Keyword arguments
    whose names are in `RESERVED_KWARGS` are rejected; rename the task parameter instead.
    """
    if clashing := RESERVED_KWARGS.intersection(kwargs):
        raise ValueError(f"Task keyword arguments clash with queue options: {sorted(clashing)}")
    options = {"sync": settings.TASK_SYNC}
    return async_task(func, *args, q_options=options, **kwargs)


def enqueue_on_commit(func: TaskFunc, *args: Any, **kwargs: Any) -> None:
    """Enqueue after the current transaction commits, so the worker sees the committed rows."""
    transaction.on_commit(lambda: enqueue(func, *args, **kwargs))


def schedule(
    func: str,
    *args: Any,
    name: str,
    minutes: int | None = None,
    cron: str | None = None,
    repeats: int = -1,
    **kwargs: Any,
) -> Schedule:
    """Create or update the periodic job called `name` (idempotent).

    Exactly one of `minutes` (fixed interval) or `cron` (5-field cron expression) is required.
    `func` must be a dotted path because schedules are stored in the database.
    """
    if (minutes is None) == (cron is None):
        raise ValueError("Pass exactly one of `minutes` or `cron`.")

    defaults: dict[str, Any] = {
        "func": func,
        "args": repr(args) if args else None,
        "kwargs": repr(kwargs) if kwargs else None,
        "schedule_type": Schedule.MINUTES if minutes is not None else Schedule.CRON,
        "minutes": minutes,
        "cron": cron,
        "repeats": repeats,
    }
    job, _ = Schedule.objects.update_or_create(name=name, defaults=defaults)
    return job


# --- Housekeeping jobs (registered in `ensure_schedules.SCHEDULES`) ------------------------------

#: The heartbeat's dotted path — what `worker_heartbeat()` looks for among the queue's records.
HEARTBEAT_FUNC = "workshop_manager.core.tasks.heartbeat"

#: How long `/healthz` waits for a heartbeat before it calls the worker stale.
WORKER_STALE_AFTER = timedelta(minutes=5)

#: Failed tasks are kept this long; the queue prunes successes itself (`save_limit`), never these.
FAILURE_RETENTION_DAYS = 30


def heartbeat() -> str:
    """Do nothing, successfully: the queue's record of this run is the proof the worker lives."""
    return timezone.now().isoformat(timespec="seconds")


def clear_sessions() -> None:
    """Database-backed sessions are never garbage-collected on their own (nightly)."""
    call_command("clearsessions")


def prune_task_results(days: int = FAILURE_RETENTION_DAYS) -> int:
    """Delete failed-task records older than `days`; returns how many. Nightly."""
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _by_model = Failure.objects.filter(stopped__lt=cutoff).delete()
    return deleted


def worker_heartbeat() -> datetime | None:
    """When the worker last completed a heartbeat, or None if it never has."""
    return (
        Success.objects.filter(func=HEARTBEAT_FUNC)
        .order_by("-stopped")
        .values_list("stopped", flat=True)
        .first()
    )


def worker_status(now: datetime | None = None) -> tuple[str, int | None]:
    """`("ok" | "stale" | "unknown", age in seconds or None)` — what `/healthz` reports."""
    beat = worker_heartbeat()
    if beat is None:
        return "unknown", None
    age = max(0, int(((now or timezone.now()) - beat).total_seconds()))
    return ("ok" if age <= WORKER_STALE_AFTER.total_seconds() else "stale"), age
