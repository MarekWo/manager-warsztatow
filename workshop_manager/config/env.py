"""Helpers that turn 12-factor environment values into Django settings structures.

Kept free of Django model imports so settings modules can use them safely.
"""

from email.errors import HeaderParseError
from email.headerregistry import Address, AddressHeader
from email.utils import parseaddr
from typing import Any

import environ
from django.core.exceptions import ImproperlyConfigured

# django-environ still produces the pre-6.1 EMAIL_* keys; Django 6.1 configures mail via MAILERS.
_MAILER_OPTION_KEYS = {
    "EMAIL_HOST": "host",
    "EMAIL_PORT": "port",
    "EMAIL_HOST_USER": "username",
    "EMAIL_HOST_PASSWORD": "password",
    "EMAIL_USE_TLS": "use_tls",
    "EMAIL_USE_SSL": "use_ssl",
    "EMAIL_FILE_PATH": "file_path",
}


def mailer_from_url(url: str, timeout: int = 10) -> dict[str, Any]:
    """Build one `MAILERS` entry from an `EMAIL_URL` such as `smtp+tls://user:pw@host:587`."""
    config = environ.Env.email_url_config(url)
    backend = config.pop("EMAIL_BACKEND")
    options = {
        _MAILER_OPTION_KEYS[key]: value
        for key, value in config.items()
        if key in _MAILER_OPTION_KEYS and value not in (None, "")
    }
    if backend.endswith("smtp.EmailBackend"):
        options["timeout"] = timeout
    mailer: dict[str, Any] = {"BACKEND": backend}
    if options:
        mailer["OPTIONS"] = options
    return mailer


def mail_address(value: str, *, name: str = "DEFAULT_FROM_EMAIL") -> str:
    """One `Name <address>` (or a bare address) as Django's SMTP backend will accept it.

    A display name with a period, a comma or another special character must be quoted; unquoted,
    the SMTP backend refuses every message long after start-up. The value is re-composed with the
    quotes it needs, and anything that is still not one address stops the start with the
    setting's name. An empty value stays empty.
    """
    text = value.strip()
    if not text:
        return ""
    refusal = ImproperlyConfigured(
        f"{name}: {text!r} is not one email address"
        " (a name containing a comma must be in double quotes)."
    )
    display_name, addr_spec = parseaddr(text)
    try:
        address = str(Address(display_name=display_name, addr_spec=addr_spec))
    except (ValueError, IndexError, HeaderParseError) as error:
        raise refusal from error
    parsed = AddressHeader.value_parser(address)
    if "@" not in addr_spec or parsed.all_defects or len(parsed.all_mailboxes) != 1:
        raise refusal
    return address
