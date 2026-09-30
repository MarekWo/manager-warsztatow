"""Helpers for the panel's templates."""

from django import template

register = template.Library()

#: url_name prefix → menu section. The first match wins; everything else is "workshops".
SECTIONS = [
    ("dashboard", "dashboard"),
    ("application", "applications"),
    ("participant", "participants"),
    ("audit", "audit"),
    ("location", "locations"),
    ("email_template", "settings"),
    ("email", "emails"),
    ("settings", "settings"),
    ("dictionary", "settings"),
]


@register.filter
def panel_section(url_name: str | None) -> str:
    for prefix, section in SECTIONS:
        if (url_name or "").startswith(prefix):
            return section
    return "workshops"


@register.simple_tag
def unseen_applications() -> int:
    """How many applications nobody has opened yet — the badge next to "Zgłoszenia"."""
    from workshop_manager.applications.models import Application

    return Application.objects.filter(is_seen=False).count()
