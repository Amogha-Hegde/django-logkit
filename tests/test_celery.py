from types import SimpleNamespace

from django_logkit.celery import (
    bind_log_context_from_task,
    bind_request_id_from_task,
    build_celery_headers,
    extract_log_context_from_task,
    extract_request_id_from_task,
)
from django_logkit.request_id import bind_log_context, get_log_context, get_request_id, reset_request_id, set_request_id


def test_build_celery_headers_uses_explicit_request_id():
    assert build_celery_headers("req-1") == {"x-request-id": "req-1"}


def test_build_celery_headers_uses_current_request_id():
    token = set_request_id("req-2")
    try:
        assert build_celery_headers() == {"x-request-id": "req-2"}
    finally:
        reset_request_id(token)


def test_build_celery_headers_includes_trace_and_span():
    with bind_log_context(trace_id="trace-1", span_id="span-1"):
        assert build_celery_headers() == {"x-trace-id": "trace-1", "x-span-id": "span-1"}


def test_build_celery_headers_includes_extended_context_fields():
    with bind_log_context(project_id="project-1", org_id="org-1", tenant="tenant-1", user_id="user-1"):
        assert build_celery_headers() == {
            "x-project-id": "project-1",
            "x-org-id": "org-1",
            "x-tenant": "tenant-1",
            "x-user-id": "user-1",
        }


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


def test_extract_log_context_from_task_reads_request_trace_and_span_headers():
    task = SimpleNamespace(
        request=SimpleNamespace(
            headers={"x-request-id": "req-7", "x-trace-id": "trace-7", "x-span-id": "span-7"},
            request_id="fallback",
        )
    )

    assert extract_log_context_from_task(task) == {
        "request_id": "req-7",
        "trace_id": "trace-7",
        "span_id": "span-7",
        "project_id": None,
        "org_id": None,
        "tenant": None,
        "user_id": None,
    }


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


def test_bind_log_context_from_task_sets_request_trace_and_span():
    task = SimpleNamespace(
        request=SimpleNamespace(
            headers={
                "x-request-id": "req-8",
                "x-trace-id": "trace-8",
                "x-span-id": "span-8",
                "x-project-id": "project-8",
                "x-org-id": "org-8",
                "x-tenant": "tenant-8",
                "x-user-id": "user-8",
            }
        )
    )

    with bind_log_context_from_task(task) as values:
        assert values["request_id"] == "req-8"
        assert values["trace_id"] == "trace-8"
        assert values["span_id"] == "span-8"
        assert values["project_id"] == "project-8"
        assert values["org_id"] == "org-8"
        assert values["tenant"] == "tenant-8"
        assert values["user_id"] == "user-8"
        assert get_log_context()["trace_id"] == "trace-8"

    assert get_log_context()["trace_id"] is None
