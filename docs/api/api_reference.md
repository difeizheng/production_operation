# API 参考文档

> 本文档描述周报自动化系统的 Python API，供开发者参考。

---

## 1. 数据采集模块 (src.collector)

### 1.1 ExcelCollector

**位置**: `src.collector.excel_collector`

**用途**: 从 Excel 文件采集数据

#### 初始化

```python
from src.collector.excel_collector import ExcelCollector

collector = ExcelCollector(dict_dir="data/dictionaries")
```

#### collect()

采集 Excel 数据

```python
result, errors = collector.collect(
    file_path="Excel文件.xlsx",
    sheets=["汇总表"],  # 可选
    year=2026,         # 可选
    week=21            # 可选
)
```

**参数**:
- `file_path` (str): Excel 文件路径
- `sheets` (List[str], optional): Sheet 名称列表
- `year` (int, optional): 年份
- `week` (int, optional): 周数

**返回**:
- `result` (Dict): 采集结果，包含 organizations、meta、validation_report
- `errors` (List[Dict]): 错误列表，每项含 level、message、field

#### save_json()

保存结果到 JSON

```python
output_path = collector.save_json(result, "output.json", schema_version="1.0.0")
```

#### collect_batch()

批量采集

```python
result, errors = collector.collect_batch(
    file_paths=["file1.xlsx", "file2.xlsx"],
    year=2026,
    week=21
)
```

---

### 1.2 SemanticParser

**位置**: `src.collector.semantic_parser`

**用途**: 语义定位解析器

#### 初始化

```python
from src.collector.semantic_parser import SemanticParser
from src.utils.entity_resolver import EntityResolver

parser = SemanticParser(EntityResolver())
```

#### find_header_row()

找到表头行

```python
header_row = parser.find_header_row(ws, max_rows=20)
# 返回: int (0-indexed) 或 None
```

#### find_org_rows()

找到组织行

```python
org_rows = parser.find_org_rows(ws, start_row=0)
# 返回: Dict[str, int] {组织名: 行号}
```

#### parse_sheet()

解析整个 Sheet

```python
result, errors = parser.parse_sheet(ws, sheet_name="汇总表")
# 返回: (数据字典, 错误列表)
```

---

## 2. 数据验证模块 (src.validator)

### 2.1 SchemaValidator

**位置**: `src.validator.schema_validator`

**用途**: JSON Schema 校验

#### 初始化

```python
from src.validator.schema_validator import SchemaValidator

validator = SchemaValidator("data/schema/weekly_data.schema.json")
```

#### validate()

Schema 校验

```python
is_valid, errors = validator.validate(data)
# 返回: (是否通过, 错误列表)
```

#### validate_structure()

结构快速检查

```python
structure = validator.validate_structure(data)
# 返回: {has_meta, has_organizations, org_count, missing_fields}
```

#### validate_business_rules()

业务规则校验

```python
errors = validator.validate_business_rules(data)
# 检查: 电费一致性等
```

#### full_validate()

完整校验

```python
result = validator.full_validate(data)
# 返回: {status, schema_valid, structure, errors, error_count, warn_count}
```

---

### 2.2 DataCleaner

**位置**: `src.validator.data_cleaner`

**用途**: 数据清洗

#### 初始化

```python
from src.validator.data_cleaner import DataCleaner

cleaner = DataCleaner()
```

#### clean_value()

清洗单个数值

```python
cleaned_value, report = cleaner.clean_value(
    value=550544.26,
    metric="电量",
    source={"row": 5, "col": 3}
)
# 返回: (清洗后值, 清洗报告)
```

#### clean_organization_data()

清洗组织数据

```python
cleaned_data, reports = cleaner.clean_organization_data(org_data, org_name)
```

#### clean_full_data()

清洗完整数据集

```python
cleaned_data, all_reports = cleaner.clean_full_data(data)
```

#### fill_missing_values()

填充缺失值

```python
filled_data, reports = cleaner.fill_missing_values(data, strategy="null")
# strategy: "null", "zero", "mean"
```

---

## 3. 数据存储模块 (src.storage)

### 3.1 JSONStore

**位置**: `src.storage.json_store`

**用途**: JSON 数据存储管理

#### 初始化

```python
from src.storage.json_store import JSONStore

store = JSONStore(base_dir="data/processed")
```

#### save()

保存数据

```python
path = store.save(data, year=2026, week=21, version="1")
# 返回: 文件路径
```

#### load()

加载数据

```python
data = store.load(year=2026, week=21)
# 返回: Dict 或 None
```

#### load_latest()

加载最新版本

```python
data = store.load_latest(year=2026, week=21)
```

#### list_weeks()

列出所有周数据

```python
weeks = store.list_weeks(year=2026)
# 返回: [{year, week, file, size, modified}]
```

#### get_history()

获取历史数据

```python
history = store.get_history(year=2026, week=21, count=4)
# 返回: 前N周数据列表
```

#### archive()

归档数据

```python
archive_path = store.archive(year=2026, week=21, archive_dir="archive")
```

---

## 4. 报告生成模块 (src.generator)

### 4.1 ChartBuilder

**位置**: `src.generator.chart_builder`

**用途**: 图表生成

#### 初始化

