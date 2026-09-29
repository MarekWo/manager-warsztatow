"""Presentation helpers for workshops: dates in Polish, state and registration labels."""

from datetime import date

from django import template
from django.template.defaultfilters import date as date_filter
from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe

from workshop_manager.workshops.models import Workshop

register = template.Library()

STATE_BADGES = {
    "draft": ("szkic", "text-bg-secondary"),
    "scheduled": ("zaplanowany", "text-bg-info"),
    "published": ("opublikowany", "text-bg-success"),
    "finished": ("zakończony", "text-bg-light border"),
    "archived": ("w archiwum", "text-bg-dark"),
}

REGISTRATION_LABELS = {
    "not_published": ("", ""),
    "closed": ("Zapisy zamknięte", "text-bg-secondary"),
    "not_yet": ("Zapisy wkrótce", "text-bg-info"),
    "open": ("Zapisy otwarte", "text-bg-success"),
    "over": ("Zapisy zakończone", "text-bg-secondary"),
}


@register.simple_tag
def state_badge(workshop: Workshop) -> SafeString:
    label, css = STATE_BADGES[workshop.state()]
    badge = format_html('<span class="badge {}">{}</span>', css, label)
    if workshop.is_cancelled:
        badge += mark_safe(' <span class="badge text-bg-danger">odwołany</span>')
    return badge


@register.simple_tag
def registration_badge(workshop: Workshop) -> SafeString:
    label, css = REGISTRATION_LABELS[workshop.registration_status()]
    if workshop.is_cancelled:
        return mark_safe('<span class="badge text-bg-danger">Warsztat odwołany</span>')
    if not label:
        return mark_safe("")
    return format_html('<span class="badge {}">{}</span>', css, label)


@register.filter
def date_range(workshop: Workshop) -> str:
    """ "28.11–14.12.2026 · 5 spotkań" — the short form for cards and lists."""
    sessions = workshop.ordered_sessions()
    if not sessions:
        return "terminy do ustalenia"
    first, last = sessions[0].date, sessions[-1].date
    if first == last:
        span = f"{first:%d.%m.%Y}"
    elif first.year == last.year:
        span = f"{first:%d.%m}–{last:%d.%m.%Y}"
    else:
        span = f"{first:%d.%m.%Y}–{last:%d.%m.%Y}"
    count = len(sessions)
    return f"{span} · {count} {meetings(count)}"


def meetings(count: int) -> str:
    """Polish plural of "spotkanie"."""
    if count == 1:
        return "spotkanie"
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return "spotkania"
    return "spotkań"


@register.filter
def long_date(value: date) -> str:
    """Like "sobota, 28 listopada 2026": Django capitalises Polish day names, we do not."""
    text = date_filter(value, "l, j E Y")
    return text[:1].lower() + text[1:]
