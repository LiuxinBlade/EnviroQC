"""Rules model and YAML loader.

The rules file is validated strictly: unknown keys, wrong types and
inconsistent values raise :class:`~enviroqc.exceptions.ConfigError` with the
exact location of the problem (for example ``columns[2].range.min``).
"""

from __future__ import annotations

import difflib
import hashlib
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ConfigError
from .i18n import t
from .models import Severity

SUPPORTED_RULES_VERSION = 1

DEFAULT_MISSING_VALUES: tuple[str, ...] = (
    "",
    "NA",
    "N/A",
    "NaN",
    "nan",
    "null",
    "NULL",
    "None",
)


class ColumnType(StrEnum):
    """Value types a column can be declared with."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"


NUMERIC_TYPES = frozenset({ColumnType.INTEGER, ColumnType.FLOAT})


@dataclass(frozen=True)
class RangeRule:
    """A configurable numeric bound. Not a regulatory limit unless you say so."""

    name: str
    min: float | None = None
    max: float | None = None
    min_inclusive: bool = True
    max_inclusive: bool = True
    severity: Severity = Severity.WARNING
    note: str | None = None


@dataclass(frozen=True)
class ColumnSpec:
    """Expectations for a single column."""

    name: str
    type: ColumnType = ColumnType.STRING
    required: bool = True
    nullable: bool = False
    missing_severity: Severity = Severity.ERROR
    type_severity: Severity = Severity.ERROR
    format: str | None = None
    pattern: str | None = None
    allowed: tuple[str, ...] | None = None
    ranges: tuple[RangeRule, ...] = ()
    unit: str | None = None
    description: str | None = None

    @property
    def compiled_pattern(self) -> re.Pattern[str] | None:
        return re.compile(self.pattern) if self.pattern is not None else None


@dataclass(frozen=True)
class DuplicateRule:
    """Rows sharing the same values in ``columns`` are duplicates.

    ``columns`` is ``None`` when every column of the file must match
    (exact duplicate rows).
    """

    name: str
    columns: tuple[str, ...] | None
    severity: Severity = Severity.ERROR


@dataclass(frozen=True)
class InputOptions:
    """How the data file is read."""

    encoding: str = "utf-8-sig"
    delimiter: str = ","
    sheet: str | None = None
    header_row: int = 1
    missing_values: tuple[str, ...] = DEFAULT_MISSING_VALUES


@dataclass(frozen=True)
class RuleSet:
    """A complete, validated rules configuration."""

    columns: tuple[ColumnSpec, ...]
    duplicates: tuple[DuplicateRule, ...] = ()
    input: InputOptions = field(default_factory=InputOptions)
    unexpected_columns: Severity | None = Severity.WARNING
    name: str | None = None
    description: str | None = None
    source_path: str | None = None
    source_sha256: str | None = None

    def column(self, name: str) -> ColumnSpec | None:
        for spec in self.columns:
            if spec.name == name:
                return spec
        return None


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def load_rules(path: str | Path) -> RuleSet:
    """Read and validate a YAML rules file."""
    p = Path(path)
    if not p.is_file():
        raise ConfigError(t("cfg.not_found", path=p))
    try:
        raw_bytes = p.read_bytes()
    except OSError as exc:
        raise ConfigError(t("cfg.read_failed", path=p, reason=exc.strerror or exc)) from exc
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ConfigError(
            t("cfg.not_utf8", path=p, offset=exc.start),
            hint=t("cfg.not_utf8.hint"),
        ) from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        location = ""
        mark = getattr(exc, "problem_mark", None)
        if mark is not None:
            location = t("cfg.yaml_location", line=mark.line + 1, column=mark.column + 1)
        raise ConfigError(t("cfg.yaml_error", path=p, location=location, error=exc)) from exc
    rules = parse_rules(data)
    return _with_source(rules, str(p), hashlib.sha256(raw_bytes).hexdigest())


def _with_source(rules: RuleSet, path: str, sha: str) -> RuleSet:
    from dataclasses import replace

    return replace(rules, source_path=path, source_sha256=sha)


def parse_rules(data: Any) -> RuleSet:
    """Validate an already-parsed rules mapping (e.g. from YAML or JSON)."""
    if data is None:
        raise ConfigError(t("cfg.empty"))
    top = _mapping(data, "rules")
    _check_keys(
        top,
        "rules",
        allowed={
            "version",
            "name",
            "description",
            "input",
            "columns",
            "duplicates",
            "unexpected_columns",
        },
        required={"version", "columns"},
    )
    version = top["version"]
    if version != SUPPORTED_RULES_VERSION or isinstance(version, bool):
        raise ConfigError(
            t(
                "cfg.bad_version",
                where="rules.version",
                value=version,
                supported=SUPPORTED_RULES_VERSION,
            )
        )

    input_opts = _parse_input(top.get("input"), "input")

    raw_columns = top["columns"]
    if not isinstance(raw_columns, list) or not raw_columns:
        raise ConfigError(t("cfg.columns_empty"))
    columns = tuple(_parse_column(c, f"columns[{i}]") for i, c in enumerate(raw_columns))
    seen: set[str] = set()
    for i, col in enumerate(columns):
        if col.name in seen:
            raise ConfigError(t("cfg.column_twice", where=f"columns[{i}].name", name=col.name))
        seen.add(col.name)

    raw_dups = top.get("duplicates", [])
    if raw_dups is None:
        raw_dups = []
    if not isinstance(raw_dups, list):
        raise ConfigError(t("cfg.dups_not_list"))
    duplicates = tuple(
        _parse_duplicate(d, f"duplicates[{i}]", seen) for i, d in enumerate(raw_dups)
    )
    dup_names = [d.name for d in duplicates]
    for name in dup_names:
        if dup_names.count(name) > 1:
            raise ConfigError(t("cfg.dup_name_reused", name=name))

    unexpected = top.get("unexpected_columns", "warning")
    if unexpected == "ignore":
        unexpected_sev: Severity | None = None
    else:
        unexpected_sev = _severity(unexpected, "unexpected_columns", extra=("ignore",))

    return RuleSet(
        columns=columns,
        duplicates=duplicates,
        input=input_opts,
        unexpected_columns=unexpected_sev,
        name=_opt_str(top.get("name"), "name"),
        description=_opt_str(top.get("description"), "description"),
    )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(t("cfg.expected_mapping", where=where, got=_type_name(value)))
    for key in value:
        if not isinstance(key, str):
            raise ConfigError(t("cfg.key_not_string", where=where, key=key))
    return value


def _check_keys(
    mapping: dict[str, Any], where: str, *, allowed: set[str], required: set[str] = frozenset()
) -> None:
    for key in mapping:
        if key not in allowed:
            close = difflib.get_close_matches(key, sorted(allowed), n=1)
            suggestion = t("cfg.did_you_mean", key=close[0]) if close else ""
            raise ConfigError(
                t(
                    "cfg.unknown_key",
                    where=where,
                    key=key,
                    suggestion=suggestion,
                    allowed=", ".join(sorted(allowed)),
                )
            )
    for key in sorted(required):
        if key not in mapping:
            raise ConfigError(t("cfg.missing_key", where=where, key=key))


def _type_name(value: Any) -> str:
    if value is None:
        return t("cfg.kind.null")
    kind = {dict: "mapping", list: "list", str: "string", bool: "boolean"}.get(type(value))
    if kind is None:
        return t("cfg.kind.other", name=type(value).__name__)
    return t(f"cfg.kind.{kind}")


def _opt_str(value: Any, where: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(t("cfg.expected_string", where=where, got=_type_name(value)))
    return value


def _req_str(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(t("cfg.expected_nonempty_string", where=where, value=value))
    return value.strip()


def _bool(value: Any, where: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(t("cfg.expected_bool", where=where, value=value))
    return value


def _number(value: Any, where: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError(t("cfg.expected_number", where=where, value=value))
    if value != value or value in (float("inf"), float("-inf")):
        raise ConfigError(t("cfg.finite_number", where=where, value=value))
    return float(value)


def _severity(value: Any, where: str, extra: tuple[str, ...] = ()) -> Severity:
    choices = [s.value for s in Severity] + list(extra)
    if not isinstance(value, str) or value not in {s.value for s in Severity}:
        raise ConfigError(
            t("cfg.expected_one_of", where=where, choices=", ".join(choices), value=value)
        )
    return Severity(value)


def _parse_input(value: Any, where: str) -> InputOptions:
    if value is None:
        return InputOptions()
    m = _mapping(value, where)
    _check_keys(
        m,
        where,
        allowed={"encoding", "delimiter", "sheet", "header_row", "missing_values"},
    )
    kwargs: dict[str, Any] = {}
    if "encoding" in m:
        enc = _req_str(m["encoding"], f"{where}.encoding")
        import codecs

        try:
            codecs.lookup(enc)
        except LookupError as exc:
            raise ConfigError(
                t("cfg.unknown_encoding", where=f"{where}.encoding", value=enc)
            ) from exc
        kwargs["encoding"] = enc
    if "delimiter" in m:
        delim = m["delimiter"]
        if not isinstance(delim, str) or len(delim) != 1 or delim in '\r\n"':
            raise ConfigError(t("cfg.bad_delimiter", where=f"{where}.delimiter", value=delim))
        kwargs["delimiter"] = delim
    if "sheet" in m:
        kwargs["sheet"] = None if m["sheet"] is None else _req_str(m["sheet"], f"{where}.sheet")
    if "header_row" in m:
        hr = m["header_row"]
        if isinstance(hr, bool) or not isinstance(hr, int) or hr < 1:
            raise ConfigError(t("cfg.bad_header_row", where=f"{where}.header_row", value=hr))
        kwargs["header_row"] = hr
    if "missing_values" in m:
        mv = m["missing_values"]
        if not isinstance(mv, list) or not all(isinstance(x, str | int | float) for x in mv):
            raise ConfigError(t("cfg.missing_values_list", where=f"{where}.missing_values"))
        # Booleans are rejected because YAML turns `no`/`yes` into booleans silently.
        if any(isinstance(x, bool) for x in mv):
            raise ConfigError(t("cfg.missing_values_bool", where=f"{where}.missing_values"))
        tokens = tuple(_token(x) for x in mv)
        kwargs["missing_values"] = tokens
    return InputOptions(**kwargs)


def _token(x: str | int | float) -> str:
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x).strip()


_COLUMN_KEYS = {
    "name",
    "type",
    "required",
    "nullable",
    "missing_severity",
    "type_severity",
    "format",
    "pattern",
    "allowed",
    "range",
    "ranges",
    "unit",
    "description",
}


def _parse_column(value: Any, where: str) -> ColumnSpec:
    m = _mapping(value, where)
    _check_keys(m, where, allowed=_COLUMN_KEYS, required={"name"})
    name = _req_str(m["name"], f"{where}.name")
    raw_type = m.get("type", "string")
    try:
        col_type = ColumnType(raw_type)
    except ValueError as exc:
        raise ConfigError(
            t(
                "cfg.unknown_type",
                where=f"{where}.type",
                value=raw_type,
                choices=", ".join(ct.value for ct in ColumnType),
            )
        ) from exc

    fmt = _opt_str(m.get("format"), f"{where}.format")
    if fmt is not None and col_type not in (ColumnType.DATE, ColumnType.DATETIME):
        raise ConfigError(t("cfg.format_only_dates", where=f"{where}.format"))
    if fmt is not None and "%" not in fmt:
        raise ConfigError(t("cfg.format_not_strftime", where=f"{where}.format", value=fmt))

    pattern = _opt_str(m.get("pattern"), f"{where}.pattern")
    if pattern is not None:
        if col_type is not ColumnType.STRING:
            raise ConfigError(t("cfg.only_string", where=f"{where}.pattern"))
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ConfigError(t("cfg.bad_regex", where=f"{where}.pattern", error=exc)) from exc

    allowed = m.get("allowed")
    allowed_t: tuple[str, ...] | None = None
    if allowed is not None:
        if col_type is not ColumnType.STRING:
            raise ConfigError(t("cfg.only_string", where=f"{where}.allowed"))
        if (
            not isinstance(allowed, list)
            or not allowed
            or not all(
                isinstance(a, str | int | float) and not isinstance(a, bool) for a in allowed
            )
        ):
            raise ConfigError(t("cfg.allowed_list", where=f"{where}.allowed"))
        allowed_t = tuple(_token(a) for a in allowed)

    if "range" in m and "ranges" in m:
        raise ConfigError(t("cfg.range_and_ranges", where=where))
    raw_ranges: list[Any]
    if "range" in m:
        raw_ranges = [m["range"]]
        range_where = [f"{where}.range"]
    else:
        rr = m.get("ranges", [])
        if rr is None:
            rr = []
        if not isinstance(rr, list):
            raise ConfigError(t("cfg.ranges_list", where=f"{where}.ranges"))
        raw_ranges = rr
        range_where = [f"{where}.ranges[{i}]" for i in range(len(rr))]
    ranges = tuple(
        _parse_range(r, w, name, idx)
        for idx, (r, w) in enumerate(zip(raw_ranges, range_where, strict=True))
    )
    if ranges and col_type not in NUMERIC_TYPES:
        raise ConfigError(t("cfg.ranges_numeric_only", where=where))
    range_names = [r.name for r in ranges]
    if len(set(range_names)) != len(range_names):
        raise ConfigError(t("cfg.range_names_unique", where=where))

    return ColumnSpec(
        name=name,
        type=col_type,
        required=_bool(m.get("required", True), f"{where}.required"),
        nullable=_bool(m.get("nullable", False), f"{where}.nullable"),
        missing_severity=_severity(m.get("missing_severity", "error"), f"{where}.missing_severity"),
        type_severity=_severity(m.get("type_severity", "error"), f"{where}.type_severity"),
        format=fmt,
        pattern=pattern,
        allowed=allowed_t,
        ranges=ranges,
        unit=_opt_str(m.get("unit"), f"{where}.unit"),
        description=_opt_str(m.get("description"), f"{where}.description"),
    )


def _parse_range(value: Any, where: str, column: str, index: int) -> RangeRule:
    m = _mapping(value, where)
    _check_keys(
        m,
        where,
        allowed={"name", "min", "max", "min_inclusive", "max_inclusive", "severity", "note"},
    )
    lo = _number(m.get("min"), f"{where}.min")
    hi = _number(m.get("max"), f"{where}.max")
    if lo is None and hi is None:
        raise ConfigError(t("cfg.range_needs_bound", where=where))
    if lo is not None and hi is not None and lo > hi:
        raise ConfigError(t("cfg.range_min_gt_max", where=where, min=lo, max=hi))
    default_name = f"{column}.range" if index == 0 else f"{column}.range{index + 1}"
    name = _req_str(m["name"], f"{where}.name") if "name" in m else default_name
    return RangeRule(
        name=name,
        min=lo,
        max=hi,
        min_inclusive=_bool(m.get("min_inclusive", True), f"{where}.min_inclusive"),
        max_inclusive=_bool(m.get("max_inclusive", True), f"{where}.max_inclusive"),
        severity=_severity(m.get("severity", "warning"), f"{where}.severity"),
        note=_opt_str(m.get("note"), f"{where}.note"),
    )


def _parse_duplicate(value: Any, where: str, known_columns: set[str]) -> DuplicateRule:
    m = _mapping(value, where)
    _check_keys(m, where, allowed={"name", "columns", "severity"}, required={"columns"})
    cols = m["columns"]
    columns: tuple[str, ...] | None
    if cols == "*":
        columns = None
    else:
        if not isinstance(cols, list) or not cols or not all(isinstance(c, str) for c in cols):
            raise ConfigError(t("cfg.dup_columns_list", where=f"{where}.columns"))
        if len(set(cols)) != len(cols):
            raise ConfigError(t("cfg.dup_columns_repeat", where=f"{where}.columns"))
        unknown = [c for c in cols if c not in known_columns]
        if unknown:
            raise ConfigError(
                t(
                    "cfg.dup_columns_unknown",
                    where=f"{where}.columns",
                    columns=", ".join(map(repr, unknown)),
                )
            )
        columns = tuple(cols)
    default_name = "duplicate_rows" if columns is None else "duplicate_" + "_".join(columns)
    name = _req_str(m["name"], f"{where}.name") if "name" in m else default_name
    return DuplicateRule(
        name=name,
        columns=columns,
        severity=_severity(m.get("severity", "error"), f"{where}.severity"),
    )
