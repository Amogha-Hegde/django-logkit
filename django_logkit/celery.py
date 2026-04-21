from contextlib import contextmanager

from .request_id import bind_log_context, get_log_context, get_request_id, reset_request_id, set_request_id


REQUEST_ID_HEADER = "x-request-id"
TRACE_ID_HEADER = "x-trace-id"
SPAN_ID_HEADER = "x-span-id"
PROJECT_ID_HEADER = "x-project-id"
ORG_ID_HEADER = "x-org-id"
TENANT_HEADER = "x-tenant"
USER_ID_HEADER = "x-user-id"


def build_celery_headers(request_id=None, trace_id=None, span_id=None, project_id=None, org_id=None, tenant=None, user_id=None):
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

    resolved_project_id = project_id or current_context["project_id"]
    if resolved_project_id:
        headers[PROJECT_ID_HEADER] = resolved_project_id

    resolved_org_id = org_id or current_context["org_id"]
    if resolved_org_id:
        headers[ORG_ID_HEADER] = resolved_org_id

    resolved_tenant = tenant or current_context["tenant"]
    if resolved_tenant:
        headers[TENANT_HEADER] = resolved_tenant

    resolved_user_id = user_id or current_context["user_id"]
    if resolved_user_id:
        headers[USER_ID_HEADER] = resolved_user_id

    return headers


def extract_request_id_from_task(task):
    return extract_log_context_from_task(task)["request_id"]


def extract_log_context_from_task(task):
    task_request = getattr(task, "request", None)
    if task_request is None:
        return {
            "request_id": None,
            "trace_id": None,
            "span_id": None,
            "project_id": None,
            "org_id": None,
            "tenant": None,
            "user_id": None,
        }

    headers = getattr(task_request, "headers", None) or {}
    return {
        "request_id": headers.get(REQUEST_ID_HEADER) or getattr(task_request, "request_id", None),
        "trace_id": headers.get(TRACE_ID_HEADER),
        "span_id": headers.get(SPAN_ID_HEADER),
        "project_id": headers.get(PROJECT_ID_HEADER),
        "org_id": headers.get(ORG_ID_HEADER),
        "tenant": headers.get(TENANT_HEADER),
        "user_id": headers.get(USER_ID_HEADER),
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
def bind_log_context_from_task(task=None, request_id=None, trace_id=None, span_id=None, project_id=None, org_id=None, tenant=None, user_id=None):
    extracted_context = extract_log_context_from_task(task)
    with bind_log_context(
        request_id=request_id or extracted_context["request_id"],
        trace_id=trace_id or extracted_context["trace_id"],
        span_id=span_id or extracted_context["span_id"],
        project_id=project_id or extracted_context["project_id"],
        org_id=org_id or extracted_context["org_id"],
        tenant=tenant or extracted_context["tenant"],
        user_id=user_id or extracted_context["user_id"],
    ) as values:
        yield values
