from __future__ import annotations

import tomllib

import enviroqc

from .conftest import ROOT


def test_version_matches_pyproject():
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert meta["project"]["version"] == enviroqc.__version__


def test_public_api_names_exist():
    for name in enviroqc.__all__:
        assert hasattr(enviroqc, name), name


def test_runtime_dependencies_stay_minimal():
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    names = sorted(d.split(">")[0].split("=")[0].lower() for d in meta["project"]["dependencies"])
    assert names == ["openpyxl", "pyyaml"]
