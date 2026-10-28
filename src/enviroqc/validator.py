"""Run a :class:`~enviroqc.config.RuleSet` against a table and build a report."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import __version__
from .coerce import coerce, display, expected_description, is_missing
from .config import ColumnSpec, DuplicateRule, RangeRule, RuleSet, load_rules
from .i18n import Msg, resolve_language
from .models import Check, ColumnStats, Issue, Report, Severity, SourceInfo
from .reader import Record, Table, read_table

_CHECK_ORDER = {c: i for i, c in enumerate(Check)}
_MISSING_KEY = object()


def validate_file(
    path: str | Path,
    rules: RuleSet | str | Path,
    *,
    encoding: str | None = None,
    sheet: str | None = None,
    delimiter: str | None = None,
    lang: str | None = None,
) -> Report:
    """Validate a CSV/XLSX file. The file is opened read-only and never modified.

    ``encoding``, ``sheet`` and ``delimiter`` override the ``input`` section of
    the rules file when given. ``lang`` (``"zh"`` or ``"en"``) sets the report
    language; by default the current language (Chinese unless changed) is used.
    """
    ruleset = rules if isinstance(rules, RuleSet) else load_rules(rules)
    overrides: dict[str, Any] = {}
    if encoding is not None:
        overrides["encoding"] = encoding
    if sheet is not None:
        overrides["sheet"] = sheet
    if delimiter is not None:
        overrides["delimiter"] = delimiter
    options = replace(ruleset.input, **overrides) if overrides else ruleset.input
    table = read_table(path, options)
    return validate_table(table, ruleset, lang=lang)


def validate_dataframe(
    df: Any, rules: RuleSet | str | Path, *, name: str = "<dataframe>", lang: str | None = None
) -> Report:
    """Validate a pandas DataFrame.

    Row numbers in the report are spreadsheet-style: the first DataFrame row is
    reported as row 2 (the header being row 1).
    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "validate_dataframe() needs pandas / 需要安装 pandas: pip install 'enviroqc[pandas]'"
        ) from exc

    ruleset = rules if isinstance(rules, RuleSet) else load_rules(rules)
    header = tuple(str(c).strip() for c in df.columns)
    records = []
    for pos, row in enumerate(df.itertuples(index=False, name=None)):
        values = tuple(_from_pandas(v, pd) for v in row)
        records.append(Record(row=pos + 2, values=values))
    table = Table(
        file=name,
        path=name,
        format="dataframe",
        sheet=None,
        header=header,
        header_row=1,
        records=tuple(records),
        sha256=None,
    )
    return validate_table(table, ruleset, lang=lang)


def _from_pandas(v: Any, pd: Any) -> Any:
    if v is None or v is pd.NA or v is pd.NaT:
        return None
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    if type(v).__module__ == "numpy" and hasattr(v, "item"):
        v = v.item()
    return v


def validate_table(table: Table, rules: RuleSet, *, lang: str | None = None) -> Report:
    """Validate an already-loaded table."""
    language = resolve_language(lang)
    v = _Validation(table, rules, language)
    v.run()
    issues = sorted(v.issues, key=v.sort_key)
    source = SourceInfo(
        file=table.file,
        path=table.path,
        format=table.format,
        sha256=table.sha256,
        sheet=table.sheet,
        header_row=table.header_row,
        data_rows=len(table.records),
        columns=table.header,
    )
    return Report(
        source=source,
        issues=issues,
        column_stats=v.stats,
        tool_version=__version__,
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        rules_name=rules.name,
        rules_path=rules.source_path,
        rules_sha256=rules.source_sha256,
        lang=language,
    )


