from types import SimpleNamespace

import django_logkit.middleware as middleware_module
from django_logkit.filters import RequestIdFilter
from django_logkit.middleware import RequestContextMiddleware, RequestIdMiddleware, _extract_request_headers, _extract_response_headers
from django_logkit.request_id import (
    clear_pending_server_log_context,
    get_log_context,
    get_request_id,
    get_pending_server_log_context,
    reset_request_id,
    set_pending_server_log_context,
    set_request_id,
)


def test_request_id_filter_sets_record_value():
    token = set_request_id("req-1")
    try:
        record = SimpleNamespace()
        result = RequestIdFilter().filter(record)
    finally:
        reset_request_id(token)

    assert result is True
    assert record.request_id == "req-1"


def test_request_id_filter_uses_defaults_when_missing():
    record = SimpleNamespace()

    RequestIdFilter().filter(record)

    assert record.request_id == "-"
    assert record.trace_id == "-"
    assert record.span_id == "-"
    assert record.project_id == "-"
    assert record.org_id == "-"
    assert record.user_id == "-"
    assert record.tenant == "-"
    assert record.duration_ms == "-"


def test_request_id_filter_uses_request_attribute_when_context_missing():
    record = SimpleNamespace(
        request=SimpleNamespace(
            request_id="req-3",
            trace_id="trace-3",
            span_id="span-3",
            project_id="project-3",
            org_id="org-3",
            user_id="user-3",
            tenant="tenant-3",
            duration_ms=45,
        )
    )

    RequestIdFilter().filter(record)

    assert record.request_id == "req-3"
    assert record.trace_id == "trace-3"
    assert record.span_id == "span-3"
    assert record.project_id == "project-3"
    assert record.org_id == "org-3"
    assert record.user_id == "user-3"
    assert record.tenant == "tenant-3"
    assert record.duration_ms == 45


def test_request_id_filter_uses_request_meta_header_when_context_missing():
    record = SimpleNamespace(
        request=SimpleNamespace(
            META={
                "HTTP_X_REQUEST_ID": "req-4",
                "HTTP_X_PROJECT_ID": "project-4",
                "HTTP_X_ORG_ID": "org-4",
                "HTTP_X_TENANT": "tenant-4",
            }
        )
    )

    RequestIdFilter().filter(record)

    assert record.request_id == "req-4"
    assert record.project_id == "project-4"
    assert record.org_id == "org-4"
    assert record.tenant == "tenant-4"


class DummyResponse(dict):
    pass


def test_request_context_middleware_alias_matches_request_id_middleware():
    assert RequestContextMiddleware is RequestIdMiddleware


def test_request_id_middleware_uses_existing_headers_and_binds_context(monkeypatch):
    times = iter([100.0, 100.125])
    monkeypatch.setattr(middleware_module, "perf_counter", lambda: next(times))

    request = SimpleNamespace(
        META={
            "HTTP_X_REQUEST_ID": "req-2",
            "HTTP_X_TRACE_ID": "trace-2",
            "HTTP_X_SPAN_ID": "span-2",
            "HTTP_X_PROJECT_ID": "project-2",
            "HTTP_X_ORG_ID": "org-2",
            "HTTP_X_TENANT": "tenant-2",
        },
        user=SimpleNamespace(is_authenticated=True, pk="user-2"),
    )

    def get_response(incoming_request):
        assert incoming_request.request_id == "req-2"
        assert incoming_request.trace_id == "trace-2"
        assert incoming_request.span_id == "span-2"
        assert incoming_request.project_id == "project-2"
        assert incoming_request.org_id == "org-2"
        assert incoming_request.user_id == "user-2"
        assert incoming_request.tenant == "tenant-2"
        assert get_request_id() == "req-2"
        assert get_log_context()["trace_id"] == "trace-2"
        return DummyResponse()

    response = RequestIdMiddleware(get_response)(request)

    assert response["X-Request-ID"] == "req-2"
    assert request.duration_ms == 125
    assert get_request_id() is None
    assert get_log_context()["trace_id"] is None


