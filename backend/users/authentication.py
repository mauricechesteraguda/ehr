"""type-10022026-Maurice: Session authentication with an explicit 401 challenge."""

from rest_framework.authentication import SessionAuthentication

from .logging import log_event
from .tracing import trace_function


class SessionAuthenticationWithChallenge(SessionAuthentication):
    """type-10022026-Maurice: Preserve session/CSRF auth while exposing 401 semantics."""

    @trace_function
    def authenticate_header(self, request):
        """type-10022026-Maurice: Return a safe challenge for unauthenticated requests."""
        log_event("auth.session.challenge")
        return "Session"