class _Validation:
    def __init__(self, table: Table, rules: RuleSet, lang: str) -> None:
        self.lang = lang
        self.table = table
        self.rules = rules
        self.issues: list[Issue] = []
        self.index = {name: i for i, name in enumerate(table.header)}
        self.missing_tokens = frozenset(rules.input.missing_values)
        self.stats: dict[str, ColumnStats] = {
            spec.name: ColumnStats(present=spec.name in self.index) for spec in rules.columns
        }
        # Parsed values per (row number, column name), reused by duplicate checks.
        self.parsed: dict[tuple[int, str], Any] = {}

    # ---- helpers ---------------------------------------------------------

    def add(self, **kwargs: Any) -> None:
        self.issues.append(
            Issue(file=self.table.file, sheet=self.table.sheet, lang=self.lang, **kwargs)
        )

    def sort_key(self, issue: Issue) -> tuple[int, int, int, str]:
        # Within a row: malformed-row first, then cells in file column order, then
        # multi-column findings such as duplicates.
        if issue.column in self.index:
            col = self.index[issue.column]
        elif issue.row is None or issue.check is Check.MALFORMED_ROW:
            col = -1
        else:
            col = len(self.index)
        return (
            -1 if issue.row is None else issue.row,
            col,
            _CHECK_ORDER[issue.check],
            issue.rule,
        )

    # ---- checks ----------------------------------------------------------

    def run(self) -> None:
        self.check_columns()
        if not self.table.records:
            self.add(
                row=None,
                column=None,
                check=Check.EMPTY_DATASET,
                rule="dataset.not_empty",
                severity=Severity.WARNING,
                msg=Msg.of("issue.empty_dataset"),
            )
        width = len(self.table.header)
        present_specs = [s for s in self.rules.columns if s.name in self.index]
        for record in self.table.records:
            n = len(record.values)
            if n != width:
                self.add(
                    row=record.row,
                    column=None,
                    check=Check.MALFORMED_ROW,
                    rule="row.field_count",
                    severity=Severity.ERROR,
                    msg=Msg.of(
                        "issue.malformed_long" if n > width else "issue.malformed_short",
                        n=n,
                        width=width,
                    ),
                    value=str(n),
                    expected_msg=str(width),
                )
            for spec in present_specs:
                idx = self.index[spec.name]
                if idx >= n:
                    continue
                self.check_cell(record, spec, record.values[idx])
        for rule in self.rules.duplicates:
            self.check_duplicates(rule)

    def check_columns(self) -> None:
        for spec in self.rules.columns:
            if spec.name not in self.index and spec.required:
                self.add(
                    row=None,
                    column=spec.name,
                    check=Check.MISSING_COLUMN,
                    rule=f"{spec.name}.required",
                    severity=Severity.ERROR,
                    msg=Msg.of("issue.missing_column", column=spec.name),
                    expected_msg=spec.name,
                )
        sev = self.rules.unexpected_columns
        if sev is None:
            return
        for name in self.table.header:
            if self.rules.column(name) is None:
                self.add(
                    row=None,
                    column=name,
                    check=Check.UNEXPECTED_COLUMN,
                    rule="columns.unexpected",
                    severity=sev,
                    msg=Msg.of("issue.unexpected_column", column=name),
                )

    def check_cell(self, record: Record, spec: ColumnSpec, raw: Any) -> None:
        stats = self.stats[spec.name]
        if is_missing(raw, self.missing_tokens):
            stats.missing += 1
            self.parsed[(record.row, spec.name)] = _MISSING_KEY
            if not spec.nullable:
                self.add(
                    row=record.row,
                    column=spec.name,
                    check=Check.MISSING_VALUE,
                    rule=f"{spec.name}.not_null",
                    severity=spec.missing_severity,
                    msg=Msg.of("issue.missing_value", column=spec.name),
                    value=None if raw is None else display(raw),
                    expected_msg=Msg.of("expected.value"),
                )
            return
        result = coerce(raw, spec)
        shown = display(raw)
        if not result.ok:
            stats.invalid_type += 1
            self.parsed[(record.row, spec.name)] = ("raw", shown.strip())
            self.add(
                row=record.row,
                column=spec.name,
                check=Check.INVALID_TYPE,
                rule=f"{spec.name}.type",
                severity=spec.type_severity,
                msg=Msg.of(
                    "issue.invalid_type",
                    value=shown,
                    column=spec.name,
                    type=Msg.of(f"type.{spec.type.value}"),
                ),
                value=shown,
                expected_msg=expected_description(spec),
            )
            return
        value = result.value
        self.parsed[(record.row, spec.name)] = value
        pattern = spec.compiled_pattern
        if pattern is not None and not pattern.fullmatch(value):
            self.add(
                row=record.row,
                column=spec.name,
                check=Check.PATTERN_MISMATCH,
                rule=f"{spec.name}.pattern",
                severity=Severity.ERROR,
                msg=Msg.of("issue.pattern_mismatch", value=shown, column=spec.name),
                value=shown,
                expected_msg=spec.pattern,
            )
        if spec.allowed is not None and value not in spec.allowed:
            self.add(
                row=record.row,
                column=spec.name,
                check=Check.NOT_ALLOWED,
                rule=f"{spec.name}.allowed",
                severity=Severity.ERROR,
                msg=Msg.of("issue.not_allowed", value=shown, column=spec.name),
                value=shown,
                expected_msg=", ".join(spec.allowed),
            )
        violated = False
        for rr in spec.ranges:
            problem = _range_problem(float(value), rr)
            if problem is None:
                continue
            violated = True
            key, bound = problem
            unit = f" {spec.unit}" if spec.unit else ""
            note: Msg | str = Msg.of("issue.note", note=rr.note) if rr.note else ""
            self.add(
                row=record.row,
                column=spec.name,
                check=Check.OUT_OF_RANGE,
                rule=rr.name,
                severity=rr.severity,
                msg=Msg.of(key, column=spec.name, value=shown, unit=unit, bound=bound, note=note),
                value=shown,
                expected_msg=_range_text(rr),
            )
        if violated:
            stats.out_of_range += 1

    def check_duplicates(self, rule: DuplicateRule) -> None:
        if rule.columns is None:
            cols = list(self.table.header)
        else:
            if any(c not in self.index for c in rule.columns):
                return  # reported as missing columns already
            cols = list(rule.columns)
        first_seen: dict[tuple[Any, ...], int] = {}
        for record in self.table.records:
            key_parts: list[Any] = []
            skip = False
            for c in cols:
                k = self._key_part(record, c)
                if k is _MISSING_KEY and rule.columns is not None:
                    skip = True  # incomplete keys are reported as missing values instead
                    break
                key_parts.append(("<missing>",) if k is _MISSING_KEY else k)
            if skip:
                continue
            key = tuple(key_parts)
            first = first_seen.get(key)
            if first is None:
                first_seen[key] = record.row
                continue
            msg = (
                Msg.of("issue.duplicate_all", first=first)
                if rule.columns is None
                else Msg.of("issue.duplicate_keys", first=first, columns=", ".join(cols))
            )
            shown = (
                None
                if rule.columns is None
                else " | ".join(_key_display(record, self.index[c]) for c in cols)
            )
            self.add(
                row=record.row,
                column=None if rule.columns is None else ", ".join(cols),
                check=Check.DUPLICATE_RECORD,
                rule=rule.name,
                severity=rule.severity,
                msg=msg,
                value=shown,
                expected_msg=Msg.of("expected.unique"),
                related_rows=(first,),
            )

    def _key_part(self, record: Record, column: str) -> Any:
        if (record.row, column) in self.parsed:
            return self.parsed[(record.row, column)]
        idx = self.index[column]
        raw = record.values[idx] if idx < len(record.values) else None
        if is_missing(raw, self.missing_tokens):
            return _MISSING_KEY
        return ("raw", display(raw).strip())


