from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse


def client_ip(request: HttpRequest) -> str:
    """The visitor's address: the proxy's own header when we sit behind one, else REMOTE_ADDR.

    Only a header the reverse proxy sets itself is trusted (`CLIENT_IP_HEADER`, by default
    Nginx Proxy Manager's X-Real-IP), never X-Forwarded-For, which a client can prepend to.
    """
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get(settings.CLIENT_IP_HEADER, "").strip()
        if forwarded:
            return forwarded
    return request.META.get("REMOTE_ADDR", "")


class ClientIpMiddleware:
    """Put the visitor's address on `request.client_ip` for rate limits and the audit log."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.client_ip = client_ip(request)  # type: ignore[attr-defined]
        return self.get_response(request)


#: What a server with `SITE_NOINDEX` says about every response.
NOINDEX_EVERYTHING = "noindex, nofollow"


class NoIndexMiddleware:
    """`X-Robots-Tag: noindex, nofollow` on every response when `SITE_NOINDEX` is on (TEST).

    High in the list, so it sees the answer after everything else — WhiteNoise's static files
    included — and has the last word.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if settings.SITE_NOINDEX:
            response.headers["X-Robots-Tag"] = NOINDEX_EVERYTHING
        return response


class PermissionsPolicyMiddleware:
    """Send `settings.PERMISSIONS_POLICY`, which Django has no setting for."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if settings.PERMISSIONS_POLICY:
            response.headers.setdefault("Permissions-Policy", settings.PERMISSIONS_POLICY)
        return response
