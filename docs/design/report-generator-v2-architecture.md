# report_generator_v2 整体架构设计

> 周报自动化系统 v2 的**整体架构设计**——基于"业务图谱"重新构建系统
> 目标：把 **4 维度 × 8 段实战** 全部自动化 + 提供 **Streamlit Web UI**
> 版本：v1.0
> 设计日期：2026-06-06

---

## 0. 文档说明

### 0.1 设计背景

基于 `docs/design/business-map-master.md` 业务图谱的 v2 重构。当前 v1 系统已完成国内电价段（Phase 1R+2R），但其他 3 个维度的分析能力尚未实现，且无 Web UI。v2 旨在：

- **补全分析能力**：把 4 维度（国内/国际/市场化/碳资产）的 8 段全部实现
- **提供 Web UI**：让分析师在浏览器里查看、对比、导出周报
- **保持向后兼容**：保留现有 CLI 入口，不破坏现有数据流

### 0.2 设计目标

| 目标 | 度量 | 优先级 |
|------|------|--------|
| 8 段全部自动化 | 段覆盖数 = 8 | P0 |
| Web UI 可视化 | Streamlit 多页应用 | P0 |
| 双线（同比/环比）分析 | 所有 4 维度都支持 | P0 |
| 关键数字勾稽自动验证 | 验算通过率 100% | P0 |
| Word 报告导出 | docx 文件生成 | P1 |
| 交互式图表 | Plotly 集成 | P1 |
| 历史周对比 | 多周趋势图 | P2 |
| 异常告警 | 阈值检测 + 通知 | P2 |

### 0.3 关键决策

| 决策项 | 选择 | 原因 |
|--------|------|------|
| UI 框架 | **Streamlit** | Python 原生、数据驱动、快速原型、零前端 |
| 架构 | **增量重构** | 保留现有 collector/validator，只新增 analyzer |
| 数据流 | **JSON 中间层** | 与现有系统对齐，不重做数据采集 |
| 缓存 | **Streamlit @st.cache_data** | 周数据不频繁变化，缓存提升性能 |
| 部署 | **单进程** | 内网友好，CLI 和 Web 共用一套代码 |

---

## 1. 整体架构

### 1.1 5 层架构

```
═══════════════════════════════════════════════════════════════════════
         周报自动化系统 v2 - 5 层架构
═══════════════════════════════════════════════════════════════════════

  ┌──────────────────────────────────────────────────────┐
  │  Layer 0: 数据源层 (Data Sources)                       │
  │  ├─ 综合分析表 (186 字段)                              │
  │  └─ 汇总表 (现货+原因补充)                            │
  └─────────────────────┬────────────────────────────────┘
                        │
                        ▼
  ┌──────────────────────────────────────────────────────┐
  │  Layer 1: 数据采集层 (Collectors) [v1 已有]            │
  │  ├─ analysis_collector.py    主采集器                  │
  │  └─ summary_collector.py     补充采集器                │
  └─────────────────────┬────────────────────────────────┘
                        │
                        ▼
  ┌──────────────────────────────────────────────────────┐
  │  Layer 2: 数据标准化层 (Standardization) [v1 已有]      │
  │  ├─ schema_validator.py    Schema 校验                │
  │  ├─ data_cleaner.py        数据清洗                   │
  │  ├─ entity_resolver.py     实体词典匹配               │
  │  └─ exchange_rate_collector.py  汇率采集 (v2 新增)    │
  └─────────────────────┬────────────────────────────────┘
                        │
                        ▼
  ┌──────────────────────────────────────────────────────┐
  │  Layer 3: 数据存储层 (Storage) [v1 已有]                │
  │  ├─ data/processed/2026_week21.json                   │
  │  └─ 实体词典 dictionaries/                            │
  └─────────────────────┬────────────────────────────────┘
                        │
                        ▼
  ┌──────────────────────────────────────────────────────┐
  │  Layer 4: 分析层 (Analyzers) [v2 新增 ⭐ 核心]          │
  │  ├─ DomesticAnalyzer       段 1-2 (国内)              │
  │  ├─ InternationalAnalyzer   段 3-4 (国际)              │
  │  ├─ MarketTradingAnalyzer   段 5-7 (市场化)            │
  │  └─ EnvironmentalAnalyzer   段 8 (碳资产)              │
  └─────────────────────┬────────────────────────────────┘
                        │
                        ▼
  ┌──────────────────────────────────────────────────────┐
  │  Layer 5: 表现层 (Presentation) [v2 新增 ⭐]            │
  │  ├─ Streamlit Web UI      5 个 Tabs/Pages            │
  │  ├─ CLI 入口 (scripts/run_pipeline.py) [保留]         │
  │  └─ Word 报告导出 (docxtpl + python-docx)            │
  └──────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════
```

