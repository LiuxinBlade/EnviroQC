# EnviroQC

**面向环境监测数据的开源数据质量检查工具。**

**简体中文** | [English](README.en.md)

EnviroQC 用于检查环境监测（空气、水、土壤、气象等）CSV 与 Excel（XLSX）表格中的缺失值、重复记录、
格式错误和可配置的数值异常。每一条问题都标注**源文件中的行号**，便于追溯和复核。结果可输出为
JSON（供程序使用）和 HTML（供人阅读）。

- 完全本地运行：无需账号、无需云服务、不联网。
- 数据文件以**只读**方式打开，永远不会被修改。
- 所有规则写在由你维护的 YAML 文件中。
- 既可在命令行使用，也可作为 Python 库调用。
- 界面与报告支持中文和英文，**默认中文**（`--lang en` 切换为英文）。

> **适用范围。** EnviroQC 是数据质量**初筛**工具，不是法定环境合规认证软件。阈值来自你的规则文件，
> 除非你明确如此设定，否则它们不代表任何法规限值。被标记的数值是“需要复核的记录”，并不等于“测量错误”。

## 当前状态

0.1.0 版本（alpha）。规则格式（`version: 1`）、报告 Schema（`1.0`）和退出码均有文档和测试覆盖；
1.0 之前仍可能调整，任何变化都会记录在 [CHANGELOG](CHANGELOG.md) 中。

## 安装

需要 Python 3.11 及以上版本。EnviroQC 通过 GitHub 发布，不在 PyPI 上。

**方式一：克隆仓库（推荐，自带示例数据）**

```bash
git clone https://github.com/LiuxinBlade/EnviroQC.git
cd EnviroQC
python -m venv .venv
. .venv/bin/activate          # Windows：.venv\Scripts\activate
pip install .
```

**方式二：直接安装某个发布版本**

```bash
pip install "git+https://github.com/LiuxinBlade/EnviroQC.git@v0.1.0"
```

也可以在 [Releases](https://github.com/LiuxinBlade/EnviroQC/releases) 页面下载 `.whl` 文件，然后
`pip install enviroqc-0.1.0-py3-none-any.whl`。需要 `validate_dataframe()` 时另外安装 pandas：
`pip install pandas`。

## 快速开始

仓库自带一份合成的逐小时空气质量数据，其中故意埋入了各类问题：

```bash
enviroqc validate examples/air_quality_sample.csv --rules examples/air_quality_rules.yaml --output report.html --output report.json
```

终端输出（节选）：

```text
air_quality_sample.csv：26 行数据，12 个问题（错误 10，警告 2，提示 0）-> 不通过
  错误 第 4 行 [pm25] pm25.not_null: “pm25”列存在缺失值。
  错误 第 5 行 [pm25] pm25.type: “pm25”列的值“12,5”不是有效的数值。
  错误 第 6 行 [pm25] pm25.non_negative: pm25 = -3.2 µg/m³，低于下限 0（浓度不能为负 / concentrations cannot be negative）。
  ...
  错误 第 16 行 [station_id, timestamp] duplicate_station_time: 与第 15 行重复（station_id, timestamp）。
报告已写入：report.html
报告已写入：report.json
```

用浏览器打开 `report.html` 即可查看完整表格。需要英文输出时加上 `--lang en`：

```bash
enviroqc validate examples/air_quality_sample.csv --rules examples/air_quality_rules.yaml --lang en
```
Excel 文件用法相同：

```bash
enviroqc validate examples/air_quality_sample.xlsx --rules examples/air_quality_rules.yaml
```

## 检查项目

| 检查 | `check` 标识 | 配置方式 |
|---|---|---|
| 缺少必需列 | `missing_column` | `required` |
| 规则中未定义的列 | `unexpected_column` | `unexpected_columns` |
| 字段数与表头不符的行 | `malformed_row` | 始终启用（CSV） |
| 只有表头没有数据 | `empty_dataset` | 始终启用 |
| 缺失值 | `missing_value` | `nullable`、`input.missing_values` |
| 类型错误 | `invalid_type` | `type`、`format` |
| 不符合正则 | `pattern_mismatch` | `pattern` |
| 不在允许列表中 | `not_allowed` | `allowed` |
| 数值超出范围 | `out_of_range` | `range` / `ranges` |
| 重复记录 | `duplicate_record` | `duplicates` |

## 规则文件示例

```yaml
version: 1
input:
  encoding: utf-8-sig        # 很多中文导出文件需改为 gbk 或 gb18030
  missing_values: ["", "NA", "-999"]
columns:
  - name: station_id
    pattern: "^ST\\d{3}$"
  - name: timestamp
    type: datetime
    format: "%Y-%m-%d %H:%M"
  - name: pm25
    type: float
    unit: µg/m³
    ranges:
      - {name: pm25.non_negative, min: 0, severity: error}
      - {name: pm25.plausible_upper, max: 500, severity: warning, note: 示例经验范围，非法规限值}
duplicates:
  - name: duplicate_station_time
    columns: [station_id, timestamp]
```

只检查规则文件本身：

```bash
enviroqc check-rules examples/air_quality_rules.yaml
```

全部选项见 [docs/configuration.md](docs/configuration.md)。

## Python API

```python
from enviroqc import validate_file, write_report

report = validate_file("examples/air_quality_sample.csv", "examples/air_quality_rules.yaml")
print(report.status, report.summary()["by_severity"])
for issue in report.issues:
    print(issue.row, issue.column, issue.rule, issue.message)
write_report(report, "report.json", overwrite=True)
```

## 显示语言

| 方式 | 示例 |
|---|---|
| 默认 | 中文 |
| 命令行参数 | `enviroqc validate data.csv -r rules.yaml --lang en` |
| 环境变量 | `ENVIROQC_LANG=en`（`zh` 或 `en`） |
| Python API | `validate_file(..., lang="en")`、`report.to_html(lang="zh")`、`enviroqc.set_language("en")` |

语言只影响说明文字。检查结果、行号、规则名以及 JSON 中的 `check`、`message_id` 等机器可读字段与语言无关。
规则文件里你自己写的 `note`、`unit` 等内容按原样显示。

## 退出码

| 退出码 | 含义 |
|---|---|
| 0 | 没有达到 `--fail-on` 级别（默认 `error`）的问题 |
| 1 | 至少有一条达到 `--fail-on` 级别的问题 |
| 2 | 命令行参数错误 |
| 3 | 规则文件无效或无法读取 |
| 4 | 输入文件不存在、为空、编码错误、损坏或格式不支持 |
| 5 | 报告无法写入（或会覆盖输入文件） |
| 10 | 内部错误（请提交 Issue） |

## 文档

- [使用说明](docs/usage.md) · [规则配置](docs/configuration.md) · [报告格式](docs/report-schema.md)
- [Python API](docs/python-api.md) · [故障排查](docs/troubleshooting.md)
- [开发指南](docs/development.md) · [发布流程](docs/release.md)

（详细文档目前为英文。）

## 常见问题

- **中文 CSV 报编码错误**：加上 `--encoding gbk`（或 `gb18030`），或在规则文件 `input.encoding` 中设置。
- **数据前面有标题行**：设置 `input.header_row` 为表头所在行号。
- **用 -999 表示缺测**：把 `"-999"` 加入 `input.missing_values`。

更多见 [docs/troubleshooting.md](docs/troubleshooting.md)。

## 参与贡献

欢迎提交问题报告、规则格式建议和 Pull Request，请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。
请勿在公开 Issue 中附带保密或包含个人信息的监测数据，请改用缩减后的合成示例。

## 许可证

[MIT](LICENSE)
