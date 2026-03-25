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

## Public API

```python
from pathlib import Path

from django_logkit import (
    RequestIdMiddleware,
    bind_request_id,
    bind_request_id_from_task,
    build_celery_headers,
    get_logger_config,
    get_logger_config_with_file,
    get_logger_config_without_file,
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

Arguments:

- `log_level`: default level for configured named loggers
- `base_dir`: required when `log_file_name` is provided
- `log_file_name`: enables timed rotating file logging under `BASE_DIR/logs/`
- `console_style`: `plain`, `color`, or `json`
- `file_style`: `plain`, `color`, or `json`
- `log_backup`: rotated file retention count, default `100`
- `log_when`: rotation schedule, one of `S`, `M`, `H`, `D`, `MIDNIGHT`, `W0`-`W6`
- `app_loggers`: additional logger names to configure
- `logger_levels`: per-logger level overrides
- `include_request_id`: adds request ID filter support to handlers

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

## Request ID Middleware

Add the middleware if you want request-scoped IDs in logs:

```python
MIDDLEWARE = [
    # ...
    "django_logkit.middleware.RequestIdMiddleware",
]
```

The middleware reads `X-Request-ID` if present, otherwise generates one, stores it in a context variable, and writes it back to the response header.

## Threads And Executors

For threads or executors, bind the request ID explicitly:

```python
from concurrent.futures import ThreadPoolExecutor

from django_logkit import bind_request_id, wrap_with_request_id


def do_work(order_id):
    logger.info("processing order", extra={"order_id": order_id})


with bind_request_id("req-123"):
    do_work(1)


executor = ThreadPoolExecutor(max_workers=4)
executor.submit(wrap_with_request_id(do_work), 2)
```

## JSON Logging

When `console_style="json"` or `file_style="json"`, logs are emitted as JSON with fields including:

- `timestamp`
- `level`
- `hostname`
- `logger`
- `message`
- `module`
- `function`
- `line`
- `process`
- `thread`
- `request_id`
- `exception`

Optional service metadata can be added with environment variables:

- `DJANGO_LOGKIT_SERVICE_NAME`
- `DJANGO_LOGKIT_ENVIRONMENT`

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
{"timestamp": "2026-03-25T13:12:11.245000+00:00", "level": "INFO", "hostname": "app-worker-01", "logger": "payments.service", "message": "invoice created", "module": "service", "function": "create_invoice", "line": 87, "process": 42110, "thread": 140735197184768, "request_id": "req-123", "service": "billing-api", "environment": "production"}
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
import os
from pathlib import Path

from django_logkit import get_logger_config

BASE_DIR = Path(__file__).resolve().parent


def get_bool_env(name, default="false"):
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


LOGGING = get_logger_config(
    log_level=os.environ.get("LOGLEVEL", "INFO").upper(),
    base_dir=BASE_DIR,
    log_file_name=os.environ.get("LOG_FILE_NAME", "application.log") if get_bool_env("LOG_INTO_FILE") else None,
    console_style=os.environ.get("LOG_CONSOLE_STYLE", "json"),
    file_style=os.environ.get("LOG_FILE_STYLE", "json"),
    include_request_id=get_bool_env("LOG_INCLUDE_REQUEST_ID", "true"),
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
- `log_file_name`, `log_when`, `log_backup`, and log styles are validated before config is returned.
- `MIDNIGHT` is normalized correctly for `TimedRotatingFileHandler`.
- The root logger stays at `WARNING` to limit noisy third-party logs.
