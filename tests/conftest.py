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
