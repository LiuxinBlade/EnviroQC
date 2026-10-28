"""Read-only loading of CSV and XLSX files with exact source row numbers.

The data file is only ever opened in binary read mode; EnviroQC never writes
to it. CSV parsing uses the standard :mod:`csv` module so that the physical
line on which each record starts is known even when quoted fields contain line
breaks.
"""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import InputOptions
from .exceptions import (
    CorruptFileError,
    EmptyFileError,
    EncodingError,
    FileNotFoundInputError,
    HeaderError,
    InputFileError,
    UnsupportedFormatError,
)
from .i18n import t

CSV_SUFFIXES = frozenset({".csv", ".txt", ".tsv"})
XLSX_SUFFIXES = frozenset({".xlsx", ".xlsm"})


@dataclass(frozen=True)
class Record:
    """One data row. ``row`` is the 1-based source row number."""

    row: int
    values: tuple[Any, ...]
    """Cell values. ``str`` for CSV; native Python types (or ``None``) for XLSX."""


@dataclass(frozen=True)
class Table:
    """The parsed content of a data file."""

    file: str
    path: str
    format: str
    sheet: str | None
    header: tuple[str, ...]
    header_row: int
    records: tuple[Record, ...]
    sha256: str | None = None


def read_table(path: str | Path, options: InputOptions | None = None) -> Table:
    """Read a CSV or XLSX file. The file is never modified."""
    options = options or InputOptions()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundInputError(t("in.not_found", path=p))
    if not p.is_file():
        raise FileNotFoundInputError(t("in.not_file", path=p))
    suffix = p.suffix.lower()
    if suffix == ".xls":
        raise UnsupportedFormatError(
            t("in.xls", name=p.name),
            hint=t("in.xls.hint"),
        )
    if suffix not in CSV_SUFFIXES | XLSX_SUFFIXES:
        raise UnsupportedFormatError(
            t("in.unsupported", suffix=suffix or t("in.no_extension"), name=p.name),
            hint=t("in.unsupported.hint"),
        )
    try:
        raw = p.read_bytes()
    except OSError as exc:
        raise InputFileError(t("in.read_failed", path=p, reason=exc.strerror or exc)) from exc
    if not raw.strip():
        raise EmptyFileError(t("in.empty", name=p.name))
    sha = hashlib.sha256(raw).hexdigest()
    if suffix in XLSX_SUFFIXES:
        return _read_xlsx(p, raw, sha, options)
    delimiter = options.delimiter
    if suffix == ".tsv" and options.delimiter == ",":
        delimiter = "\t"
    return _read_csv(p, raw, sha, options, delimiter)


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------


def _read_csv(p: Path, raw: bytes, sha: str, options: InputOptions, delimiter: str) -> Table:
    try:
        text = raw.decode(options.encoding)
    except UnicodeDecodeError as exc:
        line = raw[: exc.start].count(b"\n") + 1
        raise EncodingError(
            t("in.decode", name=p.name, encoding=options.encoding, line=line, offset=exc.start),
            hint=t("in.decode.hint"),
        ) from exc
    if "\x00" in text:
        raise EncodingError(
            t("in.nul", name=p.name),
            hint=t("in.nul.hint"),
        )

    # Lines above ``header_row`` (titles, notes) are skipped before parsing.
    skip = options.header_row - 1
    if skip:
        # Split exactly like the csv reader does (only \n, \r and \r\n).
        lines = io.StringIO(text, newline="").readlines()
        text = "".join(lines[skip:])
    stream = io.StringIO(text, newline="")
    reader = csv.reader(stream, delimiter=delimiter, strict=True)
    header: tuple[str, ...] | None = None
    header_line = 0
    records: list[Record] = []
    start_line = skip + 1
    try:
        for fields in reader:
            # reader.line_num counts physical lines consumed so far, so each
            # record starts on the line after the previous record ended.
            this_start = start_line
            start_line = skip + reader.line_num + 1
            if not fields or all(f.strip() == "" for f in fields):
                continue
            if header is None:
                header = _clean_header(fields, p.name, this_start)
                header_line = this_start
                continue
            records.append(Record(row=this_start, values=_fit(tuple(fields), len(header))))
    except csv.Error as exc:
        raise CorruptFileError(
            t("in.bad_csv", name=p.name, line=skip + reader.line_num, error=exc),
            hint=t("in.bad_csv.hint"),
        ) from exc
    if header is None:
        raise EmptyFileError(t("in.no_header_csv", name=p.name, row=options.header_row))
    return Table(
        file=p.name,
        path=str(p),
        format="csv",
        sheet=None,
        header=header,
        header_row=header_line,
        records=tuple(records),
        sha256=sha,
    )


