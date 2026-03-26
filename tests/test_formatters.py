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


def test_json_formatter_uses_json_fallback(monkeypatch):
    formatter = formatters.JsonFormatter()
    record = make_record("invoice created")
    record.request_id = "req-1"
    monkeypatch.setattr(formatters, "orjson", None)
    monkeypatch.setenv("DJANGO_LOGKIT_SERVICE_NAME", "billing-api")
    monkeypatch.setenv("DJANGO_LOGKIT_ENVIRONMENT", "production")
    monkeypatch.setattr(formatters.socket, "gethostname", lambda: "app-worker-01")

    rendered = formatter.format(record)

    assert '"logger": "payments.service"' in rendered
    assert '"request_id": "req-1"' in rendered
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
