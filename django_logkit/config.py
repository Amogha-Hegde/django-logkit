from pathlib import Path


DJANGO_SERVER = "django.server"
COLOR_FORMATTER = "log_color"
PLAIN_FORMATTER = "log_no_color"
JSON_FORMATTER = "log_json"
REQUEST_ID_FILTER = "request_id"
CONSOLE_HANDLER = "console"
FILE_HANDLER = "file"
DEFAULT_ROOT_LEVEL = "WARNING"
DEFAULT_LOG_BACKUP = 100
DEFAULT_LOG_WHEN = "W0"
DEFAULT_FILE_ENCODING = "utf-8"
DEFAULT_LOG_STYLE = "plain"
DEFAULT_APP_LOGGERS = (
    "billiard",
    "celery",
    "celery.app.trace",
    "celery.redirected",
    "celery.task",
    "django.request",
    "django.response",
    "django_celery_beat",
    "kombu",
    "main",
)
VALID_LOG_WHEN_VALUES = {"S", "M", "H", "D", "MIDNIGHT", "W0", "W1", "W2", "W3", "W4", "W5", "W6"}
VALID_LOG_STYLES = {"plain", "color", "json"}
VALID_LOG_WHEN_VALUES_UPPER = {value.upper() for value in VALID_LOG_WHEN_VALUES}

DEFAULT_LOG_FORMAT = (
    "[%(asctime)s] [%(process)s:%(thread)s] [%(levelname)s] "
    "[%(name)s:%(lineno)d %(funcName)s()] %(message)s"
)
REQUEST_ID_SUFFIX = " [request_id=%(request_id)s]"
DEFAULT_LOG_COLORS = {
    "DEBUG": "blue",
    "INFO": "bold_white",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold_red",
}


def _validate_log_level(log_level):
    if not isinstance(log_level, str) or not log_level.strip():
        raise ValueError("log_level must be a non-empty string")
    return log_level.strip().upper()


def _validate_log_style(log_style, parameter_name):
    if not isinstance(log_style, str) or not log_style.strip():
        raise ValueError(f"{parameter_name} must be a non-empty string")

    normalized_style = log_style.strip().lower()
    if normalized_style not in VALID_LOG_STYLES:
        raise ValueError(f"{parameter_name} must be one of: plain, color, json")

    return normalized_style


def _validate_log_when(log_when):
    if log_when is None:
        return DEFAULT_LOG_WHEN

    if not isinstance(log_when, str) or not log_when.strip():
        raise ValueError("log_when must be a non-empty string")

    normalized_log_when = log_when.strip().upper()
    if normalized_log_when not in VALID_LOG_WHEN_VALUES_UPPER:
        raise ValueError("log_when must be one of S, M, H, D, MIDNIGHT, or W0-W6")

    return normalized_log_when


def _validate_log_backup(log_backup):
    if log_backup is None:
        return DEFAULT_LOG_BACKUP

    if not isinstance(log_backup, int) or log_backup < 0:
        raise ValueError("log_backup must be an integer greater than or equal to 0")

    return log_backup


def _validate_log_file_name(log_file_name):
    if not isinstance(log_file_name, str) or not log_file_name.strip():
        raise ValueError("log_file_name must be a non-empty string")

    path = Path(log_file_name.strip())
    if path.is_absolute() or path.name != path.as_posix():
        raise ValueError("log_file_name must be a file name, not a path")

    return path.name


def _validate_log_format(log_format):
    if log_format is None:
        return DEFAULT_LOG_FORMAT

    if not isinstance(log_format, str) or not log_format.strip():
        raise ValueError("log_format must be a non-empty string")

    return log_format


def _validate_log_colors(log_colors):
    if log_colors is None:
        return dict(DEFAULT_LOG_COLORS)

    if not isinstance(log_colors, dict):
        raise ValueError("log_colors must be a dictionary of level name to color")

    normalized_log_colors = {}
    for level_name, color_name in log_colors.items():
        if not isinstance(level_name, str) or not level_name.strip():
            raise ValueError("log_colors keys must be non-empty strings")
        if not isinstance(color_name, str) or not color_name.strip():
            raise ValueError("log_colors values must be non-empty strings")
        normalized_log_colors[level_name.strip().upper()] = color_name.strip()

    return normalized_log_colors


