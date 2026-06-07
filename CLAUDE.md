# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

周例会营销发言材料自动化生成项目。

**核心目标**: Excel 数据汇总表 → JSON 标准化 → Word 营销发言材料

**技术路径**: 语义定位采集 + 实体词典匹配 + 模板填充生成

---

## Quick Commands

```bash
# 完整流程
python scripts/run_pipeline.py --week 21 --year 2026

# 仅数据采集
python scripts/extract_data.py --input data/raw/2026/week21/汇总表.xlsx

# 仅数据验证
python scripts/validate_data.py --json data/processed/2026_week21.json

# 仅报告生成
python scripts/generate_report.py --json data/processed/2026_week21.json

# 运行测试
pytest tests/ -v --cov=src

# 安装依赖
pip install -r requirements.txt
```

---

## Project Structure

```
production_operation/
├── data/                          # 数据层
│   ├── schema/                    # JSON Schema 定义
│   │   ├── weekly_data.schema.json  # 主 Schema
│   │   └── example_data.json       # 示例数据
│   ├── dictionaries/              # 实体词典
│   │   ├── organizations.json     # 组织词典
│   │   ├── energy_types.json      # 能源类型
│   │   ├── metrics.json           # 指标词典
│   │   └ synonyms.json           # 同义词映射
│   ├── templates/                 # 模板
│   │   └── report_template.docx   # Word 模板
│   ├── raw/                       # 原始 Excel
│   │   └── 2026/week21/
│   └── processed/                 # 处理后 JSON
│       └── 2026_week21.json
│
├── src/                           # 源代码
│   ├── collector/                 # 数据采集
│   │   ├── excel_collector.py     # Excel 采集器
│   │   └ semantic_parser.py       # 语义定位解析
│   ├── validator/                 # 数据验证
│   │   ├── schema_validator.py    # Schema 校验
│   │   ├── data_cleaner.py        # 数据清洗
│   ├── storage/                   # 数据存储
│   │   └ json_store.py           # JSON 存储
│   ├── generator/                 # 报告生成
│   │   ├── report_generator.py    # 报告生成器
│   │   ├── chart_builder.py       # 图表生成
│   │   └ text_generator.py       # 文本生成
│   └ utils/                       # 工具
│       └ entity_resolver.py      # 实体解析
│
├── scripts/                       # 脚本入口
│   ├── run_pipeline.py            # 完整流程
│   ├── extract_data.py            # 数据采集
│   ├── validate_data.py           # 数据验证
│   ├── generate_report.py         # 报告生成
│   └ archive.py                   # 归档整理
│
├── tests/                         # 测试
│   ├── test_collector.py
│   ├── test_validator.py
│   ├── test_generator.py
│   └ fixtures/                    # 测试数据
│
├── docs/                          # 文档
│   ├── design/                    # 设计文档
│   │   ├── project_plan.md        # 项目计划
│   │   ├── implementation_plan.md # 实施计划
│   │   └ data_definition.md       # 口径定义
│   ├── analysis/                  # 分析文档
│   │   └ data_resilience_strategy.md
│   └ user_guide/                  # 用户指南
│   └ api/                         # API 文档
│
├── archive/                       # 历史归档
│   └ 2026/week21/
│       ├── data.json
│       ├── report.docx
│       └ excel_export.xlsx
│
├── files/                         # 原始文档存档
├── requirements.txt               # 依赖
├── README.md                      # 项目说明
└── CLAUDE.md                      # Claude 指引（本文件）
```

---

## Architecture Overview

### 5-Layer Architecture

```
Layer 0: 数据源层
├── Excel 模板（标准化）
└── 数据采集器

Layer 1: 数据标准化层
├── JSON Schema
├── 数据验证
├── 数据清洗
└── 同义词映射

Layer 2: 数据存储层
├── JSON 文件（按周）
├── 历史数据累积
└── 实体词典

Layer 3: 报告生成层
├── 模板引擎（docxtpl）
├── Word 报告生成
├── 图表自动生成
└── Excel/PDF 导出

Layer 4: 智能能力层（可选）
├── LLM 业务问答
├── 异常检测
├── 趋势预测
├── 业务洞察
```

---

## Key Design Patterns

### Semantic Positioning

**原则**: 找实体名称，不找固定位置

```python
# 语义定位示例
class SemanticParser:
    def find_org_row(self, ws) -> Dict[str, int]:
        """找组织名所在行"""
        for row_idx, row in enumerate(ws.iter_rows()):
            for cell in row:
                for org_name in ORG_LIST:
                    if org_name in str(cell.value):
                        org_rows[org_name] = row_idx
        return org_rows
```

### Graph-Compatible Schema

JSON Schema 预留图谱字段：

```json
{
  "长江电力": {
    "id": "org_001",        // 图谱 ID
    "parent": "三峡集团",   // 层级关系
    "category": "power_generation"  // 分类
  }
}
```

### Fault Tolerance Pattern

部分失败不阻塞整体：

```python
def collect_all_sheets(file_path):
    errors = []
    for sheet in SHEET_LIST:
        try:
            results[sheet] = parse_sheet(sheet)
        except Exception as e:
            errors.append({"sheet": sheet, "error": str(e)})
            results[sheet] = None  # 继续其他 Sheet
    return results, errors
```

---

## Entity Dictionary Usage

### organizations.json

组织词典，包含：
- id: 图谱预留 ID
- name: 简称
- full_name: 全称
- parent: 上级组织
- category: 业务类别
- region: 区域

