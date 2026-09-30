"""`{% help_link %}` — the "?" next to harder fields — and `{% help_shot %}` for screenshots."""

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html

from workshop_manager.help.chapters import BY_SLUG

register = template.Library()


@register.simple_tag
def help_link(slug: str, section: str = "", label: str = "") -> str:
    """A small "?" that opens the help chapter (at `section`) in a new tab.

    A new tab, so a half-filled form is not lost. The accessible name says where it leads.
    """
    chapter = BY_SLUG[slug]
    url = reverse("help:chapter", args=[slug]) + (f"#{section}" if section else "")
    name = label or chapter.title
    return format_html(
        '<a class="help-link" href="{}" target="_blank" rel="noopener" title="Pomoc: {}">'
        '<i class="bi bi-question-circle" aria-hidden="true"></i>'
        '<span class="visually-hidden">Pomoc: {} (otwiera się w nowej karcie)</span></a>',
        url,
        name,
        name,
    )


@register.simple_tag
def help_shot(name: str, alt: str, caption: str = "") -> str:
    """A screenshot from `static/help/<name>.png`, or nothing when it has not been taken yet."""
    path = f"help/{name}.png"
    if not finders.find(path):
        return ""
    return format_html(
        '<figure class="help-shot"><a href="{0}" target="_blank" rel="noopener">'
        '<img src="{0}" alt="{1}" loading="lazy"></a>{2}</figure>',
        static(path),
        alt,
        format_html("<figcaption>{}</figcaption>", caption) if caption else "",
    )
