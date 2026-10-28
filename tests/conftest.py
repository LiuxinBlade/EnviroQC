from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
import yaml

from enviroqc import RuleSet, parse_rules, set_language

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


@pytest.fixture(autouse=True)
def english_by_default(monkeypatch):
    """Most tests assert the English catalogue; Chinese output is tested in test_i18n.py.

    The environment variable is removed so a developer's ENVIROQC_LANG cannot change results.
    """
    monkeypatch.delenv("ENVIROQC_LANG", raising=False)
    set_language("en")
    yield
    set_language(None)


def make_rules(columns: list[dict[str, Any]], **top: Any) -> RuleSet:
    data: dict[str, Any] = {"version": 1, "columns": columns}
    data.update(top)
    return parse_rules(data)


@pytest.fixture
def write_csv(tmp_path: Path):
    def _write(text: str, name: str = "data.csv", encoding: str = "utf-8") -> Path:
        p = tmp_path / name
        p.write_bytes(text.encode(encoding))
        return p

    return _write


@pytest.fixture
def write_rules(tmp_path: Path):
    def _write(data: Any, name: str = "rules.yaml") -> Path:
        p = tmp_path / name
        text = data if isinstance(data, str) else yaml.safe_dump(data, allow_unicode=True)
        p.write_text(text, encoding="utf-8")
        return p

    return _write


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def issues_of(report, check: str | None = None):
    return [
        (i.row, i.column, i.check.value, i.severity.value)
        for i in report.issues
        if check is None or i.check.value == check
    ]
