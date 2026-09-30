from typing import Any

from django.conf import settings
from django.http import HttpRequest
from django.utils.functional import SimpleLazyObject

from workshop_manager.core.build import version_string
from workshop_manager.core.models import SiteSettings


def app(request: HttpRequest) -> dict[str, Any]:
    """Values every template may use: the version, the noindex flag and the site settings."""
    return {
        "app_version": version_string(),
        "site_noindex": settings.SITE_NOINDEX,
        # Lazy: pages that never touch it (healthz, redirects) cost no query.
        "site_settings": SimpleLazyObject(SiteSettings.load),
    }
