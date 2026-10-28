# AGENTS.md — maintainer guide for humans and AI agents

Read this file before changing anything in the repository.

## Project

EnviroQC: local, open-source data-quality screening for environmental monitoring tables
(CSV/XLSX). Python 3.11+, src layout, MIT license. It is **not** compliance software; never
present configurable thresholds as legal limits.

## Non-negotiable rules

1. Never modify, overwrite or "fix" a user's input data file. Reading is binary, read-only.
2. Every reported issue must be traceable to a source row (or be explicitly file-level).
3. Do not claim tests pass without running them. Do not skip, delete or weaken tests to get green.
4. Every bug fix comes with a regression test.
5. Keep runtime dependencies to `openpyxl` and `PyYAML`. pandas is optional (`[pandas]` extra).
6. Out of scope unless the maintainer decides otherwise: web UI, database, user accounts, cloud
   storage, AI/LLM API calls, paid services.
7. Never commit secrets (`.env`, tokens, keys, `.pypirc`) or real/personal monitoring data.
   Test and example data are synthetic.
8. Do not fabricate project activity (stars, users, issues, contributors, feedback).

## Commands

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff format .            # format
ruff check .             # lint (must be clean)
pytest                   # full suite (must pass)
pytest --cov=enviroqc    # coverage (currently ~97%)
python -m build          # sdist + wheel
python examples/make_example_data.py   # regenerate synthetic examples
```

## Architecture

| Module | Responsibility |
|---|---|
| `config.py` | Rules dataclasses (`RuleSet`, `ColumnSpec`, `RangeRule`, `DuplicateRule`, `InputOptions`) and strict YAML validation with located error messages. |
| `reader.py` | `read_table()`: CSV via `csv` module (tracks physical start line of each record), XLSX via openpyxl read-only. Header detection, BOM, encoding errors, corrupt files. |
| `coerce.py` | Strict per-type parsing; returns `Coerced(ok, value)` rather than raising. |
| `validator.py` | `validate_file/table/dataframe`; produces `Issue`s and `ColumnStats`, sorts issues. |
| `models.py` | `Severity`, `Check`, `Issue`, `Report`, JSON form (`REPORT_SCHEMA_VERSION`). |
| `report.py` | `render_html()` (escaped, self-contained), `write_report()` (refuses to overwrite inputs, atomic write). |
| `cli.py` | argparse CLI, `ExitCode` mapping, terminal summary. |
| `exceptions.py` | `EnviroQCError` hierarchy with `exit_code` and `hint`. |
| `i18n.py` | Bilingual text. `MESSAGES` maps each key to (English, 中文); `t()` renders, `Msg` defers rendering so a report can be shown in either language. Default `zh`; `--lang`, `ENVIROQC_LANG`, `set_language()`. |

Stable public contracts (breaking changes need a changelog entry and version bump):
rules format `version: 1`, report `schema_version` `1.0`, `Check` string values, exit codes,
names in `enviroqc.__all__`.

## Code style

- All user-facing text (messages, errors, hints, CLI help, HTML labels) goes through
  `i18n.MESSAGES` with **both** English and Chinese. Never hard-code display strings.
  Chinese is the default language. `tests/test_i18n.py` checks that both versions use the
  same placeholders.

- Ruff (config in `pyproject.toml`), line length 100, type hints on public functions.
- Errors: raise a specific `EnviroQCError` subclass with a message that says what, where and
  (via `hint`) how to fix it. No bare `except`.
- Comments explain *why*, briefly.

## Testing conventions

- `tests/test_<module>.py`; CLI tests call `cli.main([...])` and check exit codes and output.
- Assert exact rows/columns/checks/severities. Use `tmp_path` and synthetic data.
- `tests/test_examples.py` pins the expected findings of the shipped examples; update it together
  with `examples/make_example_data.py`.
- Warnings are errors in pytest (`filterwarnings = error`).
- `tests/conftest.py` pins tests to English (and clears `ENVIROQC_LANG`); Chinese output is
  asserted in `tests/test_i18n.py`. New messages need assertions in both languages.

## Workflow for each change

1. Read the relevant issue/PR and docs. Check open issues and PRs first.
2. Write or update tests, implement, run `ruff format`, `ruff check`, `pytest`.
3. Update docs (`README.md` (Chinese, default), `README.en.md`, `docs/`) and `CHANGELOG.md` (*Unreleased*).
4. Review `git diff` for accidental deletions and secrets before committing.
5. External contributions: review for tests, scope, licensing and data privacy.

## Release

See `docs/release.md`. Version lives in `pyproject.toml` and `src/enviroqc/__init__.py` (keep
equal; the release workflow checks the tag). Releases are published on GitHub only (the
maintainer chose not to use PyPI); the workflow attaches the wheel and sdist to the Release.
Releases, public repository changes and anything irreversible need the maintainer's explicit
approval.
