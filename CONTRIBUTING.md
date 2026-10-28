# Contributing to EnviroQC

Thank you for helping. EnviroQC values reliability over feature count: a small, well-tested
change is easier to accept than a large one.

## Ways to help

- **Report a bug** with the bug template. Include `enviroqc --version`, Python version, OS, the
  command, the full output and a *small synthetic* file that reproduces the problem.
- **Propose a check or rule option** with the feature template. Describe the monitoring
  scenario and what a correct result looks like.
- **Improve documentation** and translations (Chinese `README.md`, English `README.en.md`).
- **Send a pull request.**

Please never post confidential, unpublished or personal monitoring data in issues or pull requests.

## Pull requests

1. Open or comment on an issue first for anything larger than a small fix.
2. Set up the environment (see [docs/development.md](docs/development.md)):

   ```bash
   pip install -e ".[dev]"
   ```

3. Make the change with tests:
   - assert concrete results (rows, columns, checks, severities);
   - every bug fix needs a regression test that fails without the fix;
   - do not skip, delete or weaken existing tests.
4. Run before pushing:

   ```bash
   ruff format . && ruff check . && pytest
   ```

5. Update documentation and add a line under `Unreleased` in `CHANGELOG.md`.
6. Fill in the pull request template.

## Principles

- The input data file is never modified.
- Thresholds are user configuration; do not ship values presented as legal limits.
- Keep runtime dependencies minimal (currently `openpyxl` and `PyYAML`).
- Error messages say what is wrong, where, and how to fix it.
- All user-facing text is bilingual: add every new message to `src/enviroqc/i18n.py` in both
  English and Chinese (Chinese is the default), with tests for both.
- Changes to the rules format, report schema or exit codes are breaking changes and must be
  called out in the changelog.

## AI-assisted contributions

AI tools may be used, but the contributor is responsible for every line: it must be understood,
tested and correctly licensed. Do not submit generated code you have not run.

## License

By contributing you agree that your contribution is licensed under the [MIT License](LICENSE).
