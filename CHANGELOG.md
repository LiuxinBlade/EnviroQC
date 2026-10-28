# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Distribution is through GitHub Releases only; the release workflow no longer publishes to PyPI.
  Install instructions now use the repository or the release wheel.

## [0.1.0] - 2026-10-28

First public version (alpha).

### Added

- Read CSV/TSV/TXT (any single-character delimiter, configurable encoding, BOM-aware) and XLSX/XLSM
  files, strictly read-only, with exact source row numbers (correct for multi-line quoted CSV
  fields and Excel row gaps).
- YAML rules (`version: 1`) with strict validation and precise error locations.
- Checks: missing column, unexpected column, malformed row, empty dataset, missing value,
  invalid type (string, integer, float, boolean, date, datetime), regex pattern, allowed values,
  numeric ranges with per-rule severity, key-based and exact duplicate records.
- JSON report (schema 1.0) and self-contained, HTML-escaped report.
- CLI: `enviroqc validate`, `enviroqc check-rules`; documented exit codes; `--fail-on`.
- Python API: `validate_file`, `validate_dataframe`, `validate_table`, `load_rules`,
  `write_report`, stable exception hierarchy.
- Report writing refuses to overwrite the input data or rules file.
- Bilingual output: Chinese (default) and English for the terminal summary, error messages and
  hints, `--help`, and the text in JSON/HTML reports. Select with `--lang zh|en`, the
  `ENVIROQC_LANG` environment variable, `enviroqc.set_language()`, or `lang=` on the validate
  functions and `Report.to_json/to_html/to_dict`. JSON reports carry `language` and a
  language-independent `message_id` per issue.
- Synthetic air-quality example (CSV + XLSX) and generator script.
- Documentation: Chinese `README.md` (default), English `README.en.md` and English `docs/`.
- GitHub Actions CI and release workflow
  (PyPI Trusted Publishing).

[Unreleased]: https://github.com/LiuxinBlade/EnviroQC/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/LiuxinBlade/EnviroQC/releases/tag/v0.1.0
