# 周报自动化系统 v2.5 架构文档

> 本文档描述基于 v2.0（4 Analyzer + Streamlit）+ Step 1-10 增强后的完整文档生成系统。
> 核心创新：reason_map 槽位化映射 + LLM 润色器 + 数据驱动生成 + docxtpl 模板引擎。

---

## 一、整体架构（5 层）

```
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 0: 输入层
│ ┌──────────────────────────────┐ ┌──────────────────────────┐
│ │ 综合分析报表.xlsx             │ │ 周数据汇总表.xlsx         │
│ │ (186 字段 CELL_MAP)          │ │ (现货价格 + 原因文本)    │
│ └──────────────────────────────┘ └──────────────────────────┘
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 1: 数据采集层
│ ┌─────────────────────────────────────────────────────────────┐
│ │ AnalysisCollector          │ SummaryCollector     │ v2.x旧模式 │
│ │ - 单元格直接映射           │ - 现货价格           │ - 语义定位 │
│ │ - 99.46% 覆盖率            │ - 原因文本           │            │
│ └─────────────────────────────────────────────────────────────┘
│ → 输出: data dict (含 domestic/international/report_table_1)
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 2: 标准化层 (JSON)
│ ┌─────────────────────────────────────────────────────────────┐
│ │ reason_map.json: V4 段落 ↔ Excel 单元格映射规则           │
│ │ ├─ HIGH (10) - 直接取数据 + LLM 润色                     │
│ │ ├─ MEDIUM (5) - 多源拼装 + LLM 润色                       │
│ │ └─ grounded_category (4) - 数据驱动 LLM 生成              │
│ │ schemas: weekly_data.schema.json                            │
│ └─────────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 3: 解析层（LLM 驱动）                                       │
│ ┌─────────────────────────────────────────────────────────────┐
│ │ LLM Factory (.env 驱动)                                     │
│ │ ┌─────────┬─────────┬─────────┬─────────┐                  │
│ │ │ Qwen    │Anthropic│ OpenAI  │DeepSeek │                  │
│ │ └─────────┴─────────┴─────────┴─────────┘                  │
│ │           ↓           ↓           ↓                          │
│ │ ┌──────────────┐  ┌──────────────────────────┐              │
│ │ │  Polisher    │  │ GroundedReasonGenerator  │              │
│ │ │  (润色)      │  │ (数据驱动生成)           │              │
│ │ └──────────────┘  └──────────────────────────┘              │
│ │           ↓                   ↓                              │
│ │ ┌─────────────────────────────────────────┐                 │
│ │ │ ReasonCollector + ReasonResolver         │                 │
│ │ │ - 25 个 ReasonSlot 槽位定义               │                 │
│ │ │ - 双模式: extract / grounded_category    │                 │
│ │ │ - 三层 Fallback 数据路径                  │                 │
│ │ └─────────────────────────────────────────┘                 │
│ │           ↓                                                  │
│ │ {占位符 → 文本}字典                                          │
│ └─────────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 4: 模板层
│ ┌─────────────────────────────────────────────────────────────┐
│ │ V3 清洁版.docx (45 段)                                      │
│ │   ↓ convert_template.py (智能检测格式)                      │
│ │ report_template.docx                                         │
│ │   ↓ prepare_template.py (插入 {{ }} 占位符)                │
│ │ report_template_jinja.docx                                   │
│ │   ↓ prepare_table_templates.py (表格 subdoc 化)            │
│ │ report_template_jinja.docx (含 row_1.hydro 等)              │
│ │   ↓ enhance_template.py (样式美化)                          │
│ │ report_template_jinja.docx (专业 Word 样式)                  │
│ └─────────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 5: 生成层
│ ┌─────────────────────────────────────────────────────────────┐
│ │ ReportGeneratorV2 (基于 docxtpl)                             │
│ │ - 加载模板 + 上下文数据                                       │
│ │ - 渲染 Jinja2 占位符                                         │
│ │ - 输出 .docx                                                  │
│ └─────────────────────────────────────────────────────────────┘
│   ↓
│ 📄 2026 年第 21 周周例会营销发言材料.docx
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、端到端流程（从命令到 Word）

### 2.1 用户命令

```bash
python scripts/run_pipeline.py \
  --analysis-input "files/2026年第21周周数据综合分析报表.xlsx" \
  --summary-input "files/2026年第21周周数据汇总表.xlsx" \
  --year 2026 --week 21 \
  --output-dir archive/manual_run
