"""type-10022026-Maurice: Sanitize and propagate request correlation identifiers."""
import re
import uuid

from .logging import set_correlation_id
from .tracing import trace_function

_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")


@trace_function
def correlation_id(value):
    """type-10022026-Maurice: Accept a bounded identifier or generate a safe replacement."""
    return value if value and _SAFE_ID.fullmatch(value) else f"req-{uuid.uuid4().hex}"


class CorrelationMiddleware:
    """type-10022026-Maurice: Bind and return one sanitized identifier per request."""
    def __init__(self, get_response):
        """type-10022026-Maurice: Store the Django response callable without request data."""
        self.get_response = get_response

    def __call__(self, request):
        """type-10022026-Maurice: Set request context before dispatch and response metadata after."""
        value = correlation_id(request.headers.get("X-Correlation-ID", ""))
        request.correlation_id = value
        token = set_correlation_id(value)
        try:
            response = self.get_response(request)
            response["X-Correlation-ID"] = value
            return response
        finally:
            # type-10022026-Maurice: Restore the prior context on success and exception paths.
            from .logging import reset_correlation_id
            reset_correlation_id(token)
