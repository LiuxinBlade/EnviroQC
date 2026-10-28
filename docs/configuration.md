# Rules file reference

A rules file is YAML (JSON also works, since JSON is valid YAML). It is validated strictly:
unknown keys, wrong types and contradictory values stop the run with exit code 3 and a message
that names the exact location, e.g. `columns[2].range.min: expected a number, got '0'`.

Check a file on its own with `enviroqc check-rules rules.yaml`.

## Top level

| Key | Required | Default | Description |
|---|---|---|---|
| `version` | yes | — | Must be `1`. |
| `name` | no | — | Shown in reports. |
| `description` | no | — | Free text. |
| `input` | no | see below | How the data file is read. |
| `columns` | yes | — | Non-empty list of column definitions. |
| `duplicates` | no | `[]` | Duplicate-record rules. |
| `unexpected_columns` | no | `warning` | Severity for file columns not listed in `columns`: `ignore`, `info`, `warning`, `error`. |

## `input`

| Key | Default | Description |
|---|---|---|
| `encoding` | `utf-8-sig` | Text encoding for CSV. `utf-8-sig` reads UTF-8 with or without BOM. Common alternatives: `gbk`, `gb18030`, `latin-1`, `cp1252`. Can be overridden with `--encoding`. |
| `delimiter` | `,` | Single character. `.tsv` files default to tab. Override with `--delimiter` (`\t` or `tab` for tab). |
| `sheet` | first sheet | Excel worksheet name. Override with `--sheet`. |
| `header_row` | `1` | Row (Excel) or line (CSV) number of the header. Lines above it are ignored; blank lines/rows at or below it are skipped until the header is found. |
| `missing_values` | `["", "NA", "N/A", "NaN", "nan", "null", "NULL", "None"]` | Tokens treated as missing, compared after trimming whitespace, case-sensitive. **Replaces** the default list. Empty and whitespace-only cells are always missing. Numbers are matched by their text, e.g. `"-999"` matches an Excel cell `-999` but not the CSV text `-999.0`. Quote `"no"`, `"yes"` etc. because YAML would read them as booleans. |

## `columns[]`

| Key | Default | Description |
|---|---|---|
| `name` | — | Column header text (exact match after trimming spaces). |
| `type` | `string` | `string`, `integer`, `float`, `boolean`, `date`, `datetime`. |
| `required` | `true` | If the column is absent from the file: `missing_column` error. If `false`, an absent column is skipped silently. |
| `nullable` | `false` | If `false`, each missing value is a `missing_value` issue. Missing values are always counted in the summary. |
| `missing_severity` | `error` | Severity of `missing_value` issues. |
| `type_severity` | `error` | Severity of `invalid_type` issues. |
| `format` | — | `date`/`datetime` only: a `strptime` pattern such as `%Y-%m-%d %H:%M`. Without it, ISO 8601 is expected. Native Excel date cells are always accepted. |
| `pattern` | — | `string` only: regular expression the whole value must match (Python `re.fullmatch`). |
| `allowed` | — | `string` only: list of permitted values (case-sensitive). |
| `range` | — | One range rule (see below). |
| `ranges` | — | A list of range rules. Use either `range` or `ranges`. `integer`/`float` only. |
| `unit` | — | Shown in messages, e.g. `µg/m³`. |
| `description` | — | Free text. |

### Type rules

| Type | Accepted | Rejected (examples) |
|---|---|---|
| `integer` | `42`, `-7`, `+3`; Excel numbers without fraction | `4.0` (text), `4.5`, `1e3`, `1_000` |
| `float` | `3.14`, `.5`, `5.`, `1e-3`; Excel numbers | `12,5`, `1,000.0`, `nan`, `inf`, `<0.01`, `5 mg` |
| `boolean` | `true/false`, `t/f`, `yes/no`, `y/n`, `1/0` (any case) | `maybe`, `2` |
| `date` | ISO `2024-01-31` or `format`; Excel dates at midnight | `2023-02-29`, Excel date-time with a time |
| `datetime` | ISO `2024-01-31 06:00[:00]`, `2024-01-31T06:00` or `format`; Excel dates/date-times | anything not matching |
| `string` | everything | — |

Values below detection limit such as `<0.01` are deliberately **not** converted: they are reported
as `invalid_type` so that you decide how to treat them (for example, a `string` column with a
`pattern`, or a cleaned copy of the data).

### Range rules

| Key | Default | Description |
|---|---|---|
| `name` | `<column>.range`, `<column>.range2`, … | Rule name shown in reports. Must be unique in the column. |
| `min` / `max` | — | At least one is required. Numbers only. |
| `min_inclusive` / `max_inclusive` | `true` | Whether the bound value itself is allowed. |
| `severity` | `warning` | `info`, `warning` or `error`. |
| `note` | — | Appended to the message, e.g. the source of the bound. |

Range checks run only on values that are present and have a valid type. A value violating
several range rules produces one issue per rule.

**Do not present custom bounds as legal standards.** If a bound comes from a regulation, write the
reference in `note`; if it is a plausibility bound, say so.

## `duplicates[]`

| Key | Default | Description |
|---|---|---|
| `columns` | — | List of column names that together identify a record (all must be defined under `columns`), or `"*"` for exact duplicate rows across every column in the file. |
| `name` | `duplicate_<cols>` / `duplicate_rows` | Rule name. Must be unique. |
| `severity` | `error` | Severity. |

Details:

- Keys are compared on **parsed** values: `1`, `1.0` and `1e0` are equal in a `float` column, and
  `2024-01-01 00:00` equals `2024-01-01T00:00:00` in a `datetime` column. Text is trimmed.
- The first occurrence is not flagged; every later occurrence is, with `related_rows` pointing to
  the first one.
- For key rules, rows with a missing key value are skipped (they are already reported as missing).
  For `"*"`, missing cells are compared as equal.

## Complete example

See [`examples/air_quality_rules.yaml`](../examples/air_quality_rules.yaml).