def test_request_id_middleware_generates_header_when_missing(monkeypatch):
    times = iter([10.0, 10.015])
    monkeypatch.setattr(middleware_module, "perf_counter", lambda: next(times))
    monkeypatch.setattr(middleware_module, "uuid4", lambda: "generated-id")
    request = SimpleNamespace(META={})

    response = RequestIdMiddleware(lambda incoming_request: DummyResponse())(request)

    assert response["X-Request-ID"] == "generated-id"
    assert request.request_id == "generated-id"
    assert request.duration_ms == 16
    assert get_request_id() is None


def test_request_id_middleware_rounds_up_sub_millisecond_duration(monkeypatch):
    times = iter([15.0, 15.0001])
    monkeypatch.setattr(middleware_module, "perf_counter", lambda: next(times))
    monkeypatch.setattr(middleware_module, "uuid4", lambda: "generated-id")
    request = SimpleNamespace(META={})

    response = RequestIdMiddleware(lambda incoming_request: DummyResponse())(request)

    assert response["X-Request-ID"] == "generated-id"
    assert request.duration_ms == 1


def test_request_id_middleware_uses_one_millisecond_when_elapsed_is_zero(monkeypatch):
    times = iter([15.0, 15.0])
    monkeypatch.setattr(middleware_module, "perf_counter", lambda: next(times))
    monkeypatch.setattr(middleware_module, "uuid4", lambda: "generated-id")
    request = SimpleNamespace(META={})

    response = RequestIdMiddleware(lambda incoming_request: DummyResponse())(request)

    assert response["X-Request-ID"] == "generated-id"
    assert request.duration_ms == 1


def test_request_id_filter_uses_env_overridden_meta_headers(monkeypatch):
    monkeypatch.setenv("DJANGO_LOGKIT_REQUEST_ID_HEADER", "HTTP_X_CORRELATION_ID")
    monkeypatch.setenv("DJANGO_LOGKIT_TRACE_ID_HEADER", "HTTP_X_B3_TRACE_ID")
    monkeypatch.setenv("DJANGO_LOGKIT_SPAN_ID_HEADER", "HTTP_X_B3_SPAN_ID")
    monkeypatch.setenv("DJANGO_LOGKIT_PROJECT_ID_HEADER", "HTTP_X_PROJECT")
    monkeypatch.setenv("DJANGO_LOGKIT_ORG_ID_HEADER", "HTTP_X_ORGANIZATION")
    monkeypatch.setenv("DJANGO_LOGKIT_TENANT_HEADER", "HTTP_X_ACCOUNT")
    record = SimpleNamespace(
        request=SimpleNamespace(
            META={
                "HTTP_X_CORRELATION_ID": "req-9",
                "HTTP_X_B3_TRACE_ID": "trace-9",
                "HTTP_X_B3_SPAN_ID": "span-9",
                "HTTP_X_PROJECT": "project-9",
                "HTTP_X_ORGANIZATION": "org-9",
                "HTTP_X_ACCOUNT": "tenant-9",
            }
        )
    )

    RequestIdFilter().filter(record)

    assert record.request_id == "req-9"
    assert record.trace_id == "trace-9"
    assert record.span_id == "span-9"
    assert record.project_id == "project-9"
    assert record.org_id == "org-9"
    assert record.tenant == "tenant-9"


def test_request_id_filter_uses_pending_server_log_context():
    clear_pending_server_log_context()
    set_pending_server_log_context(
        {
            "request_id": "req-11",
            "trace_id": "trace-11",
            "span_id": "span-11",
            "project_id": "project-11",
            "org_id": "org-11",
            "tenant": "tenant-11",
            "user_id": "user-11",
            "duration_ms": 33,
        }
    )
    record = SimpleNamespace(name="django.server")

    RequestIdFilter().filter(record)

    assert record.request_id == "req-11"
    assert record.trace_id == "trace-11"
    assert record.span_id == "span-11"
    assert record.project_id == "project-11"
    assert record.org_id == "org-11"
    assert record.tenant == "tenant-11"
    assert record.user_id == "user-11"
    assert record.duration_ms == 33
    assert get_pending_server_log_context() is None


