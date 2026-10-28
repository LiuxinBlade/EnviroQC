from __future__ import annotations

from pathlib import Path

import pytest

from enviroqc import ColumnType, ConfigError, Severity, load_rules, parse_rules
from enviroqc.config import DEFAULT_MISSING_VALUES

from .conftest import EXAMPLES, make_rules


def test_minimal_rules_use_documented_defaults():
    rules = make_rules([{"name": "a"}])
    col = rules.columns[0]
    assert col.type is ColumnType.STRING
    assert col.required is True
    assert col.nullable is False
    assert col.missing_severity is Severity.ERROR
    assert rules.unexpected_columns is Severity.WARNING
    assert rules.input.encoding == "utf-8-sig"
    assert rules.input.delimiter == ","
    assert rules.input.header_row == 1
    assert rules.input.missing_values == DEFAULT_MISSING_VALUES
    assert rules.duplicates == ()


def test_example_rules_file_loads_with_source_hash():
    rules = load_rules(EXAMPLES / "air_quality_rules.yaml")
    assert rules.name == "Hourly air quality (example)"
    assert [c.name for c in rules.columns][:3] == ["station_id", "timestamp", "pm25"]
    pm25 = rules.column("pm25")
    assert pm25 is not None
    assert [r.name for r in pm25.ranges] == ["pm25.non_negative", "pm25.plausible_upper"]
    assert pm25.ranges[0].severity is Severity.ERROR
    assert rules.input.missing_values[-1] == "-999"
    assert rules.duplicates[1].columns is None
    assert rules.source_sha256 is not None and len(rules.source_sha256) == 64


def test_single_range_gets_default_name_and_warning_severity():
    rules = make_rules([{"name": "x", "type": "float", "range": {"min": 0, "max": 10}}])
    rr = rules.columns[0].ranges[0]
    assert rr.name == "x.range"
    assert rr.severity is Severity.WARNING
    assert (rr.min, rr.max) == (0.0, 10.0)


def test_multiple_ranges_get_distinct_default_names():
    rules = make_rules([{"name": "x", "type": "integer", "ranges": [{"min": 0}, {"max": 5}]}])
    assert [r.name for r in rules.columns[0].ranges] == ["x.range", "x.range2"]


def test_unexpected_columns_ignore_maps_to_none():
    assert make_rules([{"name": "a"}], unexpected_columns="ignore").unexpected_columns is None


