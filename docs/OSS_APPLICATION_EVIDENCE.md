# EnviroQC — open-source project evidence

This document records verifiable facts about the project for open-source program applications
(for example, Codex for OSS). It separates **done**, **in progress** and **planned** work. Update
it with links whenever something changes; do not add claims that cannot be checked.

_Last updated: 2026-10-28_

## 1. Project

- **Name:** EnviroQC
- **Description:** An open-source data quality toolkit for environmental monitoring datasets.
- **License:** MIT
- **Repository:** https://github.com/LiuxinBlade/EnviroQC (created 2026-10-28)
- **Distribution:** GitHub Releases (wheel + sdist); not published on PyPI by the maintainer's choice.

## 2. Functionality — status

### Done (released as v0.1.0 on 2026-10-28)

- CSV/TSV/TXT and XLSX/XLSM reading, read-only, with exact source row numbers.
- YAML rules with strict validation and located error messages.
- Checks: missing/unexpected columns, malformed rows, empty dataset, missing values, type errors
  (integer, float, boolean, date, datetime), regex patterns, allowed values, numeric ranges with
  configurable severity, key-based and exact duplicate records.
- JSON report (schema 1.0) and self-contained HTML report.
- CLI (`enviroqc validate`, `enviroqc check-rules`) with documented exit codes.
- Bilingual output (Chinese default, English via `--lang en` / `ENVIROQC_LANG`) for terminal,
  errors, help text and JSON/HTML reports.
- Python API (`validate_file`, `validate_dataframe`, `load_rules`, `write_report`, …).
- Friendly errors for empty files, wrong encodings, missing columns, invalid configuration,
  invalid numbers and damaged Excel files.
- Synthetic example data (CSV + XLSX) and rules.
- Chinese (default) and English README; usage, configuration, schema, API, troubleshooting, development
  and release documentation; CONTRIBUTING, SECURITY, CHANGELOG, issue/PR templates.
- GitHub Actions CI running on every push and pull request (passing); tag-triggered release
  workflow that builds and attaches packages to a GitHub Release.

### In progress

- Nothing in progress at the moment.

### Planned (not started)

- Rule-file generator from an existing data file (`enviroqc init-rules`).
- Time-series checks: gaps in expected sampling intervals, stuck values, sudden jumps.
- Cross-column checks (e.g. PM2.5 ≤ PM10).
- Optional decimal-comma parsing and below-detection-limit (`<LOD`) handling.
- Streaming mode for very large files.

## 3. Tests and CI

| Item | Result | Date | Evidence |
|---|---|---|---|
| Local test suite (`pytest`) | 467 passed, 0 failed | 2026-10-28 | run locally, Python 3.12.3, Linux |
| Coverage (`pytest --cov=enviroqc`) | 97% | 2026-10-28 | run locally |
| Ruff lint + format check | clean | 2026-10-28 | run locally |
| sdist + wheel build, install in clean venv, README commands | passed | 2026-10-28 | run locally |
| Install from the v0.1.0 Release wheel and from `git+…@v0.1.0` in clean venvs, run examples | passed | 2026-10-28 | run locally |
| GitHub Actions CI (lint; tests on Ubuntu py3.11–3.13, Windows, macOS; build + wheel smoke test) | all 7 jobs passed | 2026-10-28 | https://github.com/LiuxinBlade/EnviroQC/actions/runs/40626359918 |

## 4. Releases

| Version | Date | Where |
|---|---|---|
| v0.1.0 | 2026-10-28 | https://github.com/LiuxinBlade/EnviroQC/releases/tag/v0.1.0 |

## 5. Community activity

As of 2026-10-28 the project has **no** public issues, pull requests, external contributors,
stars or user feedback; it was published the same day. This section will only list items with
links.

## 6. Maintainer responsibilities

The project owner is the maintainer and is responsible for: deciding scope and priorities,
approving releases and other external/irreversible actions, reviewing and merging contributions,
answering issues and security reports, and final acceptance of AI-assisted work.

## 7. Use of AI assistance

Version 0.1.0 was implemented with an AI coding agent (Claude Code) under the maintainer's
direction; the maintainer reviews and accepts the work. Planned AI-assisted maintenance:

- triage and reproduction of incoming issues with synthetic data;
- drafting fixes with regression tests, which must pass CI before merge;
- review assistance for external pull requests (tests, scope, licensing, data privacy);
- keeping documentation (English/Chinese) in sync with behaviour;
- dependency and Python-version upkeep.

Rules for AI-assisted work are in [`AGENTS.md`](../AGENTS.md): no fabricated activity, no
claims without test runs, no modification of user data.
