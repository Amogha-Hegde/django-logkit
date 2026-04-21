import json
import logging
import os
import re
import socket
import warnings
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    import orjson
except ImportError:  # pragma: no cover - optional dependency
    orjson = None


DEFAULT_JSON_FIELDS = {
    "timestamp": "timestamp",
    "level": "levelname",
    "hostname": "hostname",
    "logger": "name",
    "event": "event",
    "message": "message",
    "module": "module",
    "function": "funcName",
    "line": "lineno",
    "process": "process",
    "thread": "thread",
    "method": "method",
    "path": "path",
    "headers": "headers",
    "body": "body",
    "request_id": "request_id",
    "trace_id": "trace_id",
    "span_id": "span_id",
    "project_id": "project_id",
    "org_id": "org_id",
    "user_id": "user_id",
    "tenant": "tenant",
    "duration_ms": "duration_ms",
    "drf_view": "drf_view",
    "drf_action": "drf_action",
    "drf_serializer": "drf_serializer",
}
DJANGO_SERVER_LOGGER = "django.server"
DJANGO_SERVER_EVENT = "request_summary"
VALID_DJANGO_SERVER_MESSAGE_MODES = {"request_line", "event"}
DJANGO_SERVER_MESSAGE_PATTERN = re.compile(r'^"(?P<request_line>.+)" (?P<status_code>\d{3}) (?P<response_size>\S+)$')
REQUEST_LINE_PATTERN = re.compile(r"^(?P<method>\S+)\s+(?P<path>\S+)\s+(?P<http_version>\S+)$")
STRUCTURED_EVENT_FIELDS = ("event", "method", "path", "status_code", "headers", "body")
DEFAULT_TEXT_FIELD_DEFAULTS = {
    "request_id": "-",
    "trace_id": "-",
    "span_id": "-",
    "project_id": "-",
    "org_id": "-",
    "user_id": None,
    "tenant": "-",
    "duration_ms": "-",
}


def _strip_color_fields(fmt):
    if fmt is None:
        return None
    return fmt.replace("%(log_color)s", "")


def _resolve_timezone(log_timezone):
    if log_timezone is None:
        return timezone.utc

    if not isinstance(log_timezone, str) or not log_timezone.strip():
        raise ValueError("log_timezone must be a non-empty string or None")

    normalized_log_timezone = log_timezone.strip()
    if normalized_log_timezone.lower() == "utc":
        return timezone.utc
    if normalized_log_timezone.lower() == "local":
        return datetime.now().astimezone().tzinfo

    try:
        return ZoneInfo(normalized_log_timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown log_timezone: {normalized_log_timezone}") from exc


def _format_structured_event_message(record):
    event = getattr(record, "event", None)
    if not event:
        return None

    parts = [event]
    for field_name in STRUCTURED_EVENT_FIELDS[1:]:
        value = getattr(record, field_name, None)
        if value is not None:
            parts.append(f"{field_name}={value}")
    return " ".join(parts)


class SafePlainFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, style="%", validate=True, log_timezone=None, text_field_defaults=None):
        super().__init__(fmt=fmt, datefmt=datefmt, style=style, validate=validate)
        self.log_timezone = _resolve_timezone(log_timezone)
        self.text_field_defaults = dict(DEFAULT_TEXT_FIELD_DEFAULTS)
        if text_field_defaults:
            self.text_field_defaults.update(text_field_defaults)

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=self.log_timezone)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat(sep=" ", timespec="milliseconds")

    def _format_with_structured_message(self, record):
        structured_message = _format_structured_event_message(record)
        if structured_message is None:
            return super().format(record)

        original_msg = record.msg
        original_args = record.args
        try:
            record.msg = structured_message
            record.args = ()
            return super().format(record)
        finally:
            record.msg = original_msg
            record.args = original_args

    def format(self, record):
        for field_name, value in self.text_field_defaults.items():
            if not hasattr(record, field_name):
                setattr(record, field_name, value)
        return self._format_with_structured_message(record)


class SafeColoredFormatter(SafePlainFormatter):
    def __init__(self, fmt=None, datefmt=None, style="%", validate=True, log_colors=None, log_timezone=None, text_field_defaults=None):
        super().__init__(fmt=fmt, datefmt=datefmt, style=style, validate=validate, log_timezone=log_timezone, text_field_defaults=text_field_defaults)
        try:
            from colorlog import ColoredFormatter
        except ImportError:
            warnings.warn(
                "colorlog is not installed; falling back to plain log formatting",
                RuntimeWarning,
                stacklevel=2,
            )
            self._formatter = SafePlainFormatter(
                fmt=_strip_color_fields(fmt),
                datefmt=datefmt,
                style=style,
                validate=validate,
                log_timezone=log_timezone,
                text_field_defaults=text_field_defaults,
            )
        else:
            class _TimezoneAwareColoredFormatter(ColoredFormatter):
                def __init__(self, parent, **kwargs):
                    super().__init__(**kwargs)
                    self._parent = parent

                def formatTime(self, record, datefmt=None):
                    return self._parent.formatTime(record, datefmt)

            self._formatter = _TimezoneAwareColoredFormatter(
                self,
                fmt=fmt,
                datefmt=datefmt,
                style=style,
                validate=validate,
                log_colors=log_colors,
            )

    def format(self, record):
        for field_name, value in self.text_field_defaults.items():
            if not hasattr(record, field_name):
                setattr(record, field_name, value)
        structured_message = _format_structured_event_message(record)
        if structured_message is not None:
            original_msg = record.msg
            original_args = record.args
            try:
                record.msg = structured_message
                record.args = ()
                return self._formatter.format(record)
            finally:
                record.msg = original_msg
                record.args = original_args
        return self._formatter.format(record)


