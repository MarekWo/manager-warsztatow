"""The in-app help (PRD §7.10): chapters for administrators, the participants' page, and every
"?" in the panel leading to a section that exists."""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from tests.factories import AdminFactory, UserFactory
from workshop_manager.help.chapters import BY_SLUG, CHAPTERS

TEMPLATES = Path(settings.BASE_DIR) / "workshop_manager" / "templates"
HELP_LINK = re.compile(r'{% help_link "([a-z-]+)"(?: "([a-z-]+)")?')


@pytest.fixture
def admin_client(client, db):
    client.force_login(AdminFactory())
    return client


def test_every_chapter_opens_with_its_neighbours(admin_client):
    for position, chapter in enumerate(CHAPTERS):
        response = admin_client.get(reverse("help:chapter", args=[chapter.slug]))
        assert response.status_code == 200
        content = response.content.decode()
        assert chapter.title in content
        if position + 1 < len(CHAPTERS):
            assert CHAPTERS[position + 1].title in content


def test_index_lists_the_chapters_and_the_header_links_help(admin_client):
    content = admin_client.get(reverse("help:index")).content.decode()
    for chapter in CHAPTERS:
        assert reverse("help:chapter", args=[chapter.slug]) in content
    assert 'href="/panel/pomoc/"' in admin_client.get("/panel/").content.decode()


def test_unknown_chapter_is_not_found(admin_client):
    assert admin_client.get("/panel/pomoc/nie-ma/").status_code == 404


def test_the_help_is_for_staff(client, db):
    client.force_login(UserFactory())
    assert client.get(reverse("help:index")).status_code == 302


def test_participants_page_is_public(client, db):
    response = client.get(reverse("public:help"))
    assert response.status_code == 200
    assert "Rezygnacja" in response.content.decode()
    assert reverse("public:help") in client.get("/").content.decode()  # the footer link


def test_every_question_mark_points_at_an_existing_section():
    links = set()
    for template in TEMPLATES.rglob("*.html"):
        links.update(HELP_LINK.findall(template.read_text(encoding="utf-8")))
    assert links, "no help links found"
    for slug, section in links:
        assert slug in BY_SLUG, slug
        if section:
            chapter = (TEMPLATES / BY_SLUG[slug].template).read_text(encoding="utf-8")
            assert f'id="{section}"' in chapter, f"{slug}#{section}"


def test_question_mark_says_where_it_leads(admin_client):
    from tests.factories import WorkshopFactory

    workshop = WorkshopFactory()
    content = admin_client.get(reverse("panel:workshop_edit", args=[workshop.pk])).content.decode()
    assert 'href="/panel/pomoc/warsztaty/#poziomy"' in content
    assert "Pomoc: Poziomy i limit miejsc (otwiera się w nowej karcie)" in content
