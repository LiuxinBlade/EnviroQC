# Troubleshooting

| Message | Cause | Fix |
|---|---|---|
| `Cannot decode X as 'utf-8-sig': invalid byte at line N` | The CSV is not UTF-8 (common for files exported by Excel on Chinese Windows). | `--encoding gbk` (or `gb18030`, `cp1252`, `latin-1`), or set `input.encoding`. |
| `contains NUL bytes` | The file is UTF-16 or binary. | `--encoding utf-16`, or re-export as UTF-8 CSV. |
| `Legacy Excel format (.xls) is not supported` | Old binary Excel file. | Save as `.xlsx` or `.csv`. |
| `is not a valid .xlsx file (it is not a ZIP container)` | The file is damaged, or it is a CSV/HTML file renamed to `.xlsx`. | Open and re-save in Excel/LibreOffice; check the real format. |
| `Header row N of X has empty column name(s)` | A column has data but no header, or the table does not start in column A. | Name every column, delete empty columns, or move the table to column A. |
| `duplicate column name(s)` | Two columns share a header. | Rename one of them. |
| `No header row found` | The file or sheet is empty, or `header_row` points past the end. | Check `input.header_row` and `--sheet`. |
| `Malformed CSV ... near line N` | Unbalanced quote. | Fix the quote on or before line N. |
| Every row is a `malformed_row` / everything is in one column | Wrong delimiter. | `--delimiter ";"` (or `\t`), or set `input.delimiter`. |
| `Required column 'x' is not in the file` | Header text differs (spelling, unit suffix, language). | Rename the column in `columns[].name` to match the file exactly. |
| Many `invalid_type` for numbers like `12,5` | Decimal comma. | Not converted on purpose; convert the data or use a `string` column with a `pattern`. |
| `invalid_type` for `<0.01` | Below-detection-limit notation. | Decide a policy; see configuration.md. |
| `-999` reported as out of range | Sentinel not declared as missing. | Add `"-999"` to `input.missing_values`. |
| `Output file already exists` | Reports are never overwritten silently. | Add `--overwrite`, or choose another name. |
| `Refusing to write a report to ...` | The output path is the input/rules file, or has a data-file extension. | Use a `.json` or `.html` output name. |
| Rules error: `unknown key 'rnage'. Did you mean 'range'?` | Typo in the YAML. | Fix the key. |
| Chinese text shows as `?` or garbled characters in the terminal | The console encoding cannot show Chinese (common in old Windows consoles). | Use Windows Terminal, run `chcp 65001`, or use `--lang en`. Reports are always written as UTF-8. |
| Output is in Chinese but you need English | Chinese is the default. | `--lang en` or `ENVIROQC_LANG=en`. |
| Rules error mentioning booleans in `missing_values` | YAML reads `no`, `yes`, `off` as booleans. | Quote them: `"no"`. |

## Reporting a bug

Please open an issue with: EnviroQC version (`enviroqc --version`), Python version, operating
system, the command, the full error output, and a **small synthetic** file that reproduces the
problem. Do not upload confidential or personal data.
