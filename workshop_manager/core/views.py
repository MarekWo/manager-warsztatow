import contextlib

from django.db import DatabaseError, connection
from django.http import HttpRequest, HttpResponse, HttpResponsePermanentRedirect, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from workshop_manager.core.build import build_info
from workshop_manager.core.tasks import worker_status


@never_cache
@require_http_methods(["GET", "HEAD"])
def healthz(request: HttpRequest) -> JsonResponse:
    """Liveness and readiness probe for Docker healthchecks and uptime monitors.

    `status` (and the HTTP code) follows the database alone: the container healthcheck restarts
    on it, and a worker that stopped is not a reason to restart the web container. The worker is
    reported beside it — `ok`, `stale` (no heartbeat for `WORKER_STALE_AFTER`) or `unknown`
    (none recorded yet) — with the heartbeat's age in seconds.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "ok"
    except DatabaseError:
        db_status = "error"

    healthy = db_status == "ok"
    worker, worker_age = "unknown", None
    if healthy:
        with contextlib.suppress(DatabaseError):
            worker, worker_age = worker_status()
    payload = {
        "status": "ok" if healthy else "error",
        "db": db_status,
        "worker": worker,
        "worker_age": worker_age,
        **build_info(),
    }
    response = JsonResponse(payload, status=200 if healthy else 503)
    if request.method == "HEAD":
        response.content = b""  # gunicorn drops (and logs) bodies sent on HEAD responses
    return response


def csrf_failure(request: HttpRequest, reason: str = "") -> HttpResponse:
    """The page shown when a form's CSRF token is missing or stale (`CSRF_FAILURE_VIEW`).

    Django's own page is in English and meant for developers; people see this mostly after
    leaving a form open for a long time, so it says that in plain Polish and how to go on.
    """
    return render(request, "errors/csrf.html", status=403)


def static_redirect(request: HttpRequest, path: str) -> HttpResponse:
    """Send `/favicon.ico` and friends, which browsers ask for at the root, to the static file.

    Resolved per request: the hashed name comes from the static files manifest.
    """
    return HttpResponsePermanentRedirect(static(path))