### 1.2 架构亮点

1. **Layer 0-3 完全复用 v1**——不重做数据采集、标准化、存储
2. **Layer 4 是 v2 核心**——4 个 Analyzer 类对应 4 个维度
3. **Layer 5 双重入口**——CLI 和 Web 共用 Analyzer
4. **横向解耦**——4 个 Analyzer 之间无依赖，可独立测试

---

## 2. 模块结构

### 2.1 目录结构（v2 新增部分用 ⭐ 标记）

```
production_operation/
├── data/                          # 数据层
│   ├── schema/
│   ├── dictionaries/              # 实体词典
│   ├── templates/                 # Word 模板
│   ├── raw/                       # 原始 Excel
│   └── processed/                 # 处理后 JSON
│
├── src/                           # 源代码
│   ├── collector/                 # 数据采集 (v1)
│   ├── validator/                 # 数据验证 (v1)
│   ├── storage/                   # 数据存储 (v1)
│   ├── generator/                 # 报告生成 (v1)
│   │   ├── report_generator.py    # 主生成器
│   │   ├── analysis_text.py       # 文本生成
│   │   └── table_builder.py       # 表格构建
│   ├── analyzer/                  # ⭐ v2 新增：分析层
│   │   ├── __init__.py
│   │   ├── base.py                # 基础抽象类
│   │   ├── domestic.py            # 国内分析器 (段 1-2)
│   │   ├── international.py       # 国际分析器 (段 3-4)
│   │   ├── market_trading.py      # 市场化分析器 (段 5-7)
│   │   └── environmental.py       # 碳资产分析器 (段 8)
│   ├── visualizer/                # ⭐ v2 新增：可视化层
│   │   ├── __init__.py
│   │   ├── charts.py              # Plotly 图表
│   │   └── tables.py              # 表格渲染
│   └── utils/
│       └── entity_resolver.py
│
├── streamlit_app/                 # ⭐ v2 新增：Streamlit Web UI
│   ├── app.py                     # 主入口
│   ├── pages/                     # 多页结构
│   │   ├── 1_🏠_国内分析.py
│   │   ├── 2_🌍_国际分析.py
│   │   ├── 3_💹_市场化分析.py
│   │   ├── 4_🌱_碳资产分析.py
│   │   └── 5_📄_报告生成.py
│   ├── components/                # 复用组件
│   │   ├── __init__.py
│   │   ├── kpi_card.py            # KPI 卡片
│   │   ├── story_panel.py         # 故事面板
│   │   ├── data_table.py          # 数据表格
│   │   └── export_button.py       # 导出按钮
│   └── requirements.txt           # 依赖清单
│
├── scripts/                       # CLI 入口 (v1 保留)
│   ├── run_pipeline.py            # 完整流程
│   ├── extract_data.py
│   ├── validate_data.py
│   └── generate_report.py
│
├── tests/                         # 测试
│   ├── test_collector.py
│   ├── test_validator.py
│   ├── test_generator.py
│   └── test_analyzer/             # ⭐ v2 新增
│       ├── test_domestic.py
│       ├── test_international.py
│       ├── test_market_trading.py
│       └── test_environmental.py
│
├── docs/
│   ├── design/                    # 设计文档
│   │   ├── business-map-master.md          # ⭐ 新增
│   │   ├── report-generator-v2-architecture.md  # ⭐ 本文档
│   │   ├── project_plan.md
│   │   ├── implementation_plan.md
│   │   └── data_definition.md
│   ├── analysis/                  # 分析文档
│   ├── user_guide/                # 用户指南
│   └── api/                       # API 文档
│
└── archive/                       # 历史归档
```

