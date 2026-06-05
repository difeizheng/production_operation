# 周报自动化项目计划

> 项目代号：Weekly Report Automation
> 目标：从 Excel 数据源 → 标准化 JSON → 模板化周报生成
> 路线：Excel 模拟 API 起步，预留 API 迁移能力

---

## 核心目标

**第一目标**：按模板生成标准周例会营销发言材料
- 输入：Excel 数据汇总表
- 输出：Word 营销发言材料
- 路径：Excel → JSON → 模板填充 → Word

**延伸目标**（解锁智能能力）：
- LLM 业务问答
- 异常自动检测
- 趋势分析
- 业务洞察生成

---

## 架构设计

```
┌─────────────────────────────────────────────────────┐
│  Layer 0: 数据源层                                  │
│  - Excel 模板（标准化）                             │
│  - 数据采集器                                       │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│  Layer 1: 数据标准化层                              │
│  - JSON Schema                                      │
│  - 数据验证                                         │
│  - 数据清洗                                         │
│  - 同义词映射                                       │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│  Layer 2: 数据存储层                                │
│  - JSON 文件（按周）                                │
│  - 历史数据累积                                     │
│  - 实体词典（组织/能源/指标）                       │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│  Layer 3: 报告生成层                                │
│  - 模板引擎（docxtpl）                              │
│  - Word 报告生成                                    │
│  - 图表自动生成                                     │
│  - Excel/PDF 导出                                   │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│  Layer 4: 智能能力层（未来扩展）                     │
│  - LLM 业务问答                                     │
│  - 异常检测                                         │
│  - 趋势预测                                         │
│  - 业务洞察                                         │
└─────────────────────────────────────────────────────┘
```

---

## 项目结构

```
production_operation/
├── data/                          # 数据层
│   ├── schema/                    # JSON Schema 定义
│   │   ├── weekly_data.schema.json
│   │   └── report_template.schema.json
│   ├── dictionaries/              # 实体词典
│   │   ├── organizations.json
│   │   ├── energy_types.json
│   │   ├── metrics.json
│   │   └── synonyms.json
│   ├── templates/                 # 模板
│   │   ├── input_excel_template.xlsx
│   │   └── report_template.docx
│   ├── raw/                       # 原始 Excel
│   │   └── 2026/
│   │       └── week21/
│   │           └── 2026年第21周周数据汇总表.xlsx
│   └── processed/                 # 处理后 JSON
│       └── 2026_week21.json
│
├── src/                           # 源代码
│   ├── collector/                 # 数据采集
│   │   ├── __init__.py
│   │   ├── excel_collector.py
│   │   └── semantic_parser.py
│   ├── validator/                 # 数据验证
│   │   ├── __init__.py
│   │   ├── schema_validator.py
│   │   └── data_cleaner.py
│   ├── storage/                   # 数据存储
│   │   ├── __init__.py
│   │   └── json_store.py
│   ├── generator/                 # 报告生成
│   │   ├── __init__.py
│   │   ├── report_generator.py
│   │   ├── chart_builder.py
│   │   └── excel_exporter.py
│   └── utils/                     # 工具
│       ├── __init__.py
│       └── entity_resolver.py
│
├── scripts/                       # 脚本入口
│   ├── run_pipeline.py            # 完整流程
│   ├── extract_data.py            # 仅采集
│   ├── validate_data.py           # 仅验证
│   ├── generate_report.py         # 仅生成
│   └── archive.py                 # 归档整理
│
├── tests/                         # 测试
│   ├── test_collector.py
│   ├── test_validator.py
│   ├── test_generator.py
│   └── fixtures/                  # 测试数据
│
├── docs/                          # 文档
│   ├── analysis/                  # 分析文档
│   │   └── data_resilience_strategy.md
│   ├── design/                    # 设计文档
│   │   └── project_plan.md
│   ├── user_guide/                # 用户指南
│   └── api/                       # API 文档
│
├── archive/                       # 历史归档
│   └── 2026/
│       └── week21/
│           ├── data.json
│           ├── report.docx
│           └── excel_export.xlsx
│
├── requirements.txt               # 依赖
├── README.md                      # 项目说明
└── CLAUDE.md                      # Claude 指引
```

---

## 实施阶段

### Phase 1：数据采集与标准化（1 周）

**目标**：完成 Excel → JSON → 验证流程

**任务清单**：

