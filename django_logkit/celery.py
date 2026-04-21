from contextlib import contextmanager

from .request_id import bind_log_context, get_log_context, get_request_id, reset_request_id, set_request_id


REQUEST_ID_HEADER = "x-request-id"
TRACE_ID_HEADER = "x-trace-id"
SPAN_ID_HEADER = "x-span-id"


def build_celery_headers(request_id=None, trace_id=None, span_id=None):
    current_context = get_log_context()
    headers = {}

    resolved_request_id = request_id or get_request_id()
    if resolved_request_id:
        headers[REQUEST_ID_HEADER] = resolved_request_id

    resolved_trace_id = trace_id or current_context["trace_id"]
    if resolved_trace_id:
        headers[TRACE_ID_HEADER] = resolved_trace_id

    resolved_span_id = span_id or current_context["span_id"]
    if resolved_span_id:
        headers[SPAN_ID_HEADER] = resolved_span_id

    return headers


def extract_request_id_from_task(task):
    return extract_log_context_from_task(task)["request_id"]


def extract_log_context_from_task(task):
    task_request = getattr(task, "request", None)
    if task_request is None:
        return {"request_id": None, "trace_id": None, "span_id": None}

    headers = getattr(task_request, "headers", None) or {}
    return {
        "request_id": headers.get(REQUEST_ID_HEADER) or getattr(task_request, "request_id", None),
        "trace_id": headers.get(TRACE_ID_HEADER),
        "span_id": headers.get(SPAN_ID_HEADER),
    }


@contextmanager
def bind_request_id_from_task(task=None, request_id=None):
    resolved_request_id = request_id or extract_request_id_from_task(task)
    token = None

    if resolved_request_id:
        token = set_request_id(resolved_request_id)

    try:
        yield resolved_request_id
    finally:
        if token is not None:
            reset_request_id(token)


@contextmanager
def bind_log_context_from_task(task=None, request_id=None, trace_id=None, span_id=None):
    extracted_context = extract_log_context_from_task(task)
    with bind_log_context(
        request_id=request_id or extracted_context["request_id"],
        trace_id=trace_id or extracted_context["trace_id"],
        span_id=span_id or extracted_context["span_id"],
    ) as values:
        yield values
