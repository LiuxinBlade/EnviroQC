# EnviroQC

**An open-source data quality toolkit for environmental monitoring datasets.**

[简体中文](README.md) | **English**

EnviroQC checks CSV and Excel (XLSX) tables from environmental monitoring (air, water, soil,
meteorology, …) for missing values, duplicate records, badly formatted values and configurable
numeric anomalies. Every finding points to the **row number in the source file**, so it can be
traced and reviewed. Results are written as JSON (for programs) and HTML (for people).

- Runs locally. No account, no cloud service, no network access.
- Your data file is opened **read-only** and is never modified.
- All rules live in a YAML file you control.
- Usable from the command line and as a Python library.
- Interface and reports in Chinese and English. **Chinese is the default**; use `--lang en`
  (or `ENVIROQC_LANG=en`) for English.

> **Scope.** EnviroQC is a data-quality *screening* tool. It is not certified compliance software.
> Thresholds come from your rules file and are not regulatory limits unless you make them so. A
> flagged value is a record to review, not proof of a measurement error.

## Status

Version 0.1.0 (alpha). The rules format (`version: 1`), the report schema (`1.0`) and the exit
codes are documented and covered by tests; they may still change before 1.0, and any change will be
recorded in the [changelog](CHANGELOG.md).

## Installation

Requires Python 3.11 or newer.

```bash
pip install enviroqc
```

> Until the first release is published on PyPI, install from a clone of this repository:
>
> ```bash
> git clone https://github.com/LiuxinBlade/EnviroQC.git
> cd EnviroQC
> pip install .
> ```

## Quick start

The repository ships a synthetic hourly air-quality dataset with deliberately planted problems.

```bash
enviroqc validate examples/air_quality_sample.csv --rules examples/air_quality_rules.yaml --output report.html --output report.json --lang en
```

Terminal output (abridged):

```text
air_quality_sample.csv: 26 data row(s), 12 issue(s) (10 error, 2 warning, 0 info) -> FAIL
  error   row 4 [pm25] pm25.not_null: Missing value in 'pm25'.
  error   row 5 [pm25] pm25.type: Value '12,5' in 'pm25' is not a valid float.
  error   row 6 [pm25] pm25.non_negative: pm25 = -3.2 µg/m³ is below the minimum 0 (浓度不能为负 / concentrations cannot be negative).
  warning row 7 [pm25] pm25.plausible_upper: pm25 = 612.0 µg/m³ is above the maximum 500 (示例经验范围，非法规限值 / example plausibility bound, not a regulatory limit).
  ...
  error   row 16 [station_id, timestamp] duplicate_station_time: Duplicate of row 15 on station_id, timestamp.
Report written: report.html
Report written: report.json
```

Open `report.html` in a browser for the full table. The same works for Excel:

```bash
enviroqc validate examples/air_quality_sample.xlsx --rules examples/air_quality_rules.yaml --lang en
```

## What it checks

| Check | `check` id | Configured by |
|---|---|---|
| Required column absent | `missing_column` | `required` |
| Column not described in rules | `unexpected_column` | `unexpected_columns` |
| Row with wrong number of fields | `malformed_row` | always on (CSV) |
| Header but no data | `empty_dataset` | always on |
| Missing value | `missing_value` | `nullable`, `input.missing_values` |
| Value of the wrong type | `invalid_type` | `type`, `format` |
| Text not matching a regex | `pattern_mismatch` | `pattern` |
| Value outside a list | `not_allowed` | `allowed` |
| Number outside a bound | `out_of_range` | `range` / `ranges` |
| Duplicate record | `duplicate_record` | `duplicates` |

## Rules file

```yaml
version: 1
input:
  encoding: utf-8-sig
  missing_values: ["", "NA", "-999"]
columns:
  - name: station_id
    pattern: "^ST\\d{3}$"
  - name: timestamp
    type: datetime
    format: "%Y-%m-%d %H:%M"
  - name: pm25
    type: float
    unit: µg/m³
    ranges:
      - {name: pm25.non_negative, min: 0, severity: error}
      - {name: pm25.plausible_upper, max: 500, severity: warning, note: example bound}
duplicates:
  - name: duplicate_station_time
    columns: [station_id, timestamp]
```

Check a rules file without reading any data:

```bash
enviroqc check-rules examples/air_quality_rules.yaml
```

See [docs/configuration.md](docs/configuration.md) for every option.

## Python API

```python
from enviroqc import validate_file, write_report

report = validate_file(
    "examples/air_quality_sample.csv", "examples/air_quality_rules.yaml", lang="en"
)
print(report.status, report.summary()["by_severity"])
for issue in report.issues:
    print(issue.row, issue.column, issue.rule, issue.message)
write_report(report, "report.json", overwrite=True)
```

`validate_dataframe(df, rules)` validates a pandas DataFrame (`pip install "enviroqc[pandas]"`).
See [docs/python-api.md](docs/python-api.md).

## Language

Output is **Chinese by default**. Switch to English with any of:

| Where | How |
|---|---|
| Command line | `--lang en` (or `--lang zh`) |
| Environment | `ENVIROQC_LANG=en` |
| Python | `validate_file(..., lang="en")`, `report.to_json(lang="en")`, `enviroqc.set_language("en")` |

Only human-readable text changes. Findings, row numbers, rule names and machine-readable JSON
fields (`check`, `message_id`, …) are identical in both languages. Text you write in the rules
file (`note`, `unit`) is shown as written.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | No issue at or above `--fail-on` (default `error`) |
| 1 | At least one issue at or above `--fail-on` |
| 2 | Invalid command-line arguments |
| 3 | Invalid or unreadable rules file |
| 4 | Input file missing, empty, undecodable, corrupt or unsupported |
| 5 | Report could not be written (or would overwrite an input) |
| 10 | Internal error (please report it) |

## Documentation

- [Usage](docs/usage.md) · [Configuration](docs/configuration.md) · [Report schema](docs/report-schema.md)
- [Python API](docs/python-api.md) · [Troubleshooting](docs/troubleshooting.md)
- [Development](docs/development.md) · [Release process](docs/release.md)

## Contributing

Bug reports, rule-format ideas and pull requests are welcome. Please read
[CONTRIBUTING.md](CONTRIBUTING.md). Never attach confidential or personal monitoring data to a
public issue; reduce it to a small synthetic example instead.

## License

[MIT](LICENSE)
