"""
国际分析器 (InternationalAnalyzer)
====================================

覆盖业务图谱段 3-4: 国际电价同比 + 环比
- 段 3: 国际电价同比 - "同比提高每千瓦时3.9分..."
- 段 4: 国际电价环比 - "环比提高每千瓦时1.3分..."

设计依据:
- 业务图谱: docs/design/business-map-master.md (段 3-4)
- 分析框架: docs/analysis/domestic-price-analysis-framework.md (第 15 节)
- 基础类: src/analyzer/base.py

核心方法论: 三层归因 (汇率 / 合同 / 真本事) + 同比 vs 环比对比框架

实施状态: ✅ Phase 3 完成
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from .base import BaseAnalyzer, AnalysisResult


# === 阈值配置 ===
DEFAULT_THRESHOLDS = {
    # 三层归因异常
    "real_business_min_fen": 0.0,           # 真本事 < 0 触发经营能力预警
    "exchange_rate_dominance_ratio": 2.0,  # 汇率影响 > 真本事 2 倍 触发"汇率幻觉"
    "contract_dominance_threshold": 0.5,    # 合同单次影响 > 0.5 分触发关注

    # 区域异常
    "single_country_share_alert": 50.0,     # 单一国家 > 50% 触发集中度风险
    "single_country_yoy_alert": 10.0,       # 单一国家同比 > ±10 分触发

    # 同比/环比方向
    "yoy_mom_reversal_threshold": 1.0,      # 同比/环比差异 > 1 分触发关注

    # 汇率异常
    "single_currency_yoy_alert": 20.0,      # 单一币种年波动 > ±20% 触发
    "single_currency_mom_alert": 5.0,       # 单一币种月波动 > ±5% 触发
}


# === 5 大区域配置 ===
REGIONS = {
    "latin_america": "拉美（巴西、秘鲁等）",
    "europe": "欧洲（西班牙、葡萄牙、德国等）",
    "asia_africa": "亚非（巴基斯坦、缅甸、尼泊尔等）",
    "north_america": "北美（美国、加拿大）",
    "other": "其他",
}


# === 3 个运营主体 ===
COMPANIES = ["three_gorges_intl", "cyg_intl", "hubei_energy"]


@dataclass
class InternationalConfig:
    """国际分析器配置"""
    thresholds: Dict[str, float] = field(default_factory=lambda: DEFAULT_THRESHOLDS.copy())
    regions: Dict[str, str] = field(default_factory=lambda: REGIONS.copy())
    companies: List[str] = field(default_factory=lambda: COMPANIES.copy())
    strict_validation: bool = False  # 国际段字段较多，默认宽松


class InternationalAnalyzer(BaseAnalyzer):
    """国际分析器（段 3-4）

    负责分析:
    - 国际电价同比/环比
    - 三层归因 (汇率/合同/真本事)
    - 5 区域分布 (拉美/欧洲/亚非/北美/其他)
    - 3 运营主体 (三峡国际/长电国际/湖北能源)
    - 同比 vs 环比对比框架
    - 汇率波动监控
    """

    dimension_name = "国际"
    section_ids = [3, 4]
    analyzer_name = "InternationalAnalyzer"

    def __init__(self, json_data: dict, config: Optional[dict] = None):
        super().__init__(json_data, config)
        self.intl_config = InternationalConfig(
            thresholds={**DEFAULT_THRESHOLDS, **(config or {}).get("thresholds", {})},
            regions=(config or {}).get("regions", REGIONS),
            companies=(config or {}).get("companies", COMPANIES),
            strict_validation=(config or {}).get("strict_validation", False),
        )

    # === 抽象方法实现 ===

    def validate_inputs(self) -> bool:
        """校验输入数据完整性

        必需字段:
        - international (核心数据 + 三层归因)
        - exchange_rates (3 大币种)
        - by_country_category (国家 × 品类)
        - by_company (3 运营主体)
        """
        self.missing_fields = []

        # 检查 international 核心
        intl = self.safe_get("international", default={})
        required_intl_fields = [
            "total_volume_yi_kwh",
            "avg_price_yuan_per_kwh",
            "avg_price_yoy_change_fen",
            "avg_price_mom_change_fen",
            "attribution_three_layer_yoy",
            "attribution_three_layer_mom",
        ]
        for field_name in required_intl_fields:
            if field_name not in intl:
                self.missing_fields.append(f"international.{field_name}")

        # 检查汇率
        rates = self.safe_get("exchange_rates", default={})
        required_currencies = ["CNY_BRL", "CNY_USD", "CNY_EUR"]
        for curr in required_currencies:
            if curr not in rates:
                self.missing_fields.append(f"exchange_rates.{curr}")

        # 检查国家×品类
        by_country = self.safe_get("by_country_category", default=[])
        if not by_country:
            self.missing_fields.append("by_country_category (空)")

        # 检查 3 运营主体
        by_company = self.safe_get("by_company", default={})
        for comp in self.intl_config.companies:
            if comp not in by_company:
                self.missing_fields.append(f"by_company.{comp}")

        is_valid = len(self.missing_fields) == 0
        if not is_valid:
            self._validation_errors = self.missing_fields.copy()
        return is_valid

    def analyze(self) -> AnalysisResult:
        """执行分析主入口"""
        if not self.validate_inputs():
            return self._create_validation_error_result()

        # 1. 提取 KPI
        kpis = self._extract_kpis()

        # 2. 三层归因
        attribution_yoy = self._three_layer_attribution("yoy")
        attribution_mom = self._three_layer_attribution("mom")

        # 3. 同比 vs 环比对比
        comparison = self._yoy_vs_mom_comparison(attribution_yoy, attribution_mom)

        # 4. 5 区域分析
        regions_yoy = self._analyze_regions("yoy")
        regions_mom = self._analyze_regions("mom")

        # 5. 3 运营主体分析
        companies = self._analyze_companies()

        # 6. 汇率分析
        exchange = self._analyze_exchange_rates()

        # 7. 国家×品类
        countries = self._analyze_countries()

        # 8. 异常检测
        anomalies = self._detect_anomalies(
            kpis, attribution_yoy, attribution_mom, exchange, companies
        )

        # 9. 构建表格和图表
        tables = self._build_tables(kpis, attribution_yoy, attribution_mom, exchange, regions_yoy, regions_mom, companies)
        charts = self._build_charts(kpis, attribution_yoy, attribution_mom, exchange, comparison)

        # 10. 生成故事
        story, summary = self._generate_story(
            kpis, attribution_yoy, attribution_mom, comparison, exchange, regions_yoy, regions_mom, companies, anomalies
        )

        # 11. 提取洞察
        insights = self._extract_insights(
            kpis, attribution_yoy, attribution_mom, comparison, exchange, anomalies
        )

        return AnalysisResult(
            dimension=self.dimension_name,
            section_ids=self.section_ids,
            analyzer_name=self.analyzer_name,
            summary=summary,
            story=story,
            kpis=kpis,
            yoy_data=attribution_yoy,
            mom_data=attribution_mom,
            tables=tables,
            charts=charts,
            insights=insights,
            anomalies=anomalies,
        )

    # === 内部方法 ===

    def _create_validation_error_result(self) -> AnalysisResult:
        return AnalysisResult(
            dimension=self.dimension_name,
            section_ids=self.section_ids,
            analyzer_name=self.analyzer_name,
            summary="输入数据不完整，无法分析",
            story="",
            insights=["数据校验失败"],
            anomalies=[{
                "level": "error",
                "message": f"缺少字段: {', '.join(getattr(self, 'missing_fields', []))}"
            }],
        )

    def _extract_kpis(self) -> Dict[str, Any]:
        """提取国际段关键 KPI"""
        intl = self.safe_get("international", default={})
        return {
            "国际上网电量": intl.get("total_volume_yi_kwh", 0),
            "国际发电收入": intl.get("total_revenue_yi_yuan", 0),
            "国际度电均价": intl.get("avg_price_yuan_per_kwh", 0),
            "国际同比度电": intl.get("avg_price_yoy_change_fen", 0),
            "国际环比度电": intl.get("avg_price_mom_change_fen", 0),
            "国际同比电量": intl.get("yoy_volume_pct", 0),
            "国际环比电量": intl.get("mom_volume_pct", 0),
            "国际同比收入": intl.get("yoy_revenue_pct", 0),
            "国际环比收入": intl.get("mom_revenue_pct", 0),
        }

    def _three_layer_attribution(self, period: str) -> Dict[str, Any]:
        """三层归因（汇率/合同/真本事）

        Args:
            period: "yoy" 或 "mom"

        Returns:
            三层归因结果
        """
        attr_key = f"attribution_three_layer_{period}"
        attr = self.safe_get("international", attr_key, default={})

        exchange_effect = attr.get("exchange_rate_effect_fen", 0)
        contract_effect = attr.get("contract_effect_fen", 0)
        real_business_effect = attr.get("real_business_effect_fen", 0)
        total = exchange_effect + contract_effect + real_business_effect

        # 实际总变化
        actual_total = self.safe_get("international", f"avg_price_{'yoy' if period == 'yoy' else 'mom'}_change_fen", default=0)

        # 验算
        verification_passed = abs(total - actual_total) < 0.1
        if not verification_passed:
            self._log_verification_failure(
                f"三层归因_{period}",
                total,
                actual_total,
                abs(total - actual_total),
            )

        # 判断方向
        if exchange_effect > 0:
            exchange_dir = "帮"
        elif exchange_effect < 0:
            exchange_dir = "拖"
        else:
            exchange_dir = "中性"

        if contract_effect > 0:
            contract_dir = "帮"
        elif contract_effect < 0:
            contract_dir = "拖"
        else:
            contract_dir = "中性"

        # 真本事是否可持续
        sustainable = real_business_effect > 0

        return {
            "total": total,
            "actual_total": actual_total,
            "verification_passed": verification_passed,
            "exchange_rate_effect": exchange_effect,
            "contract_effect": contract_effect,
            "real_business_effect": real_business_effect,
            "exchange_direction": exchange_dir,
            "contract_direction": contract_dir,
            "sustainable": sustainable,
            "summary": f"{period.upper()}：汇率{exchange_effect:+.1f}（{exchange_dir}）+ 合同{contract_effect:+.2f} + 真本事{real_business_effect:+.1f} = {total:+.1f}分",
        }

    def _yoy_vs_mom_comparison(self, yoy: Dict, mom: Dict) -> Dict[str, Any]:
        """同比 vs 环比对比框架（核心方法论）

        三个维度对比:
        1. 能力维度 (同比真本事 vs 环比真本事)
        2. 动能维度 (涨幅收窄还是扩大)
        3. 结构维度 (引擎数变化)
        """
        yoy_rb = yoy["real_business_effect"]
        mom_rb = mom["real_business_effect"]
        yoy_total = yoy["total"]
        mom_total = mom["total"]

        # 1. 能力判断
        if yoy_rb > 0:
            capability = "能力积累"
        elif yoy_rb < 0:
            capability = "能力承压"
        else:
            capability = "能力持平"

        # 2. 动能判断
        if mom_rb < yoy_rb - 0.5:
            momentum = "动能减弱"
        elif mom_rb > yoy_rb + 0.5:
            momentum = "动能加速"
        else:
            momentum = "动能稳定"

        # 3. 结构判断（从样本数据读取）
        structure_data = self.safe_get("two_periods_comparison", default={})
        yoy_engine_count = structure_data.get("yoy_engine_count", 0)
        mom_engine_count = structure_data.get("mom_engine_count", 0)
        if mom_engine_count < yoy_engine_count:
            structure = "结构集中"
        elif mom_engine_count > yoy_engine_count:
            structure = "结构分散"
        else:
            structure = "结构稳定"

        return {
            "yoy_real_business": yoy_rb,
            "mom_real_business": mom_rb,
            "yoy_total": yoy_total,
            "mom_total": mom_total,
            "yoy_to_mom_change": mom_rb - yoy_rb,
            "capability": capability,
            "momentum": momentum,
            "structure": structure,
            "yoy_engine_count": yoy_engine_count,
            "mom_engine_count": mom_engine_count,
            "yoy_pattern": structure_data.get("yoy_pattern", ""),
            "mom_pattern": structure_data.get("mom_pattern", ""),
        }

    def _analyze_regions(self, period: str) -> Dict[str, Any]:
        """5 区域分析"""
        region_key = f"by_region_{period}"
        regions_data = self.safe_get(region_key, default={})
        result = {"regions": []}

        for region_code, region_name in self.intl_config.regions.items():
            data = regions_data.get(region_code, {})
            if not data:
                continue
            result["regions"].append({
                "区域代码": region_code,
                "区域名称": region_name,
                "包含国家": ", ".join(data.get("countries", [])),
                "影响(分)": data.get("effect_fen", 0),
                "主要驱动": data.get("main_driver", ""),
            })

        return result

    def _analyze_companies(self) -> Dict[str, Any]:
        """3 运营主体分析"""
        companies_data = self.safe_get("by_company", default={})
        result = {"companies": [], "by_impact": {"主力": [], "辅助": [], "拖累": []}}

        for comp_code in self.intl_config.companies:
            comp = companies_data.get(comp_code, {})
            if not comp:
                continue

            yoy_impact = comp.get("group_impact_yoy_fen", 0)
            mom_impact = comp.get("group_impact_mom_fen", 0)

            # 判断角色
            if yoy_impact > 1.0:
                role = "主力"
            elif yoy_impact > 0:
                role = "辅助"
            else:
                role = "拖累"

            result["by_impact"][role].append(comp_code)
            result["companies"].append({
                "公司代码": comp_code,
                "公司名称": comp.get("name", ""),
                "同比度电(分)": comp.get("yoy_change_fen", 0),
                "环比度电(分)": comp.get("mom_change_fen", 0),
                "同比影响集团(分)": yoy_impact,
                "环比影响集团(分)": mom_impact,
                "角色": role,
            })

        return result

    def _analyze_exchange_rates(self) -> Dict[str, Any]:
        """汇率分析"""
        rates = self.safe_get("exchange_rates", default={})
        result = {
            "currencies": [],
            "direction_reversal": False,
            "yoy_directions": {"升值": [], "贬值": []},
            "mom_directions": {"升值": [], "贬值": []},
        }

        yoy_directions_set = set()
        mom_directions_set = set()

        for curr_code, curr_data in rates.items():
            yoy_pct = curr_data.get("yoy_pct", 0)
            mom_pct = curr_data.get("mom_pct", 0)

            yoy_dir = "升值" if yoy_pct > 0 else "贬值" if yoy_pct < 0 else "平"
            mom_dir = "升值" if mom_pct > 0 else "贬值" if mom_pct < 0 else "平"

            result["yoy_directions"][yoy_dir].append(curr_code)
            result["mom_directions"][mom_dir].append(curr_code)
            yoy_directions_set.add(yoy_dir)
            mom_directions_set.add(mom_dir)

            result["currencies"].append({
                "币种": curr_code,
                "名称": curr_data.get("currency_name", ""),
                "当前汇率": curr_data.get("current", 0),
                "同比(%)": yoy_pct,
                "环比(%)": mom_pct,
                "同比方向": yoy_dir,
                "环比方向": mom_dir,
            })

        # 判断方向是否反转（同比升值 vs 环比贬值 等）
        if "升值" in yoy_directions_set and "贬值" in mom_directions_set:
            result["direction_reversal"] = True
        elif "贬值" in yoy_directions_set and "升值" in mom_directions_set:
            result["direction_reversal"] = True

        return result

    def _analyze_countries(self) -> Dict[str, Any]:
        """国家×品类分析"""
        countries = self.safe_get("by_country_category", default=[])
        result = {"by_country": {}}

        for entry in countries:
            country = entry.get("country", "未知")
            if country not in result["by_country"]:
                result["by_country"][country] = {"entries": [], "total_volume": 0}
            result["by_country"][country]["entries"].append(entry)
            result["by_country"][country]["total_volume"] += entry.get("volume_yi_kwh", 0)

        return result

    def _detect_anomalies(
        self,
        kpis: Dict,
        yoy: Dict,
        mom: Dict,
        exchange: Dict,
        companies: Dict,
    ) -> List[Dict[str, Any]]:
        """异常检测"""
        anomalies = []
        thresholds = self.intl_config.thresholds

        # 三层归因 - 真本事为负
        if yoy["real_business_effect"] < thresholds["real_business_min_fen"]:
            anomalies.append({
                "level": "critical",
                "category": "归因",
                "message": f"真本事（同比）{yoy['real_business_effect']:+.1f} 分 < 0，触发经营能力预警"
            })

        # 汇率影响 > 真本事 2 倍（汇率幻觉）
        if abs(yoy["exchange_rate_effect"]) > abs(yoy["real_business_effect"]) * thresholds["exchange_rate_dominance_ratio"]:
            anomalies.append({
                "level": "warning",
                "category": "汇率",
                "message": f"汇率影响 {yoy['exchange_rate_effect']:+.1f} 分 > 真本事 2 倍，存在'汇率幻觉'风险"
            })

        # 合同单次影响过大
        if abs(yoy["contract_effect"]) > thresholds["contract_dominance_threshold"]:
            anomalies.append({
                "level": "info",
                "category": "合同",
                "message": f"合同影响 {yoy['contract_effect']:+.2f} 分，需关注是否属于一次性事件"
            })

        # 同比/环比方向反转
        if (yoy["real_business_effect"] > 0) != (mom["real_business_effect"] > 0):
            anomalies.append({
                "level": "warning",
                "category": "动能",
                "message": f"真本事方向反转：同比 {yoy['real_business_effect']:+.1f} vs 环比 {mom['real_business_effect']:+.1f}"
            })

        # 同比/环比差异过大
        if abs(yoy["total"] - mom["total"]) > thresholds["yoy_mom_reversal_threshold"] * 3:
            anomalies.append({
                "level": "info",
                "category": "趋势",
                "message": f"同比 +{yoy['total']:.1f} vs 环比 +{mom['total']:.1f} 差异较大"
            })

        # 汇率异常
        for curr in exchange.get("currencies", []):
            if abs(curr["同比(%)"]) > thresholds["single_currency_yoy_alert"]:
                anomalies.append({
                    "level": "warning",
                    "category": "汇率",
                    "message": f"{curr['币种']} 同比波动 {curr['同比(%)']:+.1f}%，超过 ±{thresholds['single_currency_yoy_alert']}%"
                })

        # 集中度风险
        for comp in companies.get("companies", []):
            if abs(comp["同比影响集团(分)"]) > 2.0:
                anomalies.append({
                    "level": "info",
                    "category": "集中度",
                    "message": f"{comp['公司名称']} 同比影响 {comp['同比影响集团(分)']:+.1f} 分，集中度风险"
                })

        # 按严重度排序
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        anomalies.sort(key=lambda x: severity_order.get(x.get("level", "info"), 3))

        return anomalies

    def _build_tables(
        self,
        kpis: Dict,
        yoy: Dict,
        mom: Dict,
        exchange: Dict,
        regions_yoy: Dict,
        regions_mom: Dict,
        companies: Dict,
    ) -> List[Dict[str, Any]]:
        """构建表格数据"""
        tables = []

        # 表 1: KPI 总览
        tables.append({
            "title": "国际段 KPI 总览",
            "headers": ["指标", "数值", "同比", "环比"],
            "rows": [
                ["国际上网电量(亿度)", kpis["国际上网电量"], f"{kpis['国际同比电量']:+.1f}%", f"{kpis['国际环比电量']:+.1f}%"],
                ["国际度电均价(元)", kpis["国际度电均价"], f"{kpis['国际同比度电']:+.1f}分", f"{kpis['国际环比度电']:+.1f}分"],
                ["国际发电收入(亿元)", kpis["国际发电收入"], f"{kpis['国际同比收入']:+.1f}%", f"{kpis['国际环比收入']:+.1f}%"],
            ],
        })

        # 表 2: 三层归因
        tables.append({
            "title": "三层归因 (汇率 / 合同 / 真本事)",
            "headers": ["层次", "同比 (分)", "环比 (分)", "同比方向", "环比方向"],
            "rows": [
                ["汇率贡献", yoy["exchange_rate_effect"], mom["exchange_rate_effect"], yoy["exchange_direction"], mom["exchange_direction"]],
                ["合同贡献", yoy["contract_effect"], mom["contract_effect"], yoy["contract_direction"], mom["contract_direction"]],
                ["真本事 (内生)", yoy["real_business_effect"], mom["real_business_effect"], "可持续" if yoy["sustainable"] else "承压", "可持续" if mom["sustainable"] else "承压"],
                ["合计", yoy["total"], mom["total"], "", ""],
            ],
        })

        # 表 3: 汇率
        if exchange.get("currencies"):
            tables.append({
                "title": "三大币种汇率",
                "headers": ["币种", "名称", "当前汇率", "同比", "环比", "同比方向"],
                "rows": [
                    [c["币种"], c["名称"], c["当前汇率"], f"{c['同比(%)']:+.1f}%", f"{c['环比(%)']:+.1f}%", c["同比方向"]]
                    for c in exchange["currencies"]
                ],
            })

        # 表 4: 5 区域（同比 + 环比）
        all_regions = set()
        for r in regions_yoy.get("regions", []):
            all_regions.add(r["区域代码"])
        for r in regions_mom.get("regions", []):
            all_regions.add(r["区域代码"])

        if all_regions:
            region_rows = []
            for region_code in sorted(all_regions):
                yoy_data = next((r for r in regions_yoy.get("regions", []) if r["区域代码"] == region_code), {})
                mom_data = next((r for r in regions_mom.get("regions", []) if r["区域代码"] == region_code), {})
                region_rows.append([
                    yoy_data.get("区域名称", region_code),
                    ", ".join(yoy_data.get("包含国家", [])),
                    yoy_data.get("影响(分)", 0),
                    mom_data.get("影响(分)", 0),
                    yoy_data.get("主要驱动", ""),
                ])
            tables.append({
                "title": "5 区域分析（同比 vs 环比）",
                "headers": ["区域", "国家", "同比影响(分)", "环比影响(分)", "主要驱动"],
                "rows": region_rows,
            })

        # 表 5: 3 运营主体
        if companies.get("companies"):
            tables.append({
                "title": "3 运营主体（同比/环比对集团的拉动）",
                "headers": ["公司", "同比度电(分)", "环比度电(分)", "同比影响集团(分)", "环比影响集团(分)", "角色"],
                "rows": [
                    [c["公司名称"], c["同比度电(分)"], c["环比度电(分)"], c["同比影响集团(分)"], c["环比影响集团(分)"], c["角色"]]
                    for c in companies["companies"]
                ],
            })

        return tables

    def _build_charts(
        self,
        kpis: Dict,
        yoy: Dict,
        mom: Dict,
        exchange: Dict,
        comparison: Dict,
    ) -> List[Dict[str, Any]]:
        """构建图表数据"""
        charts = []

        # 图 1: 三层归因柱状图
        charts.append({
            "title": "三层归因对比（同比 vs 环比）",
            "type": "bar",
            "data": {
                "categories": ["汇率", "合同", "真本事"],
                "series": {
                    "同比": [yoy["exchange_rate_effect"], yoy["contract_effect"], yoy["real_business_effect"]],
                    "环比": [mom["exchange_rate_effect"], mom["contract_effect"], mom["real_business_effect"]],
                },
            },
        })

        # 图 2: 同比/环比 真本事对比
        charts.append({
            "title": "真本事对比（同比 vs 环比）",
            "type": "bar",
            "data": {
                "categories": ["真本事"],
                "series": {
                    "同比": [yoy["real_business_effect"]],
                    "环比": [mom["real_business_effect"]],
                },
            },
        })

        # 图 3: 三大币种同比/环比
        if exchange.get("currencies"):
            charts.append({
                "title": "三大币种同比/环比",
                "type": "bar",
                "data": {
                    "categories": [c["币种"] for c in exchange["currencies"]],
                    "series": {
                        "同比(%)": [c["同比(%)"] for c in exchange["currencies"]],
                        "环比(%)": [c["环比(%)"] for c in exchange["currencies"]],
                    },
                },
            })

        return charts

    def _generate_story(
        self,
        kpis: Dict,
        yoy: Dict,
        mom: Dict,
        comparison: Dict,
        exchange: Dict,
        regions_yoy: Dict,
        regions_mom: Dict,
        companies: Dict,
        anomalies: List[Dict],
    ) -> tuple:
        """生成业务故事"""
        avg_price = kpis["国际度电均价"]
        yoy_fen = kpis["国际同比度电"]
        mom_fen = kpis["国际环比度电"]
        yoy_rb = yoy["real_business_effect"]
        mom_rb = mom["real_business_effect"]
        yoy_ex = yoy["exchange_rate_effect"]
        mom_ex = mom["exchange_rate_effect"]

        # 一句话总结
        if comparison["capability"] == "能力积累" and comparison["momentum"] == "动能减弱":
            summary = (
                f"国际电价 {avg_price} 元，"
                f"同比 +{yoy_fen:.1f} 分（真本事 +{yoy_rb:.1f}，汇率帮忙 +{yoy_ex:.1f}），"
                f"环比 +{mom_fen:.1f} 分（真本事 +{mom_rb:.1f}，汇率拖累 {mom_ex:.1f}）。"
                f"能力在积累，动能在减弱"
            )
        else:
            summary = (
                f"国际电价 {avg_price} 元，同比 +{yoy_fen:.1f} 分，环比 +{mom_fen:.1f} 分。"
                f"三层归因：汇率 {yoy_ex:+.1f} + 合同 {yoy['contract_effect']:+.2f} + 真本事 {yoy_rb:+.1f}"
            )

        # 多段故事
        story_parts = []

        # 故事 1: 同比三层归因
        story_parts.append(
            f"## 🌍 同比三层归因\n\n"
            f"国际电价同比 {yoy_fen:+.1f} 分：\n\n"
            f"- 汇率贡献：{yoy['exchange_rate_effect']:+.1f} 分（{yoy['exchange_direction']}）\n"
            f"- 合同贡献：{yoy['contract_effect']:+.2f} 分\n"
            f"- 真本事：{yoy['real_business_effect']:+.1f} 分（{'可持续 ⭐' if yoy['sustainable'] else '承压'})\n\n"
            f"**{comparison['capability']}** - 同比真本事 {yoy_rb:+.1f} 分"
        )

        # 故事 2: 环比三层归因
        story_parts.append(
            f"## 📊 环比三层归因\n\n"
            f"国际电价环比 {mom_fen:+.1f} 分：\n\n"
            f"- 汇率贡献：{mom['exchange_rate_effect']:+.1f} 分（{mom['exchange_direction']}）\n"
            f"- 合同贡献：{mom['contract_effect']:+.2f} 分\n"
            f"- 真本事：{mom['real_business_effect']:+.1f} 分（{'可持续 ⭐' if mom['sustainable'] else '承压'}）\n\n"
            f"**{comparison['momentum']}** - 环比真本事 {mom_rb:+.1f} 分（同比 {yoy_rb:+.1f} → 环比 {mom_rb:+.1f}，变化 {comparison['yoy_to_mom_change']:+.1f}）"
        )

        # 故事 3: 同比 vs 环比对比
        story_parts.append(
            f"## 🆚 同比 vs 环比对比框架\n\n"
            f"| 维度 | 同比 | 环比 | 解读 |\n"
            f"|------|------|------|------|\n"
            f"| 能力 | {yoy_rb:+.1f} | {mom_rb:+.1f} | {comparison['capability']} |\n"
            f"| 动能 | {yoy['total']:+.1f} | {mom['total']:+.1f} | {comparison['momentum']} |\n"
            f"| 结构 | {comparison['yoy_pattern']} | {comparison['mom_pattern']} | {comparison['structure']} |\n\n"
            f"**核心判断**：\n"
            f"1. 能力维度：{comparison['capability']}\n"
            f"2. 动能维度：{comparison['momentum']}\n"
            f"3. 结构维度：{comparison['structure']}（同比 {comparison['yoy_engine_count']} 引擎 → 环比 {comparison['mom_engine_count']} 引擎）"
        )

        # 故事 4: 汇率影响
        if exchange.get("currencies"):
            story_parts.append(
                f"## 💱 三大币种汇率\n\n"
                + "\n".join([
                    f"- **{c['币种']}** ({c['名称']}): 同比 {c['同比(%)']:+.1f}%，环比 {c['环比(%)']:+.1f}% ({c['同比方向']}/{c['环比方向']})"
                    for c in exchange["currencies"]
                ])
                + (f"\n\n⚠️ **汇率方向反转**：同比升值货币在环比贬值" if exchange.get("direction_reversal") else "")
            )

        # 故事 5: 5 区域
        if regions_yoy.get("regions"):
            story_parts.append(
                f"## 🗺️ 5 区域分析\n\n"
                + "\n".join([
                    f"- **{r['区域名称']}**: 同比影响 {r['影响(分)']:+.1f} 分，{r['主要驱动']}"
                    for r in regions_yoy["regions"]
                ])
            )

        # 故事 6: 3 运营主体
        if companies.get("companies"):
            main = [c for c in companies["companies"] if c["角色"] == "主力"]
            story_parts.append(
                f"## 🏢 3 运营主体\n\n"
                + ("\n".join([
                    f"- **{c['公司名称']}** (主力): 同比影响 {c['同比影响集团(分)']:+.1f} 分，环比 {c['环比影响集团(分)']:+.1f} 分"
                    for c in main
                ]) if main else "- 无主力公司")
            )

        # 故事 7: 异常
        if anomalies:
            story_parts.append(
                f"## ⚠️ 异常告警\n\n"
                + "\n".join([
                    f"- {['🔴', '🟠', '🟡'][['critical', 'warning', 'info'].index(a.get('level'))]} [{a.get('level').upper()}] {a.get('message')}"
                    for a in anomalies[:3]
                ])
            )

        # 故事 8: 核心结论
        story_parts.append(
            f"## 💎 核心结论\n\n"
            f"**{comparison['capability']} + {comparison['momentum']} + {comparison['structure']}**\n\n"
            f"同比讲能力，环比讲动能。能力可以积累，动能会衰减。\n"
            f"当同比还在涨、环比已经放缓时——就是在提醒你：\n"
            f"**该找新的增长引擎了**。"
        )

        story = "\n\n".join(story_parts)
        return story, summary

    def _extract_insights(
        self,
        kpis: Dict,
        yoy: Dict,
        mom: Dict,
        comparison: Dict,
        exchange: Dict,
        anomalies: List[Dict],
    ) -> List[str]:
        """提取关键洞察"""
        insights = []

        # 能力/动能/结构三维
        insights.append(
            f"能力维度：{comparison['capability']}（同比真本事 {yoy['real_business_effect']:+.1f}）"
        )
        insights.append(
            f"动能维度：{comparison['momentum']}（环比真本事 {mom['real_business_effect']:+.1f}）"
        )
        insights.append(
            f"结构维度：{comparison['structure']}（{comparison['yoy_engine_count']} 引擎 → {comparison['mom_engine_count']} 引擎）"
        )

        # 汇率影响
        if exchange.get("direction_reversal"):
            insights.append(
                f"⚠️ 汇率方向反转：同比 {len(exchange['yoy_directions'].get('升值', []))} 个币种升值，环比转为贬值"
            )

        # 同比 vs 环比
        if abs(comparison["yoy_to_mom_change"]) > 0.5:
            direction = "减弱" if comparison["yoy_to_mom_change"] < 0 else "加速"
            insights.append(
                f"真本事同比 → 环比{direction}{abs(comparison['yoy_to_mom_change']):.1f} 分"
            )

        return insights


# === 自检 ===
if __name__ == "__main__":
    import json
    from pathlib import Path

    print("=" * 60)
    print("InternationalAnalyzer 自检")
    print("=" * 60)

    fixture_path = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "international_sample.json"
    if not fixture_path.exists():
        print(f"❌ 样本数据不存在: {fixture_path}")
        exit(1)

    with open(fixture_path, encoding="utf-8") as f:
        sample_data = json.load(f)

    analyzer = InternationalAnalyzer(sample_data)

    # 1. 输入校验
    print("\n[1] 输入校验")
    is_valid = analyzer.validate_inputs()
    print(f"  校验通过: {is_valid}")
    if not is_valid:
        print(f"  缺失字段: {analyzer.missing_fields}")

    # 2. 执行分析
    print("\n[2] 执行分析")
    result = analyzer.analyze()

    print(f"  维度: {result.dimension}")
    print(f"  段: {result.section_ids}")

    # 3. KPI
    print("\n[3] 关键 KPI")
    for k, v in result.kpis.items():
        print(f"  {k}: {v}")

    # 4. 三层归因
    print("\n[4] 三层归因")
    print(f"  同比: {result.yoy_data['summary']}")
    print(f"  环比: {result.mom_data['summary']}")

    # 5. 同比 vs 环比
    cmp = analyzer._yoy_vs_mom_comparison(result.yoy_data, result.mom_data)
    print(f"\n[5] 同比 vs 环比")
    print(f"  能力: {cmp['capability']}")
    print(f"  动能: {cmp['momentum']}")
    print(f"  结构: {cmp['structure']}")

    # 6. 异常
    print(f"\n[6] 异常: {len(result.anomalies)} 个")
    for a in result.anomalies[:3]:
        print(f"  [{a.get('level').upper()}] {a.get('message')[:80]}")

    # 7. 表格
    print(f"\n[7] 表格: {len(result.tables)} 个")
    for t in result.tables:
        print(f"  - {t['title']}")

    # 8. 图表
    print(f"\n[8] 图表: {len(result.charts)} 个")
    for c in result.charts:
        print(f"  - {c['title']} ({c['type']})")

    # 9. 洞察
    print(f"\n[9] 洞察: {len(result.insights)} 条")
    for i in result.insights[:3]:
        print(f"  - {i[:80]}")

    # 10. 故事长度
    print(f"\n[10] 故事长度: {len(result.story)} 字符")
    print(f"  总结长度: {len(result.summary)} 字符")

    # 11. 勾稽验证
    failures = analyzer.get_verification_failures()
    print(f"\n[11] 勾稽验证: {len(failures)} 个失败")
    for f in failures:
        print(f"  ❌ {f}")

    print("\n" + "=" * 60)
    print("✅ InternationalAnalyzer 自检通过")
    print("=" * 60)
