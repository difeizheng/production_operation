# 周报自动化实施计划

> 项目代号：Weekly Report Automation
> 策略：渐进式（先实体词典，验证后考虑知识图谱）
> 目标：Excel → JSON → Word 周报生成 + 智能能力预留

---

## Phase 0：项目初始化（准备工作）

**目标**：搭建项目骨架，确认业务口径

**时间**：1 天

### 任务清单

| ID | 任务 | 产出 | 工时 |
|----|------|------|------|
| 0.1 | 创建项目目录结构 | 文件夹结构 | 0.5h |
| 0.2 | 初始化 Git 仓库 | `.git/` | 0.5h |
| 0.3 | 编写 README | `README.md` | 1h |
| 0.4 | 确认数据口径 | `docs/business/data_definition.md` | 2h |
| 0.5 | 设计 JSON Schema 初版 | `data/schema/weekly_data.schema.json` | 2h |
| 0.6 | 设计实体词典初版 | `data/dictionaries/*.json` | 1h |
| 0.7 | 创建空的 knowledge 模块 | `src/knowledge/__init__.py` | 0.5h |
| 0.8 | 编写项目依赖文件 | `requirements.txt` | 0.5h |

### 技术要点

```
目录结构：
production_operation/
├── data/
│   ├── schema/
│   ├── dictionaries/
│   ├── templates/
│   ├── raw/
│   └── processed/
├── src/
│   ├── collector/
│   ├── validator/
│   ├── storage/
│   ├── generator/
│   ├── knowledge/        # 预留图谱模块
│   └── utils/
├── scripts/
├── tests/
├── docs/
│   ├── analysis/
│   ├── design/
│   └── business/
└── archive/
```

### JSON Schema 设计要点（图谱兼容）

```json
{
  "meta": {
    "year": {"type": "integer"},
    "week": {"type": "integer"},
    "start_date": {"type": "string", "format": "date"},
    "end_date": {"type": "string", "format": "date"},
    "extracted_at": {"type": "string", "format": "date-time"},
    "source_file": {"type": "string"},
    "version": {"type": "string", "default": "1.0"}
  },
  "organizations": {
    "type": "object",
    "additionalProperties": {
      "$ref": "#/definitions/organization"
    }
  },
  "definitions": {
    "organization": {
      "type": "object",
      "properties": {
        "id": {"type": "string"},              // 预留图谱 ID
        "full_name": {"type": "string"},
        "type": {"type": "string"},            // domestic/international
        "parent": {"type": "string"},          // 预留层级关系
        "电力销售": {"$ref": "#/definitions/power_sales"},
        "市场化交易": {"$ref": "#/definitions/market_trade"},
        "绿证CCER": {"$ref": "#/definitions/green_cert"}
      }
    },
    "power_sales": {
      "type": "object",
      "properties": {
        "国内": {"$ref": "#/definitions/region_data"},
        "国际": {"$ref": "#/definitions/region_data"}
      }
    },
    "region_data": {
      "type": "object",
      "properties": {
        "电量": {"$ref": "#/definitions/metric_by_energy"},
        "电价": {"$ref": "#/definitions/metric_by_energy"},
        "电费": {"$ref": "#/definitions/metric_by_energy"},
        "同比": {"$ref": "#/definitions/change_data"},
        "环比": {"$ref": "#/definitions/change_data"}
      }
    },
    "metric_by_energy": {
      "type": "object",
      "properties": {
        "总量": {"type": "number"},
        "水电": {"type": "number"},
        "风电": {"type": "number"},
        "光伏": {"type": "number"},
        "火电": {"type": "number"},
        "source": {"$ref": "#/definitions/data_source"}  // 数据来源追溯
      }
    },
    "data_source": {
      "type": "object",
      "properties": {
        "file": {"type": "string"},
        "sheet": {"type": "string"},
        "cell": {"type": "string"},
        "extracted_at": {"type": "string"}
      }
    }
  }
}
```

### 实体词典设计要点（图谱兼容）

