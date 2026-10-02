"""type-10022026-Maurice: Allowlisted, recursively redacted operational events."""
import contextvars
import logging
import re
import traceback
import json
from functools import wraps

from .tracing import safe_location, trace_function

logger = logging.getLogger("ehr.auth")
_correlation_id = contextvars.ContextVar("ehr_correlation_id", default="")
_SENSITIVE = re.compile(r"password|passphrase|secret|otp|totp|token|cookie|authorization|username|email|name|ssn|address|patient|clinical|payload|body|connection|string", re.I)
_ALLOWED = {"outcome", "status", "http_status", "http_class", "duration_ms", "correlation_id", "component", "operation", "user_role", "exception_type", "exception_class", "error_class", "exception_code", "cause_chain", "stack_trace", "request", "db_outcome"}


class JsonConsoleFormatter(logging.Formatter):
    """type-10022026-Maurice: Serialize only the safe event envelope as one JSON line."""
    def format(self, record):
        context = getattr(record, "context", {})
        safe = {key: _redact(value, key) for key, value in context.items() if key in _ALLOWED}
        safe.setdefault("correlation_id", "")
        return json.dumps({"event": getattr(record, "event", record.getMessage()), **safe}, separators=(",", ":"), sort_keys=True)


def set_correlation_id(value):
    """type-10022026-Maurice: Bind the sanitized request correlation to this execution context."""
    return _correlation_id.set(value)


def reset_correlation_id(token):
    """type-10022026-Maurice: Restore the correlation context that preceded a request."""
    _correlation_id.reset(token)


def _redact(value, key=""):
    """type-10022026-Maurice: Recursively redact sensitive mapping keys without inspecting values."""
    if _SENSITIVE.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(child_key): _redact(child_value, str(child_key)) for child_key, child_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item, key) for item in value]
    return value if isinstance(value, (str, int, float, bool)) or value is None else type(value).__name__


def log_event(event, level=logging.INFO, **context):
    """type-10022026-Maurice: Emit only the central operational schema with safe context."""
    if isinstance(context.get("exception"), BaseException):
        # type-10022026-Maurice: Emit exception shape only, never exception text or args.
        error = context["exception"]
        context["exception_type"] = type(error).__name__
        context["exception_class"] = type(error).__name__
        code = getattr(error, "code", None)
        context["exception_code"] = code if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,40}", code) else type(error).__name__
        causes = []
        cause = error.__cause__ or error.__context__
        while cause is not None and len(causes) < 8:
            causes.append(type(cause).__name__)
            cause = cause.__cause__ or cause.__context__
        context["cause_chain"] = causes
        context["stack_trace"] = [safe_location(frame.filename, frame.lineno, frame.name) for frame in traceback.extract_tb(error.__traceback__)[-8:]]
        context["error_class"] = type(error).__name__
    safe = {key: _redact(value, key) for key, value in context.items() if key in _ALLOWED}
    safe.setdefault("correlation_id", _correlation_id.get())
    logger.log(level, event, extra={"event": event, "context": safe})


@trace_function
def external_authenticate(authenticator):
    """type-10022026-Maurice: Observe an authentication call without arguments or returned bodies."""
    started = __import__("time").monotonic()
    log_event("auth.external.entry", component="authentication", operation="authenticate", outcome="started")
    try:
        result = authenticator()
        log_event("auth.external.exit", outcome="success", status=200, http_status=200, duration_ms=int((__import__("time").monotonic()-started)*1000), component="authentication", operation="authenticate")
        return result
    except Exception as error:
        log_event("auth.external.failure", outcome="failure", status=500, http_status=500, duration_ms=int((__import__("time").monotonic()-started)*1000), component="authentication", operation="authenticate", exception=error)
        raise


def traced_operation(function):
    """type-10022026-Maurice: Trace entry, success, and failure while preserving exception context."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        log_event(f"function.{function.__name__}.entry", component="backend", operation=function.__name__)
        try:
            result = function(*args, **kwargs)
            log_event(f"function.{function.__name__}.success", outcome="success", component="backend", operation=function.__name__)
            return result
        except Exception as error:
            log_event(f"function.{function.__name__}.failure", outcome="failure", component="backend", operation=function.__name__, exception_type=type(error).__name__)
            raise
    return wrapped
