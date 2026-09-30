"""Counters per level against the limit — the dashboard's main question (PRD §7.1).

One grouped query for any number of workshops; the templates only read the results.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from django.db.models import Count

from workshop_manager.applications.models import Application, Status


@dataclass
class LevelSummary:
    level: Any
    counts: dict[str, int] = field(default_factory=dict)

    def _get(self, status: str) -> int:
        return self.counts.get(status, 0)

    @property
    def new(self) -> int:
        return self._get(Status.NEW)

    @property
    def accepted(self) -> int:
        return self._get(Status.ACCEPTED)

    @property
    def waitlisted(self) -> int:
        return self._get(Status.WAITLISTED)

    @property
    def rejected(self) -> int:
        return self._get(Status.REJECTED)

    @property
    def left(self) -> int:
        """Withdrawn by the participant or cancelled by the organiser."""
        return self._get(Status.WITHDRAWN) + self._get(Status.CANCELLED)

    @property
    def capacity(self) -> int | None:
        return self.level.capacity

    @property
    def over_capacity(self) -> bool:
        return self.capacity is not None and self.accepted > self.capacity

    @property
    def free(self) -> int | None:
        return None if self.capacity is None else self.capacity - self.accepted

    @property
    def place_for_waitlisted(self) -> bool:
        """A place is free and someone waits for it — worth a look."""
        free = self.free
        return free is not None and free > 0 and self.waitlisted > 0


def level_summaries(workshops: list[Any]) -> dict[int, list[LevelSummary]]:
    """{workshop pk: [LevelSummary, …]} in the levels' order; levels must be prefetched."""
    rows = (
        Application.objects.filter(workshop__in=[w.pk for w in workshops])
        .values("level_id", "status")
        .annotate(n=Count("pk"))
    )
    counts: dict[int, dict[str, int]] = defaultdict(dict)
    for row in rows:
        counts[row["level_id"]][row["status"]] = row["n"]
    return {
        workshop.pk: [
            LevelSummary(level, counts.get(level.pk, {})) for level in workshop.levels.all()
        ]
        for workshop in workshops
    }