def test_request_id_middleware_uses_env_overridden_headers(monkeypatch):
    times = iter([20.0, 20.010])
    monkeypatch.setattr(middleware_module, "perf_counter", lambda: next(times))
    monkeypatch.setenv("DJANGO_LOGKIT_REQUEST_ID_HEADER", "HTTP_X_CORRELATION_ID")
    monkeypatch.setenv("DJANGO_LOGKIT_TRACE_ID_HEADER", "HTTP_X_B3_TRACE_ID")
    monkeypatch.setenv("DJANGO_LOGKIT_SPAN_ID_HEADER", "HTTP_X_B3_SPAN_ID")
    monkeypatch.setenv("DJANGO_LOGKIT_PROJECT_ID_HEADER", "HTTP_X_PROJECT")
    monkeypatch.setenv("DJANGO_LOGKIT_ORG_ID_HEADER", "HTTP_X_ORGANIZATION")
    monkeypatch.setenv("DJANGO_LOGKIT_TENANT_HEADER", "HTTP_X_ACCOUNT")
    request = SimpleNamespace(
        META={
            "HTTP_X_CORRELATION_ID": "req-10",
            "HTTP_X_B3_TRACE_ID": "trace-10",
            "HTTP_X_B3_SPAN_ID": "span-10",
            "HTTP_X_PROJECT": "project-10",
            "HTTP_X_ORGANIZATION": "org-10",
            "HTTP_X_ACCOUNT": "tenant-10",
        }
    )

    response = RequestIdMiddleware(lambda incoming_request: DummyResponse())(request)

    assert request.request_id == "req-10"
    assert request.trace_id == "trace-10"
    assert request.span_id == "span-10"
    assert request.project_id == "project-10"
    assert request.org_id == "org-10"
    assert request.tenant == "tenant-10"
    assert request.duration_ms == 11
    assert response["X-Correlation-ID"] == "req-10"


def test_request_id_middleware_stores_pending_server_context(monkeypatch):
    times = iter([30.0, 30.021])
    monkeypatch.setattr(middleware_module, "perf_counter", lambda: next(times))
    request = SimpleNamespace(
        META={
            "HTTP_X_REQUEST_ID": "req-12",
            "HTTP_X_TRACE_ID": "trace-12",
            "HTTP_X_SPAN_ID": "span-12",
            "HTTP_X_PROJECT_ID": "project-12",
            "HTTP_X_ORG_ID": "org-12",
        }
    )

    response = RequestIdMiddleware(lambda incoming_request: DummyResponse())(request)
    pending_context = get_pending_server_log_context()

    assert response["X-Request-ID"] == "req-12"
    assert pending_context["request_id"] == "req-12"
    assert pending_context["trace_id"] == "trace-12"
    assert pending_context["span_id"] == "span-12"
    assert pending_context["project_id"] == "project-12"
    assert pending_context["org_id"] == "org-12"
    assert pending_context["duration_ms"] == 22


def test_extract_request_headers_redacts_sensitive_values():
    request = SimpleNamespace(
        headers={
            "Authorization": "Bearer secret",
            "Cookie": "session=value",
            "X-Trace-Id": "trace-1",
        }
    )

    headers = _extract_request_headers(request)

    assert headers["Authorization"] == "[REDACTED]"
    assert headers["Cookie"] == "[REDACTED]"
    assert headers["X-Trace-Id"] == "trace-1"


def test_extract_response_headers_redacts_sensitive_values():
    response = SimpleNamespace(headers={"Set-Cookie": "session=value", "Content-Type": "application/json"})

    headers = _extract_response_headers(response)

    assert headers["Set-Cookie"] == "[REDACTED]"
    assert headers["Content-Type"] == "application/json"