```

### 2.2 内部串联流程

```
run_pipeline.py
   ↓
┌─────────────────────────────────────────────────────────┐
│ Step 1: AnalysisCollector.collect(analysis_input)       │
│ ─────────────────────────────────────────────────────── │
│ 读 综合分析表.xlsx (Sheet: 综合分析表)                  │
│ 按 CELL_MAP (186 字段映射) 读单元格                     │
│ 输出: data dict                                          │
│ ├─ meta: {year, week, start_date, end_date}             │
│ ├─ domestic: {electricity, price, revenue, yoy, wow}    │
│ ├─ international: {price, yoy, wow}                     │
│ ├─ report_table_1: {headers, data} (9 行 × 6 列)        │
│ └─ validation_report: {coverage: 99.46%}                │
└─────────────────────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────────────────────┐
│ Step 1b: SummaryCollector.collect(summary_input)        │
│ ─────────────────────────────────────────────────────── │
│ 读 周数据汇总表.xlsx                                     │
│ 采集:                                                     │
│ ├─ spot_prices: 10 地区均价/同比/环比/原因               │
│ └─ reasons: yoy_summary / wow_summary / 长江电力        │
│             湖北能源 / 三峡发展 / 湖南分                │
└─────────────────────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────────────────────┐
│ Step 2: 数据存储到 JSON                                  │
│ ─────────────────────────────────────────────────────── │
│ data/processed/2026_week21.json                          │
└─────────────────────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────────────────────┐
│ Step 2b: ReasonResolver.resolve_all() ⭐ 核心            │
│ ─────────────────────────────────────────────────────── │
│ 1. 加载 reason_map.json (15 条映射)                      │
│ 2. 创建 ReasonResolver                                   │
│    ├─ ReasonCollector (槽位采集)                        │
│    ├─ ReasonPolisher (LLM 润色)                          │
│    ├─ GroundedReasonGenerator (数据驱动)                │
│    └─ data (AnalysisCollector 输出)                     │
│                                                            │
│ 3. 对每条映射处理:                                       │
│    ┌──────────────────────────────────────────┐          │
│    │ generation_mode == 'extract'             │          │
│    │ → ReasonCollector 提取 Excel 单元格     │          │
│    │ → 可选 LLM 润色                          │          │
│    └──────────────────────────────────────────┘          │
│    ┌──────────────────────────────────────────┐          │
│    │ generation_mode == 'grounded_category'   │          │
│    │ → 从 data 提取品类数据 (水电/风电...)    │          │
│    │ → GroundedReasonGenerator 调用 LLM      │          │
│    │ → 防幻觉验证（数字必须来自输入）         │          │
│    └──────────────────────────────────────────┘          │
│                                                            │
│ 4. 输出: {占位符: 文本}字典                              │
│    例: {"v4_P6_dom_elec_yoy_wow": "1、全集团电量..."} │
└─────────────────────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────────────────────┐
│ Step 3: ReportGeneratorV2.generate_report()             │
│ ─────────────────────────────────────────────────────── │
│ 1. 加载模板: data/templates/report_template_jinja.docx  │
│ 2. 构建 Jinja2 上下文:                                    │
│    context = {                                            │
│      "title": "市场营销部汇报材料",                       │
│      "week": 21,                                           │
│      "dom_overview": "上周，集团公司合计...",             │
│      "row_1": {"hydro": "59.05", ...},  ← 表格数据      │
│      "row_2": {"hydro": "+6.6%", ...},                   │
│      ...                                                   │
│      "v4_P6_dom_elec_yoy_wow": "1、全集团电量...",       │
│      ...                                                   │
│      "v4_P13_hydro_price_wow": "水电电价环比下降...",     │
│    }                                                       │
│ 3. DocxTemplate.render(context)                          │
│ 4. 输出: archive/2026/week21/2026年第21周周例会营销发言材料.docx │
└─────────────────────────────────────────────────────────┘
```

---

## 三、核心设计思想

### 思想 1：单一数据源 + 单一模板

```
Excel 数据 ──┐
             ├→ JSON 中间层 ─→ Jinja2 模板 ─→ Word 输出
