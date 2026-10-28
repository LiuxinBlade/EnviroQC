# Release process

EnviroQC is distributed through **GitHub Releases** only (no PyPI). Pushing a `vX.Y.Z` tag runs
`.github/workflows/release.yml`, which tests, builds the sdist and wheel, checks that the tag
matches the package version and creates a GitHub Release with both files attached. Release notes
are taken from the matching section of `CHANGELOG.md`. No tokens or secrets are needed beyond
the workflow's built-in `GITHUB_TOKEN`.

## Each release

1. Make sure `main` is green in CI.
2. Update the version in `pyproject.toml` **and** `src/enviroqc/__init__.py`.
3. Move the `Unreleased` entries in `CHANGELOG.md` under the new version with today's date, and
   add the compare/tag links at the bottom.
4. Update the version in the install commands in `README.md`, `README.en.md` and
   `docs/usage.md` (`...EnviroQC.git@vX.Y.Z`, wheel file name).
5. Run locally:

   ```bash
   ruff check . && ruff format --check . && pytest
   rm -rf dist && python -m build
   ```

6. Commit (`Release vX.Y.Z`), tag and push:

   ```bash
   git tag -a vX.Y.Z -m "EnviroQC vX.Y.Z"
   git push origin main vX.Y.Z
   ```

7. Check the *Release* workflow run, then install the published wheel in a clean virtual
   environment and run the example to confirm.

Tags and releases are public and should not be moved or deleted once published; fix mistakes
with a new patch version.

## Versioning

[Semantic Versioning](https://semver.org/). Before 1.0, minor versions may contain breaking changes;
they are always listed in the changelog. The rules format (`version`) and report schema
(`schema_version`) are versioned separately.

## Publishing to PyPI later (optional)

If the project should become installable with `pip install enviroqc`, the maintainer needs a
PyPI account and a *Trusted Publisher* for owner `LiuxinBlade`, repository `EnviroQC`, workflow
`release.yml`, environment `pypi`; then a `pypa/gh-action-pypi-publish` job can be added to the
release workflow. No API token should ever be stored in the repository.