```json
// organizations.json
{
  "长江电力": {
    "id": "org_001",
    "full_name": "中国长江电力股份有限公司",
    "type": "domestic",
    "parent": "三峡集团",
    "region": "国内",
    "description": "主营水电发电，拥有三峡、葛洲坝等电站"
  },
  "三峡能源": {
    "id": "org_002",
    "full_name": "中国三峡新能源（集团）股份有限公司",
    "type": "domestic",
    "parent": "三峡集团",
    "region": "国内",
    "description": "主营风电、光伏等新能源发电"
  }
}

// energy_types.json - 带层级
{
  "水电": {
    "id": "energy_001",
    "code": "hydro",
    "category": "清洁能源",
    "parent": "清洁能源",
    "description": "水力发电"
  },
  "清洁能源": {
    "id": "energy_cat_001",
    "is_category": true,
    "children": ["水电", "风电", "光伏"]
  }
}

// synonyms.json
{
  "水力发电": "水电",
  "上网电量": "电量",
  "平均电价": "电价",
  "发电收入": "电费",
  "清洁能源发电": "清洁能源"
}
```

### 数据口径确认文档要点

```markdown
# 数据口径定义

## 电量
- 定义：上网电量（而非发电量）
- 单位：万千瓦时（Excel中），报告转换为亿千瓦时
- 数据源：国内数据填报表

## 电价
- 定义：平均上网电价（含税）
- 单位：元/千瓦时
- 计算方式：电费/电量

## 同比
- 定义：与去年同期对比
- 计算方式：(本期-去年同期)/去年同期
- 表述方式："同比提高3.2%"（正数）/"同比下降3.2%"（负数）

## 环比
- 定义：与上周对比
- 计算方式：(本期-上周)/上周

## 组织范围
- 国内：长江电力、三峡能源、湖北能源等18个
- 国际：长电国际、三峡国际等
```

### 交付物

- [ ] 项目目录结构完整
- [ ] Git 仓库初始化
- [ ] README 文档
- [ ] JSON Schema 定义文件
- [ ] 实体词典文件（organizations、energy_types、metrics、synonyms）
- [ ] 数据口径确认文档
- [ ] requirements.txt

### 验收标准

- [ ] 目录结构与计划一致
- [ ] JSON Schema 通过 jsonschema 库验证
- [ ] 实体词典包含所有组织和能源类型
- [ ] 数据口径与用户确认签字

---

## Phase 1：数据采集与标准化

**目标**：完成 Excel → JSON → 验证流程，用真实数据测试

**时间**：5-7 天（含缓冲）

### 任务清单

| ID | 任务 | 产出 | 工时 |
|----|------|------|------|
| 1.1 | Excel 采集器框架 | `src/collector/excel_collector.py` | 4h |
| 1.2 | 语义定位解析器 | `src/collector/semantic_parser.py` | 6h |
| 1.3 | 数据来源追溯实现 | 采集器增加 source 字段 | 2h |
| 1.4 | Schema 验证器 | `src/validator/schema_validator.py` | 3h |
| 1.5 | 数据清洗器 | `src/validator/data_cleaner.py` | 3h |
| 1.6 | 缺失数据处理策略 | 配置 + 实现 | 2h |
| 1.7 | JSON 存储模块 | `src/storage/json_store.py` | 2h |
| 1.8 | 单元测试 | `tests/test_collector.py` | 4h |
| 1.9 | **真实数据测试** | 用 21/22 周数据 | 4h |
| 1.10 | 问题修复 | 根据真实数据问题修复 | 4h（缓冲）|
| 1.11 | 采集脚本入口 | `scripts/extract_data.py` | 1h |
| 1.12 | 采集日志规范化 | logging 配置 | 1h |

### 技术要点

#### 语义定位解析器核心逻辑

