import logging
import math
import os
from time import perf_counter
from uuid import uuid4

from .request_id import bind_log_context, clear_pending_server_log_context, set_pending_server_log_context


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
    "project_id": "DJANGO_LOGKIT_PROJECT_ID_HEADER",
    "org_id": "DJANGO_LOGKIT_ORG_ID_HEADER",
    "tenant": "DJANGO_LOGKIT_TENANT_HEADER",
}
DEFAULT_HEADER_NAMES = {
    "request_id": "HTTP_X_REQUEST_ID",
    "trace_id": "HTTP_X_TRACE_ID",
    "span_id": "HTTP_X_SPAN_ID",
    "project_id": "HTTP_X_PROJECT_ID",
    "org_id": "HTTP_X_ORG_ID",
    "tenant": "HTTP_X_TENANT",
}
DEFAULT_REDACTED_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key", "proxy-authorization"}
LOG_FLAG_ENV_VARS = {
    "request_summary": "DJANGO_LOGKIT_LOG_REQUESTS",
    "request_headers": "DJANGO_LOGKIT_LOG_REQUEST_HEADERS",
    "response_headers": "DJANGO_LOGKIT_LOG_RESPONSE_HEADERS",
    "request_body": "DJANGO_LOGKIT_LOG_REQUEST_BODY",
    "response_body": "DJANGO_LOGKIT_LOG_RESPONSE_BODY",
}
REQUEST_LOGGER_ENV_VAR = "DJANGO_LOGKIT_REQUEST_LOGGER"
BODY_MAX_LENGTH_ENV_VAR = "DJANGO_LOGKIT_BODY_MAX_LENGTH"
REQUEST_GUARD_ATTR = "_django_logkit_request_middleware_applied"
REQUEST_SUMMARY_EVENT = "request_summary"
REQUEST_HEADERS_EVENT = "request_headers"
RESPONSE_HEADERS_EVENT = "response_headers"
REQUEST_BODY_EVENT = "request_body"
RESPONSE_BODY_EVENT = "response_body"


def _get_env_flag(env_var, default=False):
    value = os.getenv(env_var)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_body_max_length():
    value = os.getenv(BODY_MAX_LENGTH_ENV_VAR, "4096").strip()
    try:
        return max(0, int(value))
    except ValueError:
        return 4096


def _normalize_header_name(header_name):
    if header_name.startswith("HTTP_"):
        header_name = header_name[5:]
    return "-".join(part if part in {"ID", "B3"} else part.title() for part in header_name.split("_"))


def _get_redacted_headers():
    custom_headers = os.getenv("DJANGO_LOGKIT_REDACT_HEADERS")
    if custom_headers is None:
        return set(DEFAULT_REDACTED_HEADERS)
    return {header.strip().lower() for header in custom_headers.split(",") if header.strip()}


def _redact_headers(headers):
    redacted_headers = _get_redacted_headers()
    redacted = {}
    for key, value in headers.items():
        if key.lower() in redacted_headers:
            redacted[key] = "[REDACTED]"
        else:
            redacted[key] = value
    return redacted


def _extract_request_headers(request):
    headers = getattr(request, "headers", None)
    if headers is not None:
        return _redact_headers(dict(headers))

    meta = getattr(request, "META", {})
    extracted = {}
    for key, value in meta.items():
        if key.startswith("HTTP_") or key in {"CONTENT_TYPE", "CONTENT_LENGTH"}:
            extracted[_normalize_header_name(key)] = value
    return _redact_headers(extracted)


def _extract_response_headers(response):
    headers = getattr(response, "headers", None)
    if headers is not None:
        return _redact_headers(dict(headers))

    if hasattr(response, "items"):
        return _redact_headers(dict(response.items()))

    return {}


def _decode_body(value, max_length):
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    else:
        value = str(value)
    if len(value) > max_length:
        return value[:max_length] + "...[truncated]"
    return value


def _extract_request_body(request, max_length):
    try:
        return _decode_body(getattr(request, "body", None), max_length)
    except Exception:
        return None


def _extract_response_body(response, max_length):
    try:
        return _decode_body(getattr(response, "content", None), max_length)
    except Exception:
        return None


def _calculate_duration_ms(started_at, finished_at):
    elapsed_ms = (finished_at - started_at) * 1000
    if elapsed_ms < 0:
        return 0
    return max(1, int(math.ceil(elapsed_ms)))


def get_header_name(field_name):
    return os.getenv(HEADER_ENV_VARS[field_name], DEFAULT_HEADER_NAMES[field_name]).strip() or DEFAULT_HEADER_NAMES[field_name]


