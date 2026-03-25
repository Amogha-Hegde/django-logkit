from contextlib import contextmanager

from .request_id import get_request_id, reset_request_id, set_request_id


REQUEST_ID_HEADER = "x-request-id"


def build_celery_headers(request_id=None):
    resolved_request_id = request_id or get_request_id()
    if not resolved_request_id:
        return {}
    return {REQUEST_ID_HEADER: resolved_request_id}


def extract_request_id_from_task(task):
    task_request = getattr(task, "request", None)
    if task_request is None:
        return None

    headers = getattr(task_request, "headers", None) or {}
    if REQUEST_ID_HEADER in headers:
        return headers[REQUEST_ID_HEADER]

    return getattr(task_request, "request_id", None)


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
