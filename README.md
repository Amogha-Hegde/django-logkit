# django-logkit

`django-logkit` provides reusable Django logging configs with:

- plain, color, or JSON output
- optional rotating file logging
- request ID injection via middleware + logging filter
- per-logger level overrides
- Celery-oriented default logger coverage

## Install

```bash
pip install django-logkit
```

Optional color support:

```bash
pip install "django-logkit[color]"
```

Optional high-performance JSON support:

```bash
pip install "django-logkit[json]"
```

## Public API

```python
from pathlib import Path

from django_logkit import (
    RequestContextMiddleware,
    RequestIdMiddleware,
    bind_log_context,
    bind_request_id,
    bind_request_id_from_task,
    build_celery_headers,
    get_log_context,
    get_logger_config,
    get_logger_config_from_file,
    get_logger_config_with_file,
    get_logger_config_without_file,
    wrap_with_log_context,
    wrap_with_request_id,
)

BASE_DIR = Path(__file__).resolve().parent
```

## Main Config Function

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

LOGGING = get_logger_config(
    log_level="INFO",
    base_dir=BASE_DIR,
    enable_file_logging=True,
    log_file_name="application.log",
    console_style="json",
    file_style="json",
    include_request_id=True,
    log_format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    log_colors={"INFO": "green", "ERROR": "red"},
    json_fields={"ts": "timestamp", "level": "levelname", "msg": "message", "rid": "request_id"},
    log_timezone="UTC",
    app_loggers=["payments", "notifications"],
    logger_levels={
        "django.db.backends": "WARNING",
        "payments": "DEBUG",
    },
)
```

Arguments:

- `log_level`: default level for configured named loggers
- `base_dir`: required when `log_file_name` is provided
- `enable_file_logging`: explicitly enables or disables the file handler; if omitted, file logging is enabled only when `log_file_name` is provided
- `log_file_name`: enables timed rotating file logging under `BASE_DIR/logs/`
- `console_style`: `plain`, `color`, or `json`
- `file_style`: `plain`, `color`, or `json`
- `log_backup`: rotated file retention count, default `100`
- `log_when`: rotation schedule, one of `S`, `M`, `H`, `D`, `MIDNIGHT`, `W0`-`W6`
- `app_loggers`: additional logger names to configure
- `logger_levels`: per-logger level overrides
- `include_request_id`: adds request-context filter support to handlers
- `log_format`: optional override for the plain/color formatter string
- `log_colors`: optional override for color formatter level-to-color mapping
- `json_fields`: optional override for JSON output fields as `{output_key: record_field_name}`
- `log_timezone`: optional timezone applied to plain, color, and JSON timestamps; defaults to `UTC`, and also accepts values like `local` or `Asia/Kolkata`

## Logger Behavior

### `log_level`

`log_level` is the default level applied to every named logger configured by `django-logkit`.

That includes:

- built-in logger names such as `celery`, `celery.task`, `django.request`, and `main`
- any extra logger names added through `app_loggers`

It does not change the root logger level. The root logger stays at `WARNING`.

Example:

```python
LOGGING = get_logger_config(
    log_level="INFO",
    app_loggers=["payments"],
)
```

This makes these named loggers use `INFO` unless overridden:

- `celery`
- `celery.task`
- `django.request`
- `main`
- `payments`

### `app_loggers`

`app_loggers` adds extra logger names to the configured logger set.

Behavior:

- entries are appended to the built-in default logger list
- duplicate names are ignored
- each added logger gets the same handlers as the rest of the configured named loggers
- each added logger uses `log_level` unless overridden by `logger_levels`

Example:

```python
LOGGING = get_logger_config(
    log_level="INFO",
    app_loggers=["payments", "notifications", "payments"],
)
```

Effective result:

- `payments` is added once
- `notifications` is added
- both get the configured handlers and default to `INFO`

### `logger_levels`

`logger_levels` overrides the level for specific logger names.

Behavior:

- values in `logger_levels` take precedence over `log_level`
- keys from `logger_levels` are also added to the configured logger set, even if they are not listed in `app_loggers`
- this is the mechanism to tune noisy modules such as `django.db.backends`

Example:

```python
LOGGING = get_logger_config(
    log_level="INFO",
    app_loggers=["payments"],
    logger_levels={
        "payments": "DEBUG",
        "django.db.backends": "WARNING",
    },
)
```

Effective result:

- built-in loggers still default to `INFO`
- `payments` is configured and uses `DEBUG`
- `django.db.backends` is configured and uses `WARNING`, even though it was not listed in `app_loggers`

### Precedence Summary

1. The package starts with the built-in logger names.
2. `app_loggers` adds more logger names.
3. `logger_levels` can add more logger names and override levels for any configured logger.
4. Any named logger without a specific `logger_levels` entry uses `log_level`.
5. The root logger remains `WARNING`.

## File Logging Behavior

`get_logger_config(...)` supports both console-only and console+file logging.

Console only:

```python
LOGGING = get_logger_config(
    log_level="INFO",
    console_style="plain",
    enable_file_logging=False,
)
```

Console + file:

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

LOGGING = get_logger_config(
    log_level="INFO",
    base_dir=BASE_DIR,
    enable_file_logging=True,
    log_file_name="application.log",
    console_style="json",
    file_style="json",
)
```