### 2.2 4 个 Analyzer 模块设计

```python
# src/analyzer/base.py - 基础抽象类

from abc import ABC, abstractmethod
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class AnalysisResult:
    """分析结果统一数据结构"""
    dimension: str         # 维度名 (国内/国际/市场化/碳资产)
    sections: list         # 包含的段列表
    summary: str           # 一句话总结
    kpis: Dict[str, Any]   # 关键指标字典
    tables: list           # 表格数据
    charts: list           # 图表数据
    insights: list         # 关键洞察
    story: str             # 业务故事
    yoy_data: Dict         # 同比数据
    mom_data: Dict         # 环比数据
    anomalies: list        # 异常列表


class BaseAnalyzer(ABC):
    """所有分析器的基类"""

    dimension_name: str = ""
    section_ids: list = []

    def __init__(self, json_data: dict, config: dict = None):
        self.data = json_data
        self.config = config or {}

    @abstractmethod
    def analyze(self) -> AnalysisResult:
        """执行分析，返回标准化的 AnalysisResult"""
        pass

    @abstractmethod
    def validate_inputs(self) -> bool:
        """检查输入数据是否完整"""
        pass

    def calculate_yoy(self, current, last_year) -> float:
        """同比计算（带勾稽验证）"""
        if last_year == 0:
            return 0.0
        return (current - last_year) / last_year * 100

    def calculate_mom(self, current, last_week) -> float:
        """环比计算（带勾稽验证）"""
        if last_week == 0:
            return 0.0
        return (current - last_week) / last_week * 100
```

```python
# src/analyzer/domestic.py - 国内分析器

class DomesticAnalyzer(BaseAnalyzer):
    """国内分析器（段 1-2）：电量 + 电价"""
    dimension_name = "国内"
    section_ids = [1, 2]

    def analyze(self) -> AnalysisResult:
        # 1. 提取数据
        group_volume = self.data["group_total"]["domestic_ongrid_volume_yi_kwh"]
        group_price = self.data["group_total"]["domestic_avg_price_yuan_per_kwh"]

        # 2. 同比环比
        yoy = self.calculate_yoy(...)
        mom = self.calculate_mom(...)

        # 3. 量价分解
        decomposition = self._decompose_volume_price()

        # 4. 5 大品类
        categories = self._analyze_categories()

        # 5. 关键省份
        regions = self._analyze_regions()

        # 6. 异常检测
        anomalies = self._detect_anomalies()

        return AnalysisResult(
            dimension="国内",
            sections=[1, 2],
            summary="以量补价，量增价跌，收入微增",
            ...
        )

    # ... 其他方法
```

类似地：
- `InternationalAnalyzer` 覆盖段 3-4，含汇率折算 + 三层归因
- `MarketTradingAnalyzer` 覆盖段 5-7，含现货增收、欠发套利、一省一策
- `EnvironmentalAnalyzer` 覆盖段 8，含价差怪现象、库存估值

### 2.3 Analyzer 接口统一性

| 接口 | 用途 | 调用方 |
|------|------|--------|
| `analyze()` | 核心分析 | CLI / Web UI |
| `validate_inputs()` | 输入校验 | 数据采集层 |
| `get_kpis()` | 提取 KPI | Streamlit 卡片 |
| `get_story()` | 提取故事 | Streamlit 面板 |
| `export_dict()` | 字典化输出 | Word 生成器 |
| `export_chart_data()` | 图表数据 | Streamlit 图表 |

