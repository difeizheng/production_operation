# Weekly Report Automation

周例会营销发言材料自动化生成项目。

## 核心功能

| 功能 | 说明 |
|-----|------|
| 数据采集 | 从 Excel 数据汇总表提取数据（语义定位） |
| 数据标准化 | 转换为标准 JSON 格式 |
| 数据验证 | Schema 校验 + 业务规则校验 |
| 报告生成 | 自动生成 Word 营销发言材料 |
| 图表生成 | 自动生成数据可视化图表 |

## 处理流程

```
Excel 数据汇总表 → JSON 标准数据 → Word 发言材料
       ↓               ↓              ↓
    语义定位        Schema校验      模板填充
```

## 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 一键生成报告

```bash
python scripts/run_pipeline.py -i "Excel文件.xlsx" -y 2026 -w 21
```

### 分步执行

```bash
# 1. 数据采集
python scripts/extract_data.py -i "Excel.xlsx" -o "data.json"

# 2. 数据验证
python scripts/validate_data.py -j "data.json"

# 3. 报告生成
python scripts/generate_report.py -j "data.json"
```

## 项目结构

```
production_operation/
├── data/                          # 数据层
│   ├── schema/                    # JSON Schema 定义
│   │   ├── weekly_data.schema.json
│   │   └── example_data.json
│   ├── dictionaries/              # 实体词典
│   │   ├── organizations.json     # 组织词典
│   │   ├── energy_types.json      # 能源类型
│   │   ├── metrics.json           # 指标词典
│   │   └ synonyms.json           # 同义词映射
│   ├── templates/                 # Word 模板
│   ├── charts/                    # 生成的图表
│   ├── raw/                       # 原始 Excel
│   └── processed/                 # 处理后 JSON
│
├── src/                           # 源代码
│   ├── collector/                 # 数据采集
│   │   ├── excel_collector.py
│   │   └ semantic_parser.py
│   ├── validator/                 # 数据验证
│   │   ├── schema_validator.py
│   │   └ data_cleaner.py
│   ├── storage/                   # 数据存储
│   │   └ json_store.py
│   ├── generator/                 # 报告生成
│   │   ├── report_generator.py
│   │   ├── chart_builder.py
│   │   └ text_generator.py
│   └ utils/                       # 工具
│       └ entity_resolver.py
│
├── scripts/                       # 脚本入口
│   ├── run_pipeline.py            # 完整流程
│   ├── extract_data.py            # 数据采集
│   ├── validate_data.py           # 数据验证
│   └ generate_report.py           # 报告生成
│
├── tests/                         # 测试
│   ├── test_collector.py
│   ├── test_validator.py
│   ├── test_generator.py
│
├── docs/                          # 文档
│   ├── design/                    # 设计文档
│   │   ├── project_plan.md
│   │   ├── implementation_plan.md
│   │   ├── data_definition.md
│   │   ├── phase0_report.md
│   │   ├── phase1_report.md
│   │   ├── phase2_report.md
│   ├── analysis/                  # 分析文档
│   │   └ data_resilience_strategy.md
│   ├── user_guide/                # 用户指南
│   │   └ user_guide.md
│   └ api/                         # API 文档
│       └ api_reference.md
│
├── archive/                       # 历史归档
│   └ 2026/week21/
│       ├── *.json
│       ├── *.docx
│       └── *.png
│
├── files/                         # 原始文档存档
├── requirements.txt
├── README.md
└── CLAUDE.md
```

## 核心设计

### 语义定位

通过实体名称定位数据，不依赖固定位置：

```python
# 找组织名所在行（不依赖行号）
org_rows = parser.find_org_rows(ws)  # {"长江电力": 5}

# 找能源类型所在列（不依赖列号）
col_mapping = parser.build_column_mapping(ws)  # {("水电", "电量"): 3}
```

### 容错机制

部分失败不影响整体流程：

```python
# Sheet 失败 → 记录错误 → 继续其他 Sheet
# 组织失败 → 记录错误 → 继续其他组织
# 单元格缺失 → 值设为 null → 不中断流程
```

### 数据追溯

每个数据记录原始位置：

```python
{
    "value": 550544.26,
    "source": {
        "file": "汇总表.xlsx",
        "sheet": "Sheet1",
        "row": 5,
        "col": 3,
        "cell": "C5"
    }
}
```

## 文档

| 文档 | 说明 |
|-----|------|
| [用户指南](docs/user_guide/user_guide.md) | 快速上手指南 |
| [API 参考](docs/api/api_reference.md) | Python API 文档 |
| [项目计划](docs/design/project_plan.md) | 整体项目计划 |
| [实施计划](docs/design/implementation_plan.md) | 分阶段实施 |
| [数据口径](docs/design/data_definition.md) | 数据定义文档 |
| [弹性方案](docs/analysis/data_resilience_strategy.md) | 数据弹性分析 |

## 开发进度

| Phase | 状态 | 完成度 |
|-------|------|-------|
| Phase 0 | ✅ 完成 | 100% |
| Phase 1 | ✅ 核心完成 | 90% |
| Phase 2 | ✅ 完成 | 100% |
| Phase 3 | ✅ 完成 | 100% |

## 技术栈

| 技术 | 用途 |
|-----|------|
| openpyxl | Excel 读取 |
| python-docx | Word 生成 |
| docxtpl | Word 模板引擎 |
| jsonschema | Schema 校验 |
| matplotlib | 图表生成 |
| pydantic | 数据模型 |

## 许可

内部项目，仅供公司内部使用。

---

**项目状态**: MVP 完成，可用

**最后更新**: 2026-06-04