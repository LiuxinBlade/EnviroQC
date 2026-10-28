"""Core data models: severities, issues and the validation report.

The JSON form of :class:`Report` is described in ``docs/report-schema.md`` and
versioned by :data:`REPORT_SCHEMA_VERSION`.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .i18n import DEFAULT_LANGUAGE, Msg, resolve_language, t

REPORT_SCHEMA_VERSION = "1.0"


class Severity(StrEnum):
    """How serious an issue is. Ordered: info < warning < error."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    @property
    def rank(self) -> int:
        return _SEVERITY_RANK[self]


_SEVERITY_RANK = {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}


class Check(StrEnum):
    """The kind of check that produced an issue (stable identifiers)."""

    MISSING_COLUMN = "missing_column"
    UNEXPECTED_COLUMN = "unexpected_column"
    MALFORMED_ROW = "malformed_row"
    EMPTY_DATASET = "empty_dataset"
    MISSING_VALUE = "missing_value"
    INVALID_TYPE = "invalid_type"
    PATTERN_MISMATCH = "pattern_mismatch"
    NOT_ALLOWED = "not_allowed"
    OUT_OF_RANGE = "out_of_range"
    DUPLICATE_RECORD = "duplicate_record"


@dataclass(frozen=True)
class Issue:
    """One data-quality finding, traceable to a source row.

    ``row`` is the 1-based row number in the source file (the physical line in a
    CSV file where the record starts, or the Excel row number). It is ``None``
    for file-level findings such as a missing column.
    """

    file: str
    row: int | None
    column: str | None
    check: Check
    rule: str
    severity: Severity
    msg: Msg
    """Message key and parameters; rendered in either language on demand."""
    value: str | None = None
    expected_msg: Msg | str | None = None
    sheet: str | None = None
    related_rows: tuple[int, ...] = ()
    lang: str = DEFAULT_LANGUAGE
    """Language used by :attr:`message` and :attr:`expected`."""

    @property
    def message(self) -> str:
        return self.msg.render(self.lang)

    @property
    def expected(self) -> str | None:
        return self.expected_in(self.lang)

    def message_in(self, lang: str | None) -> str:
        return self.msg.render(lang)

    def expected_in(self, lang: str | None) -> str | None:
        if isinstance(self.expected_msg, Msg):
            return self.expected_msg.render(lang)
        return self.expected_msg

    def to_dict(self, lang: str | None = None) -> dict[str, Any]:
        language = self.lang if lang is None else resolve_language(lang)
        return {
            "file": self.file,
            "sheet": self.sheet,
            "row": self.row,
            "column": self.column,
            "check": self.check.value,
            "rule": self.rule,
            "severity": self.severity.value,
            "message_id": self.msg.key,
            "message": self.message_in(language),
            "value": self.value,
            "expected": self.expected_in(language),
            "related_rows": list(self.related_rows),
        }


@dataclass
class ColumnStats:
    """Per-column counters for the summary."""

    present: bool = True
    missing: int = 0
    invalid_type: int = 0
    out_of_range: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "present": self.present,
            "missing": self.missing,
            "invalid_type": self.invalid_type,
            "out_of_range": self.out_of_range,
        }


@dataclass(frozen=True)
class SourceInfo:
    """Description of the validated data file."""

    file: str
    path: str
    format: str
    sha256: str | None
    sheet: str | None
    header_row: int
    data_rows: int
    columns: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "path": self.path,
            "format": self.format,
            "sha256": self.sha256,
            "sheet": self.sheet,
            "header_row": self.header_row,
            "data_rows": self.data_rows,
            "columns": list(self.columns),
        }


@dataclass
class Report:
    """The result of validating one data file against one rule set."""

    source: SourceInfo
    issues: list[Issue]
    column_stats: dict[str, ColumnStats]
    tool_version: str
    generated_at: str
    rules_name: str | None = None
    rules_path: str | None = None
    rules_sha256: str | None = None
    lang: str = DEFAULT_LANGUAGE
    """Default language for :meth:`to_dict`, :meth:`to_json` and :meth:`to_html`."""
    extra: dict[str, Any] = field(default_factory=dict)

    # ---- convenience -----------------------------------------------------

    def count(self, severity: Severity) -> int:
        return sum(1 for i in self.issues if i.severity is severity)

    @property
    def error_count(self) -> int:
        return self.count(Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return self.count(Severity.WARNING)

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    @property
    def status(self) -> str:
        """``"fail"`` if any error, ``"warn"`` if any warning, else ``"pass"``."""
        if self.error_count:
            return "fail"
        if self.warning_count:
            return "warn"
        return "pass"

    def max_severity(self) -> Severity | None:
        if not self.issues:
            return None
        return max((i.severity for i in self.issues), key=lambda s: s.rank)

    def issues_at_least(self, severity: Severity) -> list[Issue]:
        return [i for i in self.issues if i.severity.rank >= severity.rank]

    @property
    def rows_with_issues(self) -> int:
        return len({i.row for i in self.issues if i.row is not None})

    def summary(self) -> dict[str, Any]:
        by_sev = Counter(i.severity.value for i in self.issues)
        by_check = Counter(i.check.value for i in self.issues)
        by_rule = Counter(i.rule for i in self.issues)
        return {
            "status": self.status,
            "total_issues": len(self.issues),
            "by_severity": {s.value: by_sev.get(s.value, 0) for s in Severity},
            "by_check": dict(sorted(by_check.items())),
            "by_rule": dict(sorted(by_rule.items())),
            "data_rows": self.source.data_rows,
            "rows_with_issues": self.rows_with_issues,
            "columns": {name: st.to_dict() for name, st in self.column_stats.items()},
        }

    # ---- serialisation ---------------------------------------------------

    def to_dict(self, lang: str | None = None) -> dict[str, Any]:
        language = self.lang if lang is None else resolve_language(lang)
        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "tool": {"name": "enviroqc", "version": self.tool_version},
            "generated_at": self.generated_at,
            "language": language,
            "disclaimer": t("disclaimer", language),
            "source": self.source.to_dict(),
            "rules": {
                "name": self.rules_name,
                "path": self.rules_path,
                "sha256": self.rules_sha256,
            },
            "summary": self.summary(),
            "issues": [i.to_dict(language) for i in self.issues],
        }

    def to_json(self, *, indent: int | None = 2, lang: str | None = None) -> str:
        return json.dumps(self.to_dict(lang), ensure_ascii=False, indent=indent)

    def to_html(self, lang: str | None = None) -> str:
        from .report import render_html

        return render_html(self, lang)
