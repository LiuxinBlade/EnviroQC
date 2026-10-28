"""End-to-end checks on the shipped synthetic examples (keeps docs honest)."""

from __future__ import annotations

from enviroqc import load_rules, validate_file

from .conftest import EXAMPLES, sha256

EXPECTED = [
    (4, "pm25", "missing_value", "error"),
    (5, "pm25", "invalid_type", "error"),
    (6, "pm25", "out_of_range", "error"),
    (7, "pm25", "out_of_range", "warning"),
    (8, "timestamp", "invalid_type", "error"),
    (9, "station_id", "pattern_mismatch", "error"),
    (10, "relative_humidity", "out_of_range", "error"),
    (11, "qc_flag", "not_allowed", "error"),
    (13, "no2", "invalid_type", "error"),
    (16, "station_id, timestamp", "duplicate_record", "error"),
    (27, "station_id, timestamp", "duplicate_record", "error"),
    (27, None, "duplicate_record", "warning"),
]


def _tuples(report):
    return [(i.row, i.column, i.check.value, i.severity.value) for i in report.issues]


def test_sample_csv_finds_every_planted_problem():
    rules = load_rules(EXAMPLES / "air_quality_rules.yaml")
    path = EXAMPLES / "air_quality_sample.csv"
    before = sha256(path)
    report = validate_file(path, rules)
    assert _tuples(report) == EXPECTED
    assert report.source.data_rows == 26
    assert report.column_stats["pm10"].missing == 1  # -999 sentinel, column is nullable
    assert sha256(path) == before


def test_sample_xlsx_matches_csv():
    rules = load_rules(EXAMPLES / "air_quality_rules.yaml")
    report = validate_file(EXAMPLES / "air_quality_sample.xlsx", rules)
    assert _tuples(report) == EXPECTED
    assert report.source.sheet == "hourly"


def test_clean_example_passes():
    report = validate_file(EXAMPLES / "air_quality_clean.csv", EXAMPLES / "air_quality_rules.yaml")
    assert report.issues == []
    assert report.status == "pass"