---

## 3. 数据流

### 3.1 v2 完整数据流

```
═══════════════════════════════════════════════════════════════════════
                 v2 数据流（从 Excel 到 Word + Web）
═══════════════════════════════════════════════════════════════════════

  Excel 文件 (综合分析表 + 汇总表)
         │
         ▼
  [Collector Layer] - 已有
  analysis_collector.py + summary_collector.py
         │
         ▼ 产出
  标准化 JSON（data/processed/2026_week21.json）
         │
         ├─────────────────┐
         │                 │
         ▼                 ▼
  [Analyzer Layer]    [Validator Layer]
  4 个 Analyzer        异常检测
  并行分析             触发告警
         │
         ▼ 产出
  AnalysisResult 对象（4 个）
         │
         ├─────────────────┬──────────────────┐
         │                 │                  │
         ▼                 ▼                  ▼
  [Streamlit UI]    [Word Generator]    [JSON 缓存]
  5 个 Tabs          report_generator   @st.cache_data
  实时可视化          导出 .docx        性能优化
         │                 │
         └────────┬────────┘
                  │
                  ▼
         输出：Web 报告 + Word 报告

═══════════════════════════════════════════════════════════════════════
```

### 3.2 数据契约（关键数据结构）

```python
# 顶层 JSON 结构（v2 扩展）
{
    "report_id": "2026_W21_001",
    "report_period": {...},
    "group_total": {...},                # 已有
    "by_category": {...},               # 已有
    "by_region": {...},                 # 已有
    "international": {                  # v1.1 已有
        "total_volume_yi_kwh": 8.8,
        "total_revenue_yi_yuan": 28.2,
        "avg_price_yuan_per_kwh": 0.32,
        ...
    },
    "market_trading": {                 # v2 新增
        "hydro": {...},
        "renewables": {...},
        "thermal": {...}
    },
    "environmental_assets": {           # v2 新增
        "green_cert": {...},
        "ccer": {...}
    },
    "analysis_results": {               # v2 新增（运行时）
        "domestic": {...},
        "international": {...},
        "market_trading": {...},
        "environmental": {...}
    }
}
```

### 3.3 异常检测触发链

```
Analyzer 检测到异常
    ↓
写入 anomalies 字段
    ↓
UI 红色高亮显示
    ↓
可选：触发邮件/钉钉通知 (P2)
```

---

## 4. Streamlit 设计

### 4.1 5 页结构

```
═══════════════════════════════════════════════════════════════════════
              Streamlit 应用 - 5 页结构
═══════════════════════════════════════════════════════════════════════

  ┌────────────────────────────────────────────────────┐
  │  📊 周报分析平台 - 周报自动化 v2                      │
  ├────────────────────────────────────────────────────┤
  │                                                    │
  │  侧边栏:                                           │
  │  ├─ 📁 数据上传 (Excel 文件)                       │
  │  ├─ 📅 周次选择 (2026-W21)                         │
  │  ├─ 🏢 集团范围 (全部/三峡国际/长电国际/湖北能源)  │
  │  └─ ▶️ 运行分析 按钮                              │
  │                                                    │
  ├────────────────────────────────────────────────────┤
  │                                                    │
  │  主区域: 5 个 Tabs (顶部)                            │
  │                                                    │
  │  [🏠 国内] [🌍 国际] [💹 市场化] [🌱 碳资产] [📄 报告]  │
  │                                                    │
  └────────────────────────────────────────────────────┘
```

### 4.2 各页面详细设计

#### Page 1: 🏠 国内分析

