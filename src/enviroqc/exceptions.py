"""Stable exception hierarchy and CLI exit codes.

Every error raised on purpose by EnviroQC derives from :class:`EnviroQCError`
and carries an ``exit_code`` used by the command-line interface.
"""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Process exit codes of the ``enviroqc`` command (stable public contract)."""

    OK = 0
    """Validation ran and no issue reached the ``--fail-on`` threshold."""
    ISSUES_FOUND = 1
    """Validation ran and at least one issue reached the ``--fail-on`` threshold."""
    USAGE_ERROR = 2
    """Invalid command-line arguments."""
    CONFIG_ERROR = 3
    """The rules (YAML) file is missing, unreadable or invalid."""
    INPUT_ERROR = 4
    """The data file is missing, empty, undecodable, corrupt or unsupported."""
    OUTPUT_ERROR = 5
    """The report could not be written (or writing it was refused)."""
    INTERNAL_ERROR = 10
    """Unexpected bug. Please report it."""


class EnviroQCError(Exception):
    """Base class of all EnviroQC errors."""

    exit_code: ExitCode = ExitCode.INTERNAL_ERROR

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        if self.hint:
            from .i18n import t

            return f"{self.message}\n{t('hint', hint=self.hint)}"
        return self.message


class ConfigError(EnviroQCError):
    """The rules configuration is invalid."""

    exit_code = ExitCode.CONFIG_ERROR


class InputFileError(EnviroQCError):
    """The input data file cannot be read."""

    exit_code = ExitCode.INPUT_ERROR


class FileNotFoundInputError(InputFileError):
    """The input file does not exist or is not a regular file."""


class UnsupportedFormatError(InputFileError):
    """The input file extension is not supported."""


class EmptyFileError(InputFileError):
    """The input file is empty or has no header row."""


class EncodingError(InputFileError):
    """The input file cannot be decoded with the configured encoding."""


class CorruptFileError(InputFileError):
    """The input file is damaged or not in the format its extension claims."""


class HeaderError(InputFileError):
    """The header row is unusable (blank or duplicated column names)."""


class OutputError(EnviroQCError):
    """The report cannot be written."""

    exit_code = ExitCode.OUTPUT_ERROR
