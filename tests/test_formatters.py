import importlib
import logging
import sys
import types

import pytest

import django_logkit.formatters as formatters


def make_record(message="hello"):
    return logging.LogRecord(
        name="payments.service",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg=message,
        args=(),
        exc_info=None,
        func="create_invoice",
    )


def test_safe_plain_formatter_injects_request_id():
    formatter = formatters.SafePlainFormatter("%(message)s [%(request_id)s]")
    record = make_record()

    assert formatter.format(record) == "hello [-]"


def test_safe_plain_formatter_uses_configured_timezone():
    formatter = formatters.SafePlainFormatter("%(asctime)s %(message)s", log_timezone="UTC")
    record = make_record()
    record.created = 0

    assert formatter.format(record).startswith("1970-01-01 00:00:00.000+00:00 hello")


def test_safe_plain_formatter_renders_structured_event_message():
    formatter = formatters.SafePlainFormatter("%(message)s [%(request_id)s]")
    record = make_record("ignored")
    record.event = "response_headers"
    record.path = "/api/health/"
    record.status_code = 500
    record.headers = {"Content-Type": "application/json"}
    record.request_id = "req-1"

    rendered = formatter.format(record)

    assert rendered == "response_headers path=/api/health/ status_code=500 headers={'Content-Type': 'application/json'} [req-1]"


def test_safe_colored_formatter_falls_back_without_colorlog(monkeypatch):
    original_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "colorlog":
            raise ImportError("missing colorlog")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.warns(RuntimeWarning, match="colorlog is not installed"):
        formatter = formatters.SafeColoredFormatter("%(message)s [%(request_id)s]")

    record = make_record()
    assert formatter.format(record) == "hello [-]"


def test_safe_colored_formatter_strips_log_color_field_when_falling_back(monkeypatch):
    original_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "colorlog":
            raise ImportError("missing colorlog")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.warns(RuntimeWarning, match="colorlog is not installed"):
        formatter = formatters.SafeColoredFormatter("%(log_color)s%(message)s [%(request_id)s]")

    record = make_record()

    assert formatter.format(record) == "hello [-]"


def test_safe_colored_formatter_uses_colorlog_when_available(monkeypatch):
    class DummyColoredFormatter:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def format(self, record):
            return f"colored:{record.getMessage()}:{record.request_id}"

    dummy_module = types.SimpleNamespace(ColoredFormatter=DummyColoredFormatter)
    monkeypatch.setitem(sys.modules, "colorlog", dummy_module)

    formatter = formatters.SafeColoredFormatter("%(message)s [%(request_id)s]")
    record = make_record()

    assert formatter.format(record) == "colored:hello:-"


def test_safe_colored_formatter_renders_structured_event_when_colorlog_available(monkeypatch):
    class DummyColoredFormatter:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def format(self, record):
            return record.getMessage()

    dummy_module = types.SimpleNamespace(ColoredFormatter=DummyColoredFormatter)
    monkeypatch.setitem(sys.modules, "colorlog", dummy_module)

    formatter = formatters.SafeColoredFormatter("%(message)s")
    record = make_record("ignored")
    record.event = "request_summary"
    record.method = "GET"
    record.path = "/api/health/"
    record.status_code = 200

    rendered = formatter.format(record)

    assert rendered == "request_summary method=GET path=/api/health/ status_code=200"


def test_json_formatter_uses_json_fallback(monkeypatch):
    formatter = formatters.JsonFormatter()
    record = make_record("invoice created")
    record.event = "request_summary"
    record.method = "GET"
    record.path = "/api/health/"
    record.headers = {"Host": "localhost:8000"}
    record.body = '{"ok":true}'
    record.request_id = "req-1"
    record.trace_id = "trace-1"
    record.span_id = "span-1"
    record.user_id = "user-1"
    record.tenant = "tenant-1"
    record.duration_ms = 42
    monkeypatch.setattr(formatters, "orjson", None)
    monkeypatch.setenv("DJANGO_LOGKIT_SERVICE_NAME", "billing-api")
    monkeypatch.setenv("DJANGO_LOGKIT_ENVIRONMENT", "production")
    monkeypatch.setattr(formatters.socket, "gethostname", lambda: "app-worker-01")

    rendered = formatter.format(record)

    assert '"logger": "payments.service"' in rendered
    assert '"event": "request_summary"' in rendered
    assert '"method": "GET"' in rendered
    assert '"path": "/api/health/"' in rendered
    assert '"headers": {"Host": "localhost:8000"}' in rendered
    assert '"body": "{\\"ok\\":true}"' in rendered
    assert '"request_id": "req-1"' in rendered
    assert '"trace_id": "trace-1"' in rendered
    assert '"span_id": "span-1"' in rendered
    assert '"user_id": "user-1"' in rendered
    assert '"tenant": "tenant-1"' in rendered
    assert '"duration_ms": 42' in rendered
    assert '"service": "billing-api"' in rendered
    assert '"environment": "production"' in rendered
    assert '"hostname": "app-worker-01"' in rendered


