"""type-10022026-Maurice: Enforce configurable inactivity expiration."""
import time
from django.conf import settings
from django.contrib.auth import logout
from .logging import log_event
from .tracing import trace_function


class InactivityMiddleware:
    """type-10022026-Maurice: Invalidate sessions idle beyond the configured limit."""
    def __init__(self, get_response):
        self.get_response = get_response

    @trace_function
    def __call__(self, request):
        now = time.time()
        last = request.session.get("last_activity")
        if request.user.is_authenticated and last and now - last > settings.SESSION_INACTIVITY_SECONDS:
            logout(request)
            log_event("session.expired", user_role=getattr(request.user, "role", "unknown"))
        if request.user.is_authenticated:
            request.session["last_activity"] = now
        return self.get_response(request)