def _validate_base_dir(base_dir):
    if isinstance(base_dir, Path):
        return base_dir

    if not isinstance(base_dir, str) or not base_dir.strip():
        raise ValueError("base_dir must be a non-empty path string or pathlib.Path")

    return Path(base_dir.strip())


def _normalize_logger_levels(default_level, logger_levels=None):
    normalized_levels = {}

    if logger_levels is None:
        return normalized_levels

    if not isinstance(logger_levels, dict):
        raise ValueError("logger_levels must be a dictionary of logger name to log level")

    for logger_name, logger_level in logger_levels.items():
        if not isinstance(logger_name, str) or not logger_name.strip():
            raise ValueError("logger_levels keys must be non-empty strings")
        normalized_levels[logger_name.strip()] = _validate_log_level(logger_level)

    normalized_levels.setdefault(DJANGO_SERVER, default_level)
    return normalized_levels


def _get_logger_names(app_loggers=None, logger_levels=None):
    merged_logger_names = list(DEFAULT_APP_LOGGERS)

    if app_loggers:
        for logger_name in app_loggers:
            if not isinstance(logger_name, str) or not logger_name.strip():
                raise ValueError("app_loggers entries must be non-empty strings")
            normalized_logger_name = logger_name.strip()
            if normalized_logger_name not in merged_logger_names:
                merged_logger_names.append(normalized_logger_name)

    if logger_levels:
        for logger_name in logger_levels:
            if logger_name != DJANGO_SERVER and logger_name not in merged_logger_names:
                merged_logger_names.append(logger_name)

    return tuple(merged_logger_names)


def _get_formatter_name(log_style):
    normalized_style = _validate_log_style(log_style, "log_style")
    if normalized_style == "color":
        return COLOR_FORMATTER
    if normalized_style == "json":
        return JSON_FORMATTER
    return PLAIN_FORMATTER


def _build_formatters(include_request_id, log_format, log_colors):
    base_format = _validate_log_format(log_format)
    plain_format = base_format + REQUEST_ID_SUFFIX if include_request_id else base_format
    return {
        COLOR_FORMATTER: {
            "()": "django_logkit.formatters.SafeColoredFormatter",
            "format": "%(log_color)s" + plain_format,
            "log_colors": _validate_log_colors(log_colors),
        },
        PLAIN_FORMATTER: {
            "()": "django_logkit.formatters.SafePlainFormatter",
            "format": plain_format,
        },
        JSON_FORMATTER: {
            "()": "django_logkit.formatters.JsonFormatter",
        },
    }


def _build_filters(include_request_id):
    if not include_request_id:
        return {}

    return {
        REQUEST_ID_FILTER: {
            "()": "django_logkit.filters.RequestIdFilter",
        }
    }


def _build_handler(handler_formatter, include_request_id):
    handler = {
        "formatter": handler_formatter,
    }

    if include_request_id:
        handler["filters"] = [REQUEST_ID_FILTER]

    return handler


def _build_handlers(
    console_formatter,
    include_request_id,
    file_formatter=None,
    file_name=None,
    log_when=None,
    log_backup=None,
):
    handlers = {
        CONSOLE_HANDLER: {
            "class": "logging.StreamHandler",
            **_build_handler(console_formatter, include_request_id),
        },
    }

    if file_formatter and file_name:
        handlers[FILE_HANDLER] = {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": file_name,
            "when": _validate_log_when(log_when),
            "backupCount": _validate_log_backup(log_backup),
            "encoding": DEFAULT_FILE_ENCODING,
            "delay": True,
            **_build_handler(file_formatter, include_request_id),
        }

    return handlers


def _build_named_loggers(default_log_level, active_handlers, logger_names, logger_levels=None):
    logger_levels = logger_levels or {}
    logger_config = {
        name: {
            "level": logger_levels.get(name, default_log_level),
            "handlers": list(active_handlers),
            "propagate": False,
        }
        for name in logger_names
    }
    logger_config[DJANGO_SERVER] = {
        "handlers": list(active_handlers),
        "level": logger_levels.get(DJANGO_SERVER, default_log_level),
        "propagate": False,
    }
    return logger_config