| ID | 任务 | 产出 | 工时 |
|----|------|------|------|
| 1.1 | JSON Schema 设计 | `data/schema/weekly_data.schema.json` | 4h |
| 1.2 | 实体词典构建 | `data/dictionaries/*.json` | 4h |
| 1.3 | Excel 采集器实现 | `src/collector/excel_collector.py` | 8h |
| 1.4 | 语义解析器实现 | `src/collector/semantic_parser.py` | 8h |
| 1.5 | Schema 验证器 | `src/validator/schema_validator.py` | 4h |
| 1.6 | 数据清洗器 | `src/validator/data_cleaner.py` | 4h |
| 1.7 | 单元测试 | `tests/test_collector.py` 等 | 8h |
| 1.8 | 集成测试 | 端到端流程验证 | 4h |

**验收**：
- 能从 Excel 提取数据到 JSON
- Schema 校验通过
- 单元测试覆盖率 > 80%

---

### Phase 2：模板与报告生成（1 周）

**目标**：完成 JSON → 标准周报

**任务清单**：

| ID | 任务 | 产出 | 工时 |
|----|------|------|------|
| 2.1 | Word 模板设计 | `data/templates/report_template.docx` | 8h |
| 2.2 | 模板引擎集成（docxtpl） | `src/generator/report_generator.py` | 8h |
| 2.3 | 图表自动生成 | `src/generator/chart_builder.py` | 8h |
| 2.4 | Excel 导出器 | `src/generator/excel_exporter.py` | 4h |
| 2.5 | PDF 转换（可选） | `src/generator/pdf_converter.py` | 4h |
| 2.6 | 端到端测试 | `tests/test_generator.py` | 4h |
| 2.7 | 真实数据验证 | 用 21/22 周数据 | 4h |

**验收**：
- 能从 JSON 生成标准 Word 周报
- 报告质量接近人工
- 端到端流程跑通

---

### Phase 3：用户验证与优化（1 周）

**目标**：用真实数据验证、收集反馈

**任务清单**：

| ID | 任务 | 产出 | 工时 |
|----|------|------|------|
| 3.1 | 真实数据处理 | 处理 21/22 周完整数据 | 8h |
| 3.2 | 报告质量评估 | 与人工报告对比 | 4h |
| 3.3 | 用户反馈收集 | 反馈文档 | 4h |
| 3.4 | 模板迭代优化 | 优化后的模板 | 8h |
| 3.5 | 文档编写 | 用户指南 | 4h |
| 3.6 | 部署脚本 | `scripts/run_pipeline.py` | 4h |

**验收**：
- 真实数据无错
- 用户验收通过
- 文档完整

---

### Phase 4：智能能力 PoC（2 周，可选）

**目标**：验证 LLM 与智能能力价值

**任务清单**：

| ID | 任务 | 产出 | 工时 |
|----|------|------|------|
| 4.1 | LLM 问答 PoC | `src/llm/qa_engine.py` | 16h |
| 4.2 | 异常检测算法 | `src/analysis/anomaly_detector.py` | 12h |
| 4.3 | 趋势分析 | `src/analysis/trend_analyzer.py` | 12h |
| 4.4 | 业务洞察生成 | `src/analysis/insight_generator.py` | 12h |
| 4.5 | 智能能力文档 | 能力说明 | 4h |

**验收**：
- LLM 问答准确率 > 80%
- 异常检测发现真实异常
- 趋势分析有参考价值

---

## 关键技术选型

| 技术 | 用途 | 选择理由 |
|-----|------|---------|
| openpyxl | Excel 读取 | 已熟悉、功能强 |
| python-docx | Word 生成 | 主流选择 |
| docxtpl | Word 模板 | 用户友好、模板方式 |
| Jinja2 | 文本模板 | 通用模板引擎 |
| jsonschema | Schema 验证 | 标准方案 |
| pydantic | 数据模型 | Pythonic、类型提示 |
| pandas | 数据处理 | 灵活强大 |
| matplotlib | 图表生成 | 标准方案 |
| Claude API | LLM 能力 | 用户已有、效果好 |

---

## 数据 Schema 设计示例

### JSON Schema（核心字段）

```json
{
  "meta": {
    "year": "integer",
    "week": "integer",
    "start_date": "date",
    "end_date": "date",
    "extracted_at": "datetime",
    "source_file": "string"
  },
  "organizations": {
    "type": "object",
    "pattern": "实体匹配",
    "properties": {
      "电力销售": {
        "国内": {
          "电量": {
            "总量": "number",
            "水电": "number",
            "风电": "number",
            "光伏": "number",
            "火电": "number"
          },
          "电价": {
            "总量": "number",
            "水电": "number",
            "风电": "number",
            "光伏": "number",
            "火电": "number"
          },
          "电费": {...},
          "同比": {...},
          "环比": {...}
        },
        "国际": {...}
      },
      "市场化交易": {...},
      "绿证CCER": {...}
    }
  }
}
```

