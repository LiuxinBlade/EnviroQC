"""Strict, predictable conversion of raw cell values to typed values.

Each converter returns a :class:`Coerced` result instead of raising, so that a
bad value becomes a report entry rather than a crash.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any

from .config import ColumnSpec, ColumnType
from .i18n import Msg

_INT_RE = re.compile(r"[+-]?\d+")
_FLOAT_RE = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_TRUE = frozenset({"true", "t", "yes", "y", "1"})
_FALSE = frozenset({"false", "f", "no", "n", "0"})


@dataclass(frozen=True)
class Coerced:
    ok: bool
    value: Any = None


_FAIL = Coerced(False)


def is_missing(value: Any, missing_tokens: frozenset[str]) -> bool:
    """True if a cell counts as missing.

    Empty and whitespace-only cells are always missing; other tokens come from
    ``input.missing_values``.
    """
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str):
        s = value.strip()
        return s == "" or s in missing_tokens
    if isinstance(value, int | float) and not isinstance(value, bool):
        return display(value) in missing_tokens
    return False


def display(value: Any, limit: int = 200) -> str:
    """Human-readable form of a raw value, used in reports."""
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e16:
        text = str(int(value))
    elif isinstance(value, datetime):
        text = value.isoformat(sep=" ")
    else:
        text = str(value)
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def coerce(value: Any, spec: ColumnSpec) -> Coerced:
    """Convert a non-missing raw value according to the column type."""
    return _CONVERTERS[spec.type](value, spec)


def _to_string(value: Any, spec: ColumnSpec) -> Coerced:
    if isinstance(value, str):
        return Coerced(True, value.strip())
    return Coerced(True, display(value, limit=10_000))


def _to_integer(value: Any, spec: ColumnSpec) -> Coerced:
    if isinstance(value, bool):
        return _FAIL
    if isinstance(value, int):
        return Coerced(True, value)
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer():
            return Coerced(True, int(value))
        return _FAIL
    if isinstance(value, str):
        s = value.strip()
        if _INT_RE.fullmatch(s):
            return Coerced(True, int(s))
    return _FAIL


def _to_float(value: Any, spec: ColumnSpec) -> Coerced:
    if isinstance(value, bool):
        return _FAIL
    if isinstance(value, int | float):
        f = float(value)
        return Coerced(True, f) if math.isfinite(f) else _FAIL
    if isinstance(value, str):
        s = value.strip()
        if _FLOAT_RE.fullmatch(s):
            f = float(s)
            if math.isfinite(f):
                return Coerced(True, f)
    return _FAIL


def _to_boolean(value: Any, spec: ColumnSpec) -> Coerced:
    if isinstance(value, bool):
        return Coerced(True, value)
    if isinstance(value, int | float) and value in (0, 1):
        return Coerced(True, bool(value))
    if isinstance(value, str):
        s = value.strip().lower()
        if s in _TRUE:
            return Coerced(True, True)
        if s in _FALSE:
            return Coerced(True, False)
    return _FAIL


def _to_date(value: Any, spec: ColumnSpec) -> Coerced:
    if isinstance(value, datetime):
        # Excel stores dates as datetimes; accept them only at midnight.
        if value.time() == time(0, 0):
            return Coerced(True, value.date())
        return _FAIL
    if isinstance(value, date):
        return Coerced(True, value)
    if isinstance(value, str):
        s = value.strip()
        try:
            if spec.format:
                return Coerced(True, datetime.strptime(s, spec.format).date())
            return Coerced(True, date.fromisoformat(s))
        except ValueError:
            return _FAIL
    return _FAIL


def _to_datetime(value: Any, spec: ColumnSpec) -> Coerced:
    if isinstance(value, datetime):
        return Coerced(True, value)
    if isinstance(value, date):
        return Coerced(True, datetime.combine(value, time(0, 0)))
    if isinstance(value, str):
        s = value.strip()
        try:
            if spec.format:
                return Coerced(True, datetime.strptime(s, spec.format))
            return Coerced(True, datetime.fromisoformat(s))
        except ValueError:
            return _FAIL
    return _FAIL


_CONVERTERS: dict[ColumnType, Callable[[Any, ColumnSpec], Coerced]] = {
    ColumnType.STRING: _to_string,
    ColumnType.INTEGER: _to_integer,
    ColumnType.FLOAT: _to_float,
    ColumnType.BOOLEAN: _to_boolean,
    ColumnType.DATE: _to_date,
    ColumnType.DATETIME: _to_datetime,
}


def expected_description(spec: ColumnSpec) -> Msg:
    """Short description of what a valid value looks like (translatable)."""
    match spec.type:
        case ColumnType.INTEGER:
            return Msg.of("expected.integer")
        case ColumnType.FLOAT:
            return Msg.of("expected.float")
        case ColumnType.BOOLEAN:
            return Msg.of("expected.boolean")
        case ColumnType.DATE:
            if spec.format:
                return Msg.of("expected.date_format", format=spec.format)
            return Msg.of("expected.date_iso")
        case ColumnType.DATETIME:
            if spec.format:
                return Msg.of("expected.datetime_format", format=spec.format)
            return Msg.of("expected.datetime_iso")
        case _:
            return Msg.of("expected.text")
