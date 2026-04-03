from contextvars import ContextVar
from functools import wraps


class _Missing:
    pass


_MISSING = _Missing()

LOG_CONTEXT_FIELDS = (
    "request_id",
    "trace_id",
    "span_id",
    "user_id",
    "tenant",
    "duration_ms",
)

_context_vars = {field_name: ContextVar(f"django_logkit_{field_name}", default=None) for field_name in LOG_CONTEXT_FIELDS}
_pending_server_log_context = ContextVar("django_logkit_pending_server_log_context", default=None)


def _get_context_value(field_name):
    return _context_vars[field_name].get()


def _set_context_value(field_name, value):
    return _context_vars[field_name].set(value)


def _reset_context_value(field_name, token):
    _context_vars[field_name].reset(token)


def _resolve_bound_value(field_name, value):
    if value is _MISSING:
        return _get_context_value(field_name)
    return value


def get_log_context():
    return {field_name: _get_context_value(field_name) for field_name in LOG_CONTEXT_FIELDS}


def set_pending_server_log_context(context):
    return _pending_server_log_context.set(dict(context))


def get_pending_server_log_context():
    return _pending_server_log_context.get()


def clear_pending_server_log_context():
    _pending_server_log_context.set(None)


def bind_log_context(
    request_id=_MISSING,
    trace_id=_MISSING,
    span_id=_MISSING,
    user_id=_MISSING,
    tenant=_MISSING,
    duration_ms=_MISSING,
):
    resolved_values = {
        "request_id": _resolve_bound_value("request_id", request_id),
        "trace_id": _resolve_bound_value("trace_id", trace_id),
        "span_id": _resolve_bound_value("span_id", span_id),
        "user_id": _resolve_bound_value("user_id", user_id),
        "tenant": _resolve_bound_value("tenant", tenant),
        "duration_ms": _resolve_bound_value("duration_ms", duration_ms),
    }

    class _LogContextBinding:
        def __enter__(self):
            self._tokens = {}
            for field_name, value in resolved_values.items():
                if value is not None:
                    self._tokens[field_name] = _set_context_value(field_name, value)
            return dict(resolved_values)

        def __exit__(self, exc_type, exc, tb):
            for field_name, token in reversed(tuple(self._tokens.items())):
                _reset_context_value(field_name, token)

    return _LogContextBinding()


def wrap_with_log_context(
    func,
    request_id=_MISSING,
    trace_id=_MISSING,
    span_id=_MISSING,
    user_id=_MISSING,
    tenant=_MISSING,
    duration_ms=_MISSING,
):
    resolved_values = {
        "request_id": _resolve_bound_value("request_id", request_id),
        "trace_id": _resolve_bound_value("trace_id", trace_id),
        "span_id": _resolve_bound_value("span_id", span_id),
        "user_id": _resolve_bound_value("user_id", user_id),
        "tenant": _resolve_bound_value("tenant", tenant),
        "duration_ms": _resolve_bound_value("duration_ms", duration_ms),
    }

    @wraps(func)
    def _wrapped(*args, **kwargs):
        with bind_log_context(**resolved_values):
            return func(*args, **kwargs)

    return _wrapped


def get_request_id():
    return _get_context_value("request_id")


def set_request_id(value):
    return _set_context_value("request_id", value)


def reset_request_id(token):
    _reset_context_value("request_id", token)


def bind_request_id(request_id=_MISSING):
    class _RequestIdBinding:
        def __enter__(self):
            self._binding = bind_log_context(request_id=request_id)
            values = self._binding.__enter__()
            return values["request_id"]

        def __exit__(self, exc_type, exc, tb):
            return self._binding.__exit__(exc_type, exc, tb)

    return _RequestIdBinding()


def wrap_with_request_id(func, request_id=_MISSING):
    resolved_request_id = _resolve_bound_value("request_id", request_id)

    @wraps(func)
    def _wrapped(*args, **kwargs):
        with bind_request_id(resolved_request_id):
            return func(*args, **kwargs)

    return _wrapped
