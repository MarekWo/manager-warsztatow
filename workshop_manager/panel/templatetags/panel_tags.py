"""Helpers for the panel's templates."""

from django import template

register = template.Library()

#: url_name prefix → menu section. The first match wins; everything else is "workshops".
SECTIONS = [
    ("dashboard", "dashboard"),
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
