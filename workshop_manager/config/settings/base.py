"""Settings shared by every environment. Values come from the environment.

The optional env file (`ENV_FILE`, default `.env` in the repository root) only fills variables
that are not already set, so container environments always win over the file.
"""

from pathlib import Path
from typing import Any

import environ
from django.utils.csp import CSP

from workshop_manager import __version__
from workshop_manager.config.env import mail_address, mailer_from_url

BASE_DIR = Path(__file__).resolve().parents[3]

env = environ.Env()
_env_file = Path(env.str("ENV_FILE", default=str(BASE_DIR / ".env")))
if _env_file.is_file():
    environ.Env.read_env(_env_file)

APP_VERSION = __version__
# The commit the image was built from (Dockerfile build arg); empty for a source checkout.
APP_BUILD = env.str("APP_BUILD", default="")

# --- Core ---------------------------------------------------------------------------------------

DEBUG = env.bool("DEBUG", default=False)
SECRET_KEY = env.str("SECRET_KEY", default="")
SITE_URL = env.str("SITE_URL", default="http://localhost:8000").rstrip("/")
# Encrypts secrets kept in the database (the SMTP password). Empty = derived from SECRET_KEY.
FIELD_ENCRYPTION_KEY = env.str("FIELD_ENCRYPTION_KEY", default="")
# TEST servers must stay out of search engines: every response then says `noindex, nofollow`.
SITE_NOINDEX = env.bool("SITE_NOINDEX", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "workshop_manager.core",
    "workshop_manager.accounts",
    "workshop_manager.workshops",
    "workshop_manager.forms_builder",
    "workshop_manager.applications",
    "workshop_manager.communications",
    "workshop_manager.public",
    "workshop_manager.panel",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Django's own widget templates, found by the TemplatesSetting form renderer.
    "django.forms",
    # Authentication: email + one-time code, no passwords for participants (ADR-0001).
    "allauth",
    "allauth.account",
    "django_htmx",
    "django_q",
]

MIDDLEWARE = [
    "workshop_manager.core.middleware.ClientIpMiddleware",
    # Sees every answer last, static files included, so `SITE_NOINDEX` has the final word.
    "workshop_manager.core.middleware.NoIndexMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "workshop_manager.core.middleware.PermissionsPolicyMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "workshop_manager.config.urls"
WSGI_APPLICATION = "workshop_manager.config.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

_TEMPLATE_LOADERS: list[Any] = [
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
]

TEMPLATES: list[dict[str, Any]] = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Project templates win over app templates, which is how the allauth pages are re-skinned.
        "DIRS": [BASE_DIR / "workshop_manager" / "templates"],
        "OPTIONS": {
            "loaders": (
                _TEMPLATE_LOADERS
                if DEBUG
                else [("django.template.loaders.cached.Loader", _TEMPLATE_LOADERS)]
            ),
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.csp",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "workshop_manager.core.context_processors.app",
            ],
        },
    },
]

FORM_RENDERER = "workshop_manager.core.forms.BootstrapRenderer"

# --- Data ---------------------------------------------------------------------------------------

# Everything the application writes lives under DATA_DIR: the SQLite database and uploads.
# In containers it is the `data` volume mounted at /data (ADR-0002: SQLite, not PostgreSQL).
DATA_DIR = Path(env.str("DATA_DIR", default=str(BASE_DIR / "data")))

DATABASES = {
    "default": env.db_url("DATABASE_URL", default=f"sqlite:///{DATA_DIR / 'db.sqlite3'}"),
}
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    # SQLite creates the file but not its directory (a fresh checkout has no `data/`).
    Path(DATABASES["default"]["NAME"]).parent.mkdir(parents=True, exist_ok=True)
    # WAL lets the web and worker processes read while one of them writes; IMMEDIATE takes the
    # write lock at BEGIN, so two writers queue on `timeout` instead of failing with "database is
    # locked" halfway through a transaction.
    DATABASES["default"]["OPTIONS"] = {
        "transaction_mode": "IMMEDIATE",
        "timeout": 20,
        "init_command": (
            "PRAGMA journal_mode=WAL;"
            "PRAGMA synchronous=NORMAL;"
            "PRAGMA foreign_keys=ON;"
            "PRAGMA busy_timeout=20000;"
        ),
    }

# A database table shared by all processes: allauth's rate limits must count across gunicorn
# workers, which a per-process memory cache would not.
CACHES = {"default": env.cache_url("CACHE_URL", default="dbcache://django_cache")}

SESSION_ENGINE = "django.contrib.sessions.backends.db"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Authentication and sessions (PRD §6.4; ADR-0001) --------------------------------------------

