"""Command-line interface: ``enviroqc validate`` and ``enviroqc check-rules``.

Output is Chinese by default; ``--lang en`` (or ``ENVIROQC_LANG=en``) switches
to English.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
import traceback
from collections.abc import Iterator, Sequence
from typing import TextIO

from . import __version__
from .config import load_rules
from .exceptions import EnviroQCError, ExitCode
from .i18n import (
    SUPPORTED_LANGUAGES,
    get_language,
    language_override,
    normalize_language,
    set_language,
    t,
)
from .models import Report, Severity
from .report import write_report
from .validator import validate_file

FAIL_ON_CHOICES = ("error", "warning", "info", "never")

# Chinese versions of argparse's own built-in messages (usage, errors, help).
# Strings not listed here are shown unchanged.
_ARGPARSE_ZH = {
    "usage: ": "用法：",
    "positional arguments": "位置参数",
    "options": "选项",
    "optional arguments": "选项",
    "show this help message and exit": "显示帮助信息并退出",
    "%(prog)s: error: %(message)s\n": "%(prog)s：错误：%(message)s\n",
    "the following arguments are required: %s": "缺少必需参数：%s",
    "unrecognized arguments: %s": "无法识别的参数：%s",
    "expected one argument": "需要提供一个参数值",
    "invalid choice: %(value)r (choose from %(choices)s)": (
        "无效的选项 %(value)r（可选：%(choices)s）"
    ),
    "argument %(argument_name)s: %(message)s": "参数 %(argument_name)s：%(message)s",
    "invalid %(type)s value: %(value)r": "无效的 %(type)s 值：%(value)r",
}


@contextlib.contextmanager
def _argparse_language(lang: str) -> Iterator[None]:
    """Temporarily translate argparse's built-in strings (it looks up ``_`` at call time)."""
    if lang != "zh":
        yield
        return
    original = argparse._  # type: ignore[attr-defined]
    argparse._ = lambda text: _ARGPARSE_ZH.get(text, original(text))  # type: ignore[attr-defined]
    try:
        yield
    finally:
        argparse._ = original  # type: ignore[attr-defined]


def _language_from_argv(argv: Sequence[str]) -> str | None:
    """Find ``--lang X`` / ``--lang=X`` before argparse runs, so help text is translated."""
    for i, arg in enumerate(argv):
        value = None
        if arg == "--lang" and i + 1 < len(argv):
            value = argv[i + 1]
        elif arg.startswith("--lang="):
            value = arg.split("=", 1)[1]
        if value is not None:
            try:
                return normalize_language(value)
            except ValueError:
                return None  # argparse reports the invalid choice
    return None


def build_parser(lang: str | None = None) -> argparse.ArgumentParser:
    L = get_language() if lang is None else normalize_language(lang)

    def h(key: str) -> str:
        return t(key, L)

    parser = argparse.ArgumentParser(
        prog="enviroqc", description=h("help.description"), epilog=h("help.epilog")
    )
    parser.add_argument(
        "--version", action="version", version=f"enviroqc {__version__}", help=h("help.version")
    )
    lang_arg = {
        "choices": SUPPORTED_LANGUAGES,
        "type": str.lower,
        "default": argparse.SUPPRESS,
        "help": h("help.lang"),
    }
    parser.add_argument("--lang", **lang_arg)
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    v = sub.add_parser("validate", help=h("help.validate"), description=h("help.validate_desc"))
    v.add_argument("input", help=h("help.input"))
    v.add_argument("-r", "--rules", required=True, help=h("help.rules"))
    v.add_argument(
        "-o", "--output", action="append", default=[], metavar="PATH", help=h("help.output")
    )
    v.add_argument("--format", choices=("json", "html"), help=h("help.format"))
    v.add_argument("--encoding", help=h("help.encoding"))
    v.add_argument("--sheet", help=h("help.sheet"))
    v.add_argument("--delimiter", help=h("help.delimiter"))
    v.add_argument("--fail-on", choices=FAIL_ON_CHOICES, default="error", help=h("help.fail_on"))
    v.add_argument("--overwrite", action="store_true", help=h("help.overwrite"))
    v.add_argument("--max-print", type=int, default=20, metavar="N", help=h("help.max_print"))
    v.add_argument("-q", "--quiet", action="store_true", help=h("help.quiet"))
    v.add_argument("--lang", **lang_arg)

    c = sub.add_parser(
        "check-rules", help=h("help.check_rules"), description=h("help.check_rules_desc")
    )
    c.add_argument("rules", help=h("help.rules"))
    c.add_argument("--lang", **lang_arg)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _safe_streams()
    args_list = list(sys.argv[1:] if argv is None else argv)
    lang = _language_from_argv(args_list) or get_language()
    with _argparse_language(lang):
        parser = build_parser(lang)
        args = parser.parse_args(args_list)
    previous = language_override()  # restore exactly, so ENVIROQC_LANG keeps working
    set_language(lang)
    try:
        if args.command == "validate":
            return _cmd_validate(args, parser, lang)
        return _cmd_check_rules(args)
    except EnviroQCError as exc:
        print(t("cli.error", message=str(exc)), file=sys.stderr)
        return int(exc.exit_code)
    except KeyboardInterrupt:
        print(t("cli.interrupted"), file=sys.stderr)
        return 130
    except Exception:  # pragma: no cover - safety net for unexpected bugs
        traceback.print_exc()
        print(t("cli.internal"), file=sys.stderr)
        return int(ExitCode.INTERNAL_ERROR)
    finally:
        set_language(previous)


