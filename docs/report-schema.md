# Report schema (version 1.0)

`enviroqc validate ... --output report.json` and `Report.to_json()` produce this structure.
`schema_version` changes when the structure changes: a minor bump adds fields, a major bump
removes or renames fields.

```json
{
  "schema_version": "1.0",
  "tool": {"name": "enviroqc", "version": "0.1.0"},
  "generated_at": "2026-01-01T08:00:00+00:00",
  "language": "zh",
  "disclaimer": "EnviroQC 是数据质量初筛工具。……",
  "source": {
    "file": "air_quality_sample.csv",
    "path": "examples/air_quality_sample.csv",
    "format": "csv",
    "sha256": "…64 hex chars…",
    "sheet": null,
    "header_row": 1,
    "data_rows": 26,
    "columns": ["station_id", "timestamp", "pm25", "..."]
  },
  "rules": {"name": "Hourly air quality (example)", "path": "examples/air_quality_rules.yaml", "sha256": "…"},
  "summary": {
    "status": "fail",
    "total_issues": 12,
    "by_severity": {"info": 0, "warning": 2, "error": 10},
    "by_check": {"duplicate_record": 3, "invalid_type": 3, "...": 0},
    "by_rule": {"pm25.not_null": 1, "...": 0},
    "data_rows": 26,
    "rows_with_issues": 11,
    "columns": {
      "pm25": {"present": true, "missing": 1, "invalid_type": 1, "out_of_range": 2}
    }
  },
  "issues": [
    {
      "file": "air_quality_sample.csv",
      "sheet": null,
      "row": 4,
      "column": "pm25",
      "check": "missing_value",
      "rule": "pm25.not_null",
      "severity": "error",
      "message_id": "issue.missing_value",
      "message": "“pm25”列存在缺失值。",
      "value": "",
      "expected": "非空值",
      "related_rows": []
    }
  ]
}
```

## Fields

### Top level

| Field | Description |
|---|---|
| `language` | `zh` or `en`: language of `disclaimer`, `issues[].message` and `issues[].expected`. Everything else is language-independent. |

### `source`

| Field | Description |
|---|---|
| `file` | File name only. |
| `path` | Path as given on the command line / API call (not resolved, so no home directory leaks unless you passed one). |
| `format` | `csv`, `xlsx` or `dataframe`. |
| `sha256` | Hash of the file bytes, to prove which file was checked. `null` for DataFrames. |
| `sheet` | Worksheet name for Excel, else `null`. |
| `header_row` | Row/line number of the header. |
| `data_rows` | Number of non-blank data rows. |

### `summary`

`status` is `fail` if there is any `error`, `warn` if there is any `warning`, otherwise `pass`.
`columns` has one entry per column defined in the rules: `present` (found in the file), and
counts of `missing`, `invalid_type` and `out_of_range` values (a value violating several ranges
counts once).

### `issues[]`

| Field | Type | Description |
|---|---|---|
| `row` | integer or null | 1-based row number in the source: the CSV line where the record **starts** (correct even when quoted fields contain line breaks), or the Excel row number. For DataFrames, position + 2 (header = row 1). `null` for file-level findings. |
| `column` | string or null | Column name; for key duplicates, the key columns joined by `, `; `null` for row/file-level findings. |
| `check` | string | One of `missing_column`, `unexpected_column`, `malformed_row`, `empty_dataset`, `missing_value`, `invalid_type`, `pattern_mismatch`, `not_allowed`, `out_of_range`, `duplicate_record`. |
| `rule` | string | Rule name (e.g. `pm25.range`, a user-defined range or duplicate rule name, `row.field_count`). |
| `severity` | string | `info`, `warning` or `error`. |
| `message_id` | string | Stable identifier of the message template (e.g. `issue.missing_value`), the same in every language. |
| `message` | string | Human-readable explanation, in the report `language`. |
| `value` | string or null | The offending value as text (truncated to 200 characters). |
| `expected` | string or null | What a valid value looks like (in the report `language` where it is descriptive text). |
| `related_rows` | list of integers | For duplicates: the row of the first occurrence. |

Issues are ordered by row (file-level first), then by column position in the file, then by check.
