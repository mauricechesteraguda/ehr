"""type-10022026-Maurice: Redacted JSONL function tracing outside the repository."""
import hashlib
import json
import os
import re
import time
import traceback
from functools import wraps
from pathlib import Path

SESSION_ID = os.environ.get("TRACE_SESSION_ID", f"pid-{os.getpid()}")
REPO_HASH = hashlib.sha256(str(Path(__file__).resolve().parents[2]).encode()).hexdigest()[:12]
REPO_ROOT = Path(__file__).resolve().parents[2]
TRACE_FILE = Path.home() / ".cache" / "agent-trace" / REPO_HASH / f"{SESSION_ID}.jsonl"


def trace_function(function):
    """type-10022026-Maurice: Trace safe entry, exit, and exception events."""
    @wraps(function)
    def traced(*args, **kwargs):
        TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        name = function.__qualname__
        _write("entry", name)
        try:
            result = function(*args, **kwargs)
            _write("exit", name)
            return result
        except Exception as error:
            _write_exception(name, error)
            raise
    return traced


def _write(event, function, error=None):
    """type-10022026-Maurice: Append a credential-free trace record."""
    record = {"ts": time.time(), "event": event, "function": function}
    if error:
        record["error"] = error
    with TRACE_FILE.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record) + "\n")


def _safe_code(error):
    """type-10022026-Maurice: Keep only a bounded code-like exception attribute."""
    code = getattr(error, "code", None)
    return code if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,40}", code) else type(error).__name__


def _cause_chain(error):
    """type-10022026-Maurice: Record only bounded exception class names from causes."""
    chain = []
    cause = error.__cause__ or error.__context__
    while cause is not None and len(chain) < 8:
        chain.append(type(cause).__name__)
        cause = cause.__cause__ or cause.__context__
    return chain


def safe_location(filename, lineno, function):
    """type-10022026-Maurice: Keep bounded diagnostic locations path-safe."""
    path = Path(filename)
    try:
        location = path.resolve().relative_to(REPO_ROOT)
        rendered = location.as_posix()
    except ValueError:
        rendered = f"<external>/{path.name}"
    return f"{rendered}:{lineno}:{function}"


def _write_exception(function, error):
    """type-10022026-Maurice: Trace safe exception metadata without messages or arguments."""
    stack = [safe_location(frame.filename, frame.lineno, frame.name) for frame in traceback.extract_tb(error.__traceback__)[-8:]]
    record = {
        "ts": time.time(),
        "event": "exception",
        "function": function,
        "exception_class": type(error).__name__,
        "exception_code": _safe_code(error),
        "cause_chain": _cause_chain(error),
        "stack_trace": stack,
    }
    with TRACE_FILE.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record) + "\n")