模板规范 ────┘
```

**优势**：
- 数据与模板分离，互不影响
- 修改模板不影响数据处理逻辑
- 复用同一个数据字典用于多种输出（Word + Streamlit + Markdown）

### 思想 2：槽位化（Slot）抽象

```python
# 每个原因文本是一个独立槽位
ReasonSlot(
    slot_id="dom.elec.yoy.changjiang",
    sheet_name="国内数据填报表",
    row=29, col=8,  # H29
    description="国内电量同比原因（长江电力+全集团）",
    category="domestic_yoy",
)
```

**优势**：
- 25 个槽位定义清晰
- 槽位 ID 语义化（`dom.elec.yoy.changjiang` 一眼读懂）
- 易扩展（新增原因只需加新槽位）

### 思想 3：三模式生成

```
┌──────────────────────────────────────────────────────────┐
│ 模式 1: extract（提取式）                                │
│ ──────────────────────────────────────────────────────── │
│ 数据源: Excel 单元格（如 H29）                          │
│ 流程: 直接读 → 拼接 → 可选润色                          │
│ 适用: 公司级原因（H29, H53, H71, H101, H119）           │
│ 例: 长江电力+全集团 电量同比/环比原因                    │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│ 模式 2: grounded_category（数据驱动生成）⭐ 新          │
│ ──────────────────────────────────────────────────────── │
│ 数据源: 综合分析表报告表 1 (R78-86)                     │
│ 流程: 收集品类数据 → 喂给 LLM → 生成解释                │
│ 适用: 品类级原因（4 段落：水电/风电/光伏/火电环比）     │
│ 防幻觉: 输出数字必须出现在输入中（±0.01 容差）          │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│ 模式 3: fallback（兜底）                                 │
│ ──────────────────────────────────────────────────────── │
│ 数据源: reason_map.json 中预定义的 fallback_text         │
│ 流程: 当 extract/grounded 都失败时使用                  │
│ 适用: 数据缺失的极端情况                                 │
└──────────────────────────────────────────────────────────┘
```

### 思想 4：三层 Fallback 数据路径

```python
# build_sales_rows 中的三层 fallback
def _get_value(row_def, col_def, data):
    # 路径 1: report_table_1.data[行][列]  ← 最优先
    # 路径 2: domestic.electricity.hydro  ← 嵌套结构
    # 路径 3: data["report.electricity.hydro"]  ← flat 键
    # 路径 4: "—"  ← 兜底
```

**为什么需要三层？** 因为 AnalysisCollector 在不同模式下数据结构不同，必须兼容。

### 思想 5：多 Provider LLM 抽象

```python
# 同一套代码支持 Qwen/Anthropic/OpenAI/DeepSeek
# 切换只需改 .env 一行
# LLM_PROVIDER=qwen → 用 dashscope
# LLM_PROVIDER=anthropic → 用 claude
# LLM_PROVIDER=openai → 用 gpt-4o-mini

# 统一接口
def call_llm(prompt, system, max_tokens, temperature):
    if provider == "anthropic":
        return anthropic_client.messages.create(...)
    else:  # OpenAI 兼容
        return openai_client.chat.completions.create(...)
```

### 思想 6：防幻觉四重保险

```python
# 保险 1: Prompt 黑名单
forbidden = ["预计将", "据预测", "有望", "可能会"]

# 保险 2: 数字验证（输入 ⊇ 输出）
raw_numbers = re.findall(r"\d+\.?\d*", raw)
polished_numbers = re.findall(r"\d+\.?\d*", polished)
if not polished_numbers.issubset(raw_numbers):
    return raw_text  # 回退

