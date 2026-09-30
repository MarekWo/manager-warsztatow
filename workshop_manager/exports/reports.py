"""What the organiser prints or downloads for a workshop (PRD §7.6).

The data is gathered here once; the panel renders it as a web page to print, as a PDF
(`exports.pdf`) or as a spreadsheet (`exports.spreadsheets`).
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from workshop_manager.applications.models import ACTIVE_STATUSES, Application, Status
from workshop_manager.forms_builder.models import Question, QuestionKind


def applications(workshop: Any, statuses: list[str] | None = None) -> Any:
    qs = workshop.applications.select_related("level").prefetch_related("answers")
    if statuses:
        qs = qs.filter(status__in=statuses)
    return qs.order_by("level__order", "level__pk", "last_name", "first_name", "pk")


def by_level(workshop: Any, statuses: list[str]) -> list[tuple[Any, list[Application]]]:
    """[(level, applications)] in the levels' order, levels without anyone left out."""
    grouped: dict[int, list[Application]] = {}
    for application in applications(workshop, statuses):
        grouped.setdefault(application.level_id, []).append(application)
    return [(level, grouped[level.pk]) for level in workshop.levels.all() if level.pk in grouped]


def answer_for(application: Application, question: Question) -> str:
    """The answer to `question`, matched by the question or, if it was deleted, by its wording."""
    for answer in application.answers.all():
        if answer.question_id == question.pk or (
            answer.question_id is None and answer.label == question.label
        ):
            return answer.value
    return ""


# --- Materials ----------------------------------------------------------------------------------


@dataclass
class MaterialLine:
    choice: str
    accepted: int = 0
    waiting: int = 0  # new or on the waiting list — may still need it
    names: list[str] = field(default_factory=list)


@dataclass
class MaterialSummary:
    question: Question
    lines: list[MaterialLine]
    no_answer: int = 0


def materials(workshop: Any) -> list[MaterialSummary]:
    """Per material question: how many chose each option, accepted people counted apart.

    E.g. "Deska 26×26: Tak, zamawiam — 9 przyjętych (+2 oczekujących), Mam własną — 3".
    """
    questions = list(
        workshop.questions.filter(kind=QuestionKind.MATERIAL)
        .select_related("level")
        .order_by("order")
    )
    people = list(applications(workshop, list(ACTIVE_STATUSES)))
    summaries = []
    for question in questions:
        lines = {choice: MaterialLine(choice) for choice in question.choice_list()}
        no_answer = 0
        for application in people:
            if question.level_id is not None and application.level_id != question.level_id:
                continue
            value = answer_for(application, question)
            if not value:
                no_answer += application.status == Status.ACCEPTED
                continue
            line = lines.setdefault(value, MaterialLine(value))
            if application.status == Status.ACCEPTED:
                line.accepted += 1
                line.names.append(application.full_name)
            else:
                line.waiting += 1
        summaries.append(MaterialSummary(question, list(lines.values()), no_answer))
    return summaries


def material_choices(workshop: Any) -> list[tuple[str, str]]:
    """Options for the application list's filter: ("<question id>|<choice>", label)."""
    options = []
    for question in workshop.questions.filter(kind=QuestionKind.MATERIAL).order_by("order"):
        for choice in question.choice_list():
            options.append((f"{question.pk}|{choice}", f"{question.label}: {choice}"))
    return options


def status_counts(workshop: Any) -> Counter[str]:
    return Counter(workshop.applications.values_list("status", flat=True))
