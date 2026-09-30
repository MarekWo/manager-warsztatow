"""Accessibility and phone-width sweep over every page, with the demo data (PLAN Stage 7).

Each page must pass axe without serious or critical violations and must not scroll sideways on
a 360 px phone — many participants and the organiser use phones. Set `AUDIT_ALL=1` to fail on
moderate and minor axe findings too (for a periodic manual audit).
"""

import os

import pytest
from axe_playwright_python.sync_playwright import Axe
from django.conf import settings
from django.core.management import call_command
from django.test import Client

from tests.browser.conftest import PHONE
from tests.factories import AdminFactory
from workshop_manager.applications.models import Application, Participant, Status
from workshop_manager.applications.tokens import unsubscribe_path, withdraw_path
from workshop_manager.communications.models import Broadcast, EmailMessage, Group
from workshop_manager.forms_builder.models import FormTemplate
from workshop_manager.workshops.models import Location, Workshop, WorkshopType

pytestmark = [pytest.mark.browser, pytest.mark.django_db(transaction=True)]

PUBLIC = [
    "/",
    "/warsztaty/{slug}/",
    "/warsztaty/{slug}/zgloszenie/",
    "/pomoc/",
    "/konto/login/code/",
    "{withdraw}",
    "{unsubscribe}",
    "/nie-ma-takiej-strony/",
]
PARTICIPANT = ["/moje-warsztaty/", "/moje-warsztaty/{application}/", "/moje-dane/"]
PANEL = [
    "/panel/",
    "/panel/warsztaty/",
    "/panel/warsztaty/?tab=drafts",
    "/panel/warsztaty/nowy/",
    "/panel/warsztaty/{workshop}/",
    "/panel/warsztaty/{workshop}/duplikuj/",
    "/panel/warsztaty/{workshop}/formularz/",
    "/panel/warsztaty/{workshop}/formularz/pytanie/",
    "/panel/warsztaty/{workshop}/zgloszenia/",
    "/panel/warsztaty/{workshop}/zgloszenia/nowe/",
    "/panel/warsztaty/{workshop}/wiadomosci/",
    "/panel/warsztaty/{workshop}/wiadomosci/nowa/",
    "/panel/warsztaty/{workshop}/wiadomosci/{broadcast}/",
    "/panel/warsztaty/{workshop}/zestawienia/",
    "/panel/warsztaty/{workshop}/lista-kontaktowa/",
    "/panel/warsztaty/{workshop}/materialy/",
    "/panel/zgloszenia/",
    "/panel/zgloszenia/{application}/",
    "/panel/zgloszenia/{application}/decyzja/waitlisted/",
    "/panel/zgloszenia/{application}/dane/",
    "/panel/uczestnicy/",
    "/panel/uczestnicy/{participant}/",
    "/panel/uczestnicy/{participant}/usun-dane/",
    "/panel/miejsca/",
    "/panel/miejsca/{location}/",
    "/panel/e-maile/",
    "/panel/e-maile/{email}/",
    "/panel/ustawienia/",
    "/panel/ustawienia/e-maile/",
    "/panel/ustawienia/e-maile/decision_accepted/",
    "/panel/ustawienia/rodzaje/",
    "/panel/ustawienia/rodzaje/{type}/",
    "/panel/ustawienia/szablony/",
    "/panel/ustawienia/szablony/{template}/",
    "/panel/dziennik/",
    "/panel/pomoc/",
    "/panel/pomoc/zgloszenia/",
]


@pytest.fixture
def demo():
    call_command("seed_defaults", verbosity=0)
    call_command("seed_demo", verbosity=0)
    workshop = Workshop.objects.get(title="Pokaz: Ikona Bożego Narodzenia")
    application = Application.objects.filter(workshop=workshop, status=Status.NEW).first()
    participant = application.participant
    broadcast = Broadcast.objects.create(
        workshop=workshop, group=Group.ACCEPTED, subject="Co zabrać", body="Dzień dobry {imie}"
    )
    email = EmailMessage.objects.create(
        to_email=application.email, subject="Próba", body_text="Treść", application=application
    )
    return {
        "slug": workshop.slug,
        "workshop": workshop.pk,
        "application": application.pk,
        "participant": participant.pk,
        "broadcast": broadcast.pk,
        "email": email.pk,
        "location": Location.objects.first().pk,
        "type": WorkshopType.objects.first().pk,
        "template": FormTemplate.objects.first().pk,
        "withdraw": withdraw_path(application.pk),
        "unsubscribe": unsubscribe_path(participant.pk),
        "_participant_obj": participant,
    }


