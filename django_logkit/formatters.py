import json
import logging
import os
import re
import socket
import warnings
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

try:
    import orjson
except ImportError:  # pragma: no cover - optional dependency
    orjson = None


DEFAULT_JSON_FIELDS = {
    "timestamp": "timestamp",
    "level": "levelname",
    "hostname": "hostname",
    "logger": "name",
    "message": "message",
    "module": "module",
    "function": "funcName",
    "line": "lineno",
    "process": "process",
    "thread": "thread",
    "request_id": "request_id",
}
DJANGO_SERVER_LOGGER = "django.server"
DJANGO_SERVER_MESSAGE_PATTERN = re.compile(r'^"(?P<request_line>.+)" (?P<status_code>\d{3}) (?P<response_size>\S+)$')


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

    return ZoneInfo(normalized_log_timezone)


class SafePlainFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, style="%", validate=True, log_timezone=None):
        super().__init__(fmt=fmt, datefmt=datefmt, style=style, validate=validate)
        self.log_timezone = _resolve_timezone(log_timezone)

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=self.log_timezone)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat(sep=" ", timespec="milliseconds")

    def format(self, record):
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return super().format(record)


class SafeColoredFormatter(SafePlainFormatter):
    def __init__(self, fmt=None, datefmt=None, style="%", validate=True, log_colors=None, log_timezone=None):
        super().__init__(fmt=fmt, datefmt=datefmt, style=style, validate=validate, log_timezone=log_timezone)
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
            )
        else:
            self._formatter = ColoredFormatter(
                fmt=fmt,
                datefmt=datefmt,
                style=style,
                validate=validate,
                log_colors=log_colors,
            )
            self._formatter.formatTime = self.formatTime

    def format(self, record):
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return self._formatter.format(record)


class JsonFormatter(logging.Formatter):
    def __init__(self, json_fields=None, log_timezone=None):
        super().__init__()
        self.json_fields = dict(json_fields or DEFAULT_JSON_FIELDS)
        self.log_timezone = _resolve_timezone(log_timezone)

    def _resolve_field_value(self, record, field_name):
        if field_name == "timestamp":
            return datetime.fromtimestamp(record.created, tz=self.log_timezone).isoformat()
        if field_name == "asctime":
            return self.formatTime(record, self.datefmt)
        if field_name == "message":
            return self._resolve_message(record)
        if field_name == "hostname":
            return socket.gethostname()
        if field_name == "request_id":
            return getattr(record, "request_id", None)
        return getattr(record, field_name, None)

    def _parse_django_server_message(self, record):
        if record.name != DJANGO_SERVER_LOGGER:
            return None

        message = record.getMessage()
        match = DJANGO_SERVER_MESSAGE_PATTERN.match(message)
        if not match:
            return None

        return match.groupdict()

    def _resolve_message(self, record):
        parsed_message = self._parse_django_server_message(record)
        if parsed_message is not None:
            return parsed_message["request_line"]
        return record.getMessage()

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=self.log_timezone)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat(sep=" ", timespec="milliseconds")

    def format(self, record):
        payload = {}
        for output_key, field_name in self.json_fields.items():
            value = self._resolve_field_value(record, field_name)
            if value is not None:
                payload[output_key] = value

        parsed_message = self._parse_django_server_message(record)
        if parsed_message is not None:
            payload["request_line"] = parsed_message["request_line"]
            payload["status_code"] = int(parsed_message["status_code"])
            response_size = parsed_message["response_size"]
            payload["response_size"] = None if response_size == "-" else int(response_size)

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
