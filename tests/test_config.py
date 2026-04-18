from pathlib import Path

import pytest

from django_logkit import config


def test_get_logger_config_without_file_uses_console_only():
    logging_config = config.get_logger_config(
        log_level="info",
        enable_file_logging=False,
        app_loggers=["payments"],
        logger_levels={"payments": "debug", "django.db.backends": "warning"},
    )

    assert "file" not in logging_config["handlers"]
    assert logging_config["loggers"][""]["handlers"] == ["console"]
    assert logging_config["loggers"]["payments"]["level"] == "DEBUG"
    assert logging_config["loggers"]["django.db.backends"]["level"] == "WARNING"
    assert logging_config["loggers"]["celery"]["level"] == "INFO"


def test_get_logger_config_with_file_creates_file_handler(tmp_path):
    logging_config = config.get_logger_config(
        log_level="INFO",
        base_dir=tmp_path,
        enable_file_logging=True,
        log_file_name="app.log",
        console_style="plain",
        file_style="json",
        include_request_id=True,
    )

    assert (tmp_path / "logs").is_dir()
    assert logging_config["handlers"]["file"]["filename"] == str(tmp_path / "logs" / "app.log")
    assert logging_config["handlers"]["file"]["formatter"] == config.JSON_FORMATTER
    assert logging_config["handlers"]["file"]["filters"] == [config.REQUEST_ID_FILTER]
    assert logging_config["loggers"][""]["handlers"] == ["console", "file"]


def test_get_logger_config_uses_default_log_when_and_backup(tmp_path):
    logging_config = config.get_logger_config(
        log_level="INFO",
        base_dir=tmp_path,
        enable_file_logging=True,
        log_file_name="defaults.log",
    )

    assert logging_config["handlers"]["file"]["when"] == config.DEFAULT_LOG_WHEN
    assert logging_config["handlers"]["file"]["backupCount"] == config.DEFAULT_LOG_BACKUP


def test_get_logger_config_enables_file_logging_from_log_file_name(tmp_path):
    logging_config = config.get_logger_config(
        log_level="INFO",
        base_dir=tmp_path,
        log_file_name="implicit.log",
    )

    assert "file" in logging_config["handlers"]
    assert logging_config["handlers"]["file"]["filename"].endswith("implicit.log")


def test_get_logger_config_with_file_wrapper(tmp_path):
    logging_config = config.get_logger_config_with_file(
        base_dir=tmp_path,
        log_level="INFO",
        log_file_name="wrapper.log",
        log_color_console=False,
        log_color_file=True,
    )

    assert logging_config["handlers"]["console"]["formatter"] == config.PLAIN_FORMATTER
    assert logging_config["handlers"]["file"]["formatter"] == config.COLOR_FORMATTER


def test_get_logger_config_without_file_wrapper():
    logging_config = config.get_logger_config_without_file(
        log_level="INFO",
        log_color=True,
    )

    assert logging_config["handlers"]["console"]["formatter"] == config.COLOR_FORMATTER
    assert "file" not in logging_config["handlers"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"log_level": ""}, "log_level must be a non-empty string"),
        ({"log_level": "INFO", "enable_file_logging": "yes"}, "enable_file_logging must be a boolean"),
        (
            {"log_level": "INFO", "enable_file_logging": True, "log_file_name": "app.log"},
            "base_dir is required when file logging is enabled",
        ),
        (
            {"log_level": "INFO", "enable_file_logging": True, "base_dir": Path(".")},
            "log_file_name is required when file logging is enabled",
        ),
        (
            {"log_level": "INFO", "base_dir": "", "log_file_name": "app.log"},
            "base_dir must be a non-empty path string or pathlib.Path",
        ),
        (
            {"log_level": "INFO", "app_loggers": [""]},
            "app_loggers entries must be non-empty strings",
        ),
        (
            {"log_level": "INFO", "logger_levels": {"": "DEBUG"}},
            "logger_levels keys must be non-empty strings",
        ),
        (
            {"log_level": "INFO", "log_format": ""},
            "log_format must be a non-empty string",
        ),
        (
            {"log_level": "INFO", "log_colors": {"INFO": ""}},
            "log_colors values must be non-empty strings",
        ),
        (
            {"log_level": "INFO", "log_when": "bad", "base_dir": Path("."), "log_file_name": "app.log"},
            "log_when must be one of",
        ),
        (
            {"log_level": "INFO", "log_backup": -1, "base_dir": Path("."), "log_file_name": "app.log"},
            "log_backup must be an integer greater than or equal to 0",
        ),
        (
            {"log_level": "INFO", "base_dir": Path("."), "log_file_name": "nested/app.log"},
            "log_file_name must be a file name, not a path",
        ),
    ],
)
def test_get_logger_config_validation_errors(kwargs, message):
    with pytest.raises(ValueError, match=message):
        config.get_logger_config(**kwargs)


def test_get_logger_config_log_colors_normalized():
    logging_config = config.get_logger_config(
        log_level="INFO",
        enable_file_logging=False,
        console_style="color",
        log_colors={"info": "green"},
    )

    assert logging_config["formatters"][config.COLOR_FORMATTER]["log_colors"]["INFO"] == "green"


def test_get_logger_config_uses_default_log_format_and_colors():
    logging_config = config.get_logger_config(
        log_level="INFO",
        enable_file_logging=False,
        console_style="color",
    )

    assert logging_config["formatters"][config.PLAIN_FORMATTER]["format"] == config.DEFAULT_LOG_FORMAT
    assert logging_config["formatters"][config.COLOR_FORMATTER]["log_colors"] == config.DEFAULT_LOG_COLORS
    assert logging_config["formatters"][config.PLAIN_FORMATTER]["log_timezone"] == config.DEFAULT_LOG_TIMEZONE