```python
# src/collector/semantic_parser.py
from typing import Dict, List, Optional
import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)

class SemanticParser:
    """语义定位解析器 - 不依赖固定行列位置"""
    
    def __init__(self, dictionary_path: str):
        self.orgs = self._load_dict(f"{dictionary_path}/organizations.json")
        self.energy_types = self._load_dict(f"{dictionary_path}/energy_types.json")
        self.metrics = self._load_dict(f"{dictionary_path}/metrics.json")
        self.synonyms = self._load_dict(f"{dictionary_path}/synonyms.json")
    
    def _load_dict(self, path: str) -> dict:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    
    def _resolve_synonym(self, text: str) -> str:
        """同义词映射"""
        return self.synonyms.get(text, text)
    
    def find_org_row(self, ws) -> Dict[str, int]:
        """找组织名所在行"""
        org_rows = {}
        for row_idx, row in enumerate(ws.iter_rows(), start=1):
            for cell in row:
                text = str(cell.value) if cell.value else ""
                for org_name in self.orgs.keys():
                    if org_name in text:
                        org_rows[org_name] = row_idx
                        logger.debug(f"找到组织 '{org_name}' 在第 {row_idx} 行")
        return org_rows
    
    def find_header_columns(self, ws, header_row: int = 3) -> Dict[tuple, int]:
        """找表头列"""
        col_mapping = {}
        header = [cell.value for cell in ws[header_row]]
        
        for col_idx, cell_value in enumerate(header, start=1):
            if cell_value is None:
                continue
            header_text = str(cell_value)
            resolved_text = self._resolve_synonym(header_text)
            
            # 匹配能源类型 + 指标组合
            for energy in self.energy_types.keys():
                if energy in resolved_text or self._resolve_synonym(energy) in resolved_text:
                    for metric in self.metrics.keys():
                        if metric in resolved_text or self._resolve_synonym(metric) in resolved_text:
                            col_mapping[(energy, metric)] = col_idx
                            logger.debug(f"找到列 '{energy}.{metric}' 在第 {col_idx} 列")
        
        return col_mapping
    
    def parse_sheet(self, ws, sheet_name: str) -> dict:
        """解析单个 Sheet"""
        logger.info(f"开始解析 Sheet: {sheet_name}")
        
        org_rows = self.find_org_row(ws)
        col_mapping = self.find_header_columns(ws)
        
        data = {}
        for org_name, row_idx in org_rows.items():
            data[org_name] = {
                "id": self.orgs[org_name]["id"],
                "电力销售": {}
            }
            for (energy, metric), col_idx in col_mapping.items():
                value = ws.cell(row=row_idx, column=col_idx).value
                if energy not in data[org_name]["电力销售"]:
                    data[org_name]["电力销售"][energy] = {}
                data[org_name]["电力销售"][energy][metric] = {
                    "value": value,
                    "source": {
                        "sheet": sheet_name,
                        "cell": f"{self._col_to_letter(col_idx)}{row_idx}"
                    }
                }
        
        logger.info(f"完成解析，共 {len(data)} 个组织")
        return data
    
    def _col_to_letter(self, col: int) -> str:
        """列号转字母 (1 → A)"""
        result = ""
        while col > 0:
            col, remainder = divmod(col - 1, 26)
            result = chr(65 + remainder) + result
        return result
```

#### 数据清洗器

```python
# src/validator/data_cleaner.py
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_VALUES = {
    "电量": 0,
    "电价": 0,
    "电费": 0
}

class DataCleaner:
    def clean_value(self, value: Any, metric: str) -> Optional[float]:
        """清洗单个值"""
        if value is None:
            logger.warning(f"数据缺失，指标 '{metric}' 使用默认值 {DEFAULT_VALUES.get(metric, 0)}")
            return DEFAULT_VALUES.get(metric, None)
        
        # 处理字符串类型数字
        if isinstance(value, str):
            try:
                value = float(value.replace(',', '').strip())
            except ValueError:
                logger.error(f"无法解析值 '{value}'，指标 '{metric}'")
                return None
        
        # 处理负数（某些指标不应为负）
        if metric == "电量" and value < 0:
            logger.warning(f"电量为负数 {value}，已修正为 0")
            return 0
        
        return float(value)
    
    def clean_org_data(self, org_data: dict) -> dict:
        """清洗组织数据"""
        cleaned = {}
        for energy, metrics in org_data.get("电力销售", {}).items():
            cleaned[energy] = {}
            for metric, data in metrics.items():
                if isinstance(data, dict) and "value" in data:
                    cleaned[energy][metric] = {
                        "value": self.clean_value(data["value"], metric),
                        "source": data.get("source", {})
                    }
                else:
                    cleaned[energy][metric] = {
                        "value": self.clean_value(data, metric),
                        "source": {}
                    }
        return cleaned
```

