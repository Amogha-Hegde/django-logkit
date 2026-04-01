import logging

from .request_id import get_request_id


def _get_request_id_from_record(record):
    request = getattr(record, "request", None)
    if request is None:
        return None

    request_id = getattr(request, "request_id", None)
    if request_id:
        return request_id

    meta = getattr(request, "META", None)
    if isinstance(meta, dict):
        return meta.get("HTTP_X_REQUEST_ID")

    return None


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = get_request_id() or _get_request_id_from_record(record) or "-"
        return True
