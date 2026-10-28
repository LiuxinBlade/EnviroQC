"""Report rendering (HTML) and safe report writing.

All data values are HTML-escaped: the report is safe to open even when the
source file contains markup or script text.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from .exceptions import OutputError
from .i18n import resolve_language, t

if TYPE_CHECKING:
    from .models import Report

REPORT_FORMATS = {".json": "json", ".html": "html", ".htm": "html"}
_PROTECTED_SUFFIXES = frozenset({".csv", ".tsv", ".txt", ".xlsx", ".xlsm", ".xls", ".yaml", ".yml"})


def write_report(
    report: Report,
    output: str | Path,
    *,
    fmt: str | None = None,
    overwrite: bool = False,
    protected: tuple[str | Path, ...] = (),
) -> Path:
    """Write ``report`` to ``output`` as JSON or HTML.

    The format is taken from ``fmt`` or the file extension. Writing is refused
    when the target is one of the ``protected`` paths (the input data and rules
    file), has a data/rules extension, or already exists and ``overwrite`` is
    false.
    """
    out = Path(output)
    fmt = fmt or REPORT_FORMATS.get(out.suffix.lower())
    if fmt not in ("json", "html"):
        raise OutputError(
            t("out.unknown_format", name=out.name),
            hint=t("out.unknown_format.hint"),
        )
    if out.suffix.lower() in _PROTECTED_SUFFIXES:
        raise OutputError(
            t("out.protected_ext", name=out.name),
            hint=t("out.protected_ext.hint"),
        )
    out_resolved = out.resolve()
    sources = [Path(report.source.path)] + [Path(p) for p in protected]
    for src in sources:
        try:
            same = src.exists() and out.exists() and src.samefile(out)
        except OSError:
            same = False
        if same or src.resolve() == out_resolved:
            raise OutputError(t("out.is_input", path=src))
    if out.exists() and not overwrite:
        raise OutputError(
            t("out.exists", path=out),
            hint=t("out.exists.hint"),
        )
    if out.exists() and not out.is_file():
        raise OutputError(t("out.not_file", path=out))
    text = report.to_json() + "\n" if fmt == "json" else render_html(report)
    try:
        if out.parent and not out.parent.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temporary file first so a crash never leaves half a report.
        tmp = out.with_name(f".{out.name}.tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(out)
    except OSError as exc:
        raise OutputError(t("out.write_failed", path=out, reason=exc.strerror or exc)) from exc
    return out


_CSS = """
:root{--bg:#fff;--fg:#1d2329;--muted:#5d6b78;--line:#d9dfe5;--card:#f5f7f9;
--err:#b42318;--errbg:#fde8e7;--warn:#8a5a00;--warnbg:#fff4d6;--info:#1f5f9e;--infobg:#e6f0fa;
--ok:#1b6e3a;--okbg:#e3f4e8}
@media (prefers-color-scheme:dark){:root{--bg:#14181c;--fg:#e6e9ec;--muted:#9aa7b3;
--line:#2c343c;--card:#1c2228;--err:#ff8a80;--errbg:#3b1d1b;--warn:#ffcc66;--warnbg:#3a2f12;
--info:#8cc4ff;--infobg:#14283d;--ok:#7ddc9c;--okbg:#14301f}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 system-ui,-apple-system,"Segoe UI","Noto Sans SC","PingFang SC",sans-serif}
main{max-width:1200px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.6rem;margin:0 0 4px}h2{font-size:1.15rem;margin:32px 0 8px}
.muted{color:var(--muted)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
.card b{display:block;font-size:1.5rem}
.badge{display:inline-block;padding:1px 8px;border-radius:999px;font-size:.8rem;font-weight:600}
.error{color:var(--err);background:var(--errbg)}.warning{color:var(--warn);background:var(--warnbg)}
.info{color:var(--info);background:var(--infobg)}.pass{color:var(--ok);background:var(--okbg)}
.fail{color:var(--err);background:var(--errbg)}.warn{color:var(--warn);background:var(--warnbg)}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:var(--card);position:sticky;top:0}
td.num{text-align:right;font-variant-numeric:tabular-nums}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.85em;word-break:break-all}
.note{border-left:3px solid var(--line);padding:8px 12px;margin:16px 0;background:var(--card)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;margin:0}
dt{color:var(--muted)}dd{margin:0;word-break:break-all}
"""


def _e(value: object) -> str:
    return "" if value is None else escape(str(value), quote=True)


def render_html(report: Report, lang: str | None = None) -> str:
    """Render a self-contained HTML report (no external resources).

    ``lang`` is ``"zh"`` or ``"en"``; by default the report's own language.
    """
    L = report.lang if lang is None else resolve_language(lang)

    def tr(key: str, **params: object) -> str:
        return _e(t(key, L, **params))

    s = report.summary()
    src = report.source
    sev = s["by_severity"]
    status = s["status"]

    rows = []
    for i in report.issues:
        rows.append(
            "<tr>"
            f'<td class="num">{_e(i.row) if i.row is not None else "—"}</td>'
            f"<td>{_e(i.column) if i.column else '—'}</td>"
            f'<td><span class="badge {_e(i.severity.value)}">{tr("sev." + i.severity.value)}'
            "</span></td>"
            f'<td title="{_e(i.check.value)}">{tr("chk." + i.check.value)}</td>'
            f"<td><code>{_e(i.rule)}</code></td>"
            f"<td>{_e(i.message_in(L))}</td>"
            f"<td><code>{_e(i.value)}</code></td>"
            f"<td>{_e(i.expected_in(L))}</td>"
            "</tr>"
        )
    issues_html = (
        f'<div class="scroll"><table><thead><tr><th>{tr("html.row")}</th>'
        f"<th>{tr('html.column')}</th><th>{tr('html.severity')}</th>"
        f"<th>{tr('html.check')}</th><th>{tr('html.rule')}</th><th>{tr('html.message')}</th>"
        f"<th>{tr('html.value')}</th><th>{tr('html.expected')}</th></tr>"
        "</thead><tbody>" + "".join(rows) + "</tbody></table></div>"
        if rows
        else f'<p class="badge pass">{tr("html.no_issues")}</p>'
    )

    col_rows = []
    for name, st in report.column_stats.items():
        present = tr("html.yes") if st.present else f"<b>{tr('html.no')}</b>"
        col_rows.append(
            "<tr>"
            f"<td>{_e(name)}</td>"
            f"<td>{present}</td>"
            f'<td class="num">{st.missing}</td>'
            f'<td class="num">{st.invalid_type}</td>'
            f'<td class="num">{st.out_of_range}</td>'
            "</tr>"
        )
    check_rows = "".join(
        f'<tr><td>{tr("chk." + k)} <code>{_e(k)}</code></td><td class="num">{v}</td></tr>'
        for k, v in s["by_check"].items()
    )
    sheet = f" · {tr('html.sheet', sheet=src.sheet)}" if src.sheet else ""

    return f"""<!doctype html>
<html lang="{tr("html.lang_attr")}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{tr("html.title", file=src.file)}</title>
<style>{_CSS}</style>
</head>
<body>
<main>
<h1>{tr("html.heading")}</h1>
<p class="muted">{_e(src.file)}{sheet}
 · {tr("html.generated", time=report.generated_at)} · EnviroQC {_e(report.tool_version)}</p>
<p><span class="badge {status}">{tr("html.status." + status)}</span></p>
<div class="cards">
<div class="card"><span class="muted">{tr("html.data_rows")}</span><b>{src.data_rows}</b></div>
<div class="card"><span class="muted">{tr("html.rows_with_issues")}</span>
<b>{s["rows_with_issues"]}</b></div>
<div class="card"><span class="muted">{tr("html.errors")}</span><b>{sev["error"]}</b></div>
<div class="card"><span class="muted">{tr("html.warnings")}</span><b>{sev["warning"]}</b></div>
<div class="card"><span class="muted">{tr("html.info")}</span><b>{sev["info"]}</b></div>
</div>
<div class="note">{tr("disclaimer")}</div>

<h2>{tr("html.source")}</h2>
<dl>
<dt>{tr("html.file")}</dt><dd>{_e(src.path)}</dd>
<dt>{tr("html.format")}</dt><dd>{_e(src.format)}</dd>
<dt>SHA-256</dt><dd><code>{_e(src.sha256)}</code></dd>
<dt>{tr("html.header_row")}</dt><dd>{src.header_row}</dd>
<dt>{tr("html.rules")}</dt>
<dd>{_e(report.rules_name or "")} <code>{_e(report.rules_path or "")}</code></dd>
<dt>{tr("html.rules_sha")}</dt><dd><code>{_e(report.rules_sha256 or "")}</code></dd>
</dl>

<h2>{tr("html.columns")}</h2>
<div class="scroll"><table><thead><tr><th>{tr("html.column")}</th><th>{tr("html.present")}</th>
<th>{tr("html.missing")}</th><th>{tr("html.invalid_type")}</th><th>{tr("html.out_of_range")}</th>
</tr></thead>
<tbody>{"".join(col_rows)}</tbody></table></div>

<h2>{tr("html.by_check")}</h2>
<div class="scroll"><table><thead><tr><th>{tr("html.check")}</th><th>{tr("html.count")}</th></tr>
</thead><tbody>{check_rows or '<tr><td colspan="2">—</td></tr>'}</tbody></table></div>

<h2>{tr("html.issues", n=len(report.issues))}</h2>
<p class="muted">{tr("html.row_note", row=src.header_row)}</p>
{issues_html}
</main>
</body>
</html>
"""
