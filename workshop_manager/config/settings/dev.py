"""Local development: Docker Compose DEV stack or `uv run python manage.py …` on the host."""

from .base import *  # noqa: F403
from .base import ALLOWED_HOSTS, SECRET_KEY, STORAGES, env

DEBUG = env.bool("DEBUG", default=True)
SECRET_KEY = SECRET_KEY or "django-insecure-dev-only-never-use-this-key-in-production"
ALLOWED_HOSTS = [*ALLOWED_HOSTS, "localhost", "127.0.0.1", "0.0.0.0", "[::1]"]  # noqa: S104

# Serve static files straight from app directories, without running collectstatic first.
WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