Rules:

- if `enable_file_logging=False`, no file handler is created
- if `enable_file_logging=True`, both `base_dir` and `log_file_name` are required
- if `enable_file_logging` is omitted, file logging is enabled only when `log_file_name` is provided
- file logs are written to `BASE_DIR/logs/<log_file_name>`

Default `log_format`:

```python
"[%(asctime)s] [%(process)s:%(thread)s] [%(levelname)s] [%(name)s:%(lineno)d %(funcName)s()] %(message)s"
```

Default `log_colors`:

```python
{
    "DEBUG": "blue",
    "INFO": "bold_white",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold_red",
}
```

## Backward-Compatible Helpers

```python
LOGGING = get_logger_config_without_file(
    log_level="INFO",
    log_color=True,
    app_loggers=["payments"],
    logger_levels={"payments": "DEBUG"},
    include_request_id=True,
)
```

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

LOGGING = get_logger_config_with_file(
    base_dir=BASE_DIR,
    log_level="INFO",
    log_file_name="application.log",
    log_color_console=True,
    log_color_file=False,
    app_loggers=["payments"],
    logger_levels={"payments": "DEBUG"},
    include_request_id=True,
)
```

## INI Config File

If you want logging config to live outside Python code, use:

```python
from django_logkit import get_logger_config_from_file


LOGGING = get_logger_config_from_file("/path/to/django-logkit.ini")
```

Ready-to-copy sample files are included at:

- [django-logkit.sample.ini](/Users/amogha/PycharmProjects/django-logkit/django-logkit.sample.ini) for JSON-oriented output
- [django-logkit.plain.sample.ini](/Users/amogha/PycharmProjects/django-logkit/django-logkit.plain.sample.ini) for plain/color output

The file must contain a `[django-logkit]` section. Example:

```ini
[django-logkit]
log_level = INFO
base_dir = /srv/app
enable_file_logging = true
log_file_name = application.log
console_style = json
file_style = plain
include_request_id = true
app_loggers = payments, notifications
log_backup = 7
log_when = D
log_timezone = UTC

[logger_levels]
payments = DEBUG
django.db.backends = WARNING

[log_colors]
info = green
error = red

[json_fields]
ts = timestamp
msg = message
rid = request_id
```

Supported sections:

- `[django-logkit]` for scalar options such as `log_level`, `base_dir`, `console_style`, `file_style`, `include_request_id`, `log_format`, and `log_timezone`
- `[logger_levels]` for per-logger level overrides
- `[log_colors]` for color formatter mappings
- `[json_fields]` for JSON output field mappings

Notes:

- `log_level` is required
- `app_loggers` accepts comma-separated or newline-separated logger names
- boolean values accept `true/false`, `yes/no`, `on/off`, or `1/0`

## Request Context Middleware

Add the middleware if you want request-scoped log context in logs:

```python
MIDDLEWARE = [
    # ...
    "django_logkit.middleware.RequestContextMiddleware",
]
```

Yes, you need to register the middleware in your Django `MIDDLEWARE` setting if you want automatic request-scoped values.

Register it once. If the same middleware is added multiple times, you can get duplicate request / response logs or mismatched request IDs. The middleware now guards against accidental double application on the same request, but it should still appear only once in `MIDDLEWARE`.

`RequestContextMiddleware` is the preferred name because it binds request-scoped context beyond `request_id`. `RequestIdMiddleware` remains available as a backward-compatible alias.

Without the middleware:

- `request_id` is not generated automatically
- `trace_id`, `span_id`, `tenant`, and `user_id` are not pulled from the request
- `duration_ms` is not measured automatically
- you can still use `bind_log_context(...)`, `wrap_with_log_context(...)`, `bind_request_id(...)`, or `wrap_with_request_id(...)` manually

Recommended placement:

- put it after authentication / tenant resolution middleware if you want `user_id` and `tenant` to be available automatically
- put it before application middleware or views that emit logs so those logs receive the bound context

Typical example:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "your_project.middleware.TenantMiddleware",
    "django_logkit.middleware.RequestContextMiddleware",
    # other middleware that should see request_id / trace_id / tenant / user_id
]
```