# --------------------------------------------------------------------------
# XLSX
# --------------------------------------------------------------------------


def _read_xlsx(p: Path, raw: bytes, sha: str, options: InputOptions) -> Table:
    import openpyxl
    from openpyxl.utils.exceptions import InvalidFileException

    if not zipfile.is_zipfile(io.BytesIO(raw)):
        raise CorruptFileError(
            t("in.not_zip", name=p.name),
            hint=t("in.not_zip.hint"),
        )
    try:
        wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except (InvalidFileException, zipfile.BadZipFile, KeyError, OSError, ValueError) as exc:
        raise CorruptFileError(
            t("in.bad_workbook", name=p.name, error=exc),
            hint=t("in.bad_workbook.hint"),
        ) from exc
    try:
        if options.sheet is not None:
            if options.sheet not in wb.sheetnames:
                raise InputFileError(
                    t("in.no_sheet", sheet=options.sheet, name=p.name),
                    hint=t("in.no_sheet.hint", sheets=", ".join(wb.sheetnames)),
                )
            ws = wb[options.sheet]
        else:
            ws = wb.worksheets[0]
        sheet_name = ws.title
        header: tuple[str, ...] | None = None
        header_line = 0
        records: list[Record] = []
        try:
            for row_no, values in _iter_sheet(ws):
                if header is None:
                    if row_no < options.header_row:
                        continue
                    if _blank(values):
                        continue
                    header = _clean_header(
                        ["" if v is None else str(v) for v in _trim(values)], p.name, row_no
                    )
                    header_line = row_no
                    continue
                if _blank(values):
                    continue
                records.append(Record(row=row_no, values=tuple(values)))
        except (zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
            raise CorruptFileError(
                t("in.bad_sheet", sheet=sheet_name, name=p.name, error=exc)
            ) from exc
    finally:
        wb.close()
    if header is None:
        raise EmptyFileError(t("in.no_header_xlsx", sheet=sheet_name, name=p.name))
    width = len(header)
    fixed = tuple(Record(r.row, _fit(r.values, width)) for r in records)
    return Table(
        file=p.name,
        path=str(p),
        format="xlsx",
        sheet=sheet_name,
        header=header,
        header_row=header_line,
        records=fixed,
        sha256=sha,
    )


def _iter_sheet(ws: Any) -> Iterator[tuple[int, tuple[Any, ...]]]:
    # min_row=1 so that enumerate() gives true Excel row numbers even when the
    # first used row is lower down; openpyxl fills gaps with empty rows.
    for row_no, values in enumerate(ws.iter_rows(min_row=1, values_only=True), start=1):
        yield row_no, tuple(values)


def _fit(values: tuple[Any, ...], width: int) -> tuple[Any, ...]:
    """Pad/trim Excel rows: trailing empty cells beyond the header are not data."""
    if len(values) > width and all(_is_blank_cell(v) for v in values[width:]):
        values = values[:width]
    return values


def _trim(values: tuple[Any, ...]) -> tuple[Any, ...]:
    end = len(values)
    while end > 0 and _is_blank_cell(values[end - 1]):
        end -= 1
    return values[:end]


def _is_blank_cell(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _blank(values: tuple[Any, ...]) -> bool:
    return all(_is_blank_cell(v) for v in values)


# --------------------------------------------------------------------------
# Shared
# --------------------------------------------------------------------------


def _clean_header(fields: list[str], file: str, row: int) -> tuple[str, ...]:
    names = [f.strip() for f in fields]
    # Ignore trailing empty header cells (common with spreadsheet exports).
    while names and names[-1] == "":
        names.pop()
    if not names:
        raise HeaderError(t("in.header_empty", row=row, name=file))
    blanks = [i + 1 for i, n in enumerate(names) if n == ""]
    if blanks:
        raise HeaderError(
            t("in.header_blank_names", row=row, name=file, positions=", ".join(map(str, blanks))),
            hint=t("in.header_blank_names.hint"),
        )
    seen: set[str] = set()
    dups: list[str] = []
    for n in names:
        if n in seen and n not in dups:
            dups.append(n)
        seen.add(n)
    if dups:
        raise HeaderError(
            t("in.header_dups", row=row, name=file, names=", ".join(map(repr, dups))),
            hint=t("in.header_dups.hint"),
        )
    return tuple(names)
