from contextvars import ContextVar
from functools import wraps


class _Missing:
    pass


_MISSING = _Missing()


_request_id = ContextVar("django_logkit_request_id", default=None)


def get_request_id():
    return _request_id.get()


def set_request_id(value):
    return _request_id.set(value)


def reset_request_id(token):
    _request_id.reset(token)


def bind_request_id(request_id=_MISSING):
    class _RequestIdBinding:
        def __enter__(self):
            resolved_request_id = get_request_id() if request_id is _MISSING else request_id
            self._token = None
            if resolved_request_id is not None:
                self._token = set_request_id(resolved_request_id)
            return resolved_request_id

        def __exit__(self, exc_type, exc, tb):
            if self._token is not None:
                reset_request_id(self._token)

    return _RequestIdBinding()


def wrap_with_request_id(func, request_id=_MISSING):
    resolved_request_id = get_request_id() if request_id is _MISSING else request_id

    @wraps(func)
    def _wrapped(*args, **kwargs):
        with bind_request_id(resolved_request_id):
            return func(*args, **kwargs)

    return _wrapped
