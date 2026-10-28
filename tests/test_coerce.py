from __future__ import annotations

from datetime import date, datetime

import pytest

from enviroqc.coerce import coerce, display, expected_description, is_missing

from .conftest import make_rules

TOKENS = frozenset({"NA", "-999"})


def spec(type_: str, **kw):
    return make_rules([{"name": "c", "type": type_, **kw}]).columns[0]


@pytest.mark.parametrize(
    ("value", "missing"),
    [
        (None, True),
        ("", True),
        ("   ", True),
        ("\t", True),
        ("NA", True),
        (" NA ", True),
        ("na", False),  # tokens are case-sensitive
        ("-999", True),
        (-999, True),
        (-999.0, True),
        (float("nan"), True),
        (0, False),
        ("0", False),
        (False, False),
        ("x", False),
    ],
)
def test_is_missing(value, missing):
    assert is_missing(value, TOKENS) is missing


@pytest.mark.parametrize(
    ("raw", "ok", "parsed"),
    [
        ("42", True, 42),
        (" -7 ", True, -7),
        ("+3", True, 3),
        ("0", True, 0),
        (5, True, 5),
        (5.0, True, 5),
        ("99999999999999999999", True, 99999999999999999999),
        ("4.0", False, None),
        ("4.5", False, None),
        (4.5, False, None),
        ("1e3", False, None),
        ("1_000", False, None),
        ("abc", False, None),
        (True, False, None),
        (float("inf"), False, None),
    ],
)
def test_integer(raw, ok, parsed):
    r = coerce(raw, spec("integer"))
    assert r.ok is ok
    assert r.value == parsed


@pytest.mark.parametrize(
    ("raw", "ok", "parsed"),
    [
        ("3.14", True, 3.14),
        ("-0.5", True, -0.5),
        (".5", True, 0.5),
        ("5.", True, 5.0),
        ("1e-3", True, 0.001),
        ("2E+2", True, 200.0),
        (" 7 ", True, 7.0),
        (7, True, 7.0),
        (2.5, True, 2.5),
        ("12,5", False, None),
        ("1,000.0", False, None),
        ("nan", False, None),
        ("inf", False, None),
        ("Infinity", False, None),
        ("1_0", False, None),
        ("5 mg", False, None),
        ("<0.01", False, None),
        ("1e999", False, None),
        (True, False, None),
    ],
)
def test_float(raw, ok, parsed):
    r = coerce(raw, spec("float"))
    assert r.ok is ok
    assert r.value == parsed


@pytest.mark.parametrize(
    ("raw", "parsed"),
    [
        ("true", True),
        ("TRUE", True),
        ("Yes", True),
        ("y", True),
        ("1", True),
        ("false", False),
        ("No", False),
        ("0", False),
        (True, True),
        (0, False),
        (1.0, True),
    ],
)
def test_boolean_valid(raw, parsed):
    r = coerce(raw, spec("boolean"))
    assert r.ok and r.value is parsed


@pytest.mark.parametrize("raw", ["maybe", "2", 2, "tru"])
def test_boolean_invalid(raw):
    assert not coerce(raw, spec("boolean")).ok


def test_date_iso_and_format():
    assert coerce("2024-02-29", spec("date")).value == date(2024, 2, 29)
    assert not coerce("2023-02-29", spec("date")).ok  # not a leap year
    assert not coerce("2024-13-01", spec("date")).ok
    fmt = spec("date", format="%d/%m/%Y")
    assert coerce("31/12/2024", fmt).value == date(2024, 12, 31)
    assert not coerce("2024-12-31", fmt).ok


def test_date_accepts_excel_midnight_datetime_only():
    s = spec("date")
    assert coerce(datetime(2024, 1, 2), s).value == date(2024, 1, 2)
    assert not coerce(datetime(2024, 1, 2, 13, 0), s).ok
    assert coerce(date(2024, 1, 2), s).value == date(2024, 1, 2)
    assert not coerce(20240102.5, s).ok


def test_datetime_iso_and_format():
    assert coerce("2024-01-01 05:30", spec("datetime")).value == datetime(2024, 1, 1, 5, 30)
    assert coerce("2024-01-01T05:30:15", spec("datetime")).value == datetime(2024, 1, 1, 5, 30, 15)
    fmt = spec("datetime", format="%Y-%m-%d %H:%M")
    assert coerce("2024-01-01 23:59", fmt).ok
    assert not coerce("2024-01-01 24:00", fmt).ok
    assert not coerce("2024/01/01 05:00", fmt).ok
    assert coerce(date(2024, 1, 1), fmt).value == datetime(2024, 1, 1)
    assert coerce(datetime(2024, 1, 1, 5), fmt).ok  # native Excel datetimes ignore format
    assert not coerce(45000, fmt).ok


def test_string_converts_native_values():
    s = spec("string")
    assert coerce("  ST001 ", s).value == "ST001"
    assert coerce(12.0, s).value == "12"
    assert coerce(12.5, s).value == "12.5"


def test_display_truncates_and_formats():
    assert display(3.0) == "3"
    assert display(datetime(2024, 1, 1, 6)) == "2024-01-01 06:00:00"
    assert display("x" * 500).endswith("…")
    assert len(display("x" * 500)) == 200


def test_expected_description_mentions_format():
    assert "%d/%m/%Y" in expected_description(spec("date", format="%d/%m/%Y")).render("en")
    assert expected_description(spec("float")).render("en") == "number (e.g. 3.14)"
    assert expected_description(spec("float")).render("zh") == "数值（如 3.14）"