```
┌──────────────────────────────────────────────────────┐
│ 🏠 国内分析 - 段 1-2                                  │
├──────────────────────────────────────────────────────┤
│                                                      │
│  顶部 KPI 卡片 (4 个)                                 │
│  ┌────────┬────────┬────────┬────────┐               │
│  │总电量   │国内占比 │度电均价 │同比变化 │               │
│  │89.1 亿 │90.1%   │0.311元 │-0.9 分 │               │
│  │+3.2%↑ │         │         │         │               │
│  └────────┴────────┴────────┴────────┘               │
│                                                      │
│  📊 同比环比 双线对比图 (Plotly)                       │
│  ┌────────────────────────────────────┐              │
│  │  电量 vs 电价 vs 收入 三线对比      │              │
│  └────────────────────────────────────┘              │
│                                                      │
│  📋 5 大品类明细表                                    │
│  ┌─────────┬──────┬──────┬──────┬──────┐            │
│  │品类      │电量   │度电   │收入   │同比  │            │
│  ├─────────┼──────┼──────┼──────┼──────┤            │
│  │水电      │59.0  │0.283 │16.7  │+6.2% │            │
│  │新能源    │18.0  │0.381 │6.8   │+1.2% │            │
│  │...                                          │     │
│  └─────────┴──────┴──────┴──────┴──────┘            │
│                                                      │
│  💡 业务故事 + 段位解读                                │
│  "以量补价，量增价跌..."                              │
│                                                      │
└──────────────────────────────────────────────────────┘
```

#### Page 2-4: 国际 / 市场化 / 碳资产

类似结构，针对各自维度的关键指标和故事：
- **国际**: 真本事 +2.7 分/1.4 分、汇率/合同贡献、5 区域分布
- **市场化**: 3 大板块对比、现货增收、欠发套利、3 种新能源策略
- **碳资产**: 绿证/CCER 累计、库存估值、价差怪现象

#### Page 5: 📄 报告生成

```
┌──────────────────────────────────────────────────────┐
│ 📄 报告生成                                           │
├──────────────────────────────────────────────────────┤
│                                                      │
│  模板选择:                                            │
│  ◉ 完整周报 (45 段 + 3 表)                            │
│  ◯ 仅国内电价段                                      │
│  ◯ 仅国际电价段                                      │
│  ◯ 仅市场化段                                        │
│  ◯ 仅碳资产段                                        │
│                                                      │
│  输出格式:                                            │
│  ☑️ Word (.docx)                                     │
│  ☑️ Markdown (.md)                                   │
│  ☐ PDF (待支持)                                      │
│                                                      │
│  [🚀 生成报告]                                       │
│                                                      │
│  生成进度: ████████░░ 80%                            │
│                                                      │
│  📥 下载链接:                                        │
│  - weekly_report_2026_W21.docx (1.2 MB)             │
│  - weekly_report_2026_W21.md (89 KB)                │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 4.3 复用组件

| 组件 | 用途 | 关键功能 |
|------|------|---------|
| `kpi_card.py` | KPI 卡片 | 大数字 + 同比环比 + 趋势箭头 |
| `story_panel.py` | 故事面板 | 4 幕剧 + 反直觉点 + 一句话金句 |
| `data_table.py` | 数据表格 | 品类/省份/电站/年份 4 维切换 |
| `export_button.py` | 导出按钮 | Word/Markdown/JSON 多格式 |
| `anomaly_alert.py` | 异常告警 | 红色高亮 + 触发原因 |
| `verification_check.py` | 勾稽验证 | 显示验算通过/失败 |

### 4.4 状态管理

```python
# streamlit_app/utils/state.py
import streamlit as st

def init_session_state():
    """初始化全局 session state"""
    if 'json_data' not in st.session_state:
        st.session_state.json_data = None
    if 'analyzers' not in st.session_state:
        st.session_state.analyzers = {}
    if 'selected_week' not in st.session_state:
        st.session_state.selected_week = "2026-W21"
    if 'selected_dimension' not in st.session_state:
        st.session_state.selected_dimension = "all"