def test_json_formatter_uses_orjson_when_available(monkeypatch):
    formatter = formatters.JsonFormatter()
    record = make_record("invoice created")

    class DummyOrjson:
        @staticmethod
        def dumps(payload, default):
            assert payload["message"] == "invoice created"
            return b'{"ok":true}'

    monkeypatch.setattr(formatters, "orjson", DummyOrjson())

    assert formatter.format(record) == '{"ok":true}'


def test_json_formatter_supports_dynamic_json_fields(monkeypatch):
    formatter = formatters.JsonFormatter(
        json_fields={
            "ts": "timestamp",
            "severity": "levelname",
            "logger_name": "name",
            "time": "asctime",
            "msg": "message",
            "rid": "request_id",
            "latency_ms": "duration_ms",
            "tenant_key": "tenant",
        }
    )
    record = make_record("invoice created")
    record.request_id = "req-2"
    record.duration_ms = 9
    record.tenant = "tenant-2"
    monkeypatch.setattr(formatters, "orjson", None)

    rendered = formatter.format(record)

    assert '"ts":' in rendered
    assert '"severity": "INFO"' in rendered
    assert '"logger_name": "payments.service"' in rendered
    assert '"time":' in rendered
    assert '"msg": "invoice created"' in rendered
    assert '"rid": "req-2"' in rendered
    assert '"latency_ms": 9' in rendered
    assert '"tenant_key": "tenant-2"' in rendered
    assert '"message":' not in rendered


def test_json_formatter_uses_configured_timezone(monkeypatch):
    formatter = formatters.JsonFormatter(json_fields={"ts": "timestamp", "time": "asctime"}, log_timezone="UTC")
    record = make_record("invoice created")
    record.created = 0
    monkeypatch.setattr(formatters, "orjson", None)

    rendered = formatter.format(record)

    assert '"ts": "1970-01-01T00:00:00+00:00"' in rendered
    assert '"time": "1970-01-01 00:00:00.000+00:00"' in rendered


def test_json_formatter_includes_exception(monkeypatch):
    formatter = formatters.JsonFormatter()
    monkeypatch.setattr(formatters, "orjson", None)

    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="payments.service",
        level=logging.ERROR,
        pathname=__file__,
        lineno=20,
        msg="failed",
        args=(),
        exc_info=exc_info,
        func="create_invoice",
    )

    rendered = formatter.format(record)

    assert '"exception":' in rendered
    assert "ValueError: boom" in rendered


def test_json_formatter_parses_django_server_access_log(monkeypatch):
    formatter = formatters.JsonFormatter()
    monkeypatch.setattr(formatters, "orjson", None)
    monkeypatch.setattr(formatters.socket, "gethostname", lambda: "app-worker-01")

    record = logging.LogRecord(
        name="django.server",
        level=logging.INFO,
        pathname=__file__,
        lineno=213,
        msg='"%s" %s %s',
        args=("GET /api/health/ HTTP/1.1", "200", "15"),
        exc_info=None,
        func="log_message",
    )
    record.request_id = "req-5"

    rendered = formatter.format(record)

    assert '"message": "GET /api/health/ HTTP/1.1"' in rendered
    assert '"request_line": "GET /api/health/ HTTP/1.1"' in rendered
    assert '"status_code": 200' in rendered
    assert '"response_size": 15' in rendered
    assert '\\"GET /api/health/ HTTP/1.1\\" 200 15' not in rendered
