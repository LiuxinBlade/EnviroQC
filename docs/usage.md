# Installation and usage

## Install

Python 3.11+ is required.

```bash
pip install enviroqc                 # from PyPI, once released
pip install "enviroqc[pandas]"       # adds pandas for validate_dataframe()
pip install .                        # from a source checkout
```

Runtime dependencies are only `openpyxl` (Excel) and `PyYAML` (rules). pandas is optional.

Using a virtual environment is recommended:

```bash
python -m venv .venv
. .venv/bin/activate                 # Windows: .venv\Scripts\activate
pip install enviroqc
```

## Commands

### `enviroqc validate`

```text
enviroqc validate INPUT --rules RULES [--output PATH ...] [options]
```

| Option | Description |
|---|---|
| `-r, --rules` | YAML rules file (required). |
| `-o, --output` | Report path; `.json` or `.html`/`.htm`. Repeat to write several. Without it, only a terminal summary is printed. |
| `--format json\|html` | Force the report format when the extension is unusual. |
| `--overwrite` | Replace existing report files. Without it, an existing file is never touched. |
| `--encoding` | Override `input.encoding`. |
| `--sheet` | Override `input.sheet`. |
| `--delimiter` | Override `input.delimiter` (`\t` or `tab` for tab). |
| `--fail-on` | `error` (default), `warning`, `info` or `never`: lowest severity that makes the exit code 1. |
| `--max-print N` | Issues printed to the terminal (default 20, `0` for summary only). |
| `-q, --quiet` | Print nothing except errors. |
| `--lang zh\|en` | Output language for the terminal, error messages and reports. Default `zh` (Chinese). |

Safety rules:

- The input file is opened read-only.
- A report is never written to the input file, the rules file, or any path ending in `.csv`,
  `.tsv`, `.txt`, `.xlsx`, `.xlsm`, `.xls`, `.yaml` or `.yml`, even with `--overwrite`.
- Reports are written to a temporary file first and then moved into place.

### `enviroqc check-rules`

```bash
enviroqc check-rules rules.yaml
```

Validates a rules file without reading data. Exit code 0 if valid, 3 otherwise.

`python -m enviroqc ...` works the same as `enviroqc ...`.

## Language

All output — terminal summary, error messages and hints, `--help`, and the text inside JSON and
HTML reports — is available in Chinese and English. **Chinese is the default.**

```bash
enviroqc validate data.csv -r rules.yaml --lang en      # one command
export ENVIROQC_LANG=en                                 # whole shell session (Windows: set ENVIROQC_LANG=en)
```

Priority: `--lang` > `ENVIROQC_LANG` > default (`zh`). `--lang` may be given before or after the
sub-command. The language never changes what is detected; only the wording differs. Machine
consumers should rely on `check`, `rule` and `message_id` in the JSON report, which are the same
in both languages.

## Use in scripts and CI

```bash
enviroqc validate data.csv -r rules.yaml -o report.json --overwrite --fail-on error
if [ $? -eq 1 ]; then echo "data has errors"; fi
```

Exit codes are listed in the [README](../README.en.md#exit-codes).

## Batch checking several files

EnviroQC validates one file per call; use your shell or Python for batches:

```bash
for f in data/*.csv; do
  enviroqc validate "$f" -r rules.yaml -o "reports/$(basename "$f" .csv).html" --overwrite -q
done
```

```python
from pathlib import Path
from enviroqc import load_rules, validate_file, write_report

rules = load_rules("rules.yaml")
for path in sorted(Path("data").glob("*.csv")):
    report = validate_file(path, rules)
    write_report(report, Path("reports") / f"{path.stem}.json", overwrite=True)
    print(path.name, report.status)
```

## Regenerating the example data

```bash
python examples/make_example_data.py
```

The examples are synthetic and deterministic; the problems planted in them are listed in the
script and checked by `tests/test_examples.py`.
