"""Ticket04 expansion tests: parser boundaries and fail-safe adapter contracts."""
from datetime import date

from backend.users.udi import UnavailableGUDIDAdapter, UnsupportedAdapter, parse_gs1, parse_udi


def _udi(*parts):
    return "01" + "01234567890128" + "".join(parts)


def test_ticket04_valid_gs1_production_identifiers():
    result = parse_gs1(_udi("17", "250101", "11", "240101", "10", "LOT", "\x1d", "21", "SER"))
    assert result.status == "parsed"
    assert result.device_identifier == "01234567890128"
    assert result.lot_number == "LOT" and result.serial_number == "SER"
    assert result.expiry_date == date(2025, 1, 1) and result.manufacture_date == date(2024, 1, 1)


def test_ticket04_malformed_unknown_and_bounds_invent_nothing():
    for raw in ("bad", _udi("17", "991332"), _udi("10", "x" * 21), _udi("99", "x")):
        result = parse_gs1(raw)
        assert result.status == "parse_failed" and not result.device_identifier and not result.serial_number
    assert parse_gs1("x" * 257).error_code == "input_length"


def test_ticket04_alternate_adapters_are_explicit_and_gudid_is_visible():
    assert UnsupportedAdapter("HIBCC").parse("anything").status == "unsupported"
    assert parse_udi("+HIBCC").status == "unsupported"
    assert UnavailableGUDIDAdapter().enrich("01234567890128") == {"status": "unavailable", "synthetic_fields": {}}
