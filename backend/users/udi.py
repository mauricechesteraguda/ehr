"""Ticket04: bounded UDI parsing and deterministic external adapter seams."""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from .logging import log_event
from .tracing import trace_function


PARSER_VERSION = "gs1-ai-1"
FNC1 = "\x1d"


@dataclass(frozen=True)
class ParseResult:
    status: str
    issuer: str
    device_identifier: str = ""
    lot_number: str = ""
    serial_number: str = ""
    expiry_date: date | None = None
    manufacture_date: date | None = None
    parser_version: str = PARSER_VERSION
    error_code: str = ""


class UDIAdapter(Protocol):
    issuer: str

    def parse(self, raw: str) -> ParseResult: ...


class UnsupportedAdapter:
    """Ticket04: Alternate issuers are explicit unsupported results, never guesses."""
    def __init__(self, issuer: str):
        self.issuer = issuer

    @trace_function
    def parse(self, raw: str) -> ParseResult:
        log_event("udi.adapter", component="udi", operation="parse", outcome="unsupported", status=422, adapter=self.issuer)
        return ParseResult(status="unsupported", issuer=self.issuer, parser_version=f"{self.issuer.lower()}-adapter-1", error_code="adapter_not_implemented")


class GUDIDAdapter(Protocol):
    def enrich(self, device_identifier: str) -> dict: ...


class UnavailableGUDIDAdapter:
    """Ticket04: Optional enrichment fails safe and is visible to callers."""
    @trace_function
    def enrich(self, device_identifier: str) -> dict:
        log_event("udi.gudid", component="udi", operation="enrich", outcome="unavailable", status=503, adapter="gudid")
        return {"status": "unavailable", "synthetic_fields": {}}


def _check_digit(gtin: str) -> bool:
    if len(gtin) not in (8, 12, 13, 14) or not gtin.isdigit():
        return False
    total = sum(int(value) * (3 if index % 2 == 0 else 1) for index, value in enumerate(reversed(gtin[:-1])))
    return total % 10 == (10 - int(gtin[-1])) % 10


def _date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%y%m%d").date()
    except ValueError:
        return None


@trace_function
def parse_gs1(raw: str) -> ParseResult:
    """Ticket04: Parse only bounded GS1 AIs; malformed input returns no invented fields."""
    if not isinstance(raw, str) or not raw or len(raw) > 256:
        return ParseResult(status="parse_failed", issuer="GS1", error_code="input_length")
    text = raw.strip().replace(" ", "")
    if "(" in text or ")" in text:
        # Parenthesized AIs are accepted only when they are complete and unambiguous.
        import re
        text = re.sub(r"\((\d{2,4})\)", r"\1", text)
        if "(" in text or ")" in text:
            return ParseResult(status="parse_failed", issuer="GS1", error_code="malformed_parentheses")
    values: dict[str, str] = {}
    position = 0
    fixed = {"01": 14, "11": 6, "17": 6}
    variable = {"10": 20, "21": 20}
    while position < len(text):
        if text[position] == FNC1:
            position += 1
            continue
        ai = text[position:position + 2]
        if ai not in fixed and ai not in variable:
            return ParseResult(status="parse_failed", issuer="GS1", error_code="unknown_application_identifier")
        position += 2
        if ai in fixed:
            value = text[position:position + fixed[ai]]
            if len(value) != fixed[ai] or FNC1 in value or not value.isdigit():
                return ParseResult(status="parse_failed", issuer="GS1", error_code="invalid_fixed_value")
            position += fixed[ai]
        else:
            end = text.find(FNC1, position)
            if end < 0:
                end = len(text)
            value = text[position:end]
            if not value or len(value) > variable[ai] or FNC1 in value:
                return ParseResult(status="parse_failed", issuer="GS1", error_code="invalid_variable_value")
            position = end
        if ai in values:
            return ParseResult(status="parse_failed", issuer="GS1", error_code="duplicate_application_identifier")
        values[ai] = value
    if "01" not in values or not _check_digit(values["01"]):
        return ParseResult(status="parse_failed", issuer="GS1", error_code="invalid_gtin_check_digit")
    expiry = _date(values["17"]) if "17" in values else None
    manufacture = _date(values["11"]) if "11" in values else None
    if "17" in values and expiry is None or "11" in values and manufacture is None:
        return ParseResult(status="parse_failed", issuer="GS1", error_code="invalid_date")
    return ParseResult(status="parsed", issuer="GS1", device_identifier=values["01"], lot_number=values.get("10", ""), serial_number=values.get("21", ""), expiry_date=expiry, manufacture_date=manufacture)


@trace_function
def parse_udi(raw: str) -> ParseResult:
    """Ticket04: Route issuers without logging or returning the raw identifier."""
    started = datetime.now().timestamp()
    result = parse_gs1(raw) if isinstance(raw, str) and (raw.startswith("01") or raw.startswith("(")) else ParseResult(status="unsupported", issuer="UNKNOWN", parser_version="router-1", error_code="unknown_issuer")
    log_event("udi.parse", component="udi", operation="parse", outcome=result.status, status=200 if result.status == "parsed" else 422, parser_status=result.status, duration_ms=int((datetime.now().timestamp() - started) * 1000))
    return result