---

## 实体词典设计

```json
// organizations.json
{
  "长江电力": {
    "full_name": "中国长江电力股份有限公司",
    "type": "domestic"
  },
  "三峡能源": {
    "full_name": "中国三峡新能源（集团）股份有限公司",
    "type": "domestic"
  },
  "湖北能源": {
    "full_name": "湖北能源集团股份有限公司",
    "type": "domestic"
  }
}

// energy_types.json
{
  "水电": {"code": "hydro"},
  "风电": {"code": "wind"},
  "光伏": {"code": "solar"},
  "火电": {"code": "thermal"}
}

// metrics.json
{
  "电量": {"unit": "万千瓦时", "category": "quantity"},
  "电价": {"unit": "元/千瓦时", "category": "price"},
  "电费": {"unit": "万元", "category": "revenue"}
}

// synonyms.json
{
  "水力发电": "水电",
  "上网电量": "电量",
  "平均电价": "电价",
  "发电收入": "电费"
}
```

---

## 报告模板设计

### Word 模板结构（docxtpl 标签）

```
{{meta.year}}年第{{meta.week}}周生产情况（{{meta.start_date}}-{{meta.end_date}}）

一、上周销售情况
（一）电量销售情况
上周，集团公司合计上网电量{{国内.合计电量}}亿千瓦时...

[Word 表格：分组织电量统计]
{%tr for org in organizations %}
{{org.name}}|{{org.电量.总量}}|{{org.电价.总量}}
{%tr endfor}

二、外部信息
...
```

---

## 风险评估与缓解

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| Excel 结构变化 | 数据提取错误 | 语义定位 + Schema 校验 + 同义词映射 |
| 模板与数据不匹配 | 报告生成失败 | 模板标签与 Schema 字段对应 + 测试 |
| 报告质量不如人工 | 用户不接受 | 对比人工报告 + 迭代优化 + 人工审核机制 |
| API 迁移困难 | 后期重构 | 设计阶段预留 API 友好性 + Schema 与 API 兼容 |
| LLM 成本 | 运营成本高 | 限制使用场景 + 缓存 + 本地化方案 |
| 数据敏感 | 安全隐患 | 本地化部署 + 权限控制 + 加密存储 |

---

## 验收标准

### MVP（Phase 1+2）验收

- [ ] Excel 数据提取成功率 > 95%
- [ ] JSON Schema 校验通过率 100%
- [ ] 单元测试覆盖率 > 80%
- [ ] Word 报告生成成功率 > 95%
- [ ] 报告内容完整度 > 90%（对比人工报告）
- [ ] 端到端流程跑通（一条命令完成）
- [ ] 文档完整（README、用户指南）

### 完整方案（Phase 3+4）验收

- [ ] 真实数据无错
- [ ] 用户验收通过
- [ ] 智能能力 PoC 通过
- [ ] 部署脚本完善
- [ ] 监控与日志齐备

---

## 时间规划

```
Week 1: Phase 1（数据采集与标准化）
Week 2: Phase 2（模板与报告生成）
Week 3: Phase 3（用户验证与优化）
Week 4-5: Phase 4（智能能力 PoC，可选）
```

**MVP 时间**：3 周
**完整方案时间**：5 周

---

## 关键决策点

### 决策 1：是否引入 LLM？

**当前建议**：Phase 4 再考虑，先把 MVP 做好
- LLM 有 API 成本
- 准确率需要验证
- 数据敏感性问题

### 决策 2：是否上数据库？

**当前建议**：先 JSON 文件，数据量大再考虑 SQLite
- 简单、版本控制友好
- 足够支撑 1-2 年数据
- 迁移成本低

### 决策 3：是否要 Web 界面？

**当前建议**：先 CLI（命令行），后续可加 Web
- MVP 优先
- 用户群体小（营销部）
- CLI 足够

### 决策 4：是否要 PDF 输出？

**当前建议**：先 Word，PDF 可选
- Word 是用户主要输出
- PDF 可后期加（libreoffice 命令行转换）

---

## 下一步行动

### 立即可做

1. **设计 JSON Schema** - 第一个产出物
2. **构建实体词典** - 复用 Excel 中的数据
3. **Excel 采集器 PoC** - 验证可行性

### 优先级排序

```
P0: JSON Schema + 实体词典
P1: Excel 采集器（语义定位）
P2: Schema 验证
P3: Word 模板设计
P4: 报告生成
P5: 端到端测试
P6: 智能能力（未来）
```

---

## 变更日志

| 日期 | 版本 | 变更 |
|-----|------|------|
| 2026-06-04 | v1.0 | 初稿，完成项目计划 |
