"""Regenerate the synthetic example datasets in this folder.

The data is fully synthetic (deterministic, no real stations or people) and
contains deliberate problems so that every EnviroQC check has something to find.

    python examples/make_example_data.py
"""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
HEADER = [
    "station_id",
    "timestamp",
    "pm25",
    "pm10",
    "no2",
    "temperature_c",
    "relative_humidity",
    "qc_flag",
]


def clean_rows() -> list[list[str]]:
    rng = random.Random(42)
    start = datetime(2024, 1, 1, 0, 0)
    rows = []
    for station in ("ST001", "ST002"):
        for h in range(12):
            t = start + timedelta(hours=h)
            rows.append(
                [
                    station,
                    t.strftime("%Y-%m-%d %H:%M"),
                    f"{rng.uniform(5, 80):.1f}",
                    f"{rng.uniform(20, 150):.1f}",
                    f"{rng.uniform(5, 90):.1f}",
                    f"{rng.uniform(-5, 12):.1f}",
                    f"{rng.uniform(30, 95):.0f}",
                    "V",
                ]
            )
    return rows


def with_problems(rows: list[list[str]]) -> list[list[str]]:
    rows = [r[:] for r in rows]
    rows[2][2] = ""  # missing pm25
    rows[3][2] = "12,5"  # wrong decimal separator -> invalid number
    rows[4][2] = "-3.2"  # negative concentration -> error range
    rows[5][2] = "612.0"  # above plausibility bound -> warning
    rows[6][1] = "2024/01/01 06:00"  # wrong timestamp format
    rows[7][0] = "S7"  # station id pattern mismatch
    rows[8][6] = "104"  # humidity above 100 %
    rows[9][7] = "X"  # qc flag not in allowed list
    rows[10][3] = "-999"  # sentinel -> missing pm10 (allowed: nullable)
    rows[11][4] = "n/a"  # not a configured missing token -> invalid number
    dup_key = rows[13][:]  # same station+time as row 13, different values
    dup_key[2] = "33.3"
    rows.insert(14, dup_key)
    rows.append(rows[20][:])  # exact duplicate row
    return rows


def write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(rows)


def write_xlsx(path: Path, rows: list[list[str]]) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "hourly"
    ws.append(HEADER)
    for r in rows:
        out: list[object] = []
        for i, v in enumerate(r):
            if i == 1:
                try:
                    out.append(datetime.strptime(v, "%Y-%m-%d %H:%M"))
                    continue
                except ValueError:
                    pass
            try:
                out.append(float(v) if i >= 2 and i <= 6 else v)
            except ValueError:
                out.append(v if v != "" else None)
        ws.append(out)
    wb.save(path)


def main() -> None:
    clean = clean_rows()
    write_csv(HERE / "air_quality_clean.csv", clean)
    messy = with_problems(clean)
    write_csv(HERE / "air_quality_sample.csv", messy)
    write_xlsx(HERE / "air_quality_sample.xlsx", messy)
    print("Wrote air_quality_clean.csv, air_quality_sample.csv, air_quality_sample.xlsx")


if __name__ == "__main__":
    main()
