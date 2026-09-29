from typing import Any

from django.conf import settings
from django.http import HttpRequest

from workshop_manager.core.build import version_string


def app(request: HttpRequest) -> dict[str, Any]:
    """Values every template may use: the version for the footer and the noindex flag."""
    return {
        "app_version": version_string(),
        "site_noindex": settings.SITE_NOINDEX,
    }