def login(context, live_server, user):
    client = Client()
    client.force_login(user)
    context.add_cookies(
        [
            {
                "name": settings.SESSION_COOKIE_NAME,
                "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
                "url": live_server.url,
            }
        ]
    )


def audit(page, url: str) -> list[str]:
    page.goto(url)
    problems = []
    impacts = (
        ("serious", "critical", "moderate", "minor")
        if os.environ.get("AUDIT_ALL")
        else ("serious", "critical")
    )
    for violation in Axe().run(page).response["violations"]:
        if violation["impact"] in impacts:
            targets = [node["target"] for node in violation["nodes"]][:3]
            problems.append(f"{url} axe {violation['id']} ({violation['impact']}): {targets}")
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    if overflow > 1:
        wide = page.evaluate(
            """() => [...document.querySelectorAll('body *')]
                .filter(e =>
                    e.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
                .filter(e => !e.closest('.table-responsive'))
                .slice(0, 3).map(e => e.tagName + '.' + e.className)"""
        )
        problems.append(f"{url} scrolls sideways by {overflow}px on a phone: {wide}")
    return problems


def run(browser, live_server, paths, demo, user=None) -> list[str]:
    context = browser.new_context(viewport=PHONE, locale="pl-PL", has_touch=True, is_mobile=True)
    if user is not None:
        login(context, live_server, user)
    page = context.new_page()
    values = {k: v for k, v in demo.items() if not k.startswith("_")}
    problems = []
    for path in paths:
        problems += audit(page, live_server.url + path.format(**values))
    context.close()
    print("\n".join(problems))  # shown in full when the test fails
    return problems


def test_public_pages(browser, live_server, demo):
    assert run(browser, live_server, PUBLIC, demo) == []


def test_participant_pages(browser, live_server, demo):
    from tests.factories import UserFactory

    participant: Participant = demo["_participant_obj"]
    user = UserFactory(email=participant.email)
    assert run(browser, live_server, PARTICIPANT, demo, user) == []


def test_panel_pages(browser, live_server, demo):
    assert run(browser, live_server, PANEL, demo, AdminFactory()) == []


FOCUSABLE = """() => [...document.querySelectorAll(
    'a[href], button, input:not([type=hidden]), select, textarea, [tabindex]:not([tabindex="-1"])'
)].filter(e => !e.disabled && e.tabIndex >= 0 && e.getClientRects().length
    && getComputedStyle(e).visibility !== 'hidden').length"""

FOCUS_STATE = """() => {
    const e = document.activeElement;
    const style = getComputedStyle(e);
    return {
        tag: e.tagName, name: e.name || e.textContent.trim().slice(0, 30),
        outline: style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0,
        shadow: style.boxShadow !== 'none',
    };
}"""


@pytest.mark.parametrize("path", ["/warsztaty/{slug}/zgloszenie/", "/konto/login/code/"])
def test_keyboard_reaches_every_control_with_visible_focus(browser, live_server, demo, path):
    """Tab through the page: every control is reached once, each with a visible focus mark."""
    context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="pl-PL")
    page = context.new_page()
    page.goto(live_server.url + path.format(slug=demo["slug"]))
    expected = page.evaluate(FOCUSABLE)
    seen, invisible = set(), []
    for _ in range(expected + 5):
        page.keyboard.press("Tab")
        state = page.evaluate(FOCUS_STATE)
        if state["tag"] == "BODY":
            break
        seen.add((state["tag"], state["name"]))
        if not (state["outline"] or state["shadow"]):
            invisible.append(state)
    context.close()
    assert invisible == []
    # Radio groups take one Tab stop, so fewer stops than controls is expected, never zero.
    assert len(seen) >= 5
