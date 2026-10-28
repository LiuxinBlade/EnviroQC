# Security policy

## Supported versions

Only the latest released version receives fixes while the project is below 1.0.

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Use GitHub's private
vulnerability reporting: on the repository page, open **Security → Report a vulnerability**.

Include a description, affected version, steps to reproduce and, if possible, a minimal
synthetic file. You should receive an acknowledgement within 7 days. Fixes are released as soon
as practical and credited in the changelog unless you prefer otherwise.

## Scope and design notes

EnviroQC processes files that may come from untrusted sources. Relevant safeguards:

- Input files are opened read-only; reports are never written over the input or rules files.
- Rules are loaded with `yaml.safe_load` (no arbitrary object construction).
- Excel files are read with `openpyxl` in read-only, values-only mode; formulas are not evaluated
  and macros are never executed.
- All data values in HTML reports are escaped; reports load no external resources.

Known limitation: very large files are loaded into memory. Do not run EnviroQC as an exposed
service on untrusted uploads without your own size limits.