def _cmd_validate(args: argparse.Namespace, parser: argparse.ArgumentParser, lang: str) -> int:
    with _argparse_language(lang):
        if args.max_print < 0:
            parser.error(t("cli.max_print_negative"))
        delimiter = args.delimiter
        if delimiter is not None:
            delimiter = {"\\t": "\t", "tab": "\t"}.get(delimiter, delimiter)
            if len(delimiter) != 1:
                parser.error(t("cli.delimiter_single"))
    rules = load_rules(args.rules)
    report = validate_file(
        args.input,
        rules,
        encoding=args.encoding,
        sheet=args.sheet,
        delimiter=delimiter,
        lang=lang,
    )
    written = [
        write_report(
            report,
            out,
            fmt=args.format,
            overwrite=args.overwrite,
            protected=(args.rules,),
        )
        for out in args.output
    ]
    if not args.quiet:
        _print_summary(report, sys.stdout, args.max_print)
        for path in written:
            print(t("cli.written", path=path))
    return int(_exit_code(report, args.fail_on))


def _cmd_check_rules(args: argparse.Namespace) -> int:
    rules = load_rules(args.rules)
    n_ranges = sum(len(c.ranges) for c in rules.columns)
    print(
        t(
            "cli.rules_ok",
            path=args.rules,
            columns=len(rules.columns),
            ranges=n_ranges,
            dups=len(rules.duplicates),
        )
    )
    return int(ExitCode.OK)


def _exit_code(report: Report, fail_on: str) -> ExitCode:
    if fail_on == "never":
        return ExitCode.OK
    threshold = Severity(fail_on)
    return ExitCode.ISSUES_FOUND if report.issues_at_least(threshold) else ExitCode.OK


def _print_summary(report: Report, out: TextIO, max_print: int) -> None:
    s = report.summary()
    sev = s["by_severity"]
    src = report.source
    where = src.file + (t("cli.sheet_suffix", sheet=src.sheet) if src.sheet else "")
    print(
        t(
            "cli.summary",
            where=where,
            rows=src.data_rows,
            total=s["total_issues"],
            errors=sev["error"],
            warnings=sev["warning"],
            infos=sev["info"],
            status=t(f"status.{s['status']}"),
        ),
        file=out,
    )
    width = max(len(t(f"sev.{x.value}")) for x in Severity)
    for issue in report.issues[:max_print]:
        row = t("cli.row", row=issue.row) if issue.row is not None else t("cli.file_level")
        col = f" [{issue.column}]" if issue.column else ""
        label = t(f"sev.{issue.severity.value}").ljust(width)
        print(f"  {label} {row}{col} {issue.rule}: {issue.message}", file=out)
    hidden = len(report.issues) - max_print
    if max_print and hidden > 0:
        print(t("cli.more", n=hidden), file=out)


def _safe_streams() -> None:
    """Avoid UnicodeEncodeError on consoles that cannot show e.g. 'µg/m³' or Chinese."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with contextlib.suppress(ValueError, OSError):
                reconfigure(errors="replace")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
