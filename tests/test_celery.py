from types import SimpleNamespace

from django_logkit.celery import bind_request_id_from_task, build_celery_headers, extract_request_id_from_task
from django_logkit.request_id import get_request_id, reset_request_id, set_request_id


def test_build_celery_headers_uses_explicit_request_id():
    assert build_celery_headers("req-1") == {"x-request-id": "req-1"}


def test_build_celery_headers_uses_current_request_id():
    token = set_request_id("req-2")
    try:
        assert build_celery_headers() == {"x-request-id": "req-2"}
    finally:
        reset_request_id(token)


def test_build_celery_headers_returns_empty_when_unset():
    assert build_celery_headers() == {}


def test_extract_request_id_from_task_prefers_headers():
    task = SimpleNamespace(request=SimpleNamespace(headers={"x-request-id": "req-3"}, request_id="fallback"))

    assert extract_request_id_from_task(task) == "req-3"


def test_extract_request_id_from_task_falls_back_to_request_id():
    task = SimpleNamespace(request=SimpleNamespace(headers={}, request_id="req-4"))

    assert extract_request_id_from_task(task) == "req-4"


def test_extract_request_id_from_task_returns_none_when_missing():
    task = SimpleNamespace(request=None)

    assert extract_request_id_from_task(task) is None


def test_bind_request_id_from_task_sets_and_resets():
    task = SimpleNamespace(request=SimpleNamespace(headers={"x-request-id": "req-5"}))

    with bind_request_id_from_task(task) as request_id:
        assert request_id == "req-5"
        assert get_request_id() == "req-5"

    assert get_request_id() is None


def test_bind_request_id_from_task_uses_explicit_request_id():
    with bind_request_id_from_task(request_id="req-6") as request_id:
        assert request_id == "req-6"
        assert get_request_id() == "req-6"

    assert get_request_id() is None
