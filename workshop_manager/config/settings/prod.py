"""TEST and PROD servers (Docker image default). See docs/deploy.md."""

from urllib.parse import urlsplit

from .base import *  # noqa: F403
from .base import ALLOWED_HOSTS, CSP_POLICY, CSRF_TRUSTED_ORIGINS, SITE_URL, env

DEBUG = False
SECRET_KEY = env.str("SECRET_KEY")  # required: fail fast when missing

# The public origin is always allowed, so a server's .env cannot forget the host it serves;
# localhost stays allowed so the container healthchecks can reach /healthz.
_site = urlsplit(SITE_URL)
ALLOWED_HOSTS = [
    host
    for host in dict.fromkeys([*ALLOWED_HOSTS, _site.hostname, "localhost", "127.0.0.1"])
    if host
]
CSRF_TRUSTED_ORIGINS = list(
    dict.fromkeys([*CSRF_TRUSTED_ORIGINS, f"{_site.scheme}://{_site.netloc}"])
)

# TLS ends at the reverse proxy, which also redirects HTTP to HTTPS.
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]
SESSION_COOKIE_SECURE = env.bool("SECURE_COOKIES", default=True)
CSRF_COOKIE_SECURE = env.bool("SECURE_COOKIES", default=True)

# Host-only and short until PROD has run on its final domain for a while.
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=3600)
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
# W008: SSL redirect is the proxy's job. W021: no preload on a domain we do not own.
SILENCED_SYSTEM_CHECKS = ["security.W008", "security.W021"]

# Servers enforce the policy; `CSP_ENFORCE=false` is the break-glass back to report-only.
CSP_ENFORCE = env.bool("CSP_ENFORCE", default=True)
SECURE_CSP = CSP_POLICY if CSP_ENFORCE else {}
SECURE_CSP_REPORT_ONLY = {} if CSP_ENFORCE else CSP_POLICY
