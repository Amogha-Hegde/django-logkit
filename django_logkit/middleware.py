from uuid import uuid4

from .request_id import reset_request_id, set_request_id


class RequestIdMiddleware:
    header_name = "HTTP_X_REQUEST_ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get(self.header_name) or str(uuid4())
        token = set_request_id(request_id)
        request.request_id = request_id

        try:
            response = self.get_response(request)
        finally:
            reset_request_id(token)

        response["X-Request-ID"] = request_id
        return response