def _key_display(record: Record, idx: int) -> str:
    raw = record.values[idx] if idx < len(record.values) else None
    return "" if raw is None else display(raw)


def _range_problem(x: float, rr: RangeRule) -> tuple[str, str] | None:
    """Return (message key, bound) if ``x`` violates ``rr``."""
    if rr.min is not None and (x < rr.min or (not rr.min_inclusive and x == rr.min)):
        key = "issue.range_below" if rr.min_inclusive else "issue.range_at_or_below"
        return key, _num(rr.min)
    if rr.max is not None and (x > rr.max or (not rr.max_inclusive and x == rr.max)):
        key = "issue.range_above" if rr.max_inclusive else "issue.range_at_or_above"
        return key, _num(rr.max)
    return None


def _range_text(rr: RangeRule) -> Msg | str:
    low = f"{'>=' if rr.min_inclusive else '>'} {_num(rr.min)}" if rr.min is not None else None
    high = f"{'<=' if rr.max_inclusive else '<'} {_num(rr.max)}" if rr.max is not None else None
    if low and high:
        return Msg.of("expected.range_both", low=low, high=high)
    return low or high or ""


def _num(x: float) -> str:
    """Format a bound without losing precision (1000.0 -> '1000', 0.1 -> '0.1')."""
    return str(int(x)) if x.is_integer() and abs(x) < 1e16 else repr(x)
