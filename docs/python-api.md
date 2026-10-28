# Python API

Everything below is importable from the top-level `enviroqc` package. Names not listed in
`enviroqc.__all__` are internal and may change.

## Validating

```python
from enviroqc import load_rules, validate_file

rules = load_rules("rules.yaml")  # RuleSet; raises ConfigError if invalid
report = validate_file(
    "data.xlsx",
    rules,  # or pass the rules path directly
    sheet="hourly",  # optional overrides of rules.input
    encoding=None,
    delimiter=None,
)
```

- `validate_file(path, rules, *, encoding=None, sheet=None, delimiter=None, lang=None) -> Report`
- `validate_dataframe(df, rules, *, name="<dataframe>", lang=None) -> Report` — requires pandas.
  Row numbers are spreadsheet-style (first data row = 2). `NaN`, `None`, `pd.NA` and `NaT` are
  missing.
- `validate_table(table, rules, *, lang=None) -> Report` — for a `Table` from `read_table()`.
- `read_table(path, options=None) -> Table` — the read-only loader, if you only need the rows.
- `parse_rules(mapping) -> RuleSet` — build rules from a dict instead of a file.

## The report

```python
report.status  # "pass" | "warn" | "fail"
report.has_errors  # bool
report.error_count, report.warning_count
report.issues  # list[Issue], ordered by row
report.issues_at_least(Severity.WARNING)
report.summary()  # dict, see report-schema.md
report.column_stats  # dict[str, ColumnStats]
report.source  # SourceInfo (file, sha256, data_rows, ...)
report.to_dict(lang=None)
report.to_json(lang=None)
report.to_html(lang=None)
```

`Issue` fields: `file`, `sheet`, `row`, `column`, `check` (`Check` enum), `rule`, `severity`
(`Severity` enum), `message`, `value`, `expected`, `related_rows`. `issue.msg.key` is the
language-independent message id; `issue.message_in("en")` renders it in another language.

```python
from enviroqc import Check

missing_rows = [i.row for i in report.issues if i.check is Check.MISSING_VALUE]
```

## Language

Output is Chinese (`"zh"`) by default; English is `"en"`.

```python
import enviroqc

enviroqc.set_language("en")  # process-wide; None = back to ENVIROQC_LANG / default
enviroqc.get_language()  # "en"

report = validate_file("data.csv", "rules.yaml", lang="zh")  # per call
report.to_html(lang="en")  # render the same findings in English
```

`lang=None` everywhere means "use the current language". Error messages raised by EnviroQC use
the current language at the moment they are raised.

## Writing reports

```python
from enviroqc import write_report

write_report(report, "out/report.html")  # refuses to replace an existing file
write_report(report, "out/report.json", overwrite=True)
```

`write_report` raises `OutputError` instead of overwriting the input data or rules.

## Errors

All deliberate errors derive from `EnviroQCError` and carry `.message`, `.hint` and
`.exit_code`:

```text
EnviroQCError
├── ConfigError                 (exit 3)
├── InputFileError              (exit 4)
│   ├── FileNotFoundInputError
│   ├── UnsupportedFormatError
│   ├── EmptyFileError
│   ├── EncodingError
│   ├── CorruptFileError
│   └── HeaderError
└── OutputError                 (exit 5)
```

```python
from enviroqc import EncodingError, validate_file

try:
    report = validate_file("data.csv", "rules.yaml")
except EncodingError:
    report = validate_file("data.csv", "rules.yaml", encoding="gbk")
```
