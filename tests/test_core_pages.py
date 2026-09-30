"""Error pages, icons and the meta tags every page carries."""

import pytest
from django.template.loader import render_to_string
from django.test import Client

from tests.factories import WorkshopFactory


@pytest.mark.django_db
def test_missing_page_is_polish_and_links_home(client):
    response = client.get("/nie-ma-takiej-strony/")
    assert response.status_code == 404
    content = response.content.decode()
    assert "Nie ma takiej strony" in content
    assert 'href="/"' in content


def test_server_error_page_needs_no_context():
    # Rendered by Django without a request: nothing may depend on context processors.
    content = render_to_string("500.html")
    assert "Coś poszło nie tak" in content
    assert "favicon.svg" in content


@pytest.mark.django_db
def test_stale_form_explains_what_to_do():
    client = Client(enforce_csrf_checks=True)
    response = client.post("/konto/login/code/", {"email": "osoba@example.com"})
    assert response.status_code == 403
    assert "Formularz wygasł" in response.content.decode()


@pytest.mark.django_db
def test_favicon_at_the_root_redirects_to_the_static_file(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 301
    assert response["Location"].endswith("img/favicon.ico")


@pytest.mark.django_db
def test_pages_carry_description_and_open_graph(client, settings):
    settings.SITE_URL = "https://warsztaty.example.com"
    content = client.get("/").content.decode()
    assert '<meta name="description"' in content
    assert '<meta property="og:url" content="https://warsztaty.example.com/">' in content
    assert "https://warsztaty.example.com/static/img/icon-512.png" in content


@pytest.mark.django_db
def test_workshop_page_describes_the_workshop(client):
    workshop = WorkshopFactory(subtitle="Tydzień pisania ikony", publish_at="2020-01-01T00:00Z")
    content = client.get(workshop.get_absolute_url()).content.decode()
    assert '<meta property="og:title" content="' + workshop.title in content
    assert 'content="Tydzień pisania ikony"' in content
