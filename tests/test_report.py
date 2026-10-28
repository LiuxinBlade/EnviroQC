from __future__ import annotations

import json

import pytest

from enviroqc import REPORT_SCHEMA_VERSION, OutputError, validate_file, write_report

from .conftest import make_rules, sha256


@pytest.fixture
def report(write_csv):
    p = write_csv('site,v\nA,1\n<script>alert(1)</script>,abc\n"B&""C",2000\n')
    rules = make_rules(
        [{"name": "site"}, {"name": "v", "type": "float", "unit": "µg/m³", "range": {"max": 100}}],
        name="Test <rules>",
    )
    return validate_file(p, rules)


def test_json_report_schema(report):
    d = json.loads(report.to_json())
    assert d["schema_version"] == REPORT_SCHEMA_VERSION
    assert set(d) == {
        "schema_version",
        "tool",
        "generated_at",
        "language",
        "disclaimer",
        "source",
        "rules",
        "summary",
        "issues",
    }
    assert d["tool"]["name"] == "enviroqc"
    assert d["language"] == "en"
    assert [i["message_id"] for i in d["issues"]] == ["issue.invalid_type", "issue.range_above"]
    assert d["source"]["file"] == "data.csv"
    assert d["source"]["data_rows"] == 3
    assert d["source"]["columns"] == ["site", "v"]
    assert len(d["source"]["sha256"]) == 64
    assert d["rules"]["name"] == "Test <rules>"
    assert d["summary"]["by_severity"] == {"info": 0, "warning": 1, "error": 1}
    first = d["issues"][0]
    assert set(first) == {
        "file",
        "sheet",
        "row",
        "column",
        "check",
        "rule",
        "severity",
        "message_id",
        "message",
        "value",
        "expected",
        "related_rows",
    }
    assert [(i["row"], i["column"], i["check"]) for i in d["issues"]] == [
        (3, "v", "invalid_type"),
        (4, "v", "out_of_range"),
    ]
    assert "µg/m³" in d["issues"][1]["message"]  # not escaped to \\u sequences
    assert "regulatory" in d["disclaimer"]


def test_html_report_escapes_data(report, write_csv):
    p = write_csv("site,v\n<script>alert(1)</script>,abc\n", name="x.csv")
    rules = make_rules([{"name": "site", "pattern": "^[A-Z]$"}, {"name": "v", "type": "float"}])
    html = validate_file(p, rules).to_html()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert html.startswith("<!doctype html>")
    assert "http://" not in html and "https://" not in html  # self-contained


def test_html_report_content(report):
    html = report.to_html()
    assert "ERRORS" in html
    assert "data.csv" in html
    assert "Test &lt;rules&gt;" in html
    assert "out_of_range" in html and "invalid_type" in html
    assert "not regulatory limits" in html


def test_html_for_clean_report(write_csv):
    r = validate_file(write_csv("a\n1\n"), make_rules([{"name": "a"}]))
    html = r.to_html()
    assert "No issues found." in html and "PASS" in html


def test_write_json_and_html(report, tmp_path):
    j = write_report(report, tmp_path / "out" / "r.json")
    h = write_report(report, tmp_path / "out" / "r.HTML")
    assert json.loads(j.read_text(encoding="utf-8"))["summary"]["total_issues"] == 2
    assert h.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert sorted(x.name for x in (tmp_path / "out").iterdir()) == ["r.HTML", "r.json"]


def test_write_refuses_existing_without_overwrite(report, tmp_path):
    out = tmp_path / "r.json"
    out.write_text("keep me")
    with pytest.raises(OutputError, match="already exists"):
        write_report(report, out)
    assert out.read_text() == "keep me"
    write_report(report, out, overwrite=True)
    assert out.read_text().startswith("{")


@pytest.mark.parametrize("name", ["data.csv", "r.xlsx", "rules.yaml", "r.yml"])
def test_write_refuses_data_like_extensions(report, tmp_path, name):
    with pytest.raises(OutputError, match="data or rules file"):
        write_report(report, tmp_path / name, fmt="json", overwrite=True)


def test_write_refuses_input_file_even_with_overwrite(report):
    src = report.source.path
    before = sha256(__import__("pathlib").Path(src))
    with pytest.raises(OutputError):
        write_report(report, src, fmt="json", overwrite=True)
    assert sha256(__import__("pathlib").Path(src)) == before


def test_write_refuses_protected_path(report, tmp_path):
    protected = tmp_path / "rules.json"
    protected.write_text("{}")
    with pytest.raises(OutputError, match="Refusing to overwrite"):
        write_report(report, protected, overwrite=True, protected=(protected,))
    assert protected.read_text() == "{}"


def test_write_unknown_format(report, tmp_path):
    with pytest.raises(OutputError, match="report format"):
        write_report(report, tmp_path / "r.pdf")


def test_write_to_directory_fails_cleanly(report, tmp_path):
    d = tmp_path / "dir.json"
    d.mkdir()
    with pytest.raises(OutputError):
        write_report(report, d, overwrite=True)


def test_no_temp_files_left_behind(report, tmp_path):
    out_dir = tmp_path / "reports"
    write_report(report, out_dir / "r.json")
    assert [p.name for p in out_dir.iterdir()] == ["r.json"]
