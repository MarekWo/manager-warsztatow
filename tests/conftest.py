import pytest


@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    """Uploads never land in the working copy."""
    settings.MEDIA_ROOT = tmp_path / "media"