@st.cache_data
def load_and_analyze(json_path: str):
    """加载 JSON 并执行所有分析（缓存）"""
    import json
    from src.analyzer import (
        DomesticAnalyzer, InternationalAnalyzer,
        MarketTradingAnalyzer, EnvironmentalAnalyzer
    )
    with open(json_path) as f:
        data = json.load(f)

    analyzers = {
        "domestic": DomesticAnalyzer(data),
        "international": InternationalAnalyzer(data),
        "market_trading": MarketTradingAnalyzer(data),
        "environmental": EnvironmentalAnalyzer(data)
    }
    results = {k: v.analyze() for k, v in analyzers.items()}
    return results
```

---

## 5. 实施阶段

### 5.1 阶段划分

```
═══════════════════════════════════════════════════════════════════════
              v2 实施 5 阶段
═══════════════════════════════════════════════════════════════════════

Phase 1: 基础架构 (1 周)
├── 创建 src/analyzer/ 目录
├── 实现 BaseAnalyzer 抽象类
├── 实现 AnalysisResult 数据类
└── 单元测试覆盖

Phase 2: 国内段迁移 (1 周)
├── 实现 DomesticAnalyzer（基于现有 generator）
├── Streamlit Page 1 (国内分析)
└── 集成测试

Phase 3: 国际段 + 市场化段 (2 周)
├── 实现 InternationalAnalyzer（基于分析框架第 15 节）
├── 实现 MarketTradingAnalyzer（基于分析框架第 16 节）
├── 汇率采集器（如需要）
├── Streamlit Page 2-3
└── 集成测试

Phase 4: 碳资产段 + Streamlit 完善 (1 周)
├── 实现 EnvironmentalAnalyzer（基于分析框架第 17 节）
├── Streamlit Page 4-5
├── 报告生成导出
└── 完整 E2E 测试

Phase 5: 优化与文档 (1 周)
├── 性能优化（缓存、懒加载）
├── UI/UX 调优
├── 用户文档
└── 部署文档

═══════════════════════════════════════════════════════════════════════
  合计: 6 周 = 1.5 个月
═══════════════════════════════════════════════════════════════════════
```

### 5.2 阶段交付物

| Phase | 代码 | 文档 | 可演示 |
|-------|------|------|--------|
| 1 | `src/analyzer/base.py` | 本设计文档 | ❌ |
| 2 | `domestic.py` + Page 1 | - | ✅ 国内段 |
| 3 | `international.py` + `market_trading.py` + Page 2-3 | - | ✅ 国际+市场化 |
| 4 | `environmental.py` + Page 4-5 | 用户指南 | ✅ 全功能 |
| 5 | 优化 | 部署文档 | ✅ 生产可用 |

### 5.3 测试策略

```
单元测试 (test_analyzer/)
├── test_base.py          BaseAnalyzer 接口测试
├── test_domestic.py      国内段验算
├── test_international.py 国际段三层归因
├── test_market_trading.py 市场化段现货增收
└── test_environmental.py 碳资产段库存估值

集成测试
├── test_pipeline.py      端到端流程
├── test_streamlit.py     UI 渲染测试
└── test_export.py        Word/Markdown 导出

性能测试
├── test_large_data.py    大数据量性能
└── test_cache.py         Streamlit 缓存效果
```

---

## 6. 与现有系统集成

### 6.1 保留不动的部分

| 模块 | 状态 | 说明 |
|------|------|------|
| `src/collector/` | 完全保留 | 数据采集层 v1 稳定 |
| `src/validator/` | 完全保留 | 数据校验 v1 稳定 |
| `src/storage/` | 完全保留 | JSON 存储 v1 稳定 |
| `scripts/run_pipeline.py` | 完全保留 | CLI 入口 |
| `data/dictionaries/` | 完全保留 | 实体词典 |
| `data/templates/` | 完全保留 | Word 模板 |

### 6.2 重构的部分

| 模块 | 状态 | 说明 |
|------|------|------|
| `src/generator/report_generator.py` | 包装 | 内部调用 Analyzer，结果传给 Word 生成器 |
| `src/generator/analysis_text.py` | 包装 | 调用 Analyzer 获取文字段落 |
| `scripts/generate_report.py` | 包装 | CLI 入口，内部用 Analyzer |

### 6.3 新增的部分

| 模块 | 状态 | 说明 |
|------|------|------|
| `src/analyzer/` | 新增 | 4 个 Analyzer + Base |
| `src/visualizer/` | 新增 | 图表 + 表格组件 |
| `streamlit_app/` | 新增 | Web UI 入口 |
| `tests/test_analyzer/` | 新增 | 分析层测试 |

### 6.4 向后兼容保证

```python
# scripts/run_pipeline.py 改造示例