def _build_logging_config(
    log_level,
    console_style,
    file_style=None,
    file_name=None,
    log_when=None,
    log_backup=None,
    app_loggers=None,
    logger_levels=None,
    include_request_id=False,
    log_format=None,
    log_colors=None,
):
    normalized_log_level = _validate_log_level(log_level)
    active_handlers = [CONSOLE_HANDLER]
    file_formatter = None

    if file_name:
        active_handlers.append(FILE_HANDLER)
        file_formatter = _get_formatter_name(file_style or DEFAULT_LOG_STYLE)

    normalized_logger_levels = _normalize_logger_levels(
        default_level=normalized_log_level,
        logger_levels=logger_levels,
    )

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": _build_filters(include_request_id),
        "formatters": _build_formatters(
            include_request_id=include_request_id,
            log_format=log_format,
            log_colors=log_colors,
        ),
        "handlers": _build_handlers(
            console_formatter=_get_formatter_name(console_style),
            include_request_id=include_request_id,
            file_formatter=file_formatter,
            file_name=file_name,
            log_when=log_when,
            log_backup=log_backup,
        ),
        "loggers": {
            "": {"level": DEFAULT_ROOT_LEVEL, "handlers": list(active_handlers)},
            **_build_named_loggers(
                default_log_level=normalized_log_level,
                active_handlers=active_handlers,
                logger_names=_get_logger_names(app_loggers, normalized_logger_levels),
                logger_levels=normalized_logger_levels,
            ),
        },
    }


def _build_log_file_path(base_dir, log_file_name):
    log_dir = _validate_base_dir(base_dir) / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"failed to create log directory: {log_dir}") from exc
    return str(log_dir / _validate_log_file_name(log_file_name))


def get_logger_config_with_file(
    base_dir,
    log_level,
    log_file_name,
    log_color_console,
    log_color_file,
    log_backup=DEFAULT_LOG_BACKUP,
    log_when=DEFAULT_LOG_WHEN,
    app_loggers=None,
    logger_levels=None,
    include_request_id=False,
    log_format=None,
    log_colors=None,
):
    console_style = "color" if log_color_console else "plain"
    file_style = "color" if log_color_file else "plain"
    return _build_logging_config(
        log_level=log_level,
        console_style=console_style,
        file_style=file_style,
        file_name=_build_log_file_path(base_dir=base_dir, log_file_name=log_file_name),
        log_when=log_when,
        log_backup=log_backup,
        app_loggers=app_loggers,
        logger_levels=logger_levels,
        include_request_id=include_request_id,
        log_format=log_format,
        log_colors=log_colors,
    )


def get_logger_config_without_file(
    log_level,
    log_color,
    app_loggers=None,
    logger_levels=None,
    include_request_id=False,
    log_format=None,
    log_colors=None,
):
    console_style = "color" if log_color else "plain"
    return _build_logging_config(
        log_level=log_level,
        console_style=console_style,
        app_loggers=app_loggers,
        logger_levels=logger_levels,
        include_request_id=include_request_id,
        log_format=log_format,
        log_colors=log_colors,
    )


def get_logger_config(
    log_level,
    base_dir=None,
    log_file_name=None,
    console_style=DEFAULT_LOG_STYLE,
    file_style=DEFAULT_LOG_STYLE,
    log_backup=DEFAULT_LOG_BACKUP,
    log_when=DEFAULT_LOG_WHEN,
    app_loggers=None,
    logger_levels=None,
    include_request_id=False,
    log_format=None,
    log_colors=None,
):
    file_name = None
    if log_file_name is not None:
        if base_dir is None:
            raise ValueError("base_dir is required when log_file_name is provided")
        file_name = _build_log_file_path(base_dir=base_dir, log_file_name=log_file_name)

    return _build_logging_config(
        log_level=log_level,
        console_style=console_style,
        file_style=file_style,
        file_name=file_name,
        log_when=log_when,
        log_backup=log_backup,
        app_loggers=app_loggers,
        logger_levels=logger_levels,
        include_request_id=include_request_id,
        log_format=log_format,
        log_colors=log_colors,
    )