def test_get_logger_config_accepts_custom_json_fields():
    logging_config = config.get_logger_config(
        log_level="INFO",
        enable_file_logging=False,
        console_style="json",
        json_fields={"ts": "timestamp", "msg": "message"},
    )

    assert logging_config["formatters"][config.JSON_FORMATTER]["json_fields"] == {"ts": "timestamp", "msg": "message"}


def test_get_logger_config_accepts_log_timezone():
    logging_config = config.get_logger_config(
        log_level="INFO",
        enable_file_logging=False,
        console_style="json",
        log_timezone="UTC",
    )

    assert logging_config["formatters"][config.PLAIN_FORMATTER]["log_timezone"] == "UTC"
    assert logging_config["formatters"][config.COLOR_FORMATTER]["log_timezone"] == "UTC"
    assert logging_config["formatters"][config.JSON_FORMATTER]["log_timezone"] == "UTC"


def test_get_logger_config_accepts_string_base_dir(tmp_path):
    logging_config = config.get_logger_config(
        log_level="INFO",
        base_dir=str(tmp_path),
        enable_file_logging=True,
        log_file_name="string-base-dir.log",
    )

    assert logging_config["handlers"]["file"]["filename"] == str(tmp_path / "logs" / "string-base-dir.log")


def test_get_logger_config_from_file_reads_ini_config(tmp_path):
    config_file = tmp_path / "logging.ini"
    config_file.write_text(
        "\n".join(
            [
                "[django-logkit]",
                "log_level = INFO",
                f"base_dir = {tmp_path}",
                "enable_file_logging = true",
                "log_file_name = ini.log",
                "console_style = json",
                "file_style = plain",
                "include_request_id = true",
                "app_loggers = payments, notifications",
                "log_backup = 7",
                "log_when = D",
                "log_timezone = UTC",
                "",
                "[logger_levels]",
                "payments = DEBUG",
                "django.db.backends = WARNING",
                "",
                "[log_colors]",
                "info = green",
                "",
                "[json_fields]",
                "ts = timestamp",
                "msg = message",
            ]
        ),
        encoding="utf-8",
    )

    logging_config = config.get_logger_config_from_file(str(config_file))

    assert logging_config["handlers"]["console"]["formatter"] == config.JSON_FORMATTER
    assert logging_config["handlers"]["file"]["formatter"] == config.PLAIN_FORMATTER
    assert logging_config["handlers"]["file"]["filename"] == str(tmp_path / "logs" / "ini.log")
    assert logging_config["handlers"]["file"]["backupCount"] == 7
    assert logging_config["handlers"]["file"]["when"] == "D"
    assert logging_config["loggers"]["payments"]["level"] == "DEBUG"
    assert logging_config["loggers"]["notifications"]["level"] == "INFO"
    assert logging_config["formatters"][config.JSON_FORMATTER]["json_fields"] == {"ts": "timestamp", "msg": "message"}
    assert logging_config["formatters"][config.COLOR_FORMATTER]["log_colors"]["INFO"] == "green"


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("[other]\nlog_level=INFO\n", r"config file must contain \[django-logkit\] section"),
        ("[django-logkit]\nconsole_style=plain\n", "config file must define log_level"),
        ("[django-logkit]\nlog_level=INFO\nenable_file_logging=maybe\n", "enable_file_logging must be a boolean"),
    ],
)
def test_get_logger_config_from_file_validation_errors(tmp_path, contents, message):
    config_file = tmp_path / "logging.ini"
    config_file.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        config.get_logger_config_from_file(str(config_file))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"log_level": "INFO", "console_style": ""}, "log_style must be a non-empty string"),
        ({"log_level": "INFO", "console_style": "weird"}, "log_style must be one of: plain, color, json"),
        ({"log_level": "INFO", "base_dir": Path("."), "log_file_name": ""}, "log_file_name must be a non-empty string"),
        ({"log_level": "INFO", "log_colors": []}, "log_colors must be a dictionary of level name to color"),
        ({"log_level": "INFO", "log_colors": {1: "red"}}, "log_colors keys must be non-empty strings"),
        ({"log_level": "INFO", "json_fields": []}, "json_fields must be a dictionary of output key to record field name"),
        ({"log_level": "INFO", "json_fields": {"": "message"}}, "json_fields keys must be non-empty strings"),
        ({"log_level": "INFO", "json_fields": {"msg": ""}}, "json_fields values must be non-empty strings"),
        ({"log_level": "INFO", "log_timezone": ""}, "log_timezone must be a non-empty string or None"),
        ({"log_level": "INFO", "logger_levels": []}, "logger_levels must be a dictionary of logger name to log level"),
        ({"log_level": "INFO", "log_when": "", "base_dir": Path("."), "log_file_name": "app.log"}, "log_when must be a non-empty string"),
    ],
)
def test_get_logger_config_additional_validation_errors(kwargs, message):
    with pytest.raises(ValueError, match=message):
        config.get_logger_config(**kwargs)


def test_build_log_file_path_wraps_oserror(monkeypatch, tmp_path):
    monkeypatch.setattr(type(tmp_path), "mkdir", lambda self, parents=False, exist_ok=False: (_ for _ in ()).throw(OSError("permission denied")))

    with pytest.raises(RuntimeError, match="failed to create log directory"):
        config._build_log_file_path(tmp_path, "app.log")