#### 容错机制

```python
# src/collector/excel_collector.py
class ExcelCollector:
    def collect_all_sheets(self, file_path: str) -> dict:
        """采集所有 Sheet，部分失败不阻断整体"""
        results = {}
        errors = []
        
        wb = self._load_workbook(file_path)
        
        for sheet_name in self.SHEET_LIST:
            try:
                ws = wb[sheet_name]
                results[sheet_name] = self.parser.parse_sheet(ws, sheet_name)
                logger.info(f"Sheet '{sheet_name}' 采集成功")
            except Exception as e:
                logger.error(f"Sheet '{sheet_name}' 采集失败: {e}")
                errors.append({
                    "sheet": sheet_name,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                results[sheet_name] = None
        
        return {
            "data": results,
            "errors": errors,
            "success_rate": len([r for r in results.values() if r]) / len(self.SHEET_LIST)
        }
```

### 交付物

- [ ] Excel 采集器（支持语义定位）
- [ ] Schema 验证器
- [ ] 数据清洗器
- [ ] JSON 存储模块
- [ ] 单元测试（覆盖率 > 80%）
- [ ] 真实数据采集结果（21/22 周 JSON）
- [ ] 问题记录文档

### 验收标准

- [ ] 采集成功率 > 95%（真实数据）
- [ ] Schema 校验通过率 100%
- [ ] 数据缺失有明确处理策略
- [ ] 单元测试覆盖率 > 80%
- [ ] 真实数据采集日志完整
- [ ] 所有组织数据完整（18 个国内 + 国际）

### 风险与缓解

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| Excel 结构变化 | 采集失败 | 语义定位 + 同义词映射 + 日志告警 |
| 数据缺失 | 报告不完整 | 默认值策略 + 标记缺失 |
| 合并单元格 | 解析错误 | 特殊处理逻辑 + 测试覆盖 |
| 真实数据意外 | 时间延误 | 第 3 天引入真实数据 + 预留缓冲 |

---

## Phase 2：模板与报告生成

**目标**：完成 JSON → Word 周报，质量接近人工

**时间**：5-7 天（含缓冲）

### 任务清单

| ID | 任务 | 产出 | 工时 |
|----|------|------|------|
| 2.1 | Word 模板设计 | `data/templates/report_template.docx` | 4h |
| 2.2 | 模板标签与 Schema 对应文档 | `docs/design/template_mapping.md` | 2h |
| 2.3 | 模板引擎集成（docxtpl） | `src/generator/report_generator.py` | 4h |
| 2.4 | 数据转换器（JSON → 模板变量） | `src/generator/data_transformer.py` | 3h |
| 2.5 | 图表自动生成 | `src/generator/chart_builder.py` | 4h |
| 2.6 | 文字段落生成（数据解读） | `src/generator/text_generator.py` | 4h |
| 2.7 | Excel 导出器 | `src/generator/excel_exporter.py` | 2h |
| 2.8 | 单元测试 | `tests/test_generator.py` | 3h |
| 2.9 | **真实数据生成报告** | 用 21/22 周数据 | 3h |
| 2.10 | 与人工报告对比 | 对比分析文档 | 2h |
| 2.11 | 模板迭代优化 | 优化后的模板 | 4h（缓冲）|
| 2.12 | 生成脚本入口 | `scripts/generate_report.py` | 1h |

### 技术要点

#### Word 模板设计（docxtpl 标签）

