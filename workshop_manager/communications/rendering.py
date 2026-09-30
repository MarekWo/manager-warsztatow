"""Turning a template and data into an e-mail: placeholders, the HTML layout, the text part.

Templates are plain text (as workshop descriptions are, ADR-0005). Placeholders are filled in
first; the HTML part is then derived from the finished text — paragraphs, line breaks and links,
everything escaped — and wrapped in a simple layout with the logo. A placeholder the template
does not know stays as typed, so a typo is visible in the preview instead of vanishing.
"""

import re
from dataclasses import dataclass
from typing import Any

from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import urlize
from django.utils.safestring import mark_safe

from workshop_manager.applications.tokens import withdraw_path
from workshop_manager.core.models import SiteSettings, absolute_url
from workshop_manager.workshops.templatetags.workshop_tags import long_date

PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


@dataclass
class RenderedEmail:
    subject: str
    text: str
    html: str


def fill(template: str, context: dict[str, str]) -> str:
    return PLACEHOLDER.sub(lambda m: context.get(m[1], m[0]), template)


def unknown_placeholders(template: str, allowed: dict[str, str] | set[str]) -> list[str]:
    return sorted({name for name in PLACEHOLDER.findall(template) if name not in allowed})


def text_to_html(text: str) -> str:
    paragraphs = [p.strip("\n") for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    return "\n".join(
        "<p>" + urlize(paragraph, autoescape=True).replace("\n", "<br>\n") + "</p>"
        for paragraph in paragraphs
    )


def render(subject: str, body: str, context: dict[str, str], site: SiteSettings) -> RenderedEmail:
    # A subject is one line: a multi-line value (say, the sessions) must not break the header.
    subject_text = " ".join(fill(subject, context).split())
    text = fill(body, context).strip() + "\n"
    html = render_to_string(
        "emails/layout.html",
        {"subject": subject_text, "content": mark_safe(text_to_html(text)), "site": site},  # noqa: S308 — escaped by text_to_html
    )
    return RenderedEmail(subject=subject_text, text=text, html=html)


# --- Context builders ------------------------------------------------------------------------


def site_context(site: SiteSettings) -> dict[str, str]:
    account = "\n".join(
        part for part in (site.bank_account_holder, site.bank_account_number) if part
    )
    return {
        "organizacja": site.org_short_name,
        "kontakt": site.contact_email,
        "konto_bankowe": account,
    }


def sessions_text(workshop: Any) -> str:
    lines = [
        f"{long_date(s.date)}, {s.start_time:%H:%M}–{s.end_time:%H:%M}"
        + (f" ({s.note})" if s.note else "")
        for s in workshop.ordered_sessions()
    ]
    return "\n".join(lines) or "terminy zostaną podane później"


def application_summary(application: Any) -> str:
    lines = [
        f"Imię i nazwisko: {application.full_name}",
        f"E-mail: {application.email}",
    ]
    if application.phone:
        lines.append(f"Telefon: {application.phone}")
    lines.append(f"Poziom: {application.level.name}")
    for answer in application.answers.all():
        label = answer.label.rstrip()
        separator = " " if label.endswith(("?", ":", ".")) else ": "
        lines.append(f"{label}{separator}{answer.value or '—'}")
    if application.remarks:
        lines.append(f"Uwagi: {application.remarks}")
    return "\n".join(lines)


def application_context(application: Any) -> dict[str, str]:
    workshop = application.workshop
    location = workshop.location
    return {
        "imie": application.first_name,
        "nazwisko": application.last_name,
        "imie_nazwisko": application.full_name,
        "email": application.email,
        "telefon": application.phone,
        "warsztat": workshop.title,
        "terminy": sessions_text(workshop),
        "miejsce": f"{location.name}, {location.address}" if location else "",
        "poziom": application.level.name,
        "cena": application.level.price_display,
        "odpowiedzi": application_summary(application),
        "uwagi": application.remarks,
        "data_zgloszenia": f"{timezone.localtime(application.submitted_at):%d.%m.%Y, %H:%M}",
        "link_do_warsztatu": absolute_url(workshop.get_absolute_url()),
        "link_do_zgloszenia": absolute_url(application.get_panel_url()),
        "miejsce_na_liscie": str(application.waitlist_position or ""),
        "link_rezygnacji": absolute_url(withdraw_path(application.pk)),
        "link_do_konta": absolute_url(reverse("public:my_workshops")),
    }