def test_request_id_middleware_logs_request_response_when_enabled(monkeypatch):
    class DummyLogger:
        def __init__(self):
            self.calls = []

        def info(self, message, *args, **kwargs):
            self.calls.append(("info", message, kwargs.get("extra", {})))

        def debug(self, message, *args, **kwargs):
            self.calls.append(("debug", message, kwargs.get("extra", {})))

    logger = DummyLogger()
    times = iter([40.0, 40.018])
    original_get_logger = middleware_module.logging.getLogger
    monkeypatch.setattr(middleware_module, "perf_counter", lambda: next(times))
    monkeypatch.setattr(middleware_module.logging, "getLogger", lambda name=None: logger if name == "django.request" else original_get_logger(name))
    monkeypatch.setenv("DJANGO_LOGKIT_LOG_REQUESTS", "true")
    monkeypatch.setenv("DJANGO_LOGKIT_LOG_REQUEST_HEADERS", "true")
    monkeypatch.setenv("DJANGO_LOGKIT_LOG_RESPONSE_HEADERS", "true")
    monkeypatch.setenv("DJANGO_LOGKIT_LOG_REQUEST_BODY", "true")
    monkeypatch.setenv("DJANGO_LOGKIT_LOG_RESPONSE_BODY", "true")
    request = SimpleNamespace(
        META={"HTTP_X_REQUEST_ID": "req-13"},
        method="GET",
        path="/api/health/",
        get_full_path=lambda: "/api/health/?verbose=1",
        headers={"Authorization": "Bearer secret", "X-Trace-Id": "trace-13"},
        body=b'{"ok":true}',
    )
    class Response(dict):
        status_code = 200
        headers = {"Content-Type": "application/json", "Set-Cookie": "session=value"}
        content = b'{"status":"up"}'

    response = Response()

    RequestIdMiddleware(lambda incoming_request: response)(request)

    assert logger.calls[0] == (
        "info",
        "request_summary",
        {"event": "request_summary", "method": "GET", "path": "/api/health/?verbose=1", "status_code": 200},
    )
    assert logger.calls[1][0] == "debug"
    assert logger.calls[1][1] == "request_headers"
    assert logger.calls[1][2]["headers"]["Authorization"] == "[REDACTED]"
    assert logger.calls[2] == (
        "debug",
        "request_body",
        {"event": "request_body", "body": '{"ok":true}', "method": "GET", "path": "/api/health/?verbose=1"},
    )
    assert logger.calls[3][1] == "response_headers"
    assert logger.calls[3][2]["headers"]["Set-Cookie"] == "[REDACTED]"
    assert logger.calls[4] == (
        "debug",
        "response_body",
        {"event": "response_body", "body": '{"status":"up"}', "method": "GET", "path": "/api/health/?verbose=1", "status_code": 200},
    )


def test_request_id_middleware_is_idempotent_when_wrapped_twice(monkeypatch):
    class DummyLogger:
        def __init__(self):
            self.calls = []

        def info(self, message, *args, **kwargs):
            self.calls.append(("info", message, kwargs.get("extra", {})))

        def debug(self, message, *args, **kwargs):
            self.calls.append(("debug", message, kwargs.get("extra", {})))

    logger = DummyLogger()
    times = iter([50.0, 50.010])
    original_get_logger = middleware_module.logging.getLogger
    monkeypatch.setattr(middleware_module, "perf_counter", lambda: next(times))
    monkeypatch.setattr(middleware_module.logging, "getLogger", lambda name=None: logger if name == "django.request" else original_get_logger(name))
    monkeypatch.setattr(middleware_module, "uuid4", lambda: "req-20")
    monkeypatch.setenv("DJANGO_LOGKIT_LOG_REQUESTS", "true")
    request = SimpleNamespace(META={}, method="GET", path="/api/health/", get_full_path=lambda: "/api/health/")

    inner = RequestIdMiddleware(lambda incoming_request: DummyResponse())
    outer = RequestIdMiddleware(inner)

    response = outer(request)

    assert request.request_id == "req-20"
    assert response["X-Request-ID"] == "req-20"
    assert logger.calls == [("info", "request_summary", {"event": "request_summary", "method": "GET", "path": "/api/health/", "status_code": "-"})]
