import os
from time import perf_counter
from uuid import uuid4

from .request_id import bind_log_context


def _resolve_user_id(request):
    if hasattr(request, "user_id") and getattr(request, "user_id") is not None:
        return request.user_id

    user = getattr(request, "user", None)
    if user is None:
        return None

    if getattr(user, "is_authenticated", False):
        return getattr(user, "pk", None) or getattr(user, "id", None)

    return None


def _resolve_tenant(request):
    if hasattr(request, "tenant") and getattr(request, "tenant") is not None:
        tenant = request.tenant
        return getattr(tenant, "slug", None) or getattr(tenant, "id", None) or getattr(tenant, "pk", None) or tenant

    return getattr(request, "tenant_id", None) or request.META.get(get_header_name("tenant"))


HEADER_ENV_VARS = {
    "request_id": "DJANGO_LOGKIT_REQUEST_ID_HEADER",
    "trace_id": "DJANGO_LOGKIT_TRACE_ID_HEADER",
    "span_id": "DJANGO_LOGKIT_SPAN_ID_HEADER",
    "tenant": "DJANGO_LOGKIT_TENANT_HEADER",
}
DEFAULT_HEADER_NAMES = {
    "request_id": "HTTP_X_REQUEST_ID",
    "trace_id": "HTTP_X_TRACE_ID",
    "span_id": "HTTP_X_SPAN_ID",
    "tenant": "HTTP_X_TENANT",
}


def get_header_name(field_name):
    return os.getenv(HEADER_ENV_VARS[field_name], DEFAULT_HEADER_NAMES[field_name]).strip() or DEFAULT_HEADER_NAMES[field_name]


def get_response_header_name(field_name):
    uppercase_parts = {"ID", "B3"}
    header_name = get_header_name(field_name)
    if header_name.startswith("HTTP_"):
        header_name = header_name[5:]
    return "-".join(part if part in uppercase_parts else part.title() for part in header_name.split("_"))


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.header_name = get_header_name("request_id")
        self.trace_header_name = get_header_name("trace_id")
        self.span_header_name = get_header_name("span_id")
        self.tenant_header_name = get_header_name("tenant")
        self.response_header_name = get_response_header_name("request_id")

    def __call__(self, request):
        started_at = perf_counter()
        request_id = request.META.get(self.header_name) or str(uuid4())
        trace_id = request.META.get(self.trace_header_name)
        span_id = request.META.get(self.span_header_name)
        tenant = _resolve_tenant(request)
        if tenant is None:
            tenant = request.META.get(self.tenant_header_name)
        user_id = _resolve_user_id(request)

        request.request_id = request_id
        request.trace_id = trace_id
        request.span_id = span_id
        request.tenant = tenant
        request.user_id = user_id

        try:
            with bind_log_context(
                request_id=request_id,
                trace_id=trace_id,
                span_id=span_id,
                tenant=tenant,
                user_id=user_id,
            ):
                response = self.get_response(request)
        finally:
            request.duration_ms = max(0, int(round((perf_counter() - started_at) * 1000)))

        response[self.response_header_name] = request_id
        return response