AUTHENTICATION_BACKENDS = [
    # Kept first so `createsuperuser`, `force_login` and the Django admin keep working.
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_ADAPTER = "workshop_manager.accounts.adapters.AccountAdapter"
ACCOUNT_LOGIN_METHODS = {"email"}
# Participants never have a password: an account is a verified email address.
ACCOUNT_SIGNUP_FIELDS = ["email*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_MAX_ATTEMPTS = 5
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_TIMEOUT = 15 * 60
ACCOUNT_LOGIN_BY_CODE_ENABLED = True
ACCOUNT_LOGIN_BY_CODE_MAX_ATTEMPTS = 5
ACCOUNT_LOGIN_BY_CODE_TIMEOUT = 15 * 60
ACCOUNT_LOGIN_BY_CODE_SUPPORTS_RESEND = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_PREVENT_ENUMERATION = True
# None = the login form asks ("Zapamiętaj mnie na tym urządzeniu").
ACCOUNT_SESSION_REMEMBER = None
ACCOUNT_LOGOUT_ON_GET = False
ACCOUNT_EMAIL_SUBJECT_PREFIX = ""
ACCOUNT_SIGNUP_FORM_HONEYPOT_FIELD = "website"
ACCOUNT_FORMS = {"request_login_code": "workshop_manager.accounts.forms.RequestLoginCodeForm"}
ACCOUNT_RATE_LIMITS = {
    "login": "30/m/ip",
    "login_failed": "5/5m/key,10/m/ip",
    "signup": "5/m/ip",
    "confirm_email": "1/m/key",
    # Codes to one address: one a minute, five an hour (PRD §6.4).
    "request_login_code": "20/m/ip,1/m/key,5/h/key",
}
# Six digits: easy to read out of an email and type on a phone keypad (PRD §6.4).
ALLAUTH_USER_CODE_FORMAT = {"numeric": True, "length": 6, "dashed": False}

# The first administrator, created on start by `ensure_admin` (signs in with a code, no password).
ADMIN_EMAIL = env.str("ADMIN_EMAIL", default="")

LOGIN_URL = "account_request_login_code"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# Without "remember me" the session ends with the browser; with it, it lasts
# SESSION_REMEMBER_DAYS since the last request on that device (rolling).
SESSION_COOKIE_AGE = env.int("SESSION_REMEMBER_DAYS", default=180) * 24 * 60 * 60
STAFF_SESSION_REMEMBER_DAYS = env.int("STAFF_SESSION_REMEMBER_DAYS", default=30)
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# --- Internationalization -------------------------------------------------------------------------

# Polish only (client decision). UI strings are written in Polish directly (ADR-0003);
# Django's and allauth's own messages come from their Polish catalogues.
LANGUAGE_CODE = "pl"
LANGUAGES = [("pl", "Polski")]
TIME_ZONE = env.str("TIME_ZONE", default="Europe/Warsaw")
USE_I18N = True
USE_TZ = True

# --- Static files and media ---------------------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = Path(env.str("STATIC_ROOT", default=str(BASE_DIR / "staticfiles")))
STATICFILES_DIRS = [BASE_DIR / "workshop_manager" / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = Path(env.str("MEDIA_ROOT", default=str(DATA_DIR / "media")))

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    # Files that must never be public (attachments of messages to participants): outside
    # MEDIA_ROOT, which the edge serves to anyone.
    "private": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": str(DATA_DIR / "private")},
    },
}

# --- Email ---------------------------------------------------------------------------------------

# The fallback transport; SMTP settings saved in the panel take precedence when switched on
# (communications.mailer).
# Lower-case, so the URL (with its password) never becomes a setting a debug page could print.
_email_url = env.str("EMAIL_URL", default="consolemail://")
MAILERS = {"default": mailer_from_url(_email_url)}
DEFAULT_FROM_EMAIL = mail_address(
    env.str("DEFAULT_FROM_EMAIL", default="Manager Warsztatów <noreply@localhost>"),
    name="DEFAULT_FROM_EMAIL",
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# --- Security -----------------------------------------------------------------------------------

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Behind a reverse proxy (Nginx Proxy Manager on PROD) the scheme and the visitor's address come
# from headers the proxy sets itself. Never X-Forwarded-For, which a client can prepend to.
TRUST_PROXY_HEADERS = env.bool("TRUST_PROXY_HEADERS", default=False)
CLIENT_IP_HEADER = env.str("CLIENT_IP_HEADER", default="X-Real-IP")
if TRUST_PROXY_HEADERS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # allauth's rate limits read the same header, or every visitor would share one address.
    ALLAUTH_TRUSTED_CLIENT_IP_HEADER = CLIENT_IP_HEADER

PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), "
    "payment=(), usb=(), interest-cohort=(), browsing-topics=()"
)

# One policy, sent either as report-only (DEV, tests) or enforcing (`CSP_ENFORCE`, the default in
# prod.py). Templates put {{ csp_nonce }} on inline scripts and styles.
CSP_POLICY: dict[str, list[str]] = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.NONCE],
    "style-src": [CSP.SELF, CSP.NONCE],
    "img-src": [CSP.SELF, "data:"],
    "font-src": [CSP.SELF],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
}
CSP_ENFORCE = env.bool("CSP_ENFORCE", default=False)
SECURE_CSP = CSP_POLICY if CSP_ENFORCE else {}
SECURE_CSP_REPORT_ONLY = {} if CSP_ENFORCE else CSP_POLICY

# --- Background tasks: use workshop_manager.core.tasks, never django_q directly ------------------

TASK_SYNC = env.bool("TASK_SYNC", default=False)
Q_CLUSTER = {
    "name": "workshop_manager",
    "label": "Zadania w tle",
    "orm": "default",
    "workers": env.int("TASK_WORKERS", default=1),
    "timeout": 60,
    "retry": 90,
    "max_attempts": 3,
    "save_limit": 250,
    "save_limit_per": "func",
    "catch_up": False,
    # One second is plenty for email; SQLite readers are cheap in WAL mode.
    "poll": 2,
    "sync": TASK_SYNC,
}

# --- Logging ------------------------------------------------------------------------------------

LOG_LEVEL = env.str("LOG_LEVEL", default="INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
