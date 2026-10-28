from __future__ import annotations

from datetime import datetime

import pytest

from enviroqc import Check, Severity, validate_file
from enviroqc.reader import Record, Table
from enviroqc.validator import validate_table

from .conftest import issues_of, make_rules


def table(header, *rows, start=2, sheet=None):
    return Table(
        file="t.csv",
        path="t.csv",
        format="csv",
        sheet=sheet,
        header=tuple(header),
        header_row=1,
        records=tuple(Record(row=start + i, values=tuple(r)) for i, r in enumerate(rows)),
    )


# ---------------------------------------------------------------- columns


def test_missing_required_column_is_a_file_level_error():
    rules = make_rules([{"name": "a"}, {"name": "b"}, {"name": "c", "required": False}])
    r = validate_table(table(["a"], ["1"]), rules)
    assert issues_of(r) == [(None, "b", "missing_column", "error")]
    assert r.column_stats["b"].present is False
    assert r.column_stats["c"].present is False


def test_unexpected_columns_severity_and_ignore():
    t = table(["a", "extra"], ["1", "2"])
    r = validate_table(t, make_rules([{"name": "a"}]))
    assert issues_of(r) == [(None, "extra", "unexpected_column", "warning")]
    r = validate_table(t, make_rules([{"name": "a"}], unexpected_columns="error"))
    assert issues_of(r) == [(None, "extra", "unexpected_column", "error")]
    r = validate_table(t, make_rules([{"name": "a"}], unexpected_columns="ignore"))
    assert r.issues == []


def test_empty_dataset_warning():
    r = validate_table(table(["a"]), make_rules([{"name": "a"}]))
    assert issues_of(r) == [(None, None, "empty_dataset", "warning")]
    assert r.status == "warn"


def test_malformed_rows_short_and_long():
    rules = make_rules([{"name": "a"}, {"name": "b"}])
    r = validate_table(table(["a", "b"], ["1"], ["1", "2", "3"], ["4", "5"]), rules)
    # The short row is not double-reported as a missing value for 'b'.
    assert issues_of(r) == [
        (2, None, "malformed_row", "error"),
        (3, None, "malformed_row", "error"),
    ]
    assert r.issues[0].value == "1" and r.issues[0].expected == "2"


# ---------------------------------------------------------------- missing


def test_missing_values_reported_only_for_non_nullable_columns():
    rules = make_rules(
        [
            {"name": "a"},
            {"name": "b", "nullable": True},
            {"name": "c", "missing_severity": "warning"},
        ]
    )
    r = validate_table(table(["a", "b", "c"], ["", "", " "], ["x", "NA", "y"]), rules)
    assert issues_of(r) == [
        (2, "a", "missing_value", "error"),
        (2, "c", "missing_value", "warning"),
    ]
    assert r.column_stats["b"].missing == 2
    assert r.column_stats["a"].missing == 1


def test_custom_missing_tokens_replace_defaults():
    rules = make_rules([{"name": "v", "type": "float"}], input={"missing_values": ["-999"]})
    r = validate_table(table(["v"], ["-999"], ["NA"], [""]), rules)
    # "-999" is now missing; "NA" is no longer a missing token -> invalid number;
    # empty cells are always missing.
    assert issues_of(r) == [
        (2, "v", "missing_value", "error"),
        (3, "v", "invalid_type", "error"),
        (4, "v", "missing_value", "error"),
    ]


# ---------------------------------------------------------------- types


def test_invalid_types_with_expected_description():
    rules = make_rules(
        [
            {"name": "i", "type": "integer"},
            {"name": "f", "type": "float", "type_severity": "warning"},
            {"name": "d", "type": "date"},
            {"name": "b", "type": "boolean"},
        ]
    )
    r = validate_table(table(["i", "f", "d", "b"], ["1.5", "abc", "2024-02-30", "maybe"]), rules)
    assert issues_of(r) == [
        (2, "i", "invalid_type", "error"),
        (2, "f", "invalid_type", "warning"),
        (2, "d", "invalid_type", "error"),
        (2, "b", "invalid_type", "error"),
    ]
    assert r.issues[0].value == "1.5"
    assert "integer" in r.issues[0].expected
    assert r.column_stats["f"].invalid_type == 1


def test_pattern_and_allowed():
    rules = make_rules(
        [{"name": "id", "pattern": r"ST\d{3}"}, {"name": "flag", "allowed": ["V", "S"]}]
    )
    r = validate_table(
        table(["id", "flag"], ["ST001", "V"], ["ST0011", "v"], [" ST002 ", " S "]), rules
    )
    # fullmatch semantics; surrounding whitespace is ignored; values are case-sensitive.
    assert issues_of(r) == [
        (3, "id", "pattern_mismatch", "error"),
        (3, "flag", "not_allowed", "error"),
    ]


# ---------------------------------------------------------------- ranges