def test_numeric_missing_tokens_are_normalised_to_strings():
    rules = make_rules([{"name": "a"}], input={"missing_values": [-999, -999.0, " NA "]})
    assert rules.input.missing_values == ("-999", "-999", "NA")


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (None, "empty"),
        ([], "expected a mapping"),
        ({"columns": [{"name": "a"}]}, "missing required key 'version'"),
        ({"version": 2, "columns": [{"name": "a"}]}, "unsupported version"),
        ({"version": True, "columns": [{"name": "a"}]}, "unsupported version"),
        ({"version": 1}, "missing required key 'columns'"),
        ({"version": 1, "columns": []}, "non-empty list"),
        ({"version": 1, "colums": []}, "Did you mean 'columns'"),
        ({"version": 1, "columns": [{"name": "a"}, {"name": "a"}]}, "defined twice"),
        ({"version": 1, "columns": [{"type": "float"}]}, "columns[0]: missing required key"),
        ({"version": 1, "columns": [{"name": "  "}]}, "non-empty string"),
        ({"version": 1, "columns": [{"name": "a", "type": "number"}]}, "unknown type 'number'"),
        ({"version": 1, "columns": [{"name": "a", "rnage": {}}]}, "Did you mean 'range'"),
        ({"version": 1, "columns": [{"name": "a", "nullable": "yes"}]}, "true or false"),
        (
            {"version": 1, "columns": [{"name": "a", "missing_severity": "fatal"}]},
            "expected one of info, warning, error",
        ),
        (
            {"version": 1, "columns": [{"name": "a", "type": "float", "range": {}}]},
            "at least one of 'min' or 'max'",
        ),
        (
            {
                "version": 1,
                "columns": [{"name": "a", "type": "float", "range": {"min": 5, "max": 1}}],
            },
            "greater than max",
        ),
        (
            {"version": 1, "columns": [{"name": "a", "type": "float", "range": {"min": "0"}}]},
            "expected a number",
        ),
        (
            {
                "version": 1,
                "columns": [{"name": "a", "type": "float", "range": {"max": float("nan")}}],
            },
            "finite number",
        ),
        (
            {"version": 1, "columns": [{"name": "a", "range": {"min": 0}}]},
            "only allowed for integer and float",
        ),
        (
            {
                "version": 1,
                "columns": [{"name": "a", "type": "float", "range": {"min": 0}, "ranges": []}],
            },
            "either 'range' or 'ranges'",
        ),
        (
            {
                "version": 1,
                "columns": [
                    {
                        "name": "a",
                        "type": "float",
                        "ranges": [{"min": 0}, {"min": 1, "name": "a.range"}],
                    }
                ],
            },
            "must be unique",
        ),
        (
            {"version": 1, "columns": [{"name": "a", "type": "float", "pattern": "x"}]},
            "only allowed for string",
        ),
        ({"version": 1, "columns": [{"name": "a", "pattern": "("}]}, "invalid regular expression"),
        ({"version": 1, "columns": [{"name": "a", "allowed": []}]}, "non-empty list"),
        (
            {"version": 1, "columns": [{"name": "a", "type": "integer", "allowed": [1]}]},
            "only allowed for string",
        ),
        ({"version": 1, "columns": [{"name": "a", "format": "%Y"}]}, "only allowed for date"),
        ({"version": 1, "columns": [{"name": "a", "type": "date", "format": "YYYY"}]}, "strftime"),
        (
            {"version": 1, "columns": [{"name": "a"}], "duplicates": [{"columns": ["b"]}]},
            "not defined under 'columns'",
        ),
        (
            {"version": 1, "columns": [{"name": "a"}], "duplicates": [{"columns": []}]},
            "non-empty list",
        ),
        (
            {"version": 1, "columns": [{"name": "a"}], "duplicates": [{"columns": ["a", "a"]}]},
            "must not repeat",
        ),
        (
            {
                "version": 1,
                "columns": [{"name": "a"}],
                "duplicates": [{"columns": ["a"]}, {"columns": "*", "name": "duplicate_a"}],
            },
            "used more than once",
        ),
        ({"version": 1, "columns": [{"name": "a"}], "duplicates": {}}, "must be a list"),
        ({"version": 1, "columns": [{"name": "a"}], "unexpected_columns": "loud"}, "ignore"),
        (
            {"version": 1, "columns": [{"name": "a"}], "input": {"encoding": "klingon"}},
            "unknown encoding",
        ),
        (
            {"version": 1, "columns": [{"name": "a"}], "input": {"delimiter": ",,"}},
            "single character",
        ),
        ({"version": 1, "columns": [{"name": "a"}], "input": {"header_row": 0}}, "integer >= 1"),
        ({"version": 1, "columns": [{"name": "a"}], "input": {"header_row": True}}, "integer >= 1"),
        (
            {"version": 1, "columns": [{"name": "a"}], "input": {"missing_values": "NA"}},
            "list of strings",
        ),
        ({"version": 1, "columns": [{"name": "a"}], "input": {"missing_values": [False]}}, "quote"),
        (
            {"version": 1, "columns": [{"name": "a"}], "input": {"shet": "x"}},
            "Did you mean 'sheet'",
        ),
    ],
)
def test_invalid_rules_are_rejected_with_location(data, message):
    with pytest.raises(ConfigError) as excinfo:
        parse_rules(data)
    assert message in str(excinfo.value)


def test_rules_file_not_found(tmp_path: Path):
    with pytest.raises(ConfigError, match="not found"):
        load_rules(tmp_path / "nope.yaml")


def test_rules_file_invalid_yaml_reports_line(write_rules):
    p = write_rules("version: 1\ncolumns:\n  - name: a\n   bad: [\n")
    with pytest.raises(ConfigError, match=r"not valid YAML \(line \d+"):
        load_rules(p)


def test_rules_file_not_utf8(tmp_path: Path):
    p = tmp_path / "rules.yaml"
    p.write_bytes("version: 1\ncolumns:\n  - name: 温度\n".encode("gbk"))
    with pytest.raises(ConfigError, match="not valid UTF-8"):
        load_rules(p)


def test_empty_rules_file(write_rules):
    with pytest.raises(ConfigError, match="empty"):
        load_rules(write_rules(""))


def test_unicode_column_names_are_supported(write_rules):
    p = write_rules({"version": 1, "columns": [{"name": "温度", "type": "float", "unit": "°C"}]})
    rules = load_rules(p)
    assert rules.columns[0].name == "温度"
    assert rules.columns[0].unit == "°C"