The middleware supports these request-scoped fields:

- `request_id`
- `trace_id`
- `span_id`
- `project_id`
- `org_id`
- `user_id`
- `tenant`
- `duration_ms`

Behavior:

- `request_id` is read from the configured request header if present, otherwise generated automatically
- `trace_id`, `span_id`, `project_id`, `org_id`, and `tenant` are read from configured request headers when present
- `user_id` is resolved from `request.user_id` or `request.user.pk` / `request.user.id` when available
- `duration_ms` is measured automatically for the request lifecycle
- every field is optional; you can use any one of them without the others
- the request ID is written back to the response header using the configured request ID header name
- optional request / response logging can be enabled independently through environment variables

Default request header names:

- `HTTP_X_REQUEST_ID`
- `HTTP_X_TRACE_ID`
- `HTTP_X_SPAN_ID`
- `HTTP_X_PROJECT_ID`
- `HTTP_X_ORG_ID`
- `HTTP_X_TENANT`

Environment variable overrides:

- `DJANGO_LOGKIT_REQUEST_ID_HEADER`
- `DJANGO_LOGKIT_TRACE_ID_HEADER`
- `DJANGO_LOGKIT_SPAN_ID_HEADER`
- `DJANGO_LOGKIT_PROJECT_ID_HEADER`
- `DJANGO_LOGKIT_ORG_ID_HEADER`
- `DJANGO_LOGKIT_TENANT_HEADER`

Optional request / response logging flags:

- `DJANGO_LOGKIT_LOG_REQUESTS`
- `DJANGO_LOGKIT_LOG_REQUEST_HEADERS`
- `DJANGO_LOGKIT_LOG_RESPONSE_HEADERS`
- `DJANGO_LOGKIT_LOG_REQUEST_BODY`
- `DJANGO_LOGKIT_LOG_RESPONSE_BODY`
- `DJANGO_LOGKIT_REQUEST_LOGGER`
- `DJANGO_LOGKIT_BODY_MAX_LENGTH`
- `DJANGO_LOGKIT_REDACT_HEADERS`

Example:

```bash
export DJANGO_LOGKIT_REQUEST_ID_HEADER=HTTP_X_CORRELATION_ID
export DJANGO_LOGKIT_TRACE_ID_HEADER=HTTP_X_B3_TRACE_ID
export DJANGO_LOGKIT_SPAN_ID_HEADER=HTTP_X_B3_SPAN_ID
export DJANGO_LOGKIT_PROJECT_ID_HEADER=HTTP_X_PROJECT
export DJANGO_LOGKIT_ORG_ID_HEADER=HTTP_X_ORGANIZATION
export DJANGO_LOGKIT_TENANT_HEADER=HTTP_X_ACCOUNT
```

Request / response logging example:

```bash
export DJANGO_LOGKIT_LOG_REQUESTS=true
export DJANGO_LOGKIT_LOG_REQUEST_HEADERS=true
export DJANGO_LOGKIT_LOG_RESPONSE_HEADERS=true
export DJANGO_LOGKIT_LOG_REQUEST_BODY=false
export DJANGO_LOGKIT_LOG_RESPONSE_BODY=false
export DJANGO_LOGKIT_REQUEST_LOGGER=django.request
export DJANGO_LOGKIT_BODY_MAX_LENGTH=4096
```

