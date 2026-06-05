# 周报自动化系统用户指南

> 本指南帮助用户快速上手周报自动化系统，完成从 Excel 数据到 Word 报告的生成流程。

---

## 1. 系统概述

### 1.1 核心功能

周报自动化系统实现：

- **数据采集**: 从 Excel 数据汇总表提取数据
- **数据标准化**: 将数据转换为标准 JSON 格式
- **报告生成**: 自动生成周例会营销发言材料 Word 文档
- **图表生成**: 自动生成数据可视化图表

### 1.2 处理流程

```
Excel 数据汇总表 → JSON 标准数据 → Word 发言材料
```

---

## 2. 快速开始

### 2.1 系统要求

- Python 3.10+
- Windows/macOS/Linux

### 2.2 安装步骤

```bash
# 1. 进入项目目录
cd production_operation

# 2. 安装依赖
pip install -r requirements.txt
```

### 2.3 一键生成报告

```bash
# 最简单的使用方式：一条命令完成全流程
python scripts/run_pipeline.py -i "files/数据汇总表.xlsx" -y 2026 -w 21

# 输出：
# - archive/2026/week21/2026_week21.json (JSON 数据)
# - archive/2026/week21/周例会营销发言材料.docx (Word 报告)
# - data/charts/*.png (图表文件)
```

---

## 3. 详细使用说明

### 3.1 数据采集（仅采集）

```bash
# 从 Excel 提取数据到 JSON
python scripts/extract_data.py -i "Excel文件.xlsx" -o "输出.json"

# 参数说明：
# -i, --input  : Excel 文件路径（必需）
# -o, --output : JSON 输出路径（必需）
# -y, --year   : 年份（可选，自动从文件名提取）
# -w, --week   : 周数（可选，自动从文件名提取）
# -s, --sheets : 指定 Sheet 名称（可选）
# -v, --validate : 校验数据（可选）
# -c, --clean    : 清洗数据（可选）
```

**示例**：

```bash
# 基本采集
python scripts/extract_data.py -i "files/2026年第21周周数据汇总表.xlsx" -o "data/processed/2026_week21.json"

# 采集并校验
python scripts/extract_data.py -i "files/汇总表.xlsx" -o "output.json" -v -c
```

### 3.2 数据验证

```bash
# 校验 JSON 数据是否符合 Schema
python scripts/validate_data.py -j "JSON文件.json"

# 参数说明：
# -j, --json   : JSON 文件路径（必需）
# -s, --schema : Schema 文件路径（可选，默认使用内置 Schema）
# -v, --verbose : 详细输出（可选）
```

**示例**：

```bash
python scripts/validate_data.py -j "data/processed/2026_week21.json" -v
```

### 3.3 报告生成

```bash
# 从 JSON 生成 Word 报告
python scripts/generate_report.py -j "JSON文件.json"

# 参数说明：
# -j, --json    : JSON 数据文件（必需）
# -o, --output  : 输出文件名（可选）
# -y, --year    : 年份（可选）
# -w, --week    : 周数（可选）
# -c, --charts  : 生成图表（可选）
```

**示例**：

```bash
# 生成报告（含图表）
python scripts/generate_report.py -j "data/processed/2026_week21.json" -c

# 指定输出名称
python scripts/generate_report.py -j "data.json" -o "第21周发言材料.docx"
```

### 3.4 完整流程

```bash
# Excel → JSON → Word 一条命令完成
python scripts/run_pipeline.py -i "Excel文件.xlsx" -y 年份 -w 周数

# 参数说明：
# -i, --input     : Excel 文件路径（必需）
# -y, --year      : 年份（必需）
# -w, --week      : 周数（必需）
# -o, --output-dir: 输出目录（可选，默认 archive）
# -v, --validate  : 校验数据（默认启用）
# -c, --clean     : 清洗数据（默认启用）
# --charts        : 生成图表（默认启用）
# -q, --quiet     : 静默模式（可选）
```

**示例**：

```bash
# 标准流程
python scripts/run_pipeline.py -i "files/2026年第21周周数据汇总表.xlsx" -y 2026 -w 21

# 静默模式（无输出）
python scripts/run_pipeline.py -i "汇总表.xlsx" -y 2026 -w 21 -q
```

---

## 4. 数据格式说明

### 4.1 Excel 输入要求

**支持的 Excel 格式**：
- 文件格式：.xlsx（Excel 2007+）
- Sheet 名称：包含"汇总表"、"分析报表"等关键词

**数据识别方式**：
系统通过**语义定位**识别数据，而非固定位置：
- 组织名称：识别"长江电力"、"三峡能源"等
- 能源类型：识别"水电"、"风电"、"光伏"等
- 指标名称：识别"电量"、"电价"、"电费"等

