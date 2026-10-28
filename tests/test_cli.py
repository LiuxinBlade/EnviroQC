from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from enviroqc import __version__
from enviroqc.cli import main

from .conftest import sha256

RULES = {
    "version": 1,
    "columns": [
        {"name": "site"},
        {"name": "v", "type": "float", "range": {"max": 10, "severity": "warning"}},
    ],
}


@pytest.fixture
def files(write_csv, write_rules):
    data = write_csv("site,v\nA,1\nB,20\n")
    rules = write_rules(RULES)
    return data, rules


def test_validate_warning_only_exits_zero_by_default(files, capsys):
    data, rules = files
    assert main(["validate", str(data), "--rules", str(rules)]) == 0
    out = capsys.readouterr().out
    assert "2 data row(s), 1 issue(s) (0 error, 1 warning, 0 info) -> WARN" in out
    assert "row 3 [v] v.range" in out


@pytest.mark.parametrize(
    ("fail_on", "code"), [("warning", 1), ("info", 1), ("error", 0), ("never", 0)]
)
def test_fail_on_threshold(files, fail_on, code):
    data, rules = files
    assert main(["validate", str(data), "-r", str(rules), "--fail-on", fail_on, "-q"]) == code


def test_errors_exit_one_and_never_overrides(write_csv, write_rules):
    data = write_csv("site,v\n,1\n")
    rules = write_rules(RULES)
    assert main(["validate", str(data), "-r", str(rules), "-q"]) == 1
    assert main(["validate", str(data), "-r", str(rules), "-q", "--fail-on", "never"]) == 0


def test_writes_multiple_reports_and_keeps_input_unchanged(files, tmp_path, capsys):
    data, rules = files
    before = sha256(data)
    j, h = tmp_path / "r.json", tmp_path / "r.html"
    code = main(["validate", str(data), "-r", str(rules), "-o", str(j), "-o", str(h)])
    assert code == 0
    assert json.loads(j.read_text(encoding="utf-8"))["issues"][0]["row"] == 3
    assert "<table>" in h.read_text(encoding="utf-8")
    assert sha256(data) == before
    out = capsys.readouterr().out
    assert f"Report written: {j}" in out


def test_existing_report_needs_overwrite(files, tmp_path, capsys):
    data, rules = files
    out = tmp_path / "r.json"
    out.write_text("old")
    assert main(["validate", str(data), "-r", str(rules), "-o", str(out)]) == 5
    assert "already exists" in capsys.readouterr().err
    assert out.read_text() == "old"
    assert main(["validate", str(data), "-r", str(rules), "-o", str(out), "--overwrite", "-q"]) == 0


def test_refuses_to_write_report_over_input(files, capsys):
    data, rules = files
    before = sha256(data)
    code = main(
        [
            "validate",
            str(data),
            "-r",
            str(rules),
            "-o",
            str(data),
            "--format",
            "json",
            "--overwrite",
        ]
    )
    assert code == 5
    assert sha256(data) == before


def test_refuses_to_write_report_over_rules(files, tmp_path):
    data, _ = files
    rules_json = tmp_path / "rules.json"
    rules_json.write_text(json.dumps(RULES))  # JSON is valid YAML
    before = sha256(rules_json)
    code = main(
        ["validate", str(data), "-r", str(rules_json), "-o", str(rules_json), "--overwrite"]
    )
    assert code == 5
    assert sha256(rules_json) == before


def test_missing_input_exit_4(files, tmp_path, capsys):
    _, rules = files
    assert main(["validate", str(tmp_path / "none.csv"), "-r", str(rules)]) == 4
    assert "Input file not found" in capsys.readouterr().err


def test_empty_input_exit_4(write_csv, write_rules, capsys):
    assert main(["validate", str(write_csv("")), "-r", str(write_rules(RULES))]) == 4
    assert "empty" in capsys.readouterr().err


def test_bad_encoding_exit_4_with_hint_and_override(write_csv, write_rules, capsys):
    data = write_csv("site,v\n北京,1\n", encoding="gbk")
    rules = write_rules(RULES)
    assert main(["validate", str(data), "-r", str(rules)]) == 4
    err = capsys.readouterr().err
    assert "Cannot decode" in err and "Hint:" in err
    assert main(["validate", str(data), "-r", str(rules), "--encoding", "gbk", "-q"]) == 0


def test_bad_rules_exit_3(files, write_rules, capsys):
    data, _ = files
    bad = write_rules(
        {"version": 1, "columns": [{"name": "v", "type": "decimal"}]}, name="bad.yaml"
    )
    assert main(["validate", str(data), "-r", str(bad)]) == 3
    assert "columns[0].type" in capsys.readouterr().err


def test_usage_errors_exit_2(files, capsys):
    data, rules = files
    with pytest.raises(SystemExit) as e:
        main(["validate", str(data)])
    assert e.value.code == 2
    with pytest.raises(SystemExit) as e:
        main(["validate", str(data), "-r", str(rules), "--delimiter", "ab"])
    assert e.value.code == 2
    with pytest.raises(SystemExit) as e:
        main(["validate", str(data), "-r", str(rules), "--max-print", "-1"])
    assert e.value.code == 2
    with pytest.raises(SystemExit) as e:
        main([])
    assert e.value.code == 2


def test_tab_delimiter_alias(write_csv, write_rules):
    data = write_csv("site\tv\nA\t1\n")
    rules = write_rules(RULES)
    assert (
        main(
            [
                "validate",
                str(data),
                "-r",
                str(rules),
                "--delimiter",
                "\\t",
                "--fail-on",
                "warning",
                "-q",
            ]
        )
        == 0
    )


def test_max_print_limits_output(write_csv, write_rules, capsys):
    data = write_csv("site,v\n" + ",1\n" * 30)
    rules = write_rules(RULES)
    main(["validate", str(data), "-r", str(rules), "--max-print", "3"])
    out = capsys.readouterr().out
    assert out.count("site.not_null") == 3
    assert "... 27 more issue(s)" in out


def test_quiet_prints_nothing(files, capsys):
    data, rules = files
    main(["validate", str(data), "-r", str(rules), "-q"])
    assert capsys.readouterr().out == ""


def test_check_rules(write_rules, capsys):
    assert main(["check-rules", str(write_rules(RULES))]) == 0
    assert "2 column(s), 1 range rule(s) and 0 duplicate rule(s)" in capsys.readouterr().out
    assert main(["check-rules", "does-not-exist.yaml"]) == 3


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert capsys.readouterr().out.strip() == f"enviroqc {__version__}"


def test_python_dash_m_entry_point(files):
    data, rules = files
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "enviroqc",
            "validate",
            str(data),
            "-r",
            str(rules),
            "--fail-on",
            "warning",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "ENVIROQC_LANG": "en", "PYTHONIOENCODING": "utf-8"},
        check=False,
    )
    assert proc.returncode == 1
    assert "WARN" in proc.stdout


def test_sheet_option_selects_worksheet(tmp_path, write_rules, capsys):
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.title = "notes"
    wb.active.append(["just", "notes"])
    ws = wb.create_sheet("data")
    ws.append(["site", "v"])
    ws.append(["A", 50])
    p = tmp_path / "book.xlsx"
    wb.save(p)
    rules = write_rules(RULES)
    assert (
        main(["validate", str(p), "-r", str(rules), "--sheet", "data", "--fail-on", "warning"]) == 1
    )
    out = capsys.readouterr().out
    assert "[sheet data]" in out and "row 2 [v] v.range" in out
    assert main(["validate", str(p), "-r", str(rules), "--sheet", "missing"]) == 4
