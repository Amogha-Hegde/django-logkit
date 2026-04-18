from django_logkit.request_id import (
    bind_log_context,
    bind_request_id,
    get_log_context,
    get_request_id,
    reset_request_id,
    set_request_id,
    wrap_with_log_context,
    wrap_with_request_id,
)


def test_set_get_and_reset_request_id():
    token = set_request_id("req-1")
    try:
        assert get_request_id() == "req-1"
    finally:
        reset_request_id(token)

    assert get_request_id() is None


def test_bind_request_id_sets_and_resets():
    assert get_request_id() is None

    with bind_request_id("req-2") as request_id:
        assert request_id == "req-2"
        assert get_request_id() == "req-2"

    assert get_request_id() is None


def test_bind_request_id_uses_existing_when_not_passed():
    token = set_request_id("req-existing")
    try:
        with bind_request_id() as request_id:
            assert request_id == "req-existing"
            assert get_request_id() == "req-existing"
        assert get_request_id() == "req-existing"
    finally:
        reset_request_id(token)


def test_wrap_with_request_id_uses_explicit_value():
    def read_request_id():
        return get_request_id()

    wrapped = wrap_with_request_id(read_request_id, "req-3")

    assert wrapped() == "req-3"
    assert get_request_id() is None


def test_wrap_with_request_id_captures_current_value():
    token = set_request_id("req-4")
    try:
        wrapped = wrap_with_request_id(get_request_id)
    finally:
        reset_request_id(token)

    assert wrapped() == "req-4"


def test_bind_log_context_sets_requested_fields_and_resets():
    assert get_log_context()["trace_id"] is None

    with bind_log_context(
        trace_id="trace-1",
        span_id="span-1",
        project_id="project-1",
        org_id="org-1",
        user_id="user-1",
        tenant="tenant-1",
        duration_ms=123,
    ) as values:
        assert values["trace_id"] == "trace-1"
        assert values["span_id"] == "span-1"
        assert values["project_id"] == "project-1"
        assert values["org_id"] == "org-1"
        assert values["user_id"] == "user-1"
        assert values["tenant"] == "tenant-1"
        assert values["duration_ms"] == 123
        assert get_log_context()["trace_id"] == "trace-1"

    assert get_log_context()["trace_id"] is None
    assert get_log_context()["project_id"] is None
    assert get_log_context()["duration_ms"] is None


def test_wrap_with_log_context_captures_current_values():
    with bind_log_context(trace_id="trace-2", project_id="project-2", org_id="org-2", tenant="tenant-2"):
        wrapped = wrap_with_log_context(get_log_context)

    values = wrapped()

    assert values["trace_id"] == "trace-2"
    assert values["project_id"] == "project-2"
    assert values["org_id"] == "org-2"
    assert values["tenant"] == "tenant-2"
    assert get_log_context()["trace_id"] is None