```
模板结构：

{{meta.year}}年第{{meta.week}}周生产情况
（{{meta.start_date}}-{{meta.end_date}}）

一、上周销售情况

（一）电量销售情况

上周，集团公司合计上网电量{{power_sales.total}}亿千瓦时，
其中，国内上网电量{{power_sales.domestic}}亿千瓦时，
国际上网电量{{power_sales.international}}亿千瓦时。

上周，集团公司国内上网电量{{power_sales.domestic}}亿千瓦时，
同比{{power_sales.domestic_yoy_text}}，
主要原因是{{power_sales.domestic_yoy_reason}}。

[表格：分组织电量统计]
{%tr for org in org_list %}
{{org.name}}|{{org.power_total}}|{{org.price_avg}}|{{org.revenue}}
{%tr endfor %}

[图表：电量趋势]
{%chart power_trend %}

二、外部信息
...

三、重点工作情况
...

四、本周重点工作
...
```

#### 数据转换器

```python
# src/generator/data_transformer.py
class DataTransformer:
    """JSON 数据 → 模板变量"""
    
    def transform(self, json_data: dict) -> dict:
        """转换为模板变量"""
        template_vars = {
            "meta": self._transform_meta(json_data["meta"]),
            "power_sales": self._transform_power_sales(json_data),
            "org_list": self._transform_org_list(json_data),
            "market_trade": self._transform_market(json_data),
            "green_cert": self._transform_green_cert(json_data),
            "external_info": self._transform_external(json_data),
            "key_work": self._transform_key_work(json_data),
        }
        return template_vars
    
    def _transform_meta(self, meta: dict) -> dict:
        return {
            "year": meta["year"],
            "week": meta["week"],
            "start_date": meta["start_date"],
            "end_date": meta["end_date"],
        }
    
    def _transform_power_sales(self, data: dict) -> dict:
        """电力销售数据转换"""
        domestic = sum(
            org["电力销售"]["国内"]["电量"]["总量"]
            for org in data["organizations"].values()
            if org["type"] == "domestic"
        )
        
        return {
            "total": self._format_number(data["汇总"]["电量"]["总量"] / 10000),  # 万 → 亿
            "domestic": self._format_number(domestic / 10000),
            "international": self._format_number(data["汇总"]["国际"]["电量"] / 10000),
            "domestic_yoy_text": self._format_change(data["汇总"]["国内"]["同比"]["电量"]),
            "domestic_yoy_reason": self._generate_reason(data, "国内", "电量"),
        }
    
    def _format_change(self, change: float) -> str:
        """格式化同比环比"""
        if change > 0:
            return f"提高{change:.1f}%"
        elif change < 0:
            return f"下降{abs(change):.1f}%"
        else:
            return "持平"
    
    def _generate_reason(self, data: dict, region: str, metric: str) -> str:
        """生成变化原因文字"""
        # 简化版：直接拼接主要因素
        # 后续可用 LLM 生成更智能的解读
        factors = []
        for energy in ["水电", "风电", "光伏"]:
            change = data["汇总"][region][energy]["同比"][metric]
            if abs(change) > 1:
                factors.append(f"{energy}{self._format_change(change)}")
        
        if factors:
            return "主要原因是" + "、".join(factors)
        return "无显著变化因素"
```

#### 图表生成

```python
# src/generator/chart_builder.py
import matplotlib.pyplot as plt
from io import BytesIO

class ChartBuilder:
    def build_power_trend_chart(self, data: dict) -> BytesIO:
        """生成电量趋势图"""
        weeks = [w["week"] for w in data["history"]]
        power = [w["汇总"]["电量"]["总量"] for w in data["history"]]
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(weeks, power, marker='o')
        ax.set_title('电量趋势')
        ax.set_xlabel('周')
        ax.set_ylabel('电量（万千瓦时）')
        
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150)
        buf.seek(0)
        plt.close()
        
        return buf
    
    def build_org_comparison_chart(self, data: dict) -> BytesIO:
        """生成组织对比图"""
        orgs = list(data["organizations"].keys())
        power = [org["电力销售"]["国内"]["电量"]["总量"] for org in data["organizations"].values()]
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.bar(orgs, power)
        ax.set_title('各组织电量对比')
        
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150)
        buf.seek(0)
        plt.close()
        
        return buf
```

### 交付物

- [ ] Word 模板文件
- [ ] 模板标签与 Schema 对应文档
- [ ] 报告生成器
- [ ] 图表生成器
- [ ] 数据转换器
- [ ] Excel 导出器
- [ ] 单元测试
- [ ] 真实数据生成报告（Word）
- [ ] 与人工报告对比分析文档

