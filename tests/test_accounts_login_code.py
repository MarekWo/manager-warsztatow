"""Sign-in with a six-digit code sent by email (PRD §6.4; ADR-0001 spike)."""

import re

import pytest
from django.core import mail
from django.urls import reverse

from tests.factories import AdminFactory, UserFactory

CODE = re.compile(r"\b(\d{6})\b")


def _request_code(client, email):
    return client.post(reverse("account_request_login_code"), {"email": email})


def _code_from_outbox():
    assert mail.outbox, "no email was sent"
    match = CODE.search(mail.outbox[-1].body)
    assert match, mail.outbox[-1].body
    return match.group(1)


@pytest.mark.django_db
def test_participant_signs_in_with_a_six_digit_code(client):
    user = UserFactory()
    response = _request_code(client, user.email)
    assert response.status_code == 302
    assert response["Location"] == reverse("account_confirm_login_code")

    code = _code_from_outbox()
    response = client.post(reverse("account_confirm_login_code"), {"code": code})
    assert response.status_code == 302
    assert response["Location"] == "/"
    assert client.session["_auth_user_id"] == str(user.pk)


@pytest.mark.django_db
def test_email_subject_names_the_system(client):
    user = UserFactory()
    _request_code(client, user.email)
    assert mail.outbox[-1].subject.startswith("Manager Warsztatów — ")


@pytest.mark.django_db
def test_administrator_lands_in_the_panel(client):
    admin = AdminFactory()
    _request_code(client, admin.email)
    response = client.post(reverse("account_confirm_login_code"), {"code": _code_from_outbox()})
    assert response["Location"] == "/panel/"


@pytest.mark.django_db
def test_wrong_code_is_refused(client):
    user = UserFactory()
    _request_code(client, user.email)
    code = _code_from_outbox()
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    response = client.post(reverse("account_confirm_login_code"), {"code": wrong})
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_unknown_address_does_not_reveal_itself(client):
    """Prevent enumeration: same redirect, and no account is created."""
    response = _request_code(client, "nobody@example.com")
    assert response.status_code == 302
    from workshop_manager.accounts.models import User

    assert not User.objects.filter(email="nobody@example.com").exists()


@pytest.mark.django_db
def test_signup_page_is_closed(client):
    response = client.get(reverse("account_signup"))
    assert "account/signup_closed.html" in [t.name for t in response.templates]


@pytest.mark.django_db
def test_panel_requires_staff(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get(reverse("panel:dashboard"))
    assert response.status_code == 302
    client.force_login(AdminFactory())
    assert client.get(reverse("panel:dashboard")).status_code == 200


@pytest.mark.django_db
def test_ensure_admin_creates_a_verified_passwordless_admin(settings):
    from allauth.account.models import EmailAddress
    from django.core.management import call_command

    from workshop_manager.accounts.models import User

    settings.ADMIN_EMAIL = "Ojciec@Example.com"
    call_command("ensure_admin")
    call_command("ensure_admin")
    user = User.objects.get(email="ojciec@example.com")
    assert user.is_staff
    assert user.is_superuser
    assert not user.has_usable_password()
    assert EmailAddress.objects.get(user=user).verified


@pytest.mark.django_db
def test_password_login_page_forwards_to_the_code_request(client):
    response = client.get("/konto/login/?next=/panel/")
    assert response.status_code == 302
    assert response["Location"] == reverse("account_request_login_code") + "?next=/panel/"


@pytest.mark.django_db
def test_remember_is_offered_and_ticked_by_default(client):
    content = client.get(reverse("account_request_login_code")).content.decode()
    assert "Zapamiętaj mnie na tym urządzeniu" in content
    assert 'name="remember"' in content
    assert "checked" in content


def _sign_in(client, user, *, remember):
    data = {"email": user.email}
    if remember:
        data["remember"] = "on"
    client.post(reverse("account_request_login_code"), data)
    client.post(reverse("account_confirm_login_code"), {"code": _code_from_outbox()})


@pytest.mark.django_db
def test_not_remembered_session_ends_with_the_browser(client):
    _sign_in(client, UserFactory(), remember=False)
    assert client.session.get_expire_at_browser_close()


@pytest.mark.django_db
def test_remembered_participant_stays_signed_in_for_months(client, settings):
    _sign_in(client, UserFactory(), remember=True)
    assert not client.session.get_expire_at_browser_close()
    assert client.session.get_expiry_age() == settings.SESSION_COOKIE_AGE


@pytest.mark.django_db
def test_remembered_administrator_gets_a_shorter_session(client, settings):
    _sign_in(client, AdminFactory(), remember=True)
    assert client.session.get_expiry_age() == settings.STAFF_SESSION_REMEMBER_DAYS * 86400
