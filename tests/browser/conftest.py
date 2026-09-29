import os

import pytest

# Playwright's sync API runs an event loop in the test thread; Django refuses database access
# from there unless told that this is intended (it is: tests are single-threaded here).
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

PHONE = {"width": 360, "height": 740}


@pytest.fixture
def browser_context_args(browser_context_args):
    return {**browser_context_args, "locale": "pl-PL", "timezone_id": "Europe/Warsaw"}


@pytest.fixture
def phone_page(browser):
    context = browser.new_context(viewport=PHONE, locale="pl-PL", has_touch=True, is_mobile=True)
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture(autouse=True)
def _fast_form(monkeypatch):
    """The minimum fill-in time stops bots, and would stop a test that types instantly."""
    monkeypatch.setattr("workshop_manager.applications.forms.MIN_FILL_SECONDS", 0)
