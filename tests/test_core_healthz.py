import pytest
from django.urls import reverse

from workshop_manager.core.tasks import heartbeat


@pytest.mark.django_db
def test_healthz_reports_database_and_unknown_worker(client):
    response = client.get(reverse("healthz"))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["worker"] == "unknown"
    assert "version" in body


@pytest.mark.django_db
def test_healthz_sees_the_worker_after_a_heartbeat(client):
    from workshop_manager.core.tasks import enqueue

    enqueue(heartbeat)  # runs inline under TASK_SYNC and is recorded as a success
    body = client.get(reverse("healthz")).json()
    assert body["worker"] == "ok"
    assert body["worker_age"] is not None


@pytest.mark.django_db
def test_healthz_head_has_no_body(client):
    response = client.head(reverse("healthz"))
    assert response.status_code == 200
    assert response.content == b""
