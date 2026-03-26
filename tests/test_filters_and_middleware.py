from types import SimpleNamespace

from django_logkit.filters import RequestIdFilter
from django_logkit.middleware import RequestIdMiddleware
from django_logkit.request_id import get_request_id, set_request_id, reset_request_id


def test_request_id_filter_sets_record_value():
    token = set_request_id("req-1")
    try:
        record = SimpleNamespace()
        result = RequestIdFilter().filter(record)
    finally:
        reset_request_id(token)

    assert result is True
    assert record.request_id == "req-1"


def test_request_id_filter_uses_dash_when_missing():
    record = SimpleNamespace()

    RequestIdFilter().filter(record)

    assert record.request_id == "-"


class DummyResponse(dict):
    pass


def test_request_id_middleware_uses_existing_header():
    request = SimpleNamespace(META={"HTTP_X_REQUEST_ID": "req-2"})

    def get_response(incoming_request):
        assert incoming_request.request_id == "req-2"
        assert get_request_id() == "req-2"
        return DummyResponse()

    response = RequestIdMiddleware(get_response)(request)

    assert response["X-Request-ID"] == "req-2"
    assert get_request_id() is None


def test_request_id_middleware_generates_header_when_missing():
    request = SimpleNamespace(META={})

    response = RequestIdMiddleware(lambda incoming_request: DummyResponse())(request)

    assert "X-Request-ID" in response
    assert request.request_id == response["X-Request-ID"]
    assert get_request_id() is None