### 验收标准

- [ ] Word 报告生成成功率 > 95%
- [ ] 报告内容完整度 > 90%（对比人工报告）
- [ ] 所有表格正确填充
- [ ] 图表正确嵌入
- [ ] 数据解读文字准确
- [ ] 格式与模板一致

### 风险与缓解

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| 模板与数据不匹配 | 生成失败 | 标签对应文档 + 测试覆盖 |
| 图表嵌入失败 | 报告不完整 | 备用方案：图表单独生成 |
| 文字解读不准确 | 质量问题 | 人工审核机制 + LLM 辅助（未来）|
| 格式异常 | 用户体验差 | 真实数据测试 + 对比验证 |

---

## Phase 3：用户验证与优化

**目标**：真实数据无错，用户验收通过

**时间**：3-5 天（含缓冲）

### 任务清单

| ID | 任务 | 产出 | 工时 |
|----|------|------|------|
| 3.1 | 处理完整真实数据 | 21/22 周完整 JSON + Word | 4h |
| 3.2 | 数据准确性校验 | 校验报告 | 2h |
| 3.3 | 与人工报告详细对比 | 对比分析文档 | 3h |
| 3.4 | 用户试用 | 用户反馈记录 | 3h |
| 3.5 | 问题清单整理 | `docs/issues/phase3_issues.md` | 1h |
| 3.6 | 模板迭代优化 | 优化版本 | 4h |
| 3.7 | 采集器迭代优化 | 优化版本 | 3h |
| 3.8 | 用户验收 | 验收签字 | 2h |
| 3.9 | 端到端流程脚本 | `scripts/run_pipeline.py` | 2h |
| 3.10 | 用户指南编写 | `docs/user_guide/usage.md` | 2h |
| 3.11 | 归档整理脚本 | `scripts/archive.py` | 1h |

### 用户验收清单

```markdown
## 用户验收清单

### 功能验收
- [ ] 能采集完整数据（18 个国内组织 + 国际）
- [ ] JSON 校验通过
- [ ] Word 报告生成成功
- [ ] 报告内容完整（所有章节）
- [ ] 表格数据准确
- [ ] 图表正确显示

### 数据准确性验收
- [ ] 长江电力数据准确（抽查）
- [ ] 三峡能源数据准确（抽查）
- [ ] 湖北能源数据准确（抽查）
- [ ] 合计汇总数据准确
- [ ] 同比环比计算正确

### 质量验收
- [ ] 与人工报告对比（相似度 > 90%）
- [ ] 文字表述准确
- [ ] 格式符合要求
- [ ] 无明显错误

### 用户试用
- [ ] 用户能独立操作采集
- [ ] 用户能独立操作生成
- [ ] 用户反馈记录完整
- [ ] 用户验收签字
```

### 交付物

- [ ] 完整真实数据 JSON
- [ ] 完整真实数据 Word 报告
- [ ] 数据准确性校验报告
- [ ] 与人工报告对比分析文档
- [ ] 用户反馈记录
- [ ] 用户验收签字文档
- [ ] 用户指南
- [ ] 端到端流程脚本
- [ ] 归档脚本

### 验收标准

- [ ] 真实数据采集无错
- [ ] 数据准确率 100%（抽查验证）
- [ ] 报告质量相似度 > 90%
- [ ] 用户验收签字通过
- [ ] 用户能独立操作
- [ ] 文档完整

---

## Phase 4：智能能力 PoC（可选）

**目标**：验证 LLM 与智能能力价值，决定是否投入

**时间**：5-10 天

### 任务清单

| ID | 任务 | 产出 | 工时 |
|----|------|------|------|
| 4.1 | LLM 问答 PoC 设计 | 设计文档 | 2h |
| 4.2 | LLM 接口集成 | `src/llm/llm_client.py` | 4h |
| 4.3 | 问答引擎实现 | `src/llm/qa_engine.py` | 8h |
| 4.4 | 异常检测算法 | `src/analysis/anomaly_detector.py` | 6h |
| 4.5 | 趋势分析算法 | `src/analysis/trend_analyzer.py` | 6h |
| 4.6 | 业务洞察生成 | `src/analysis/insight_generator.py` | 6h |
| 4.7 | 智能能力测试 | 测试报告 | 4h |
| 4.8 | 成本效益评估 | 评估报告 | 2h |
| 4.9 | 智能能力文档 | 能力说明文档 | 2h |

