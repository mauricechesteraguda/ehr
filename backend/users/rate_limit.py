"""type-10022026-Maurice: bounded local-demo throttling without request identity logging."""
from django.core.cache import cache
from rest_framework.response import Response
from .logging import log_event


def limited(request, bucket, limit=10, window=60):
    """type-10022026-Maurice: Return a safe 429 response after a small bounded burst."""
    forwarded = request.META.get("REMOTE_ADDR", "unknown").split(",", 1)[0][:64]
    # type-10022026-Maurice: Keep authenticated actors from sharing one local-demo
    # bucket while anonymous credentials remain throttled by client address.
    actor = f"user:{request.user.pk}" if getattr(request.user, "is_authenticated", False) else f"ip:{forwarded}"
    key = f"ehr:rate:{bucket}:{actor}"
    try:
        count = cache.get(key, 0)
        if count >= limit:
            log_event("security.rate_limit", outcome="blocked", component="security", operation=bucket)
            return Response({"detail": "Too many requests; retry later."}, status=429)
        cache.set(key, count + 1, window)
    except Exception as error:
        # Rate limiting must never turn an otherwise safe request into an outage.
        log_event("security.rate_limit.cache.failure", outcome="failure", component="security", operation=bucket, error_class=type(error).__name__)
        return None
    return None