@pytest.mark.parametrize(
    ("value", "flagged"),
    [("-0.0001", True), ("0", False), ("0.0", False), ("100", False), ("100.0001", True)],
)
def test_inclusive_range_boundaries(value, flagged):
    rules = make_rules([{"name": "v", "type": "float", "range": {"min": 0, "max": 100}}])
    r = validate_table(table(["v"], [value]), rules)
    assert bool(issues_of(r, "out_of_range")) is flagged


@pytest.mark.parametrize(
    ("value", "flagged"), [("0", True), ("0.1", False), ("9.9", False), ("10", True)]
)
def test_exclusive_range_boundaries(value, flagged):
    rules = make_rules(
        [
            {
                "name": "v",
                "type": "float",
                "range": {"min": 0, "max": 10, "min_inclusive": False, "max_inclusive": False},
            }
        ]
    )
    r = validate_table(table(["v"], [value]), rules)
    assert bool(issues_of(r, "out_of_range")) is flagged


def test_multiple_ranges_with_own_severity_and_message():
    rules = make_rules(
        [
            {
                "name": "pm25",
                "type": "float",
                "unit": "µg/m³",
                "ranges": [
                    {"name": "neg", "min": 0, "severity": "error"},
                    {"name": "high", "max": 500, "severity": "info", "note": "check sensor"},
                ],
            }
        ]
    )
    r = validate_table(table(["pm25"], ["-1"], ["501"], ["250"]), rules)
    got = [(i.row, i.rule, i.severity) for i in r.issues]
    assert got == [(2, "neg", Severity.ERROR), (3, "high", Severity.INFO)]
    assert r.issues[1].message == "pm25 = 501 µg/m³ is above the maximum 500 (check sensor)."
    assert r.issues[1].expected == "<= 500"
    assert r.column_stats["pm25"].out_of_range == 2


def test_range_not_checked_for_missing_or_invalid_values():
    rules = make_rules([{"name": "v", "type": "float", "nullable": True, "range": {"min": 0}}])
    r = validate_table(table(["v"], [""], ["abc"]), rules)
    assert [i.check for i in r.issues] == [Check.INVALID_TYPE]


def test_integer_range_with_large_bounds_keeps_precision():
    rules = make_rules([{"name": "v", "type": "integer", "range": {"max": 1234567}}])
    r = validate_table(table(["v"], ["1234568"]), rules)
    assert r.issues[0].expected == "<= 1234567"


# ---------------------------------------------------------------- duplicates


def test_duplicate_keys_use_parsed_values():
    rules = make_rules(
        [{"name": "site"}, {"name": "t", "type": "datetime"}, {"name": "v", "type": "float"}],
        duplicates=[{"columns": ["site", "t"]}],
    )
    t = table(
        ["site", "t", "v"],
        ["A", "2024-01-01 00:00", "1"],
        ["A ", "2024-01-01T00:00:00", "2"],  # same key after parsing
        ["B", "2024-01-01 00:00", "3"],
        ["A", "2024-01-01 01:00", "4"],
        ["A", "2024-01-01 00:00", "5"],
    )
    r = validate_table(t, rules)
    dups = [(i.row, i.related_rows, i.rule) for i in r.issues]
    assert dups == [(3, (2,), "duplicate_site_t"), (6, (2,), "duplicate_site_t")]
    assert r.issues[0].message == "Duplicate of row 2 on site, t."


def test_numeric_duplicate_keys_compare_as_numbers():
    rules = make_rules([{"name": "k", "type": "float"}], duplicates=[{"columns": ["k"]}])
    r = validate_table(table(["k"], ["1"], ["1.0"], ["1e0"], ["2"]), rules)
    assert [i.row for i in r.issues] == [3, 4]


def test_rows_with_missing_key_are_not_duplicates():
    rules = make_rules(
        [{"name": "k", "nullable": True}, {"name": "j"}], duplicates=[{"columns": ["k", "j"]}]
    )
    r = validate_table(table(["k", "j"], ["", "x"], ["", "x"], ["a", "x"]), rules)
    assert r.issues == []


def test_invalid_values_still_participate_in_duplicate_keys():
    rules = make_rules(
        [{"name": "k", "type": "integer"}], duplicates=[{"columns": ["k"], "severity": "warning"}]
    )
    r = validate_table(table(["k"], ["x"], ["x"]), rules)
    assert issues_of(r) == [
        (2, "k", "invalid_type", "error"),
        (3, "k", "invalid_type", "error"),
        (3, "k", "duplicate_record", "warning"),
    ]


def test_exact_duplicate_rows_include_unconfigured_and_missing_cells():
    rules = make_rules(
        [{"name": "a", "nullable": True}],
        duplicates=[{"columns": "*"}],
        unexpected_columns="ignore",
    )
    t = table(["a", "note"], ["", "x"], ["", "x"], ["", "y"], ["1", "x"])
    r = validate_table(t, rules)
    assert [(i.row, i.rule, i.column, i.related_rows) for i in r.issues] == [
        (3, "duplicate_rows", None, (2,))
    ]