# 保险 3: 长度限制（polished 不超 raw 1.8 倍）
if len(polished) > len(raw) * 1.8:
    return raw_text

# 保险 4: 占位符兜底
fallback_text = mapping.get("fallback_text", "（待补充）")
```

### 思想 7：优雅降级（绝不崩溃）

```
LLM 不可用          → 用原文
LLM 输出未通过验证   → 用原文
Excel 数据缺失      → 用 fallback_text
模板不存在          → 抛 FileNotFoundError（启动时）
文件不存在          → 错误日志，不中断流程
```

---

## 四、数据流（关键路径）

```
┌────────────────────────────────────────────────────────────┐
│ 综合分析表 (Cell R78-86, Columns C-I)                       │
│   水电: 59.05 亿千瓦时, 同比 +6.6%, 电价 0.283              │
│   合计: 80.28 亿千瓦时, 同比 +3.3%, 电价 0.311              │
└────────────────────────────────────────────────────────────┘
                              ↓ AnalysisCollector (CELL_MAP)
                              ↓
┌────────────────────────────────────────────────────────────┐
│ data dict:                                                  │
│   "domestic": {                                              │
│     "electricity": {"hydro": 590454.47183, "total": 802763},│
│     "price": {"hydro": 0.283, "total": 0.311},              │
│     "yoy": {"electricity": {"hydro": 0.066}, ...}           │
│   }                                                          │
│   "report_table_1": {                                        │
│     "data": [[59.05, 17.96, 10.36, 7.59, 3.12, 80.28],      │
│              [0.066, ...], ...]                              │
│   }                                                          │
└────────────────────────────────────────────────────────────┘
                              ↓ ReasonResolver.resolve_all()
                              ↓
┌────────────────────────────────────────────────────────────┐
│ {占位符: 文本}字典:                                         │
│   "v4_P6_dom_elec_yoy_wow": "上周，集团公司国内上网电量80.3 │
│     亿千瓦时、同比提高 3.2%，主要原因是长江电力：1、全口径 │
│     电量同比增加..."                                        │
│   "v4_P13_hydro_price_wow": "水电电价环比下降 0.4 分，      │
│     主要原因是金下梯级电站..."                              │
│   "row_1": {"hydro": "59.05", "total": "80.28"}             │
│   ...                                                        │
└────────────────────────────────────────────────────────────┘
                              ↓ DocxTemplate.render(context)
                              ↓
