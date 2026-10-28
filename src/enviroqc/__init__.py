"""EnviroQC: data quality checks for environmental monitoring datasets.

Typical use::

    from enviroqc import validate_file, write_report

    report = validate_file("data.csv", "rules.yaml")
    print(report.summary()["by_severity"])
    write_report(report, "report.html")
"""

__version__ = "0.1.0"

from .config import (
    ColumnSpec,
    ColumnType,
    DuplicateRule,
    InputOptions,
    RangeRule,
    RuleSet,
    load_rules,
    parse_rules,
)
from .exceptions import (
    ConfigError,
    CorruptFileError,
    EmptyFileError,
    EncodingError,
    EnviroQCError,
    ExitCode,
    FileNotFoundInputError,
    HeaderError,
    InputFileError,
    OutputError,
    UnsupportedFormatError,
)
from .i18n import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    get_language,
    set_language,
)
from .models import REPORT_SCHEMA_VERSION, Check, Issue, Report, Severity
from .reader import read_table
from .report import render_html, write_report
from .validator import validate_dataframe, validate_file, validate_table

__all__ = [
    "DEFAULT_LANGUAGE",
    "REPORT_SCHEMA_VERSION",
    "SUPPORTED_LANGUAGES",
    "Check",
    "ColumnSpec",
    "ColumnType",
    "ConfigError",
    "CorruptFileError",
    "DuplicateRule",
    "EmptyFileError",
    "EncodingError",
    "EnviroQCError",
    "ExitCode",
    "FileNotFoundInputError",
    "HeaderError",
    "InputFileError",
    "InputOptions",
    "Issue",
    "OutputError",
    "RangeRule",
    "Report",
    "RuleSet",
    "Severity",
    "UnsupportedFormatError",
    "__version__",
    "get_language",
    "load_rules",
    "parse_rules",
    "read_table",
    "render_html",
    "set_language",
    "validate_dataframe",
    "validate_file",
    "validate_table",
    "write_report",
]
