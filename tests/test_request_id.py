from django_logkit.request_id import (
    bind_drf_context,
    bind_log_context,
    bind_request_context,
    bind_request_id,
    bind_trace_context,
    get_log_context,
    get_request_id,
    reset_request_id,
    set_request_id,
    wrap_with_drf_context,
    wrap_with_log_context,
    wrap_with_request_context,
    wrap_with_request_id,
    wrap_with_trace_context,
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


def test_bind_trace_context_sets_trace_and_span():
    with bind_trace_context("trace-3", "span-3") as values:
        assert values == {"trace_id": "trace-3", "span_id": "span-3"}
        assert get_log_context()["trace_id"] == "trace-3"
        assert get_log_context()["span_id"] == "span-3"

    assert get_log_context()["trace_id"] is None
    assert get_log_context()["span_id"] is None


def test_wrap_with_trace_context_captures_current_values():
    with bind_log_context(trace_id="trace-4", span_id="span-4"):
        wrapped = wrap_with_trace_context(get_log_context)

    values = wrapped()
    assert values["trace_id"] == "trace-4"
    assert values["span_id"] == "span-4"


def test_bind_request_context_is_alias_for_request_scoped_fields():
    with bind_request_context(request_id="req-5", trace_id="trace-5", tenant="tenant-5") as values:
        assert values["request_id"] == "req-5"
        assert values["trace_id"] == "trace-5"
        assert values["tenant"] == "tenant-5"


def test_wrap_with_request_context_captures_current_values():
    with bind_request_context(request_id="req-6", project_id="project-6"):
        wrapped = wrap_with_request_context(get_log_context)

    values = wrapped()
    assert values["request_id"] == "req-6"
    assert values["project_id"] == "project-6"


def test_bind_and_wrap_with_drf_context_resolve_names():
    class DummyView:
        pass

    class DummySerializer:
        pass

    with bind_drf_context(view=DummyView, action="list", serializer=DummySerializer):
        values = get_log_context()
        assert values["drf_view"] == "DummyView"
        assert values["drf_action"] == "list"
        assert values["drf_serializer"] == "DummySerializer"

    wrapped = wrap_with_drf_context(get_log_context, view=DummyView(), action="retrieve", serializer=DummySerializer())
    values = wrapped()
    assert values["drf_view"] == "DummyView"
    assert values["drf_action"] == "retrieve"
    assert values["drf_serializer"] == "DummySerializer"