### 技术要点

#### LLM 问答引擎

```python
# src/llm/qa_engine.py
class QAEngine:
    def __init__(self, llm_client, json_data):
        self.llm = llm_client
        self.data = json_data
    
    def answer(self, question: str) -> str:
        """回答业务问题"""
        # 1. 检索相关数据
        context = self._retrieve_context(question)
        
        # 2. 构建提示词
        prompt = f"""
        你是电力营销数据分析助手。
        
        用户问题：{question}
        
        相关数据：
        {json.dumps(context, ensure_ascii=False, indent=2)}
        
        请基于数据回答问题，给出具体数值和分析。
        """
        
        # 3. 调用 LLM
        response = self.llm.generate(prompt)
        
        return response
    
    def _retrieve_context(self, question: str) -> dict:
        """检索相关问题数据"""
        # 简化版：关键词匹配
        keywords = self._extract_keywords(question)
        context = {}
        
        for org in self.data["organizations"]:
            if any(kw in org or kw in question for kw in keywords):
                context[org] = self.data["organizations"][org]
        
        return context
```

#### 异常检测

```python
# src/analysis/anomaly_detector.py
class AnomalyDetector:
    def detect_price_anomaly(self, current_data: dict, history_data: list) -> list:
        """检测电价异常"""
        anomalies = []
        
        for org_name, org_data in current_data["organizations"].items():
            current_price = org_data["电力销售"]["国内"]["电价"]["总量"]
            
            # 计算历史均值和标准差
            history_prices = [
                h["organizations"][org_name]["电力销售"]["国内"]["电价"]["总量"]
                for h in history_data
                if org_name in h["organizations"]
            ]
            
            if history_prices:
                avg = sum(history_prices) / len(history_prices)
                std = (sum((p - avg)**2 for p in history_prices) / len(history_prices)) ** 0.5
                
                # 超过 2 倍标准差视为异常
                if std > 0 and abs(current_price - avg) > 2 * std:
                    anomalies.append({
                        "org": org_name,
                        "metric": "电价",
                        "current": current_price,
                        "avg": avg,
                        "deviation": (current_price - avg) / std,
                        "severity": "high" if abs(current_price - avg) > 3 * std else "medium"
                    })
        
        return anomalies
```

### 验收标准

- [ ] LLM 问答准确率 > 80%（人工评估）
- [ ] 异常检测发现真实异常（至少 1 个）
- [ ] 趋势分析有参考价值
- [ ] 成本效益评估完成
- [ ] 决策文档：是否继续投入

### 决策点

Phase 4 结束时需决策：

| 指标 | 继续投入 | 停止投入 |
|-----|---------|---------|
| LLM 问答准确率 | > 80% | < 60% |
| 异常检测价值 | 发现真实问题 | 无价值 |
| 成本 | 可接受 | 过高 |
| 用户反馈 | 正面 | 负面 |

---

## Phase 5：知识图谱升级（未来）

**目标**：从实体词典升级到知识图谱

**触发条件**：
- 多数据源需求
- 复杂推理需求
- 组织关系查询需求

**时间**：3-5 天

### 任务清单

| ID | 任务 | 产出 | 工时 |
|----|------|------|------|
| 5.1 | Ontology 定义 | `src/knowledge/ontology.py` | 4h |
| 5.2 | Neo4j 部署 | 部署文档 | 4h |
| 5.3 | JSON → 图谱导入 | `src/knowledge/graph_builder.py` | 6h |
| 5.4 | 关系定义扩展 | 实体关系文档 | 4h |
| 5.5 | 图谱查询接口 | `src/knowledge/graph_query.py` | 6h |
| 5.6 | 图谱问答集成 | 与 LLM 集成 | 4h |
| 5.7 | 图谱文档 | 使用文档 | 2h |