def get_response_header_name(field_name):
    header_name = get_header_name(field_name)
    return _normalize_header_name(header_name)


class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.header_name = get_header_name("request_id")
        self.trace_header_name = get_header_name("trace_id")
        self.span_header_name = get_header_name("span_id")
        self.project_header_name = get_header_name("project_id")
        self.org_header_name = get_header_name("org_id")
        self.tenant_header_name = get_header_name("tenant")
        self.response_header_name = get_response_header_name("request_id")
        self.request_logger = logging.getLogger(os.getenv(REQUEST_LOGGER_ENV_VAR, "django.request"))
        self.log_request_summary = _get_env_flag(LOG_FLAG_ENV_VARS["request_summary"])
        self.log_request_headers = _get_env_flag(LOG_FLAG_ENV_VARS["request_headers"])
        self.log_response_headers = _get_env_flag(LOG_FLAG_ENV_VARS["response_headers"])
        self.log_request_body = _get_env_flag(LOG_FLAG_ENV_VARS["request_body"])
        self.log_response_body = _get_env_flag(LOG_FLAG_ENV_VARS["response_body"])
        self.body_max_length = _get_body_max_length()

    def _log_request_response(self, request, response):
        path = getattr(request, "get_full_path", lambda: getattr(request, "path", "/"))()
        method = getattr(request, "method", "GET")
        status_code = getattr(response, "status_code", "-")

        if self.log_request_summary:
            self.request_logger.info(
                REQUEST_SUMMARY_EVENT,
                extra={
                    "event": REQUEST_SUMMARY_EVENT,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                },
            )
        if self.log_request_headers:
            self.request_logger.debug(
                REQUEST_HEADERS_EVENT,
                extra={
                    "event": REQUEST_HEADERS_EVENT,
                    "headers": _extract_request_headers(request),
                    "method": method,
                    "path": path,
                },
            )
        if self.log_request_body:
            body = _extract_request_body(request, self.body_max_length)
            if body is not None:
                self.request_logger.debug(
                    REQUEST_BODY_EVENT,
                    extra={
                        "event": REQUEST_BODY_EVENT,
                        "body": body,
                        "method": method,
                        "path": path,
                    },
                )
        if self.log_response_headers:
            self.request_logger.debug(
                RESPONSE_HEADERS_EVENT,
                extra={
                    "event": RESPONSE_HEADERS_EVENT,
                    "headers": _extract_response_headers(response),
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                },
            )
        if self.log_response_body:
            body = _extract_response_body(response, self.body_max_length)
            if body is not None:
                self.request_logger.debug(
                    RESPONSE_BODY_EVENT,
                    extra={
                        "event": RESPONSE_BODY_EVENT,
                        "body": body,
                        "method": method,
                        "path": path,
                        "status_code": status_code,
                    },
                )

    def __call__(self, request):
        if getattr(request, REQUEST_GUARD_ATTR, False):
            response = self.get_response(request)
            if hasattr(request, "request_id") and self.response_header_name not in response:
                response[self.response_header_name] = request.request_id
            return response

        setattr(request, REQUEST_GUARD_ATTR, True)
        clear_pending_server_log_context()
        started_at = perf_counter()
        request_id = request.META.get(self.header_name) or str(uuid4())
        trace_id = request.META.get(self.trace_header_name)
        span_id = request.META.get(self.span_header_name)
        project_id = request.META.get(self.project_header_name)
        org_id = request.META.get(self.org_header_name)
        tenant = _resolve_tenant(request)
        if tenant is None:
            tenant = request.META.get(self.tenant_header_name)
        user_id = _resolve_user_id(request)

        request.request_id = request_id
        request.trace_id = trace_id
        request.span_id = span_id
        request.project_id = project_id
        request.org_id = org_id
        request.tenant = tenant
        request.user_id = user_id

        binding = bind_log_context(
            request_id=request_id,
            trace_id=trace_id,
            span_id=span_id,
            project_id=project_id,
            org_id=org_id,
            tenant=tenant,
            user_id=user_id,
        )
        binding.__enter__()
        response = None
        try:
            response = self.get_response(request)
        finally:
            request.duration_ms = _calculate_duration_ms(started_at, perf_counter())
            if response is not None:
                with bind_log_context(duration_ms=request.duration_ms):
                    self._log_request_response(request, response)
            set_pending_server_log_context(
                {
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "project_id": project_id,
                    "org_id": org_id,
                    "tenant": tenant,
                    "user_id": user_id,
                    "duration_ms": request.duration_ms,
                }
            )
            binding.__exit__(None, None, None)

        response[self.response_header_name] = request_id
        return response


RequestIdMiddleware = RequestContextMiddleware
