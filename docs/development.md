# Development

## Setup

```bash
git clone https://github.com/LiuxinBlade/EnviroQC.git
cd EnviroQC
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Everyday commands

```bash
ruff format .                 # format
ruff check .                  # lint
pytest                        # all tests
pytest --cov=enviroqc         # with coverage
python -m build               # build sdist + wheel into dist/
```

CI (`.github/workflows/ci.yml`) runs lint, the test suite on Linux/Windows/macOS with Python
3.11–3.13, and a build + install smoke test. A pull request must pass all of them.

## Layout

```text
src/enviroqc/
  __init__.py     public API (__all__)
  cli.py          argparse CLI, exit codes, terminal summary
  config.py       rules model (dataclasses) + strict YAML validation
  reader.py       read-only CSV/XLSX loading with source row numbers
  coerce.py       strict value parsing (integer, float, boolean, date, datetime)
  validator.py    runs the checks, builds the Report
  models.py       Severity, Check, Issue, Report (+ JSON serialisation)
  report.py       HTML rendering, safe write_report()
  exceptions.py   exception hierarchy and ExitCode
tests/            pytest suite (unit + CLI + end-to-end on examples/)
examples/         synthetic data, rules, generator script
docs/             user and maintainer documentation
```

Data flow: `load_rules` → `read_table` → `validate_table` (→ `coerce` per cell) → `Report` →
`to_json` / `render_html` → `write_report`.

## Adding a check

1. Add a member to `Check` in `models.py` (the string value is part of the report schema).
2. Add configuration to `config.py` with strict validation and a clear error location.
3. Implement it in `validator.py`.
4. Tests: valid case, violation, boundary values, invalid configuration.
5. Document it in `docs/configuration.md`, `docs/report-schema.md`, both READMEs and
   `CHANGELOG.md`.

## Testing rules

- Assert concrete results (rows, columns, checks, severities), not only "no exception".
- Every bug fix gets a regression test that fails without the fix.
- Never skip, delete or loosen a failing test to get a green run.
- Test data must be synthetic.
