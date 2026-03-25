import json
import logging
import os
import socket
import warnings
from datetime import datetime, timezone

try:
    import orjson
except ImportError:  # pragma: no cover - optional dependency
    orjson = None


class SafePlainFormatter(logging.Formatter):
    def format(self, record):
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return super().format(record)


class SafeColoredFormatter(SafePlainFormatter):
    def __init__(self, fmt=None, datefmt=None, style="%", validate=True, log_colors=None):
        try:
            from colorlog import ColoredFormatter
        except ImportError:
            warnings.warn(
                "colorlog is not installed; falling back to plain log formatting",
                RuntimeWarning,
                stacklevel=2,
            )
            self._formatter = SafePlainFormatter(fmt=fmt, datefmt=datefmt, style=style, validate=validate)
        else:
            self._formatter = ColoredFormatter(
                fmt=fmt,
                datefmt=datefmt,
                style=style,
                validate=validate,
                log_colors=log_colors,
            )

    def format(self, record):
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return self._formatter.format(record)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "hostname": socket.gethostname(),
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process": record.process,
            "thread": record.thread,
        }
        service_name = os.getenv("DJANGO_LOGKIT_SERVICE_NAME")
        environment = os.getenv("DJANGO_LOGKIT_ENVIRONMENT")
        if service_name:
            payload["service"] = service_name
        if environment:
            payload["environment"] = environment

        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        if orjson is not None:
            return orjson.dumps(payload, default=str).decode("utf-8")

        return json.dumps(payload, ensure_ascii=False, default=str)