# 旧版本（v1）
def run_pipeline_v1(week, year):
    data = collect(week, year)
    validate(data)
    report = generate_report(data)  # 直接生成
    return report


# 新版本（v2，保持 CLI 入口不变）
def run_pipeline_v2(week, year):
    # 数据采集 - 不变
    data = collect(week, year)
    validate(data)

    # 分析 - 新增
    analyzers = run_analyzers(data)

    # 生成报告 - 内部使用 analyzers
    report = generate_report(data, analyzers)
    return report
```

---

## 7. 风险与权衡

### 7.1 已识别风险

| 风险 | 影响 | 缓解策略 |
|------|------|---------|
| Streamlit 性能瓶颈 | 大数据量时卡顿 | @st.cache_data + 分页加载 |
| 多 Analyzer 状态同步 | 并发问题 | 串行执行 + session_state 缓存 |
| Word 模板兼容性 | 模板与 Analyzer 输出不匹配 | 严格遵循 docxtpl 变量约定 |
| 数据格式变化 | 周报格式调整时 Analyzer 失效 | 输入校验 + 优雅降级 |
| 部署复杂 | Streamlit 服务器配置 | 单文件部署 + Docker |

### 7.2 关键权衡

| 权衡 | 选择 | 备选 | 理由 |
|------|------|------|------|
| 重写 vs 增量 | **增量** | 完全重写 | 保护现有投资 |
| 单体 vs 微服务 | **单体** | 拆分多个服务 | 内部工具，规模小 |
| 同步 vs 异步 | **同步** | 异步任务队列 | 响应时间可接受 |
| 缓存粒度 | **整周缓存** | 细粒度缓存 | 周数据不频繁变化 |
| 图表库 | **Plotly** | Matplotlib/Altair | 交互性更好 |

### 7.3 非目标（明确不做）

- ❌ 用户权限管理（内部工具）
- ❌ 实时数据推送（周报非实时）
- ❌ 移动端适配（仅桌面浏览器）
- ❌ 多语言（仅中文）
- ❌ 复杂 BI 报表（仅周报分析）

---

## 8. 验收标准

### 8.1 功能验收

- [ ] 4 个 Analyzer 全部实现
- [ ] 8 段实战全部自动化
- [ ] Streamlit 5 页全部可访问
- [ ] 数据上传 → 分析 → 展示 流程跑通
- [ ] Word 报告导出功能正常
- [ ] 关键数字勾稽 100% 通过

### 8.2 性能验收

- [ ] 单周数据分析 < 5 秒
- [ ] Streamlit 首屏 < 3 秒
- [ ] Word 生成 < 10 秒
- [ ] 内存占用 < 500 MB

### 8.3 质量验收

- [ ] 单元测试覆盖率 > 80%
- [ ] 关键业务逻辑 100% 覆盖
- [ ] 文档完整（设计 + 用户 + API）
- [ ] 代码风格统一（PEP 8 + 项目规范）

---

## 9. 版本历史

| 版本 | 日期 | 说明 |
|---|---|---|
| v1.0 | 2026-06-06 | 初版：5 层架构 + 4 Analyzer + Streamlit 5 页 + 5 阶段实施 + 与现有系统集成 |