Behavior:

- all request / response logging is disabled by default
- each log type can be enabled independently
- the summary log is emitted at `INFO`
- headers and bodies are emitted at `DEBUG`
- middleware-emitted logs include an `event` field so request and response logs can be distinguished reliably
- sensitive headers are redacted by default: `Authorization`, `Cookie`, `Set-Cookie`, `X-Api-Key`, `Proxy-Authorization`
- you can override the redacted header list with `DJANGO_LOGKIT_REDACT_HEADERS` as a comma-separated list

Request / response log events:

- `request_summary`
- `request_headers`
- `response_headers`
- `request_body`
- `response_body`

Plain / color formatter behavior:

- middleware-emitted request / response logs are rendered as readable event lines
- for example, plain output will look like:

```text
[2026-04-03 20:05:05.672+00:00] [INFO] [django.request] request_summary method=GET path=/api/health/ status_code=500 [request_id=6f80a469-349e-495a-8a1a-374173aa66f9]
[2026-04-03 20:05:05.672+00:00] [DEBUG] [django.request] request_headers method=GET path=/api/health/ headers={'Host': 'localhost:8000'} [request_id=6f80a469-349e-495a-8a1a-374173aa66f9]
[2026-04-03 20:05:05.672+00:00] [DEBUG] [django.request] response_headers method=GET path=/api/health/ status_code=500 headers={'Content-Type': 'text/html; charset=utf-8'} [request_id=6f80a469-349e-495a-8a1a-374173aa66f9]
```

## Threads And Executors

For threads, executors, background jobs, or standalone log enrichment, bind only the fields you need:

```python
from concurrent.futures import ThreadPoolExecutor

from django_logkit import bind_log_context, bind_request_id, wrap_with_log_context, wrap_with_request_id


def do_work(order_id):
    logger.info("processing order", extra={"order_id": order_id})


with bind_request_id("req-123"):
    do_work(1)


executor = ThreadPoolExecutor(max_workers=4)
executor.submit(wrap_with_request_id(do_work), 2)


with bind_log_context(trace_id="trace-123"):
    logger.info("trace-only log")


with bind_log_context(duration_ms=18):
    logger.info("duration-only log")


executor.submit(
    wrap_with_log_context(do_work, tenant="tenant-acme", user_id="user-42"),
    3,
)
```

## JSON Logging

When `console_style="json"` or `file_style="json"`, logs are emitted as JSON with fields including:

- `timestamp`
- `level`
- `hostname`
- `logger`
- `event`
- `message`
- `module`
- `function`
- `line`
- `process`
- `thread`
- `method`
- `path`
- `headers`
- `body`
- `request_id`
- `trace_id`
- `span_id`
- `project_id`
- `org_id`
- `user_id`
- `tenant`
- `duration_ms`
- `exception`

Optional service metadata can be added with environment variables:

- `DJANGO_LOGKIT_SERVICE_NAME`
- `DJANGO_LOGKIT_ENVIRONMENT`

If `orjson` is installed through the optional `json` extra, JSON logs are serialized with `orjson`. Otherwise the formatter falls back to Python's standard `json` module.

By default the JSON formatter emits a fixed set of fields, but you can override that with `json_fields`.

Example:

```python
LOGGING = get_logger_config(
    log_level="INFO",
    console_style="json",
    json_fields={
        "ts": "timestamp",
        "severity": "levelname",
        "logger": "name",
        "msg": "message",
        "request_id": "request_id",
    },
    log_timezone="UTC",
)
```

Supported dynamic field values include any standard `logging.LogRecord` attribute, plus:

- `timestamp`
- `message`
- `hostname`
- `event`
- `method`
- `path`
- `headers`
- `body`
- `request_id`
- `trace_id`
- `span_id`
- `project_id`
- `org_id`
- `user_id`
- `tenant`
- `duration_ms`

Common examples from Python logging:

- `name`
- `levelno`
- `levelname`
- `pathname`
- `filename`
- `module`
- `lineno`
- `funcName`
- `created`
- `asctime`
- `msecs`
- `relativeCreated`
- `thread`
- `threadName`
- `taskName`
- `process`
- `processName`

For `json_fields`, use the raw field names above, not `%`-style placeholders.

Example:

```python
LOGGING = get_logger_config(
    log_level="INFO",
    console_style="json",
    json_fields={
        "logger": "name",
        "level": "levelname",
        "path": "pathname",
        "line": "lineno",
        "function": "funcName",
        "time": "asctime",
        "pid": "process",
        "thread_name": "threadName",
        "message": "message",
        "request_id": "request_id",
    },
    log_timezone="Asia/Kolkata",
)
```

## Formatter Fields

For `log_format`, you can use standard Python `logging` record attributes such as:

- `%(name)s`
- `%(levelno)s`
- `%(levelname)s`
- `%(pathname)s`
- `%(filename)s`
- `%(module)s`
- `%(lineno)d`
- `%(funcName)s`
- `%(created)f`
- `%(asctime)s`
- `%(msecs)d`
- `%(relativeCreated)d`
- `%(thread)d`
- `%(threadName)s`
- `%(taskName)s`
- `%(process)d`
- `%(processName)s`
- `%(message)s`

Custom fields added by `django-logkit`:

- `%(request_id)s`
- `%(trace_id)s`
- `%(span_id)s`
- `%(project_id)s`
- `%(org_id)s`
- `%(user_id)s`
- `%(tenant)s`
- `%(duration_ms)s`

Example:

```python
LOGGING = get_logger_config(
    log_level="INFO",
    console_style="plain",
    include_request_id=True,
    log_format="[%(levelname)s] [%(name)s] [%(request_id)s] %(message)s",
)
```

## Sample Output

Plain / file output:

```text
[2026-03-25 18:42:11,245] [42110:140735197184768] [INFO] [payments.service:87 create_invoice()] invoice created
```

Plain / file output with request ID:

```text
[2026-03-25 18:42:11,245] [42110:140735197184768] [INFO] [payments.service:87 create_invoice()] invoice created [request_id=req-123]
```

Color console output uses the same structure as plain output, with ANSI color applied to the log level prefix.

JSON output:

```json
{"timestamp": "2026-03-25T13:12:11.245000+00:00", "level": "INFO", "hostname": "app-worker-01", "logger": "payments.service", "event": "request_summary", "message": "request_summary", "module": "service", "function": "create_invoice", "line": 87, "process": 42110, "thread": 140735197184768, "method": "GET", "path": "/api/health/", "request_id": "req-123", "trace_id": "trace-123", "span_id": "span-123", "project_id": "project-123", "org_id": "org-123", "user_id": "user-42", "tenant": "tenant-acme", "duration_ms": 18, "service": "billing-api", "environment": "production"}
```

## Celery Notes

Default configured logger names include:

- `celery`
- `celery.app.trace`
- `celery.redirected`
- `celery.task`
- `billiard`
- `kombu`

That gives worker and task execution logs the same handler and formatter setup as the rest of the project.

To propagate request IDs into Celery tasks:

```python
from django_logkit import bind_request_id_from_task, build_celery_headers

some_task.apply_async(args=[123], headers=build_celery_headers())


@shared_task(bind=True)
def some_task(self, order_id):
    with bind_request_id_from_task(self):
        logger.info("processing order", extra={"order_id": order_id})
```

## Example `settings.py`

```python
from pathlib import Path

from django_logkit import get_logger_config

BASE_DIR = Path(__file__).resolve().parent

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_logkit.middleware.RequestIdMiddleware",
]

LOGGING = get_logger_config(
    log_level="INFO",
    base_dir=BASE_DIR,
    enable_file_logging=True,
    log_file_name="application.log",
    console_style="json",
    file_style="json",
    include_request_id=True,
    app_loggers=["payments", "notifications"],
    logger_levels={
        "django.db.backends": "WARNING",
        "payments": "DEBUG",
    },
)
```

## Notes

- File logging uses UTF-8 and `delay=True`.
- Color output falls back to plain formatting if `colorlog` is not installed, and emits a runtime warning.
- JSON output uses `orjson` when installed via the optional `json` extra, otherwise it falls back to the standard library.
- `log_file_name`, `log_when`, `log_backup`, and log styles are validated before config is returned.
- `MIDNIGHT` is normalized correctly for `TimedRotatingFileHandler`.
- The root logger stays at `WARNING` to limit noisy third-party logs.