### Ontology 定义示例

```python
# src/knowledge/ontology.py

# 实体类型
ENTITY_TYPES = {
    "Organization": {
        "properties": ["id", "name", "full_name", "type", "parent", "region"],
        "relationships": ["HAS_ENERGY_TYPE", "HAS_METRIC", "BELONGS_TO"]
    },
    "EnergyType": {
        "properties": ["id", "name", "code", "category", "parent"],
        "relationships": ["HAS_METRIC"]
    },
    "Metric": {
        "properties": ["id", "name", "unit", "category"],
        "relationships": []
    },
    "Week": {
        "properties": ["id", "year", "week_number", "start_date", "end_date"],
        "relationships": ["CONTAINS_DATA"]
    }
}

# 关系类型
RELATION_TYPES = {
    "HAS_ENERGY_TYPE": {
        "from": "Organization",
        "to": "EnergyType",
        "properties": ["week", "value"]
    },
    "HAS_METRIC": {
        "from": ["Organization", "EnergyType"],
        "to": "Metric",
        "properties": ["week", "value", "source"]
    },
    "BELONGS_TO": {
        "from": "Organization",
        "to": "Organization",
        "properties": ["relation_type"]  # 子公司、控股等
    }
}
```

### 验收标准

- [ ] Ontology 定义完整
- [ ] Neo4j 部署成功
- [ ] 数据导入成功
- [ ] 图谱查询可用
- [ ] 图谱问答准确率 > 85%

---

## 时间规划总览

```
Week 1: Phase 0 + Phase 1 启动
Week 2: Phase 1 完成 + Phase 2 启动
Week 3: Phase 2 完成 + Phase 3 启动
Week 4: Phase 3 完成 + 决策点
Week 5-6: Phase 4（可选）
Week 7+: Phase 5（按需触发）
```

**MVP 时间**：约 3-4 周
**完整方案时间**：5-7 周（含智能能力）

---

## 关键决策点

### 决策点 1：Phase 1 结束

**决策内容**：数据采集是否成功？

| 指标 | 继续 | 回退优化 |
|-----|------|---------|
| 采集成功率 | > 95% | < 90% |
| Schema 校验 | 100% 通过 | 有失败 |
| 真实数据问题 | 已解决 | 未解决 |

### 决策点 2：Phase 3 结束

**决策内容**：用户验收是否通过？

| 指标 | 继续 | 回退优化 |
|-----|------|---------|
| 用户验收 | 签字通过 | 不通过 |
| 数据准确率 | 100% | 有错误 |
| 报告相似度 | > 90% | < 80% |

### 决策点 3：Phase 4 结束

**决策内容**：是否继续投入智能能力？

| 指标 | 继续 | 停止 |
|-----|------|------|
| LLM 问答准确率 | > 80% | < 60% |
| 成本 | 可接受 | 过高 |
| 用户反馈 | 正面 | 负面 |

### 决策点 4：触发知识图谱

**触发条件**：
- 需接入多数据源（API、数据库）
- 需复杂推理（"为什么"、"会怎样"）
- 需组织关系查询
- 需知识沉淀

---

## 里程碑与交付物总览

| 阶段 | 里程碑 | 核心交付物 |
|-----|--------|-----------|
| Phase 0 | 项目骨架完成 | 目录结构 + Schema + 词典 + 口径文档 |
| Phase 1 | 数据采集可用 | 采集器 + 验证器 + JSON 数据 + 测试 |
| Phase 2 | 报告生成可用 | 模板 + 生成器 + Word 报告 + 测试 |
| Phase 3 | MVP 验收通过 | 完整报告 + 用户验收 + 用户指南 |
| Phase 4 | 智能能力评估 | LLM 问答 + 异常检测 + 评估报告 |
| Phase 5 | 知识图谱上线 | Neo4j + Ontology + 图谱查询 |

---

## 变更日志

| 日期 | 版本 | 变更 |
|-----|------|------|
| 2026-06-04 | v1.0 | 初稿，完成 5 个 Phase 实施计划 |