**支持的变体**：
- 组织简称：长电 → 长江电力
- 能源同义词：水力发电 → 水电
- 指标同义词：上网电量 → 电量

### 4.2 JSON 数据结构

生成的 JSON 数据包含：

```json
{
  "meta": {
    "year": 2026,
    "week": 21,
    "start_date": "2026-05-18",
    "end_date": "2026-05-24"
  },
  "organizations": {
    "长江电力": {
      "metrics": {
        "合计": {
          "电量": {"value": 550544.26},
          "电价": {"value": 0.268},
          "电费": {"value": 147525.88}
        },
        "水电": {...}
      }
    }
  },
  "validation_report": {
    "status": "pass",
    "coverage": 100
  }
}
```

### 4.3 Word 报告结构

生成的 Word 报告包含：

1. **标题**: YYYY年第XX周生产情况
2. **一、上周销售情况**
   - 电量概述
   - 各组织上网电量统计表
   - 各组织详情段落
3. **二、外部信息**
   - 市场价格
   - 政策动态
4. **三、本周重点工作安排**

---

## 5. 常见问题

### 5.1 数据采集问题

**Q: 组织未被识别**

A: 检查组织名称是否在词典中：
- 查看 `data/dictionaries/organizations.json`
- 添加新组织到词典
- 或使用同义词映射

**Q: 数据覆盖率低于 95%**

A: 原因可能是：
- Excel 表头格式不标准
- 部分数据缺失
- Sheet 名称未被识别

解决方案：
```bash
# 查看详细错误
python scripts/extract_data.py -i "Excel.xlsx" -o "out.json" -v

# 手动指定 Sheet
python scripts/extract_data.py -i "Excel.xlsx" -o "out.json" -s "汇总表" "明细表"
```

### 5.2 报告生成问题

**Q: 报告模板缺失**

A: 系统会自动创建简单模板。如需自定义：
- 修改 `data/templates/report_template.docx`
- 使用 Jinja2 标签：`{{year}}`, `{% for org in organizations %}`

**Q: 中文显示乱码**

A: 确保文件编码为 UTF-8：
- Excel 文件：保存为标准 xlsx 格式
- JSON 文件：使用 UTF-8 编码

### 5.3 运行环境问题

**Q: 模块未找到**

A: 安装依赖：
```bash
pip install -r requirements.txt
```

**Q: Python 版本不兼容**

A: 需要 Python 3.10 或更高版本：
```bash
python --version  # 检查版本
```

---

## 6. 高级用法

### 6.1 自定义实体词典

编辑 `data/dictionaries/organizations.json`：

```json
{
  "新组织": {
    "id": "org_xxx",
    "name": "新组织",
    "full_name": "新组织全称",
    "category": "power_generation",
    "region": "domestic"
  }
}
```

编辑 `data/dictionaries/synonyms.json`：

```json
{
  "organizations": {
    "新简称": "新组织"
  }
}
```

### 6.2 批量处理

```python
# 批量处理多周数据
from src.collector.excel_collector import ExcelCollector
from src.generator.report_generator import ReportGenerator

files = [
    "files/2026年第20周.xlsx",
    "files/2026年第21周.xlsx",
    "files/2026年第22周.xlsx"
]

for i, file in enumerate(files):
    week = 20 + i
    collector = ExcelCollector()
    data, _ = collector.collect(file, year=2026, week=week)
    
    generator = ReportGenerator()
    generator.generate_report(data, year=2026, week=week)
```

### 6.3 仅生成文本内容

```python
from src.generator.text_generator import TextGenerator

tg = TextGenerator()
text = tg.generate_full_report_text(data)
print(text)  # 输出纯文本报告
```

---

## 7. 输出文件位置

| 文件类型 | 默认位置 |
|---------|---------|
| JSON 数据 | `data/processed/YYYY_weekXX.json` |
| Word 报告 | `archive/YYYY/weekXX/*.docx` |
| 图表文件 | `data/charts/*.png` |
| 归档文件 | `archive/YYYY/weekXX/` |

---

## 8. 技术支持

如遇问题：

1. 查看 `docs/design/` 目录下的设计文档
2. 查看 `docs/analysis/data_resilience_strategy.md` 了解数据弹性策略
3. 查看 CLAUDE.md 了解开发指南

---

## 附录：命令速查表

| 操作 | 命令 |
|-----|------|
| 一键流程 | `python scripts/run_pipeline.py -i Excel -y 年 -w 周` |
| 仅采集 | `python scripts/extract_data.py -i Excel -o JSON` |
| 仅校验 | `python scripts/validate_data.py -j JSON` |
| 仅生成 | `python scripts/generate_report.py -j JSON` |

---

**文档版本**: v1.0
**更新日期**: 2026-06-04