┌────────────────────────────────────────────────────────────┐
│ 报告.docx (45 段落 + 3 表格)                              │
│   第 1 段: 标题 (黑体 18pt 居中)                            │
│   第 2 段: 副标题 (黑体 14pt 居中)                          │
│   第 3 段: 一、上周销售情况 (Heading1 16pt 深蓝)           │
│   第 4 段: （一）电量销售情况                              │
│   第 5 段: 上周，集团公司合计上网电量 89.1 亿千瓦时...      │
│   第 6 段: 上周，集团公司国内上网电量 80.3 亿千瓦时...      │
│     {{ v4_P6_dom_elec_yoy_wow }} ← 已渲染                  │
│   第 7 段: 1、全口径电量同比增加... ← Qwen 润色后          │
│   ...                                                        │
│   表格 1: 国内销售情况 (10×7, 全部动态填入)              │
│   表格 2: 现货市场均价 (4×11)                              │
│   表格 3: 水位表                                            │
│   页脚: PAGE 字段 (自动页码)                               │
└────────────────────────────────────────────────────────────┘
```

---

## 五、覆盖率统计

| 阶段 | HIGH | MEDIUM | MANUAL | 自动化率 |
|------|------|--------|--------|----------|
| v2.0 (4 Analyzer) | - | - | 全部 | 0% |
| Step 1-6 (ReasonMap 提取) | 6 | 5 | 4 | 67% |
| Step 8 (GroundedCategory) | 10 | 5 | 0 | **100%** |

**最终结果**：
- 15 段全部自动化
- 7 段使用 Qwen LLM 润色
- 8 段使用数据驱动生成 + 备用 fallback

---

## 六、关键文件清单

| 文件 | 行数 | 角色 |
|------|------|------|
| `src/utils/llm_factory.py` | 280 | LLM 客户端工厂（4 provider） |
| `src/collector/reason_collector.py` | 280 | 槽位定义 + 数据采集 |
| `src/collector/analysis_collector.py` | 380 | 综合分析表采集 |
| `src/collector/summary_collector.py` | 340 | 汇总表采集（现货+原因） |
| `src/generator/reason_resolver.py` | 380 | ⭐ 核心解析器 |
| `src/generator/reason_polisher.py` | 290 | LLM 润色器 |
| `src/generator/grounded_generator.py` | 300 | 数据驱动生成 |
| `src/generator/report_generator_v2.py` | 220 | docxtpl 生成器 |
| `data/dictionaries/reason_map.json` | 60 | 15 条映射规则 |
| `data/templates/report_template_jinja.docx` | - | Jinja2 模板 |

**总计**：~2700 行核心代码 + 95 个测试 + 7 个辅助脚本

---

## 七、可改进空间

| 优先级 | 改进 | 价值 |
|--------|------|------|
| 🔴 P0 | 把 fallback 文本从代码移到 JSON 配置 | 非开发者可编辑 |
| 🟡 P1 | 增量缓存：相同数据不重复调用 LLM | 节省成本 50% |
| 🟡 P1 | LLM 输出评测（A/B test vs 范文） | 量化润色质量 |
| 🟢 P2 | 支持 Word 表格公式（`=SUM(ABOVE)`） | 数据自动汇总 |
| 🟢 P2 | 多语言版本（英文周报） | 国际化 |
| 🟢 P3 | Web UI 让人工 review 润色结果 | 闭环反馈 |

---

## 八、配置（.env）

```bash
# LLM 提供商
LLM_PROVIDER=qwen                              # anthropic / qwen / openai / deepseek

# Qwen (DashScope 兼容模式)
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-turbo                      # qwen3.5-plus / qwen-turbo / ...

# 应用配置
ENABLE_LLM_POLISH=true
LLM_MAX_TOKENS=500
LLM_VALIDATION=moderate
```

---

## 九、运行命令

```bash
# 完整流程（推荐）
PYTHONPATH=. python scripts/run_pipeline.py \
  --analysis-input "files/2026年第21周周数据综合分析报表.xlsx" \
  --summary-input "files/2026年第21周周数据汇总表.xlsx" \
  --year 2026 --week 21

# 仅准备模板（首次或模板变更时）
PYTHONPATH=. python scripts/convert_template.py
PYTHONPATH=. python scripts/prepare_template.py
PYTHONPATH=. python scripts/prepare_table_templates.py
PYTHONPATH=. python scripts/enhance_template.py
```

---

## 十、版本演进

| 版本 | 日期 | 关键能力 |
|------|------|----------|
| v1.0 | 2026-04 | 基础 Excel → JSON → Word |
| v2.0 | 2026-05-30 | 4 Analyzer + Streamlit Web UI (158 测试) |
| v2.4.1 | 2026-06-06 | Page 1 双层单选 + 18 家全量 (212 测试) |
| **v2.5** | **2026-06-07** | **reason_map + LLM 润色 + docxtpl (95+78=173 测试)** |

**v2.5 里程碑**：
- ✅ LLM 集成（4 provider 可切换）
- ✅ 100% 自动化覆盖
- ✅ 专业 Word 样式（标题/表格/页码）
- ✅ 动态表格数据填入（subdoc）
- ✅ 防幻觉 4 重保险
- ✅ 多层优雅降级

---

**总结一句话**：
> **数据采集 → 槽位定义 → LLM 润色/生成 → Jinja2 模板渲染**，
> 全程优雅降级、自动防幻觉、100% 自动化率生成专业 Word 周报。

---

*文档作者：Claude Code*
*更新日期：2026-06-07*