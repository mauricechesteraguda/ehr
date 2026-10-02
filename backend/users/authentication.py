"""type-10022026-Maurice: Session authentication with an explicit 401 challenge."""

from rest_framework.authentication import SessionAuthentication
from rest_framework.authentication import BaseAuthentication
from oauth2_provider.models import AccessToken
import hashlib
from django.contrib.auth import get_user
from django.utils import timezone

from .logging import log_event
from .tracing import trace_function


class SessionAuthenticationWithChallenge(SessionAuthentication):
    """type-10022026-Maurice: Preserve session/CSRF auth while exposing 401 semantics."""

    @trace_function
    def authenticate_header(self, request):
        """type-10022026-Maurice: Return a safe challenge for unauthenticated requests."""
        log_event("auth.session.challenge")
        return "Session"


class OAuthBearerOrSessionAuthentication(BaseAuthentication):
    """type-10022026-Maurice: Prefer bearer auth, then safely enforce Django session auth."""
    @trace_function
    def authenticate(self, request):
        # type-10022026-Maurice: Never touch DRF's lazy request.user here.  DRF
        # resolves that property through authentication again, which recurses.
        django_request = getattr(request, "_request", request)
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if header.startswith("Bearer "):
            value = header[7:].strip()
            if not value or len(value) > 512:
                return None
            token = AccessToken.objects.select_related("user", "application").filter(token_checksum=hashlib.sha256(value.encode()).hexdigest(), expires__gt=timezone.now()).first()
            if token is None or not token.user.is_active:
                return None
            request.smart_scopes = frozenset(token.scope.split())
            request.smart_patient = (token.resource or [None])[0]
            return (token.user, token)
        # type-10022026-Maurice: get_user reads the Django session directly;
        # enforce_csrf preserves SessionAuthentication's CSRF contract.
        user = get_user(django_request)
        if user.is_authenticated:
            SessionAuthentication().enforce_csrf(request)
            return (user, None)
        return None

    def authenticate_header(self, request):
        """type-10022026-Maurice: Return a standards-safe bearer challenge."""
        return "Bearer"
