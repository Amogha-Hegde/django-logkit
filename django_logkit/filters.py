import logging

from .middleware import get_header_name
from .request_id import get_log_context


LOG_RECORD_DEFAULTS = {
    "request_id": "-",
    "trace_id": "-",
    "span_id": "-",
    "user_id": None,
    "tenant": None,
    "duration_ms": None,
}


def _resolve_request_attribute(request, field_name):
    if request is None:
        return None

    meta = getattr(request, "META", {})
    if field_name == "request_id":
        return getattr(request, "request_id", None) or meta.get(get_header_name("request_id"))
    if field_name == "trace_id":
        return getattr(request, "trace_id", None) or meta.get(get_header_name("trace_id"))
    if field_name == "span_id":
        return getattr(request, "span_id", None) or meta.get(get_header_name("span_id"))
    if field_name == "tenant":
        tenant = getattr(request, "tenant", None)
        if tenant is not None:
            return getattr(tenant, "slug", None) or getattr(tenant, "id", None) or getattr(tenant, "pk", None) or tenant
        return getattr(request, "tenant_id", None) or meta.get(get_header_name("tenant"))

    if field_name == "user_id":
        user_id = getattr(request, "user_id", None)
        if user_id is not None:
            return user_id

        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            return getattr(user, "pk", None) or getattr(user, "id", None)
        return None

    return getattr(request, field_name, None)


def _resolve_record_value(record, field_name):
    if hasattr(record, field_name):
        value = getattr(record, field_name)
        if value is not None:
            return value

    context_value = get_log_context().get(field_name)
    if context_value is not None:
        return context_value

    request = getattr(record, "request", None)
    request_value = _resolve_request_attribute(request, field_name)
    if request_value is not None:
        return request_value

    return LOG_RECORD_DEFAULTS[field_name]


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        for field_name in LOG_RECORD_DEFAULTS:
            setattr(record, field_name, _resolve_record_value(record, field_name))
        return True