### energy_types.json

能源类型词典：
- 水电、风电、光伏、火电、合计
- 包含同义词映射

### metrics.json

指标词典：
- 电量、电价、电费、同比、环比
- 包含单位、聚合方式

### synonyms.json

同义词映射：
- 组织同义词
- 能源同义词
- 指标同义词

---

## Data Definition

参见 `docs/design/data_definition.md`：

- 组织机构口径
- 能源类型口径
- 指标计算规则
- 异常数据处理
- 数据源追溯

---

## Development Workflow

1. **数据采集优先**: 语义定位 + 实体词典匹配
2. **验证闭环**: Schema 校验 + 业务校验 + coverage 计算
3. **容错设计**: 部分失败记录，整体继续
4. **图谱预留**: Schema 包含 id/parent/category 字段

---

## Test Requirements

- 单元测试覆盖率 > 80%
- 集成测试：端到端流程
- 测试 fixtures：使用示例数据

---

## Key Files for Context

| 文件 | 用途 |
|-----|------|
| `docs/design/project_plan.md` | 项目整体计划 |
| `docs/design/implementation_plan.md` | 分阶段实施计划 |
| `docs/design/data_definition.md` | 数据口径定义 |
| `docs/analysis/data_resilience_strategy.md` | 数据弹性方案分析 |
| `data/schema/weekly_data.schema.json` | JSON Schema 定义 |
| `data/dictionaries/*.json` | 实体词典 |

---

## Phase Progress

| Phase | 状态 | 完成度 | 内容 |
|-------|------|-------|------|
| Phase 0 | ✅ 完成 | 100% | 项目初始化：目录、Schema、词典 |
| Phase 1 | ✅ 核心 | 90% | 数据采集：采集器、解析器、校验器 |
| Phase 2 | ✅ 完成 | 100% | 报告生成：图表、文本、Word模板 |
| Phase 3 | ✅ 完成 | 100% | 用户文档：指南、API、验收 |
| **Phase 1R** | ✅ 完成 | 95% | 数据源切换：综合分析报表采集器、CELL_MAP |
| **Phase 2R** | ✅ 完成 | 85% | 模板重建：3表格、分析文本生成、完整结构 |
| **v2.0 Analyzer 层** | ✅ **完成** | **100%** | **4 Analyzer + 139 单元测试** |
| **v2.0 Streamlit UI** | ✅ **完成** | **100%** | **5 页面 + 13 组件 + 集成测试** |
| **v2.5 docxtpl** | ✅ **完成** | **100%** | **docxtpl + LLM 润色 + 100% 自动化** |
| **v3.0 HITL** | ✅ **完成** | **100%** | **人机协同驾驶舱：7 步交互 + 反馈环（2914 行 + 58 测试）** |
| **v3.1 路由** | ✅ **完成** | **100%** | **侧边栏 v2/v3 分组 + 数据桥 + URL 深链（1100 行 + 39 测试）** |

## v2.0 架构新增内容

### Analyzer 层（src/analyzer/）
- `base.py` - BaseAnalyzer 抽象类 + AnalysisResult 数据类
- `domestic.py` - 段 1-2（国内电量电价）— 35 测试
- `international.py` - 段 3-4（国际电价同比环比）— 38 测试
- `market_trading.py` - 段 5-7（水/新/火市场化）— 36 测试
- `environmental.py` - 段 8（绿证+CCER）— 30 测试

### Streamlit 应用（streamlit_app/）
- `app.py` - 主入口（文件上传 + 4 Analyzer 工厂 + session_state）
- `utils/data_loader.py` - 数据加载器
- `components/` - 13 个复用组件（KPI/图表/表格/故事/通用渲染）
- `pages/1-4` - 4 维度分析页面
- `pages/5_📄_报告生成.py` - Markdown 报告导出

### 测试
- `tests/test_analyzer/test_*.py` - 139 单元测试
- `tests/fixtures/*.json` - 4 维度 fixture + 1 合并 fixture
- `examples/streamlit_*.py` - 5 集成测试 + AppTest 验证

### 设计文档
- `docs/design/business-map-master.md` - 业务图谱（5 总图）
- `docs/design/report-generator-v2-architecture.md` - v2 架构设计
- `docs/user_guide/weekly-report-beginner-guide.md` - 教学文档 v1.2
- `docs/analysis/domestic-price-analysis-framework.md` - 工程框架 v1.2

### 运行方式
```bash
# CLI
PYTHONPATH=. python scripts/run_pipeline.py --week 21 --year 2026

# Web UI
PYTHONPATH=. streamlit run streamlit_app/app.py
```

## Quick Commands (Updated)

```bash
# 推荐：使用综合分析报表（数据最完整）
PYTHONPATH=. python scripts/run_pipeline.py --analysis-input "files/2026年第21周周数据综合分析报表.xlsx" --year 2026 --week 21

# 仅数据采集（新模式）
PYTHONPATH=. python -m src.collector.analysis_collector --input "files/综合分析报表.xlsx" --output data/processed/test.json --year 2026 --week 21

# 兼容旧模式
PYTHONPATH=. python scripts/run_pipeline.py --input "data/raw/2026/week21/汇总表.xlsx" --year 2026 --week 21
```

---

## Change Log

| 日期 | 变更 |
|-----|------|
| 2026-06-04 | Phase 0-3 完成，MVP 验收通过 |