def test_duplicate_rule_skipped_when_key_column_absent():
    rules = make_rules([{"name": "a"}, {"name": "b"}], duplicates=[{"columns": ["a", "b"]}])
    r = validate_table(table(["a"], ["1"], ["1"]), rules)
    assert issues_of(r) == [(None, "b", "missing_column", "error")]


# ---------------------------------------------------------------- report


def test_issue_ordering_and_summary():
    rules = make_rules(
        [{"name": "a", "type": "integer"}, {"name": "b", "type": "integer", "range": {"max": 5}}],
        duplicates=[{"columns": ["a"]}],
    )
    r = validate_table(
        table(["b", "a", "z"], ["9", "x", ""], ["1", "1", ""], ["2", "1", ""]), rules
    )
    order = [(i.row, i.column, i.check.value) for i in r.issues]
    assert order == [
        (None, "z", "unexpected_column"),
        (2, "b", "out_of_range"),  # column order follows the file, not the rules
        (2, "a", "invalid_type"),
        (4, "a", "duplicate_record"),
    ]
    s = r.summary()
    assert s["status"] == "fail"
    assert s["total_issues"] == 4
    assert s["by_severity"] == {"info": 0, "warning": 2, "error": 2}
    assert s["rows_with_issues"] == 2
    assert s["data_rows"] == 3
    assert s["columns"]["a"] == {
        "present": True,
        "missing": 0,
        "invalid_type": 1,
        "out_of_range": 0,
    }


def test_clean_data_passes():
    rules = make_rules([{"name": "a", "type": "integer", "range": {"min": 0}}])
    r = validate_table(table(["a"], ["1"], ["2"]), rules)
    assert r.issues == [] and r.status == "pass" and r.max_severity() is None


def test_excel_native_values(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "data"
    ws.append(["site", "time", "v", "n", "ok"])
    ws.append(["A", datetime(2024, 1, 1, 1), 1.5, 3, True])
    ws.append(["A", "2024-01-01 02:00", "2.5", 4.0, "no"])
    ws.append(["A", datetime(2024, 1, 1, 1), -1, 2.5, "x"])
    p = tmp_path / "x.xlsx"
    wb.save(p)
    rules = make_rules(
        [
            {"name": "site"},
            {"name": "time", "type": "datetime", "format": "%Y-%m-%d %H:%M"},
            {"name": "v", "type": "float", "range": {"min": 0}},
            {"name": "n", "type": "integer"},
            {"name": "ok", "type": "boolean"},
        ],
        duplicates=[{"columns": ["site", "time"]}],
    )
    r = validate_file(p, rules)
    assert r.source.sheet == "data"
    assert issues_of(r) == [
        (4, "v", "out_of_range", "warning"),
        (4, "n", "invalid_type", "error"),
        (4, "ok", "invalid_type", "error"),
        (4, "site, time", "duplicate_record", "error"),
    ]
    assert all(i.sheet == "data" for i in r.issues)


def test_validate_file_overrides(write_csv):
    p = write_csv("a;b\n1;2\n")
    rules = make_rules([{"name": "a"}, {"name": "b"}])
    assert issues_of(validate_file(p, rules))[0][2] == "missing_column"
    assert validate_file(p, rules, delimiter=";").issues == []


def test_validate_dataframe():
    pd = pytest.importorskip("pandas")
    import numpy as np

    df = pd.DataFrame(
        {
            "site": ["A", "A", None],
            "v": [1.0, np.nan, 700.0],
            "n": pd.array([1, None, 3], dtype="Int64"),
            "t": pd.to_datetime(["2024-01-01", "2024-01-01", None]),
        }
    )
    rules = make_rules(
        [
            {"name": "site"},
            {"name": "v", "type": "float", "range": {"max": 500}},
            {"name": "n", "type": "integer"},
            {"name": "t", "type": "date"},
        ],
        duplicates=[{"columns": ["site", "t"]}],
    )
    from enviroqc import validate_dataframe

    r = validate_dataframe(df, rules, name="frame")
    assert r.source.format == "dataframe" and r.source.file == "frame"
    assert issues_of(r) == [
        (3, "v", "missing_value", "error"),
        (3, "n", "missing_value", "error"),
        (3, "site, t", "duplicate_record", "error"),
        (4, "site", "missing_value", "error"),
        (4, "v", "out_of_range", "warning"),
        (4, "t", "missing_value", "error"),
    ]


def test_validate_dataframe_without_pandas_gives_install_hint(monkeypatch):
    import sys

    from enviroqc import validate_dataframe

    monkeypatch.setitem(sys.modules, "pandas", None)
    with pytest.raises(ImportError, match=r"enviroqc\[pandas\]"):
        validate_dataframe(object(), make_rules([{"name": "a"}]))
