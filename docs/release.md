# Release process

Releases are published to PyPI by GitHub Actions using
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC). No API token is stored in
the repository or in GitHub secrets.

## One-time setup (maintainer)

1. On PyPI, add a *pending trusted publisher* for project `enviroqc`:
   owner = the GitHub account/organisation, repository = `EnviroQC`,
   workflow = `release.yml`, environment = `pypi`.
2. In the GitHub repository settings, create an environment named `pypi` (optionally with
   required reviewers so every upload needs a manual approval).

## Each release

1. Make sure `main` is green in CI.
2. Update the version in `pyproject.toml` **and** `src/enviroqc/__init__.py`.
3. Move the `Unreleased` entries in `CHANGELOG.md` under the new version with today's date.
4. Run locally:

   ```bash
   ruff check . && ruff format --check . && pytest
   rm -rf dist && python -m build
   python -m pip install --force-reinstall dist/*.whl && enviroqc --version
   ```

5. Commit (`Release vX.Y.Z`), tag and push:

   ```bash
   git tag -a vX.Y.Z -m "EnviroQC vX.Y.Z"
   git push origin main vX.Y.Z
   ```

6. Pushing the tag runs `release.yml`: it re-runs the tests, builds the sdist and wheel, checks
   that the tag matches the package version, publishes to PyPI and creates a GitHub Release with
   the built files attached.

## Versioning

[Semantic Versioning](https://semver.org/). Before 1.0, minor versions may contain breaking changes;
they are always listed in the changelog. The rules format (`version`) and report schema
(`schema_version`) are versioned separately.
