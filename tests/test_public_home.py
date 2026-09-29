import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_home_says_no_workshops_are_planned(client):
    response = client.get(reverse("public:home"))
    assert response.status_code == 200
    assert "Obecnie nie są planowane żadne warsztaty." in response.content.decode()


@pytest.mark.django_db
def test_security_headers(client):
    response = client.get(reverse("public:home"))
    assert response["X-Frame-Options"] == "DENY"
    assert "camera=()" in response["Permissions-Policy"]
    assert "Content-Security-Policy-Report-Only" in response


@pytest.mark.django_db
def test_noindex_on_test_servers(client, settings):
    settings.SITE_NOINDEX = True
    response = client.get(reverse("public:home"))
    assert response["X-Robots-Tag"] == "noindex, nofollow"