```python
from src.generator.chart_builder import ChartBuilder

builder = ChartBuilder(output_dir="data/charts")
```

#### bar_chart()

生成柱状图

```python
path = builder.bar_chart(
    data={"长江电力": 550544, "三峡能源": 125680},
    title="电量对比",
    ylabel="万千瓦时",
    horizontal=False
)
```

#### pie_chart()

生成饼图

```python
path = builder.pie_chart(
    data={"水电": 550544, "风电": 98500},
    title="能源占比"
)
```

#### line_chart()

生成折线图

```python
path = builder.line_chart(
    data=[{"week": 20, "value": 100, "label": "电量"}],
    title="趋势图"
)
```

#### generate_weekly_charts()

生成周报图表

```python
charts = builder.generate_weekly_charts(week_data)
# 返回: {"electricity_bar": "...", "energy_pie": "..."}
```

---

### 4.2 TextGenerator

**位置**: `src.generator.text_generator`

**用途**: 文本生成

#### 初始化

```python
from src.generator.text_generator import TextGenerator

generator = TextGenerator()
```

#### generate_header()

生成标题

```python
header = generator.generate_header(meta)
# 返回: "YYYY年第XX周生产情况..."
```

#### generate_electricity_summary()

生成电量概述

```python
summary = generator.generate_electricity_summary(data)
```

#### generate_organization_section()

生成组织段落

```python
texts = generator.generate_organization_section(org_name, org_data)
# 返回: List[str]
```

#### generate_full_report_text()

生成完整报告文本

```python
text = generator.generate_full_report_text(data)
```

#### generate_summary_table()

生成汇总表格数据

```python
rows = generator.generate_summary_table(data)
# 返回: [{组织, 电量, 电价, 电费}]
```

---

### 4.3 ReportGenerator

**位置**: `src.generator.report_generator`

**用途**: Word 报告生成

#### 初始化

```python
from src.generator.report_generator import ReportGenerator

generator = ReportGenerator(
    template_path="data/templates/report_template.docx",
    output_dir="archive"
)
```

#### generate_report()

生成报告

```python
path = generator.generate_report(
    data=data,
    output_filename="报告.docx",  # 可选
    year=2026,                     # 可选
    week=21                        # 可选
)
```

#### generate_with_charts()

生成报告（含图表）

```python
result = generator.generate_with_charts(data, year=2026, week=21)
# 返回: {"report_path": "...", "charts": {...}}
```

---

## 5. 工具模块 (src.utils)

### 5.1 EntityResolver

**位置**: `src.utils.entity_resolver`

**用途**: 实体名称解析

#### 初始化

```python
from src.utils.entity_resolver import EntityResolver

resolver = EntityResolver(dict_dir="data/dictionaries")
```

#### resolve_organization()

解析组织名称

```python
std_name, org_info = resolver.resolve_organization("长电")
# 返回: ("长江电力", {...}) 或 (None, None)
```

#### resolve_energy_type()

解析能源类型

```python
std_name, energy_info = resolver.resolve_energy_type("水力发电")
# 返回: ("水电", {...})
```

#### resolve_metric()

解析指标名称

```python
std_name, metric_info = resolver.resolve_metric("上网电量")
# 返回: ("电量", {...})
```

#### resolve_cell_header()

解析表头单元格

```python
result = resolver.resolve_cell_header("水电电量(万千瓦时)")
# 返回: {"energy_type": "水电", "metric": "电量", "unit": "万千瓦时"}
```

---

## 6. 数据结构

### 6.1 JSON 数据格式

```python
{
    "meta": {
        "year": int,
        "week": int,
        "start_date": str,
        "end_date": str,
        "extracted_at": str,
        "source_file": str
    },
    "organizations": {
        "组织名": {
            "id": str,
            "name": str,
            "full_name": str,
            "category": str,
            "region": str,
            "metrics": {
                "能源类型": {
                    "电量": {"value": float, "source": dict},
                    "电价": {"value": float},
                    "电费": {"value": float}
                }
            }
        }
    },
    "validation_report": {
        "status": str,  # "pass" | "warning" | "error"
        "errors": List[dict],
        "coverage": float
    }
}
```

### 6.2 错误格式

```python
{
    "level": str,  # "ERROR" | "WARN" | "INFO"
    "message": str,
    "field": str,  # 可选
    "sheet": str,  # 可选
    "cell": str    # 可选
}
```

---

## 7. 完整使用示例

```python
import json
from src.collector.excel_collector import ExcelCollector
from src.validator.schema_validator import SchemaValidator
from src.validator.data_cleaner import DataCleaner
from src.generator.report_generator import ReportGenerator

# 1. 采集数据
collector = ExcelCollector()
data, errors = collector.collect("Excel.xlsx", year=2026, week=21)

# 2. 校验数据
validator = SchemaValidator()
result = validator.full_validate(data)
print(f"校验状态: {result['status']}")

# 3. 清洗数据
cleaner = DataCleaner()
data, reports = cleaner.clean_full_data(data)

# 4. 生成报告
generator = ReportGenerator()
path = generator.generate_report(data, year=2026, week=21)
print(f"报告已生成: {path}")
```

---

**文档版本**: v1.0
**更新日期**: 2026-06-04