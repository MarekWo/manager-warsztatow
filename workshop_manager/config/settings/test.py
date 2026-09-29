"""pytest settings: an in-memory SQLite database and everything else local."""

from .base import *  # noqa: F403
from .base import _TEMPLATE_LOADERS, Q_CLUSTER, TEMPLATES

DEBUG = False

# Tests use a server's (cached) template loaders, whatever `.env` says about DEBUG.
TEMPLATES[0]["OPTIONS"]["loaders"] = [("django.template.loaders.cached.Loader", _TEMPLATE_LOADERS)]
SECRET_KEY = "test-only-secret-key-0123456789-abcdefghijklmnopqrstuvwxyz"  # noqa: S105
ALLOWED_HOSTS = ["testserver", "localhost"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "OPTIONS": {"transaction_mode": "IMMEDIATE"},
    }
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
WHITENOISE_AUTOREFRESH = True  # no collectstatic in tests; avoids the missing STATIC_ROOT warning
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}

TASK_SYNC = True
Q_CLUSTER = {**Q_CLUSTER, "sync": True}