class JsonFormatter(logging.Formatter):
    def __init__(self, json_fields=None, json_field_defaults=None, log_timezone=None, django_server_message_mode="request_line"):
        super().__init__()
        self.json_fields = dict(json_fields or DEFAULT_JSON_FIELDS)
        self.json_field_defaults = dict(json_field_defaults or {})
        self.log_timezone = _resolve_timezone(log_timezone)
        self.hostname = socket.gethostname()
        if django_server_message_mode not in VALID_DJANGO_SERVER_MESSAGE_MODES:
            raise ValueError("django_server_message_mode must be one of: request_line, event")
        self.django_server_message_mode = django_server_message_mode

    def _resolve_field_value(self, record, field_name):
        if field_name == "timestamp":
            return datetime.fromtimestamp(record.created, tz=self.log_timezone).isoformat()
        if field_name == "asctime":
            return self.formatTime(record, self.datefmt)
        if field_name == "message":
            return self._resolve_message(record)
        if field_name == "hostname":
            return self.hostname
        if field_name == "request_id":
            return getattr(record, "request_id", None)
        if field_name in {"method", "path", "http_version", "status_code", "response_size", "request_line"}:
            parsed_server_fields = self._parse_django_server_fields(record)
            if parsed_server_fields is not None and field_name in parsed_server_fields:
                return parsed_server_fields[field_name]
        return getattr(record, field_name, None)

    def _parse_django_server_message(self, record):
        if record.name != DJANGO_SERVER_LOGGER:
            return None

        message = record.getMessage()
        match = DJANGO_SERVER_MESSAGE_PATTERN.match(message)
        if not match:
            return None

        return match.groupdict()

    def _parse_django_server_fields(self, record):
        parsed_message = self._parse_django_server_message(record)
        if parsed_message is None:
            return None

        parsed_fields = dict(parsed_message)
        request_line_match = REQUEST_LINE_PATTERN.match(parsed_message["request_line"])
        if request_line_match is not None:
            parsed_fields.update(request_line_match.groupdict())
        parsed_fields["status_code"] = int(parsed_message["status_code"])
        response_size = parsed_message["response_size"]
        parsed_fields["response_size"] = None if response_size == "-" else int(response_size)
        return parsed_fields

    def _resolve_message(self, record):
        parsed_message = self._parse_django_server_message(record)
        if parsed_message is not None:
            if self.django_server_message_mode == "event":
                return DJANGO_SERVER_EVENT
            return parsed_message["request_line"]
        return record.getMessage()

    def _structured_event_payload(self, record):
        event = getattr(record, "event", None)
        if event is None:
            parsed_server_fields = self._parse_django_server_fields(record)
            if parsed_server_fields is None:
                return {}

            payload = {"event": DJANGO_SERVER_EVENT}
            for field_name in STRUCTURED_EVENT_FIELDS[1:]:
                value = parsed_server_fields.get(field_name)
                if value is not None:
                    payload[field_name] = value
            return payload

        payload = {"event": event}
        for field_name in STRUCTURED_EVENT_FIELDS[1:]:
            value = getattr(record, field_name, None)
            if value is not None:
                payload[field_name] = value
        return payload

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=self.log_timezone)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat(sep=" ", timespec="milliseconds")

    def format(self, record):
        payload = {}
        for output_key, field_name in self.json_fields.items():
            value = self._resolve_field_value(record, field_name)
            if value is None and output_key in self.json_field_defaults:
                value = self.json_field_defaults[output_key]
            if value is not None:
                payload[output_key] = value

        for key, value in self._structured_event_payload(record).items():
            payload.setdefault(key, value)

        parsed_server_fields = self._parse_django_server_fields(record)
        if parsed_server_fields is not None:
            for key, value in parsed_server_fields.items():
                if value is not None:
                    payload.setdefault(key, value)

        service_name = os.getenv("DJANGO_LOGKIT_SERVICE_NAME")
        environment = os.getenv("DJANGO_LOGKIT_ENVIRONMENT")
        if service_name:
            payload["service"] = service_name
        if environment:
            payload["environment"] = environment

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        if orjson is not None:
            return orjson.dumps(payload, default=str).decode("utf-8")

        return json.dumps(payload, ensure_ascii=False, default=str)
