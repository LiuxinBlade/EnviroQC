"""Bilingual output: Chinese by default, English on request."""

from __future__ import annotations

import json
import string

import pytest

from enviroqc import (
    ConfigError,
    EncodingError,
    get_language,
    load_rules,
    parse_rules,
    read_table,
    set_language,
    validate_file,
)
from enviroqc.cli import main
from enviroqc.i18n import MESSAGES, Msg, normalize_language, t

from .conftest import EXAMPLES, make_rules

RULES = {
    "version": 1,
    "columns": [
        {"name": "site"},
        {"name": "v", "type": "float", "unit": "µg/m³", "range": {"max": 10, "note": "示例"}},
    ],
    "duplicates": [{"columns": ["site"]}],
}


def _fields(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


# ------------------------------------------------------------------ catalogue


@pytest.mark.parametrize("key", sorted(MESSAGES))
def test_both_languages_use_the_same_placeholders(key):
    en, zh = MESSAGES[key]
    assert en.strip() and zh.strip()
    assert _fields(en) == _fields(zh), key


def test_chinese_entries_are_actually_translated():
    # Keys whose text is the same in both languages by design (codes, placeholders only).
    same_by_design = {"cfg.kind.other"}
    untranslated = [k for k, (en, zh) in MESSAGES.items() if en == zh and k not in same_by_design]
    assert untranslated == []


@pytest.mark.parametrize(
    ("raw", "lang"),
    [("zh", "zh"), ("ZH_cn", "zh"), ("zh-Hans", "zh"), ("en", "en"), ("en_US", "en"), ("EN", "en")],
)
def test_normalize_language(raw, lang):
    assert normalize_language(raw) == lang


@pytest.mark.parametrize("raw", ["fr", "", "chinese", "e"])
def test_normalize_language_rejects_others(raw):
    with pytest.raises(ValueError):
        normalize_language(raw)


# ------------------------------------------------------------------ selection


def test_default_is_chinese(monkeypatch):
    set_language(None)
    monkeypatch.delenv("ENVIROQC_LANG", raising=False)
    assert get_language() == "zh"


def test_environment_variable_selects_language(monkeypatch):
    set_language(None)
    monkeypatch.setenv("ENVIROQC_LANG", "en_US.UTF-8")
    assert get_language() == "en"
    monkeypatch.setenv("ENVIROQC_LANG", "klingon")  # invalid -> default
    assert get_language() == "zh"


def test_set_language_overrides_environment(monkeypatch):
    monkeypatch.setenv("ENVIROQC_LANG", "en")
    set_language("zh")
    assert get_language() == "zh"
    with pytest.raises(ValueError):
        set_language("de")


# ------------------------------------------------------------------ messages


def test_issue_messages_in_chinese_and_english(write_csv):
    p = write_csv("site,v\nA,abc\n,12\nA,3\n")
    rules = make_rules(RULES["columns"], duplicates=RULES["duplicates"])
    zh = validate_file(p, rules, lang="zh")
    assert [i.message for i in zh.issues] == [
        "“v”列的值“abc”不是有效的数值。",
        "“site”列存在缺失值。",
        "v = 12 µg/m³，高于上限 10（示例）。",
        "与第 2 行重复（site）。",
    ]
    assert [i.expected for i in zh.issues] == ["数值（如 3.14）", "非空值", "<= 10", "唯一"]
    en = validate_file(p, rules, lang="en")
    assert [i.message for i in en.issues] == [
        "Value 'abc' in 'v' is not a valid float.",
        "Missing value in 'site'.",
        "v = 12 µg/m³ is above the maximum 10 (示例).",
        "Duplicate of row 2 on site.",
    ]
    # Same findings regardless of language.
    assert [(i.row, i.column, i.check, i.rule) for i in zh.issues] == [
        (i.row, i.column, i.check, i.rule) for i in en.issues
    ]


def test_validation_uses_current_language_by_default(write_csv):
    p = write_csv("site,v\n,1\n")
    set_language("zh")
    report = validate_file(p, make_rules(RULES["columns"]))
    assert report.lang == "zh"
    assert report.issues[0].message == "“site”列存在缺失值。"


def test_report_can_be_rendered_in_the_other_language(write_csv):
    p = write_csv("site,v\nA,20\n")
    report = validate_file(p, make_rules(RULES["columns"]), lang="zh")
    zh = json.loads(report.to_json())
    en = json.loads(report.to_json(lang="en"))
    assert zh["language"] == "zh" and en["language"] == "en"
    assert "法规限值" in zh["disclaimer"] and "regulatory" in en["disclaimer"]
    assert zh["issues"][0]["message"] == "v = 20 µg/m³，高于上限 10（示例）。"
    assert en["issues"][0]["message"] == "v = 20 µg/m³ is above the maximum 10 (示例)."
    assert zh["issues"][0]["message_id"] == en["issues"][0]["message_id"] == "issue.range_above"
    # Everything except the human-readable text is identical.
    for d in (zh, en):
        for key in ("language", "disclaimer", "generated_at"):
            d.pop(key)
        for issue in d["issues"]:
            issue.pop("message")
            issue.pop("expected")
    assert zh == en


def test_html_report_in_chinese_and_english(write_csv):
    p = write_csv("site,v\n<b>x</b>,20\n")
    report = validate_file(p, make_rules(RULES["columns"]), lang="zh")
    html_zh = report.to_html()
    assert '<html lang="zh-CN">' in html_zh
    for text in (
        "EnviroQC 数据质量报告",
        "有警告",
        "数据行数",
        "问题列表（1）",
        "超出范围",
        "高于上限",
    ):
        assert text in html_zh, text
    assert "&lt;b&gt;x&lt;/b&gt;" not in html_zh or "<b>x</b>" not in html_zh
    html_en = report.to_html(lang="en")
    assert '<html lang="en">' in html_en
    assert "EnviroQC data quality report" in html_en and "WARNINGS" in html_en
    assert "数据行数" not in html_en


def test_errors_follow_the_language(tmp_path):
    set_language("zh")
    with pytest.raises(ConfigError) as excinfo:
        parse_rules({"version": 1, "colums": []})
    assert str(excinfo.value).startswith("rules：未知的键 'colums'。是否想写 'columns'？")
    set_language("en")
    with pytest.raises(ConfigError, match="Did you mean 'columns'"):
        parse_rules({"version": 1, "colums": []})


def test_hint_prefix_is_translated(tmp_path):
    p = tmp_path / "gbk.csv"
    p.write_bytes("站点\n北京\n".encode("gbk"))
    set_language("zh")
    with pytest.raises(EncodingError) as excinfo:
        read_table(p)
    text = str(excinfo.value)
    assert "无法以 'utf-8-sig' 编码解码 gbk.csv：第 1 行存在无效字节" in text
    assert "\n提示：请在规则文件中设置 'input.encoding'" in text


def test_nested_messages_render_in_requested_language():
    m = Msg.of("issue.invalid_type", value="x", column="c", type=Msg.of("type.date"))
    assert m.render("zh") == "“c”列的值“x”不是有效的日期。"
    assert m.render("en") == "Value 'x' in 'c' is not a valid date."
    with pytest.raises(KeyError):
        Msg.of("no.such.key")
    assert t("sev.error", "zh") == "错误"


# ------------------------------------------------------------------ CLI


@pytest.fixture
def files(write_csv, write_rules):
    return write_csv("site,v\nA,1\nB,20\n"), write_rules(RULES)


def test_cli_default_output_is_chinese(files, capsys, monkeypatch):
    set_language(None)
    monkeypatch.delenv("ENVIROQC_LANG", raising=False)
    data, rules = files
    assert main(["validate", str(data), "-r", str(rules)]) == 0
    out = capsys.readouterr().out
    assert "data.csv：2 行数据，1 个问题（错误 0，警告 1，提示 0）-> 警告" in out
    assert "警告 第 3 行 [v] v.range: v = 20 µg/m³，高于上限 10（示例）。" in out


def test_cli_lang_option_and_env(files, capsys, monkeypatch):
    set_language(None)
    data, rules = files
    main(["validate", str(data), "-r", str(rules), "--lang", "en"])
    assert "1 issue(s) (0 error, 1 warning, 0 info) -> WARN" in capsys.readouterr().out
    main(["--lang=en", "validate", str(data), "-r", str(rules)])
    assert "-> WARN" in capsys.readouterr().out
    monkeypatch.setenv("ENVIROQC_LANG", "en")
    main(["validate", str(data), "-r", str(rules)])
    assert "-> WARN" in capsys.readouterr().out
    main(["validate", str(data), "-r", str(rules), "--lang", "zh"])  # option beats env
    assert "-> 警告" in capsys.readouterr().out
    assert get_language() == "en"  # CLI restores the previous setting...
    monkeypatch.setenv("ENVIROQC_LANG", "zh")
    assert get_language() == "zh"  # ...including "not set", so the env var still applies


def test_cli_reports_are_written_in_chosen_language(files, tmp_path):
    set_language(None)
    data, rules = files
    out = tmp_path / "r.json"
    main(["validate", str(data), "-r", str(rules), "-o", str(out), "-o", str(tmp_path / "r.html")])
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["language"] == "zh"
    assert d["issues"][0]["message"] == "v = 20 µg/m³，高于上限 10（示例）。"
    assert '<html lang="zh-CN">' in (tmp_path / "r.html").read_text(encoding="utf-8")
    main(["validate", str(data), "-r", str(rules), "-o", str(out), "--overwrite", "--lang", "en"])
    assert json.loads(out.read_text(encoding="utf-8"))["language"] == "en"


def test_cli_errors_in_chinese(tmp_path, write_rules, capsys):
    set_language("zh")
    code = main(["validate", str(tmp_path / "none.csv"), "-r", str(write_rules(RULES))])
    assert code == 4
    assert "enviroqc：错误：找不到输入文件：" in capsys.readouterr().err


def test_cli_check_rules_in_chinese(capsys):
    set_language("zh")
    assert main(["check-rules", str(EXAMPLES / "air_quality_rules.yaml")]) == 0
    assert "定义了 8 列、6 条范围规则、2 条重复规则。" in capsys.readouterr().out


def test_cli_help_and_usage_errors_in_chinese(capsys):
    set_language("zh")
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert out.startswith("用法：enviroqc")
    assert "显示帮助信息并退出" in out and "输出语言" in out
    with pytest.raises(SystemExit) as e:
        main(["validate", "x.csv"])
    assert e.value.code == 2
    assert "缺少必需参数：-r/--rules" in capsys.readouterr().err
    with pytest.raises(SystemExit) as e:
        main(["--lang", "fr", "check-rules", "x.yaml"])
    assert e.value.code == 2


def test_cli_help_in_english(capsys):
    set_language("zh")
    with pytest.raises(SystemExit):
        main(["--lang", "en", "--help"])
    out = capsys.readouterr().out
    assert out.startswith("usage: enviroqc")
    assert "show this help message and exit" in out
    import argparse

    assert argparse._("usage: ") == "usage: "  # translation hook removed afterwards


def test_examples_in_chinese_find_the_same_issues():
    rules = load_rules(EXAMPLES / "air_quality_rules.yaml")
    zh = validate_file(EXAMPLES / "air_quality_sample.csv", rules, lang="zh")
    en = validate_file(EXAMPLES / "air_quality_sample.csv", rules, lang="en")
    assert len(zh.issues) == len(en.issues) == 12
    assert zh.issues[0].message == "“pm25”列存在缺失值。"
