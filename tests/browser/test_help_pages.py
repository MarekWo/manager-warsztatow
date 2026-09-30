"""The help pages pass the accessibility check, on a phone as well."""

import os

import pytest

from tests.browser.test_application_flow import serious_violations
from tests.browser.test_gdpr_pages import sign_in
from tests.factories import AdminFactory
from workshop_manager.help.chapters import CHAPTERS

pytestmark = [pytest.mark.browser, pytest.mark.django_db(transaction=True)]


@pytest.mark.parametrize("slug", ["", *[chapter.slug + "/" for chapter in CHAPTERS]])
def test_help_chapters_accessibility(live_server, page, slug):
    sign_in(page, live_server, AdminFactory())
    page.goto(f"{live_server.url}/panel/pomoc/{slug}")
    assert serious_violations(page) == []
    # Set HELP_SHOTS_DIR to look at the pages while writing the help.
    if slug and os.environ.get("HELP_SHOTS_DIR"):
        page.screenshot(path=os.path.join(os.environ["HELP_SHOTS_DIR"], slug.strip("/") + ".png"))


def test_participants_help_accessibility(live_server, phone_page, db):
    phone_page.goto(f"{live_server.url}/pomoc/")
    assert serious_violations(phone_page) == []
