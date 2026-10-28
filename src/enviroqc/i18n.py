"""Bilingual (Chinese / English) user-facing text.

Chinese (``zh``) is the default. The language is chosen, in order of priority,
by an explicit ``lang`` argument, :func:`set_language`, the ``ENVIROQC_LANG``
environment variable, and finally the default.

Every message lives in :data:`MESSAGES` with both translations, so the two
languages cannot drift apart silently (``tests/test_i18n.py`` checks that both
versions use the same placeholders).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

SUPPORTED_LANGUAGES = ("zh", "en")
DEFAULT_LANGUAGE = "zh"
ENV_VAR = "ENVIROQC_LANG"


def normalize_language(lang: str) -> str:
    """Map ``zh_CN``, ``zh-Hans``, ``EN_us`` ... to ``zh`` or ``en``.

    Raises ``ValueError`` for anything else.
    """
    code = str(lang).strip().lower().replace("_", "-")
    for supported in SUPPORTED_LANGUAGES:
        if code == supported or code.startswith(supported + "-"):
            return supported
    raise ValueError(
        f"Unsupported language {lang!r}; use one of {', '.join(SUPPORTED_LANGUAGES)}. "
        f"不支持的语言 {lang!r}，请使用 {'、'.join(SUPPORTED_LANGUAGES)}。"
    )


def _language_from_env() -> str:
    value = os.environ.get(ENV_VAR)
    if not value:
        return DEFAULT_LANGUAGE
    try:
        return normalize_language(value)
    except ValueError:
        return DEFAULT_LANGUAGE


_current: str | None = None


def set_language(lang: str | None) -> None:
    """Set the process-wide output language (``None`` = back to env/default)."""
    global _current
    _current = None if lang is None else normalize_language(lang)


def language_override() -> str | None:
    """The value set with :func:`set_language`, or ``None`` if env/default applies."""
    return _current


def get_language() -> str:
    """The current output language: ``"zh"`` or ``"en"``."""
    return _current if _current is not None else _language_from_env()


def resolve_language(lang: str | None) -> str:
    return get_language() if lang is None else normalize_language(lang)


def t(key: str, lang: str | None = None, /, **params: Any) -> str:
    """Translate ``key`` and fill in ``params``. Nested :class:`Msg` params are rendered too."""
    language = resolve_language(lang)
    en, zh = MESSAGES[key]
    template = zh if language == "zh" else en
    rendered = {k: v.render(language) if isinstance(v, Msg) else v for k, v in params.items()}
    return template.format(**rendered)


@dataclass(frozen=True)
class Msg:
    """A message that can be rendered later in either language."""

    key: str
    params: tuple[tuple[str, Any], ...] = ()

    @classmethod
    def of(cls, key: str, /, **params: Any) -> Msg:
        if key not in MESSAGES:
            raise KeyError(key)
        return cls(key, tuple(params.items()))

    def render(self, lang: str | None = None) -> str:
        return t(self.key, lang, **dict(self.params))


# key: (English, 中文)
MESSAGES: dict[str, tuple[str, str]] = {
    # ---------------------------------------------------------------- general
    "hint": ("Hint: {hint}", "提示：{hint}"),
    "disclaimer": (
        "EnviroQC is a data-quality screening tool. Thresholds come from the user's rules "
        "file and are not regulatory limits unless the rules file says so. A flagged value "
        "is a record to review, not proof of a measurement error.",
        "EnviroQC 是数据质量初筛工具。阈值来自用户的规则文件，除非规则文件明确说明，"
        "否则不代表任何法规限值。被标记的数值是需要复核的记录，并不等于测量错误。",
    ),
    "sev.error": ("error", "错误"),
    "sev.warning": ("warning", "警告"),
    "sev.info": ("info", "提示"),
    "status.pass": ("PASS", "通过"),
    "status.warn": ("WARN", "警告"),
    "status.fail": ("FAIL", "不通过"),
    # ---------------------------------------------------------------- check labels
    "chk.missing_column": ("Missing column", "缺少列"),
    "chk.unexpected_column": ("Unexpected column", "未定义的列"),
    "chk.malformed_row": ("Malformed row", "字段数异常的行"),
    "chk.empty_dataset": ("Empty dataset", "无数据"),
    "chk.missing_value": ("Missing value", "缺失值"),
    "chk.invalid_type": ("Invalid type", "类型错误"),
    "chk.pattern_mismatch": ("Pattern mismatch", "格式不符"),
    "chk.not_allowed": ("Value not allowed", "不在允许值内"),
    "chk.out_of_range": ("Out of range", "超出范围"),
    "chk.duplicate_record": ("Duplicate record", "重复记录"),
    # ---------------------------------------------------------------- column types
    "type.string": ("string", "文本"),
    "type.integer": ("integer", "整数"),
    "type.float": ("float", "数值"),
    "type.boolean": ("boolean", "布尔值"),
    "type.date": ("date", "日期"),
    "type.datetime": ("datetime", "日期时间"),
    # ---------------------------------------------------------------- issues
    "issue.missing_column": (
        "Required column {column!r} is not in the file.",
        "文件中缺少必需列“{column}”。",
    ),
    "issue.unexpected_column": (
        "Column {column!r} is not defined in the rules file.",
        "列“{column}”未在规则文件中定义。",
    ),
    "issue.empty_dataset": (
        "The file has a header but no data rows.",
        "文件只有表头，没有数据行。",
    ),
    "issue.malformed_long": (
        "Row has {n} field(s) but the header has {width}; cells beyond the header are ignored.",
        "该行有 {n} 个字段，但表头有 {width} 列；超出表头的单元格已忽略。",
    ),
    "issue.malformed_short": (
        "Row has {n} field(s) but the header has {width}; absent trailing cells are not checked.",
        "该行有 {n} 个字段，但表头有 {width} 列；缺少的末尾单元格未做检查。",
    ),
    "issue.missing_value": ("Missing value in {column!r}.", "“{column}”列存在缺失值。"),
    "issue.invalid_type": (
        "Value {value!r} in {column!r} is not a valid {type}.",
        "“{column}”列的值“{value}”不是有效的{type}。",
    ),
    "issue.pattern_mismatch": (
        "Value {value!r} in {column!r} does not match the expected pattern.",
        "“{column}”列的值“{value}”不符合规定的格式。",
    ),
    "issue.not_allowed": (
        "Value {value!r} in {column!r} is not one of the allowed values.",
        "“{column}”列的值“{value}”不在允许值列表中。",
    ),
    "issue.range_below": (
        "{column} = {value}{unit} is below the minimum {bound}{note}.",
        "{column} = {value}{unit}，低于下限 {bound}{note}。",
    ),
    "issue.range_at_or_below": (
        "{column} = {value}{unit} is at or below the minimum {bound}{note}.",
        "{column} = {value}{unit}，小于或等于下限 {bound}{note}。",
    ),
    "issue.range_above": (
        "{column} = {value}{unit} is above the maximum {bound}{note}.",
        "{column} = {value}{unit}，高于上限 {bound}{note}。",
    ),
    "issue.range_at_or_above": (
        "{column} = {value}{unit} is at or above the maximum {bound}{note}.",
        "{column} = {value}{unit}，大于或等于上限 {bound}{note}。",
    ),
    "issue.note": (" ({note})", "（{note}）"),
    "issue.duplicate_keys": (
        "Duplicate of row {first} on {columns}.",
        "与第 {first} 行重复（{columns}）。",
    ),
    "issue.duplicate_all": (
        "Duplicate of row {first} on all columns.",
        "与第 {first} 行完全重复（所有列）。",
    ),
    "expected.value": ("a value", "非空值"),
    "expected.unique": ("unique", "唯一"),
    "expected.text": ("text", "文本"),
    "expected.integer": ("integer (e.g. 42)", "整数（如 42）"),
    "expected.float": ("number (e.g. 3.14)", "数值（如 3.14）"),
    "expected.boolean": ("boolean (true/false, yes/no, 1/0)", "布尔值（true/false、yes/no、1/0）"),
    "expected.date_format": ("date in format {format}", "格式为 {format} 的日期"),
    "expected.date_iso": ("ISO date (YYYY-MM-DD)", "ISO 日期（YYYY-MM-DD）"),
    "expected.datetime_format": ("date-time in format {format}", "格式为 {format} 的日期时间"),
    "expected.datetime_iso": (
        "ISO date-time (YYYY-MM-DD HH:MM[:SS])",
        "ISO 日期时间（YYYY-MM-DD HH:MM[:SS]）",
    ),
    "expected.range_both": ("{low} and {high}", "{low} 且 {high}"),
    # ---------------------------------------------------------------- rules file errors
    "cfg.not_found": ("Rules file not found: {path}", "找不到规则文件：{path}"),
    "cfg.read_failed": (
        "Cannot read rules file {path}: {reason}",
        "无法读取规则文件 {path}：{reason}",
    ),
    "cfg.not_utf8": (
        "Rules file {path} is not valid UTF-8 (byte offset {offset}).",
        "规则文件 {path} 不是有效的 UTF-8 编码（字节偏移 {offset}）。",
    ),
    "cfg.not_utf8.hint": (
        "Save the YAML file with UTF-8 encoding.",
        "请将 YAML 文件另存为 UTF-8 编码。",
    ),
    "cfg.yaml_error": (
        "Rules file {path} is not valid YAML{location}: {error}",
        "规则文件 {path} 不是有效的 YAML{location}：{error}",
    ),
    "cfg.yaml_location": (" (line {line}, column {column})", "（第 {line} 行，第 {column} 列）"),
    "cfg.empty": ("Rules file is empty.", "规则文件为空。"),
    "cfg.bad_version": (
        "{where}: unsupported version {value!r}; this release supports version {supported}.",
        "{where}：不支持的版本 {value!r}；当前程序仅支持版本 {supported}。",
    ),
    "cfg.columns_empty": (
        "columns: must be a non-empty list of column definitions.",
        "columns：必须是非空的列定义列表。",
    ),
    "cfg.column_twice": (
        "{where}: column {name!r} is defined twice.",
        "{where}：列 {name!r} 被重复定义。",
    ),
    "cfg.dups_not_list": ("duplicates: must be a list.", "duplicates：必须是列表。"),
    "cfg.dup_name_reused": (
        "duplicates: rule name {name!r} is used more than once.",
        "duplicates：规则名 {name!r} 被重复使用。",
    ),
    "cfg.expected_mapping": (
        "{where}: expected a mapping, got {got}.",
        "{where}：应为映射（键: 值），实际为{got}。",
    ),
    "cfg.key_not_string": (
        "{where}: keys must be strings, got {key!r}.",
        "{where}：键必须是字符串，实际为 {key!r}。",
    ),
    "cfg.unknown_key": (
        "{where}: unknown key {key!r}.{suggestion} Allowed keys: {allowed}.",
        "{where}：未知的键 {key!r}。{suggestion}允许的键：{allowed}。",
    ),
    "cfg.did_you_mean": (" Did you mean {key!r}?", "是否想写 {key!r}？"),
    "cfg.missing_key": (
        "{where}: missing required key {key!r}.",
        "{where}：缺少必需的键 {key!r}。",
    ),
    "cfg.kind.null": ("nothing (null)", "空值（null）"),
    "cfg.kind.mapping": ("a mapping", "映射"),
    "cfg.kind.list": ("a list", "列表"),
    "cfg.kind.string": ("a string", "字符串"),
    "cfg.kind.boolean": ("a boolean", "布尔值"),
    "cfg.kind.other": ("{name}", "{name}"),
    "cfg.expected_string": (
        "{where}: expected a string, got {got}.",
        "{where}：应为字符串，实际为{got}。",
    ),
    "cfg.expected_nonempty_string": (
        "{where}: expected a non-empty string, got {value!r}.",
        "{where}：应为非空字符串，实际为 {value!r}。",
    ),
    "cfg.expected_bool": (
        "{where}: expected true or false, got {value!r}.",
        "{where}：应为 true 或 false，实际为 {value!r}。",
    ),
    "cfg.expected_number": (
        "{where}: expected a number, got {value!r}.",
        "{where}：应为数字，实际为 {value!r}。",
    ),
    "cfg.finite_number": (
        "{where}: must be a finite number, got {value!r}.",
        "{where}：必须是有限数值，实际为 {value!r}。",
    ),
    "cfg.expected_one_of": (
        "{where}: expected one of {choices}; got {value!r}.",
        "{where}：应为 {choices} 之一，实际为 {value!r}。",
    ),
    "cfg.unknown_encoding": (
        "{where}: unknown encoding {value!r}.",
        "{where}：未知编码 {value!r}。",
    ),
    "cfg.bad_delimiter": (
        "{where}: expected a single character such as ',' ';' or '\\t', got {value!r}.",
        "{where}：应为单个字符，如 ','、';' 或 '\\t'，实际为 {value!r}。",
    ),
    "cfg.bad_header_row": (
        "{where}: expected an integer >= 1, got {value!r}.",
        "{where}：应为大于等于 1 的整数，实际为 {value!r}。",
    ),
    "cfg.missing_values_list": (
        "{where}: expected a list of strings, e.g. ['', 'NA', '-999'].",
        "{where}：应为字符串列表，例如 ['', 'NA', '-999']。",
    ),
    "cfg.missing_values_bool": (
        "{where}: quote boolean-looking tokens, e.g. 'no' instead of no.",
        "{where}：类似布尔值的标记需要加引号，例如写 'no' 而不是 no。",
    ),
    "cfg.unknown_type": (
        "{where}: unknown type {value!r}; expected one of {choices}.",
        "{where}：未知类型 {value!r}，应为 {choices} 之一。",
    ),
    "cfg.format_only_dates": (
        "{where}: only allowed for date and datetime columns.",
        "{where}：仅适用于 date 和 datetime 类型的列。",
    ),
    "cfg.format_not_strftime": (
        "{where}: expected a strftime pattern such as '%Y-%m-%d %H:%M', got {value!r}.",
        "{where}：应为 strftime 格式，例如 '%Y-%m-%d %H:%M'，实际为 {value!r}。",
    ),
    "cfg.only_string": (
        "{where}: only allowed for string columns.",
        "{where}：仅适用于 string 类型的列。",
    ),
    "cfg.bad_regex": (
        "{where}: invalid regular expression: {error}.",
        "{where}：正则表达式无效：{error}。",
    ),
    "cfg.allowed_list": (
        "{where}: expected a non-empty list of strings.",
        "{where}：应为非空字符串列表。",
    ),
    "cfg.range_and_ranges": (
        "{where}: use either 'range' or 'ranges', not both.",
        "{where}：'range' 和 'ranges' 只能使用其中一个。",
    ),
    "cfg.ranges_list": (
        "{where}: expected a list of range rules.",
        "{where}：应为范围规则列表。",
    ),
    "cfg.ranges_numeric_only": (
        "{where}: ranges are only allowed for integer and float columns.",
        "{where}：范围规则仅适用于 integer 和 float 类型的列。",
    ),
    "cfg.range_names_unique": (
        "{where}: range rule names must be unique within a column.",
        "{where}：同一列中的范围规则名称必须唯一。",
    ),
    "cfg.range_needs_bound": (
        "{where}: define at least one of 'min' or 'max'.",
        "{where}：至少需要定义 'min' 或 'max' 之一。",
    ),
    "cfg.range_min_gt_max": (
        "{where}: min ({min!r}) is greater than max ({max!r}).",
        "{where}：min（{min!r}）大于 max（{max!r}）。",
    ),
    "cfg.dup_columns_list": (
        "{where}: expected a non-empty list of column names, or '*' for exact duplicate rows.",
        "{where}：应为非空的列名列表，或用 '*' 表示整行完全重复。",
    ),
    "cfg.dup_columns_repeat": (
        "{where}: column names must not repeat.",
        "{where}：列名不能重复。",
    ),
    "cfg.dup_columns_unknown": (
        "{where}: {columns} not defined under 'columns'.",
        "{where}：{columns} 未在 'columns' 中定义。",
    ),
    # ---------------------------------------------------------------- input file errors
    "in.not_found": ("Input file not found: {path}", "找不到输入文件：{path}"),
    "in.not_file": ("Input path is not a regular file: {path}", "输入路径不是普通文件：{path}"),
    "in.xls": (
        "Legacy Excel format (.xls) is not supported: {name}",
        "不支持旧版 Excel 格式（.xls）：{name}",
    ),
    "in.xls.hint": (
        "Open the file in Excel or LibreOffice and save it as .xlsx or .csv.",
        "请用 Excel 或 LibreOffice 打开并另存为 .xlsx 或 .csv。",
    ),
    "in.unsupported": (
        "Unsupported file type {suffix!r}: {name}",
        "不支持的文件类型 {suffix!r}：{name}",
    ),
    "in.no_extension": ("(no extension)", "（无扩展名）"),
    "in.unsupported.hint": (
        "Supported: .csv, .tsv, .txt (delimited text), .xlsx, .xlsm.",
        "支持的格式：.csv、.tsv、.txt（分隔符文本）、.xlsx、.xlsm。",
    ),
    "in.read_failed": (
        "Cannot read input file {path}: {reason}",
        "无法读取输入文件 {path}：{reason}",
    ),
    "in.empty": ("Input file is empty: {name}", "输入文件为空：{name}"),
    "in.decode": (
        "Cannot decode {name} as {encoding!r}: invalid byte at line {line} (byte offset {offset}).",
        "无法以 {encoding!r} 编码解码 {name}：第 {line} 行存在无效字节（字节偏移 {offset}）。",
    ),
    "in.decode.hint": (
        "Set 'input.encoding' in the rules file or pass --encoding "
        "(for example gbk, gb18030, latin-1, cp1252).",
        "请在规则文件中设置 'input.encoding'，或使用 --encoding 参数"
        "（例如 gbk、gb18030、latin-1、cp1252）。",
    ),
    "in.nul": (
        "{name} contains NUL bytes; it is probably not a text CSV file (or it is UTF-16 encoded).",
        "{name} 包含 NUL 字节，可能不是文本 CSV 文件（或者是 UTF-16 编码）。",
    ),
    "in.nul.hint": (
        "If the file is UTF-16, pass --encoding utf-16.",
        "如果文件是 UTF-16 编码，请使用 --encoding utf-16。",
    ),
    "in.bad_csv": (
        "Malformed CSV in {name} near line {line}: {error}",
        "{name} 的 CSV 格式错误（约第 {line} 行）：{error}",
    ),
    "in.bad_csv.hint": (
        "Check for unbalanced quotes, or set 'input.delimiter' correctly.",
        "请检查引号是否成对，或正确设置 'input.delimiter'。",
    ),
    "in.no_header_csv": (
        "No header row found in {name} (expected at row {row}).",
        "在 {name} 中找不到表头行（应在第 {row} 行或之后）。",
    ),
    "in.not_zip": (
        "{name} is not a valid .xlsx file (it is not a ZIP container).",
        "{name} 不是有效的 .xlsx 文件（不是 ZIP 容器）。",
    ),
    "in.not_zip.hint": (
        "The file may be damaged, or it may be a CSV/.xls file with the wrong extension.",
        "文件可能已损坏，或者是扩展名错误的 CSV/.xls 文件。",
    ),
    "in.bad_workbook": (
        "Cannot open {name} as an Excel workbook: {error}",
        "无法将 {name} 作为 Excel 工作簿打开：{error}",
    ),
    "in.bad_workbook.hint": (
        "Re-save the file from Excel or LibreOffice as .xlsx.",
        "请用 Excel 或 LibreOffice 重新另存为 .xlsx。",
    ),
    "in.no_sheet": ("Sheet {sheet!r} not found in {name}.", "{name} 中找不到工作表 {sheet!r}。"),
    "in.no_sheet.hint": ("Available sheets: {sheets}", "可用的工作表：{sheets}"),
    "in.bad_sheet": (
        "Cannot read sheet {sheet!r} of {name}: {error}",
        "无法读取 {name} 的工作表 {sheet!r}：{error}",
    ),
    "in.no_header_xlsx": (
        "No header row found in sheet {sheet!r} of {name}.",
        "在 {name} 的工作表 {sheet!r} 中找不到表头行。",
    ),
    "in.header_empty": ("Header row {row} of {name} is empty.", "{name} 第 {row} 行的表头为空。"),
    "in.header_blank_names": (
        "Header row {row} of {name} has empty column name(s) at position(s) {positions}.",
        "{name} 第 {row} 行表头的第 {positions} 列没有列名。",
    ),
    "in.header_blank_names.hint": (
        "Give every column a name, or remove the empty columns.",
        "请为每一列命名，或删除空列。",
    ),
    "in.header_dups": (
        "Header row {row} of {name} has duplicate column name(s): {names}.",
        "{name} 第 {row} 行表头存在重复列名：{names}。",
    ),
    "in.header_dups.hint": (
        "Column names must be unique so that rules can refer to them.",
        "列名必须唯一，规则才能引用。",
    ),
    # ---------------------------------------------------------------- output errors
    "out.unknown_format": (
        "Cannot tell the report format from {name!r}.",
        "无法从 {name!r} 判断报告格式。",
    ),
    "out.unknown_format.hint": (
        "Use a .json or .html file name, or pass --format json|html.",
        "请使用 .json 或 .html 文件名，或指定 --format json|html。",
    ),
    "out.protected_ext": (
        "Refusing to write a report to {name!r}: the extension looks like a data or rules file.",
        "拒绝将报告写入 {name!r}：该扩展名看起来是数据文件或规则文件。",
    ),
    "out.protected_ext.hint": (
        "Reports must be .json or .html files; source data is never overwritten.",
        "报告必须是 .json 或 .html 文件；源数据永远不会被覆盖。",
    ),
    "out.is_input": ("Refusing to overwrite the input file {path}.", "拒绝覆盖输入文件 {path}。"),
    "out.exists": ("Output file already exists: {path}", "输出文件已存在：{path}"),
    "out.exists.hint": (
        "Pass --overwrite (or overwrite=True) to replace an existing report.",
        "如需替换已有报告，请加 --overwrite（或 overwrite=True）。",
    ),
    "out.not_file": ("Output path is not a regular file: {path}", "输出路径不是普通文件：{path}"),
    "out.write_failed": ("Cannot write report {path}: {reason}", "无法写入报告 {path}：{reason}"),
    # ---------------------------------------------------------------- CLI
    "cli.error": ("enviroqc: error: {message}", "enviroqc：错误：{message}"),
    "cli.summary": (
        "{where}: {rows} data row(s), {total} issue(s) "
        "({errors} error, {warnings} warning, {infos} info) -> {status}",
        "{where}：{rows} 行数据，{total} 个问题（错误 {errors}，警告 {warnings}，提示 {infos}）"
        "-> {status}",
    ),
    "cli.sheet_suffix": (" [sheet {sheet}]", " [工作表 {sheet}]"),
    "cli.row": ("row {row}", "第 {row} 行"),
    "cli.file_level": ("file", "文件"),
    "cli.more": (
        "  ... {n} more issue(s); write a report with -o to see all.",
        "  …… 另有 {n} 个问题；用 -o 输出报告可查看全部。",
    ),
    "cli.written": ("Report written: {path}", "报告已写入：{path}"),
    "cli.rules_ok": (
        "OK: {path} defines {columns} column(s), {ranges} range rule(s) "
        "and {dups} duplicate rule(s).",
        "规则有效：{path} 定义了 {columns} 列、{ranges} 条范围规则、{dups} 条重复规则。",
    ),
    "cli.interrupted": ("enviroqc: interrupted", "enviroqc：已中断"),
    "cli.internal": (
        "enviroqc: internal error. Please report it with the traceback above "
        "(do not attach confidential data).",
        "enviroqc：内部错误。请附上方的错误堆栈提交问题报告（不要附带保密数据）。",
    ),
    "cli.max_print_negative": ("--max-print must be >= 0", "--max-print 必须大于等于 0"),
    "cli.delimiter_single": (
        "--delimiter must be a single character",
        "--delimiter 必须是单个字符",
    ),
    "help.description": (
        "Data quality checks for environmental monitoring datasets (CSV/XLSX).",
        "环境监测数据（CSV/XLSX）质量检查工具。",
    ),
    "help.epilog": (
        "Exit codes: 0 ok, 1 issues found, 2 usage error, 3 rules error, "
        "4 input file error, 5 output error, 10 internal error.",
        "退出码：0 正常，1 发现问题，2 参数错误，3 规则错误，"
        "4 输入文件错误，5 输出错误，10 内部错误。",
    ),
    "help.lang": (
        "output language: zh (Chinese, default) or en (English); "
        "can also be set with the ENVIROQC_LANG environment variable",
        "输出语言：zh（中文，默认）或 en（英文）；也可通过环境变量 ENVIROQC_LANG 设置",
    ),
    "help.version": ("show the version and exit", "显示版本号并退出"),
    "help.validate": ("validate a data file against a rules file", "按规则文件检查数据文件"),
    "help.validate_desc": (
        "Validate a CSV or XLSX file. The input file is opened read-only.",
        "检查 CSV 或 XLSX 文件。输入文件以只读方式打开。",
    ),
    "help.input": (
        "data file (.csv, .tsv, .txt, .xlsx, .xlsm)",
        "数据文件（.csv、.tsv、.txt、.xlsx、.xlsm）",
    ),
    "help.rules": ("YAML rules file", "YAML 规则文件"),
    "help.output": (
        "write a report (.json or .html); repeat for several reports",
        "输出报告（.json 或 .html），可重复使用以输出多份报告",
    ),
    "help.format": (
        "report format when it cannot be inferred from the extension",
        "无法从扩展名判断时，指定报告格式",
    ),
    "help.encoding": (
        "override input.encoding (e.g. gbk, latin-1)",
        "覆盖 input.encoding（如 gbk、latin-1）",
    ),
    "help.sheet": (
        "override input.sheet (Excel worksheet name)",
        "覆盖 input.sheet（Excel 工作表名）",
    ),
    "help.delimiter": (
        "override input.delimiter (use '\\t' or 'tab' for tab)",
        "覆盖 input.delimiter（制表符写 '\\t' 或 'tab'）",
    ),
    "help.fail_on": (
        "lowest severity that makes the exit code 1 (default: error)",
        "达到该严重程度即返回退出码 1（默认：error）",
    ),
    "help.overwrite": ("replace existing report files", "覆盖已存在的报告文件"),
    "help.max_print": (
        "number of issues to print to the terminal (default: 20, 0 = none)",
        "终端显示的问题条数（默认 20，0 表示不显示）",
    ),
    "help.quiet": ("print nothing except errors", "除错误外不输出任何内容"),
    "help.check_rules": ("check that a rules file is valid", "检查规则文件是否有效"),
    "help.check_rules_desc": (
        "Validate a rules YAML file without reading any data.",
        "只检查 YAML 规则文件，不读取任何数据。",
    ),
    # ---------------------------------------------------------------- HTML report
    "html.lang_attr": ("en", "zh-CN"),
    "html.title": ("EnviroQC report – {file}", "EnviroQC 报告 – {file}"),
    "html.heading": ("EnviroQC data quality report", "EnviroQC 数据质量报告"),
    "html.sheet": ("sheet {sheet}", "工作表 {sheet}"),
    "html.generated": ("generated {time}", "生成于 {time}"),
    "html.status.pass": ("PASS", "通过"),
    "html.status.warn": ("WARNINGS", "有警告"),
    "html.status.fail": ("ERRORS", "有错误"),
    "html.data_rows": ("Data rows", "数据行数"),
    "html.rows_with_issues": ("Rows with issues", "有问题的行"),
    "html.errors": ("Errors", "错误"),
    "html.warnings": ("Warnings", "警告"),
    "html.info": ("Info", "提示"),
    "html.source": ("Source", "数据来源"),
    "html.file": ("File", "文件"),
    "html.format": ("Format", "格式"),
    "html.header_row": ("Header row", "表头行"),
    "html.rules": ("Rules", "规则"),
    "html.rules_sha": ("Rules SHA-256", "规则 SHA-256"),
    "html.columns": ("Columns", "列统计"),
    "html.column": ("Column", "列"),
    "html.present": ("Present", "存在"),
    "html.missing": ("Missing", "缺失"),
    "html.invalid_type": ("Invalid type", "类型错误"),
    "html.out_of_range": ("Out of range", "超出范围"),
    "html.yes": ("yes", "是"),
    "html.no": ("no", "否"),
    "html.by_check": ("Issues by check", "按检查类型统计"),
    "html.check": ("Check", "检查"),
    "html.count": ("Count", "数量"),
    "html.issues": ("Issues ({n})", "问题列表（{n}）"),
    "html.row_note": (
        "Row numbers refer to the source file (header = row {row}).",
        "行号对应源文件中的行（表头为第 {row} 行）。",
    ),
    "html.row": ("Row", "行号"),
    "html.severity": ("Severity", "严重程度"),
    "html.rule": ("Rule", "规则"),
    "html.message": ("Message", "说明"),
    "html.value": ("Value", "值"),
    "html.expected": ("Expected", "期望"),
    "html.no_issues": ("No issues found.", "未发现问题。"),
}
