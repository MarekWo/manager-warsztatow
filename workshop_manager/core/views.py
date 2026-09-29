import contextlib

from django.db import DatabaseError, connection
from django.http import HttpRequest, JsonResponse
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
