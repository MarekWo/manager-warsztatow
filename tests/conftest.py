import pytest


@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    """Uploads never land in the working copy."""
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture(autouse=True)
def _clear_cache():
    """Rate limits live in the cache; every test starts with none spent."""
    from django.core.cache import cache

    cache.clear()


@pytest.fixture
def marketing_enabled(db):
    """The organiser asks for the consent to news about workshops (off by default)."""
    from workshop_manager.core.models import SiteSettings

    site = SiteSettings.load()
    site.marketing_enabled = True
    site.save()
    return site
