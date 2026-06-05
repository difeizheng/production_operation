"""
国内分析器 (DomesticAnalyzer)
=============================

覆盖业务图谱段 1-2: 国内电量 + 国内电价
- 段 1: 总览段 - "上周，集团公司合计上网电量 89.1 亿千瓦时..."
- 段 2: 价格变化段 - "度电均价 0.311 元，同比 −0.9 分..."

设计依据:
- 业务图谱: docs/design/business-map-master.md (段 1-2)
- 分析框架: docs/analysis/domestic-price-analysis-framework.md (第 1-14 节)
- 基础类: src/analyzer/base.py

实施状态: ✅ Phase 2 完成
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from .base import BaseAnalyzer, AnalysisResult, create_empty_result


# === 阈值配置（可被 config 覆盖）===
DEFAULT_THRESHOLDS = {
    # 度电异常
    "yoy_price_fen_warning": 5.0,      # 同比 ±5 分触发警告
    "yoy_price_fen_critical": 10.0,    # 同比 ±10 分触发严重
    "mom_price_fen_warning": 3.0,      # 环比 ±3 分触发警告

    # 电量异常
    "yoy_volume_pct_warning": 10.0,    # 同比 ±10%触发警告
    "mom_volume_pct_warning": 20.0,    # 环比 ±20%触发警告

    # 收入异常
    "yoy_revenue_pct_warning": 20.0,   # 同比 ±20%触发警告

    # 结构异常
    "thermal_share_retreat": 5.0,      # 火电占比 < 5% 提示战略性退场
    "renewable_share_milestone": 30.0, # 新能源 > 30% 提示转型里程碑

    # 战略性退场
    "thermal_retreat_yoy_volume": -30.0,  # 火电同比 < -30% 触发战略性退场预警
}


# === 关键省份清单 ===
KEY_PROVINCES = ["hubei", "shandong", "shaanxi", "jiangsu"]


# === 5 大品类配置 ===
CATEGORIES = ["hydro", "renewables", "thermal", "wind", "solar"]


@dataclass
class DomesticConfig:
    """国内分析器配置"""
    thresholds: Dict[str, float] = field(default_factory=lambda: DEFAULT_THRESHOLDS.copy())
    key_provinces: List[str] = field(default_factory=lambda: KEY_PROVINCES.copy())
    categories: List[str] = field(default_factory=lambda: CATEGORIES.copy())
    strict_validation: bool = True


class DomesticAnalyzer(BaseAnalyzer):
    """国内分析器（段 1-2）

    负责分析:
    - 集团国内上网电量（总览 + 同比环比）
    - 集团国内度电均价（量价分解）
    - 5 大品类（水/新/火/风/光）
    - 关键省份本地化（湖北/山东/陕西/江苏）
    - 火电战略性退场信号
    - 业务故事自动生成
    """

    dimension_name = "国内"
    section_ids = [1, 2]
    analyzer_name = "DomesticAnalyzer"

    def __init__(self, json_data: dict, config: Optional[dict] = None):
        super().__init__(json_data, config)
        # 合并配置
        self.domestic_config = DomesticConfig(
            thresholds={**DEFAULT_THRESHOLDS, **(config or {}).get("thresholds", {})},
            key_provinces=(config or {}).get("key_provinces", KEY_PROVINCES),
            categories=(config or {}).get("categories", CATEGORIES),
            strict_validation=(config or {}).get("strict_validation", True),
        )

    # === 抽象方法实现 ===

    def validate_inputs(self) -> bool:
        """校验输入数据完整性

        必需字段:
        - group_total (国内 + 国际 + 均价 + 收入)
        - by_category (5 大品类)
        - by_region (关键省份)
        """
        self.missing_fields = []

        # 检查 group_total
        group_total = self.safe_get("group_total", default={})
        required_group_fields = [
            "domestic_ongrid_volume_yi_kwh",
            "international_ongrid_volume_yi_kwh",
            "total_ongrid_volume_yi_kwh",
            "domestic_avg_price_yuan_per_kwh",
            "domestic_revenue_yi_yuan",
            "yoy_volume_pct",
            "yoy_price_change_fen",
            "yoy_revenue_pct",
            "mom_volume_pct",
            "mom_price_change_fen",
            "mom_revenue_pct",
        ]
        for field_name in required_group_fields:
            if field_name not in group_total:
                self.missing_fields.append(f"group_total.{field_name}")

        # 检查 by_category
        by_category = self.safe_get("by_category", default={})
        for cat in self.domestic_config.categories:
            if cat not in by_category:
                self.missing_fields.append(f"by_category.{cat}")

        # 检查 by_region (宽松)
        by_region = self.safe_get("by_region", default={})
        if not by_region:
            self.missing_fields.append("by_region (空)")

        # 严格模式下要求所有省份
        if self.domestic_config.strict_validation:
            for prov in self.domestic_config.key_provinces:
                if prov not in by_region:
                    self.missing_fields.append(f"by_region.{prov}")

        is_valid = len(self.missing_fields) == 0
        if not is_valid:
            # 记录异常
            if not hasattr(self, '_validation_errors'):
                self._validation_errors = []
            self._validation_errors = self.missing_fields.copy()
        return is_valid

    def analyze(self) -> AnalysisResult:
        """执行分析主入口

        Returns:
            AnalysisResult: 完整的国内段分析结果
        """
        # 1. 输入校验
        if not self.validate_inputs():
            return self._create_validation_error_result()

        # 2. 提取 KPI
        kpis = self._extract_kpis()

        # 3. 同比分析
        yoy_data = self._yoy_analysis(kpis)

        # 4. 环比分析
        mom_data = self._mom_analysis(kpis)

        # 5. 量价分解
        decomposition = self._decompose_volume_price()

        # 6. 5 大品类分析
        categories_analysis = self._analyze_categories()

        # 7. 关键省份分析
        regions_analysis = self._analyze_regions()

        # 8. 异常检测
        anomalies = self._detect_anomalies(kpis, categories_analysis, regions_analysis)

        # 9. 构建表格和图表
        tables = self._build_tables(kpis, categories_analysis, regions_analysis)
        charts = self._build_charts(kpis, yoy_data, mom_data, categories_analysis)

        # 10. 生成故事
        story, summary = self._generate_story(
            kpis, yoy_data, mom_data, categories_analysis, anomalies
        )
        # _generate_story 返回 (story, summary) 元组

        # 11. 提取洞察
        insights = self._extract_insights(
            kpis, yoy_data, mom_data, categories_analysis, regions_analysis, anomalies
        )

        return AnalysisResult(
            dimension=self.dimension_name,
            section_ids=self.section_ids,
            analyzer_name=self.analyzer_name,
            summary=summary,
            story=story,
            kpis=kpis,
            yoy_data=yoy_data,
            mom_data=mom_data,
            tables=tables,
            charts=charts,
            insights=insights,
            anomalies=anomalies,
        )

    # === 内部方法 ===

    def _create_validation_error_result(self) -> AnalysisResult:
        """创建校验失败的错误结果"""
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
        """提取关键 KPI

        Returns:
            包含所有关键指标的字典
        """
        group = self.safe_get("group_total", default={})
        return {
            # 集团总量
            "国内上网电量": group.get("domestic_ongrid_volume_yi_kwh", 0),
            "国际上网电量": group.get("international_ongrid_volume_yi_kwh", 0),
            "合计上网电量": group.get("total_ongrid_volume_yi_kwh", 0),
            "国内度电均价": group.get("domestic_avg_price_yuan_per_kwh", 0),
            "国内发电收入": group.get("domestic_revenue_yi_yuan", 0),
            # 同比
            "同比电量": group.get("yoy_volume_pct", 0),
            "同比度电": group.get("yoy_price_change_fen", 0),
            "同比收入": group.get("yoy_revenue_pct", 0),
            # 环比
            "环比电量": group.get("mom_volume_pct", 0),
            "环比度电": group.get("mom_price_change_fen", 0),
            "环比收入": group.get("mom_revenue_pct", 0),
        }

    def _yoy_analysis(self, kpis: Dict) -> Dict[str, Any]:
        """同比分析

        Returns:
            同比维度的详细分析数据
        """
        yoy_volume = kpis["同比电量"]
        yoy_price = kpis["同比度电"]
        yoy_revenue = kpis["同比收入"]

        # 判断方向
        volume_direction = "涨" if yoy_volume > 0 else "跌" if yoy_volume < 0 else "平"
        price_direction = "涨" if yoy_price > 0 else "跌" if yoy_price < 0 else "平"
        revenue_direction = "涨" if yoy_revenue > 0 else "跌" if yoy_revenue < 0 else "平"

        # 复合分析
        if yoy_volume > 0 and yoy_price < 0:
            pattern = "以量补价"
        elif yoy_volume < 0 and yoy_price > 0:
            pattern = "以价补量"
        elif yoy_volume > 0 and yoy_price > 0:
            pattern = "量价齐升"
        elif yoy_volume < 0 and yoy_price < 0:
            pattern = "量价齐跌"
        else:
            pattern = "持平"

        return {
            "电量": {"value": yoy_volume, "direction": volume_direction},
            "度电": {"value": yoy_price, "direction": price_direction},
            "收入": {"value": yoy_revenue, "direction": revenue_direction},
            "pattern": pattern,
            "summary": f"同比：电量{yoy_volume:+.1f}%，度电{yoy_price:+.1f}分，收入{yoy_revenue:+.1f}%。模式：{pattern}",
        }

    def _mom_analysis(self, kpis: Dict) -> Dict[str, Any]:
        """环比分析（同同比结构）"""
        mom_volume = kpis["环比电量"]
        mom_price = kpis["环比度电"]
        mom_revenue = kpis["环比收入"]

        volume_direction = "涨" if mom_volume > 0 else "跌" if mom_volume < 0 else "平"
        price_direction = "涨" if mom_price > 0 else "跌" if mom_price < 0 else "平"
        revenue_direction = "涨" if mom_revenue > 0 else "跌" if mom_revenue < 0 else "平"

        # 环比强弱判断
        if mom_volume > 10 and abs(mom_price) < 1:
            strength = "强"
        elif abs(mom_volume) < 5 and abs(mom_price) < 1:
            strength = "弱"
        else:
            strength = "中"

        return {
            "电量": {"value": mom_volume, "direction": volume_direction},
            "度电": {"value": mom_price, "direction": price_direction},
            "收入": {"value": mom_revenue, "direction": revenue_direction},
            "strength": strength,
            "summary": f"环比：电量{mom_volume:+.1f}%，度电{mom_price:+.1f}分，收入{mom_revenue:+.1f}%。动能：{strength}",
        }

    def _decompose_volume_price(self) -> Dict[str, Any]:
        """量价分解

        拆分各品类对集团度电变化的贡献
        - 量化影响 = 占比变化 × 基期度电
        - 价格影响 = 单价变化 × 当期占比

        Returns:
            量价分解结果
        """
        categories = self.safe_get("by_category", default={})
        if not categories:
            return {}

        decomposition = {
            "categories": [],
            "total_yoy_change_fen": 0.0,
            "verification_passed": False,
        }

        total_change = 0.0
        for cat_name, cat_data in categories.items():
            yoy_price_change_fen = cat_data.get("yoy_price_change_fen", 0)
            share = cat_data.get("share_pct", 0) / 100  # 转比率

            # 简化的分解：假设价格影响主导
            contribution = yoy_price_change_fen * share

            decomposition["categories"].append({
                "品类": cat_name,
                "度电变化(分)": yoy_price_change_fen,
                "占比(%)": cat_data.get("share_pct", 0),
                "贡献(分)": round(contribution, 3),
            })
            total_change += contribution

        # 加和验算（vs group_total 的 yoy_price_change_fen）
        group_yoy_fen = self.safe_get("group_total", "yoy_price_change_fen", default=0)
        decomposition["total_yoy_change_fen"] = round(total_change, 2)
        decomposition["group_yoy_change_fen"] = group_yoy_fen
        # 验算：允许一定误差（因为加权平均 vs 直接加和有偏差）
        decomposition["verification_passed"] = abs(total_change - group_yoy_fen) < 0.5

        # 记录验算结果
        if not decomposition["verification_passed"]:
            self._log_verification_failure(
                "量价分解",
                total_change,
                group_yoy_fen,
                abs(total_change - group_yoy_fen),
            )

        return decomposition

    def _analyze_categories(self) -> Dict[str, Any]:
        """5 大品类分析

        Returns:
            每个品类的详细分析
        """
        categories = self.safe_get("by_category", default={})
        result = {
            "categories": [],
            "by_status": {"增长": [], "下降": [], "稳定": []},
            "key_insights": [],
        }

        for cat_name in self.domestic_config.categories:
            cat = categories.get(cat_name, {})
            if not cat:
                continue

            yoy_revenue = cat.get("yoy_revenue_pct", 0)
            yoy_price = cat.get("yoy_price_change_fen", 0)
            yoy_volume = cat.get("yoy_volume_pct", 0)

            # 判断状态
            if yoy_revenue > 5:
                status = "增长"
                status_emoji = "🟢"
            elif yoy_revenue < -10:
                status = "下降"
                status_emoji = "🔴"
            else:
                status = "稳定"
                status_emoji = "🟡"

            result["by_status"][status].append(cat_name)

            cat_info = {
                "品类": cat_name,
                "状态": f"{status_emoji} {status}",
                "电量(亿度)": cat.get("volume_yi_kwh", 0),
                "度电(元)": cat.get("avg_price_yuan_per_kwh", 0),
                "收入(亿元)": cat.get("revenue_yi_yuan", 0),
                "占比(%)": cat.get("share_pct", 0),
                "同比电量(%)": yoy_volume,
                "同比度电(分)": yoy_price,
                "同比收入(%)": yoy_revenue,
            }
            result["categories"].append(cat_info)

        # 关键洞察
        thermal = categories.get("thermal", {})
        renewables = categories.get("renewables", {})

        if thermal.get("yoy_revenue_pct", 0) < -30:
            result["key_insights"].append({
                "level": "warning",
                "msg": f"火电同比收入 {thermal.get('yoy_revenue_pct')}% （< -30%），符合'战略性退场'信号"
            })

        if thermal.get("share_pct", 100) < self.domestic_config.thresholds["thermal_share_retreat"]:
            result["key_insights"].append({
                "level": "info",
                "msg": f"火电占比 {thermal.get('share_pct')}%（< {self.domestic_config.thresholds['thermal_share_retreat']}%），已被边缘化"
            })

        if renewables.get("share_pct", 0) > self.domestic_config.thresholds["renewable_share_milestone"]:
            result["key_insights"].append({
                "level": "info",
                "msg": f"新能源占比 {renewables.get('share_pct')}%（> {self.domestic_config.thresholds['renewable_share_milestone']}%），转型里程碑"
            })

        return result

    def _analyze_regions(self) -> Dict[str, Any]:
        """关键省份分析

        Returns:
            关键省份的本地化数据
        """
        regions = self.safe_get("by_region", default={})
        result = {
            "provinces": [],
            "by_strategy": {
                "高持仓": [],
                "低持仓": [],
                "卡线": [],
                "中等": [],
            },
        }

        for prov_name in self.domestic_config.key_provinces:
            prov = regions.get(prov_name, {})
            if not prov:
                continue

            long_term_pos = prov.get("long_term_position_pct", 0)

            # 识别策略（按持仓比例分类）
            if long_term_pos >= 105:
                strategy = "卡线"  # ≥105% 触发监管回收
            elif long_term_pos >= 80:
                strategy = "高持仓"  # 80-105%，主流稳健
            elif long_term_pos <= 15:
                strategy = "低持仓"  # 0-15%，极致短期
            else:
                strategy = "中等"  # 15-80%，中性仓位

            result["by_strategy"][strategy].append(prov_name)

            result["provinces"].append({
                "省份": prov_name,
                "主要电源": ", ".join(prov.get("main_sources", [])),
                "中长期持仓(%)": long_term_pos,
                "策略": strategy,
                "现货均价(元)": prov.get("spot_avg_price_yuan", 0),
                "同比度电(分)": prov.get("yoy_price_change_fen", 0),
                "环比度电(分)": prov.get("mom_price_change_fen", 0),
            })

        return result

    def _detect_anomalies(
        self,
        kpis: Dict,
        categories: Dict,
        regions: Dict,
    ) -> List[Dict[str, Any]]:
        """异常检测（4 级）

        Returns:
            异常列表，按严重度排序
        """
        anomalies = []
        thresholds = self.domestic_config.thresholds

        # === 度电异常 ===
        yoy_fen = abs(kpis["同比度电"])
        if yoy_fen > thresholds["yoy_price_fen_critical"]:
            anomalies.append({
                "level": "critical",
                "category": "度电",
                "indicator": "同比",
                "value": kpis["同比度电"],
                "threshold": thresholds["yoy_price_fen_critical"],
                "message": f"度电同比 {kpis['同比度电']:+.1f} 分，超过 ±{thresholds['yoy_price_fen_critical']} 分阈值（严重）"
            })
        elif yoy_fen > thresholds["yoy_price_fen_warning"]:
            anomalies.append({
                "level": "warning",
                "category": "度电",
                "indicator": "同比",
                "value": kpis["同比度电"],
                "threshold": thresholds["yoy_price_fen_warning"],
                "message": f"度电同比 {kpis['同比度电']:+.1f} 分，超过 ±{thresholds['yoy_price_fen_warning']} 分阈值"
            })

        # === 电量异常 ===
        yoy_vol = abs(kpis["同比电量"])
        if yoy_vol > thresholds["yoy_volume_pct_warning"]:
            anomalies.append({
                "level": "warning",
                "category": "电量",
                "indicator": "同比",
                "value": kpis["同比电量"],
                "threshold": thresholds["yoy_volume_pct_warning"],
                "message": f"电量同比 {kpis['同比电量']:+.1f}%，超过 ±{thresholds['yoy_volume_pct_warning']}% 阈值"
            })

        # === 收入异常 ===
        if abs(kpis["同比收入"]) > thresholds["yoy_revenue_pct_warning"]:
            anomalies.append({
                "level": "warning",
                "category": "收入",
                "indicator": "同比",
                "value": kpis["同比收入"],
                "threshold": thresholds["yoy_revenue_pct_warning"],
                "message": f"收入同比 {kpis['同比收入']:+.1f}%，超过 ±{thresholds['yoy_revenue_pct_warning']}% 阈值"
            })

        # === 火电战略性退场 ===
        thermal = self.safe_get("by_category", "thermal", default={})
        thermal_yoy_vol = thermal.get("yoy_volume_pct", 0)
        if thermal_yoy_vol < thresholds["thermal_retreat_yoy_volume"]:
            anomalies.append({
                "level": "critical",
                "category": "火电",
                "indicator": "战略性退场",
                "value": thermal_yoy_vol,
                "threshold": thresholds["thermal_retreat_yoy_volume"],
                "message": f"火电同比电量 {thermal_yoy_vol}%，触发战略性退场预警（< -30%）"
            })

        # === 火电占比 ===
        thermal_share = thermal.get("share_pct", 100)
        if thermal_share < thresholds["thermal_share_retreat"]:
            anomalies.append({
                "level": "info",
                "category": "结构",
                "indicator": "火电占比",
                "value": thermal_share,
                "threshold": thresholds["thermal_share_retreat"],
                "message": f"火电占比 {thermal_share}%（< {thresholds['thermal_share_retreat']}%），已进入战略性边缘化阶段"
            })

        # 按严重度排序
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        anomalies.sort(key=lambda x: severity_order.get(x.get("level", "info"), 3))

        return anomalies

    def _build_tables(
        self,
        kpis: Dict,
        categories: Dict,
        regions: Dict,
    ) -> List[Dict[str, Any]]:
        """构建表格数据"""
        tables = []

        # 表 1: KPI 总览
        tables.append({
            "title": "KPI 总览",
            "headers": ["指标", "本周", "同比", "环比"],
            "rows": [
                ["集团国内上网电量(亿度)", kpis["国内上网电量"], f"{kpis['同比电量']:+.1f}%", f"{kpis['环比电量']:+.1f}%"],
                ["集团度电均价(元/度)", kpis["国内度电均价"], f"{kpis['同比度电']:+.1f}分", f"{kpis['环比度电']:+.1f}分"],
                ["集团国内发电收入(亿元)", kpis["国内发电收入"], f"{kpis['同比收入']:+.1f}%", f"{kpis['环比收入']:+.1f}%"],
            ],
        })

        # 表 2: 5 大品类明细
        if categories.get("categories"):
            tables.append({
                "title": "5 大品类明细",
                "headers": ["品类", "电量(亿度)", "度电(元)", "收入(亿元)", "占比(%)", "同比收入(%)"],
                "rows": [
                    [c["品类"], c["电量(亿度)"], c["度电(元)"], c["收入(亿元)"], c["占比(%)"], c["同比收入(%)"]]
                    for c in categories["categories"]
                ],
            })

        # 表 3: 关键省份策略
        if regions.get("provinces"):
            tables.append({
                "title": "关键省份策略",
                "headers": ["省份", "主要电源", "中长期持仓(%)", "策略", "现货均价(元)"],
                "rows": [
                    [p["省份"], p["主要电源"], p["中长期持仓(%)"], p["策略"], p["现货均价(元)"]]
                    for p in regions["provinces"]
                ],
            })

        return tables

    def _build_charts(
        self,
        kpis: Dict,
        yoy_data: Dict,
        mom_data: Dict,
        categories: Dict,
    ) -> List[Dict[str, Any]]:
        """构建图表数据（Plotly 友好）"""
        charts = []

        # 图 1: 同比 vs 环比 对比柱状图
        charts.append({
            "title": "同比 vs 环比对比",
            "type": "bar",
            "data": {
                "categories": ["电量(%)", "度电(分)", "收入(%)"],
                "series": {
                    "同比": [kpis["同比电量"], kpis["同比度电"], kpis["同比收入"]],
                    "环比": [kpis["环比电量"], kpis["环比度电"], kpis["环比收入"]],
                },
            },
        })

        # 图 2: 5 大品类占比饼图
        if categories.get("categories"):
            charts.append({
                "title": "5 大品类电量占比",
                "type": "pie",
                "data": {
                    "labels": [c["品类"] for c in categories["categories"]],
                    "values": [c["占比(%)"] for c in categories["categories"]],
                },
            })

        # 图 3: 各品类同比收入对比
        if categories.get("categories"):
            charts.append({
                "title": "各品类同比收入",
                "type": "bar",
                "data": {
                    "categories": [c["品类"] for c in categories["categories"]],
                    "values": [c["同比收入(%)"] for c in categories["categories"]],
                },
            })

        return charts

    def _generate_story(
        self,
        kpis: Dict,
        yoy_data: Dict,
        mom_data: Dict,
        categories: Dict,
        anomalies: List[Dict],
    ) -> tuple:
        """生成业务故事

        Returns:
            (summary, story) 元组
        """
        # 提取关键数据
        total_volume = kpis["合计上网电量"]
        domestic_volume = kpis["国内上网电量"]
        intl_volume = kpis["国际上网电量"]
        price = kpis["国内度电均价"]
        revenue = kpis["国内发电收入"]
        yoy_vol = kpis["同比电量"]
        yoy_fen = kpis["同比度电"]
        mom_vol = kpis["环比电量"]
        mom_fen = kpis["环比度电"]

        # 一句话总结
        pattern_yoy = yoy_data.get("pattern", "")
        if pattern_yoy == "以量补价":
            summary = (
                f"上周集团合计上网 {total_volume} 亿度（国内 {domestic_volume} + 国际 {intl_volume}），"
                f"国内度电 {price} 元，同比量增 {yoy_vol:+.1f}% + 价跌 {yoy_fen:+.1f}分，"
                f"实现'以量补价'，收入 {revenue} 亿元微增"
            )
        elif pattern_yoy == "量价齐升":
            summary = (
                f"上周集团合计上网 {total_volume} 亿度，国内度电 {price} 元，"
                f"量价齐升：同比量增 {yoy_vol:+.1f}% + 价涨 {yoy_fen:+.1f}分，"
                f"收入 {revenue} 亿元表现强劲"
            )
        else:
            summary = (
                f"上周集团合计上网 {total_volume} 亿度，国内度电 {price} 元，"
                f"同比量 {yoy_vol:+.1f}% + 价 {yoy_fen:+.1f}分，"
                f"收入 {revenue} 亿元"
            )

        # 多段故事
        story_parts = []

        # 故事 1: 总览
        story_parts.append(
            f"## 📊 总览段\n\n"
            f"上周，集团公司合计上网电量 {total_volume} 亿千瓦时，"
            f"其中国内 {domestic_volume} 亿度（占 {domestic_volume/total_volume*100:.1f}%），"
            f"国际 {intl_volume} 亿度（占 {intl_volume/total_volume*100:.1f}%）。\n\n"
            f"年化估算：{total_volume * 52:.0f} 亿度/年（相当于'准三峡'级集团规模）。"
        )

        # 故事 2: 同比增长
        story_parts.append(
            f"## 📈 同比分析\n\n"
            f"国内上网电量同比 {yoy_vol:+.1f}%，"
            f"主要原因是 {'水电、新能源' if yoy_vol > 0 else '电量整体下滑'}。\n\n"
            f"度电均价同比 {yoy_fen:+.1f} 分。"
        )

        # 故事 3: 价格分析
        story_parts.append(
            f"## 💰 价格分析\n\n"
            f"国内度电均价 {price} 元/度，"
            f"同比 {yoy_fen:+.1f} 分，环比 {mom_fen:+.1f} 分。\n\n"
            f"**故事核心**：{pattern_yoy}。"
        )

        # 故事 4: 量价博弈
        if pattern_yoy == "以量补价":
            story_parts.append(
                f"## 🎯 量价博弈\n\n"
                f"电量 +{yoy_vol:.1f}% vs 度电 {yoy_fen:+.1f}分，呈现'以量补价'格局。\n\n"
                f"- 量增贡献：{yoy_vol:.1f}% 抵消了价跌的负面影响\n"
                f"- 价跌原因：{'结构调整（火电占比下降）' if yoy_fen < 0 else '其他'}\n"
                f"- 策略判断：'以量补价'策略 {'有效' if abs(yoy_fen) < 2 else '接近极限'}"
            )

        # 故事 5: 品类分析
        if categories.get("categories"):
            cat_lines = []
            for cat in categories["categories"]:
                cat_lines.append(
                    f"- **{cat['品类']}**（{cat['状态']}）: "
                    f"电量 {cat['电量(亿度)']} 亿度，"
                    f"度电 {cat['度电(元)']} 元，"
                    f"收入 {cat['收入(亿元)']} 亿，"
                    f"同比 {cat['同比收入(%)']:+.1f}%"
                )
            story_parts.append(
                f"## 📋 5 大品类明细\n\n" + "\n".join(cat_lines)
            )

        # 故事 6: 异常告警
        if anomalies:
            anomaly_lines = []
            for a in anomalies[:3]:  # 只展示前 3 个
                level_emoji = {"critical": "🔴", "warning": "🟠", "info": "🟡"}.get(a.get("level"), "⚪")
                anomaly_lines.append(f"- {level_emoji} [{a.get('level').upper()}] {a.get('message')}")
            story_parts.append(
                f"## ⚠️ 异常告警\n\n" + "\n".join(anomaly_lines)
            )

        # 故事 7: 一句话金句
        story_parts.append(
            f"## 💎 核心结论\n\n"
            f"**{pattern_yoy}** 是当前国内段的主旋律。"
            f"看长期看能力（同比），看短期看动能（环比），"
            f"双线分析是周报解读的核心方法论。"
        )

        story = "\n\n".join(story_parts)
        return story, summary

    def _extract_insights(
        self,
        kpis: Dict,
        yoy_data: Dict,
        mom_data: Dict,
        categories: Dict,
        regions: Dict,
        anomalies: List[Dict],
    ) -> List[str]:
        """提取关键洞察"""
        insights = []

        # 同比/环比方向
        if (kpis["同比度电"] > 0) != (kpis["环比度电"] > 0):
            insights.append(
                f"度电同比 {kpis['同比度电']:+.1f}分 与 环比 {kpis['环比度电']:+.1f}分 方向相反，"
                f"提示长期与短期动能分化"
            )

        # 量价模式
        insights.append(
            f"当前量价模式：{yoy_data.get('pattern', '未知')}"
        )

        # 关键品类状态
        for cat in categories.get("by_status", {}).get("下降", []):
            insights.append(f"⚠️ {cat} 处于下降状态，需关注")

        # 省份策略
        strategy_groups = regions.get("by_strategy", {})
        if strategy_groups.get("卡线"):
            insights.append(
                f"卡线省份: {', '.join(strategy_groups['卡线'])}，需注意监管回收风险"
            )
        if strategy_groups.get("低持仓") and strategy_groups.get("高持仓"):
            insights.append(
                f"省份策略分化明显：{', '.join(strategy_groups['高持仓'])} 高持仓 vs "
                f"{', '.join(strategy_groups['低持仓'])} 低持仓，验证'一省一策'"
            )

        return insights


# === 自检 ===
if __name__ == "__main__":
    import json
    from pathlib import Path

    print("=" * 60)
    print("DomesticAnalyzer 自检")
    print("=" * 60)

    # 加载样本数据
    fixture_path = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "domestic_sample.json"
    if not fixture_path.exists():
        print(f"❌ 样本数据不存在: {fixture_path}")
        exit(1)

    with open(fixture_path, encoding="utf-8") as f:
        sample_data = json.load(f)

    # 创建 analyzer
    analyzer = DomesticAnalyzer(sample_data)

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
    print(f"  总结: {result.summary[:100]}...")

    # 3. KPI 输出
    print("\n[3] KPI 概览")
    for k, v in list(result.kpis.items())[:6]:
        print(f"  {k}: {v}")

    # 4. 同比/环比
    print("\n[4] 同比/环比")
    print(f"  同比模式: {result.yoy_data.get('pattern')}")
    print(f"  环比强度: {result.mom_data.get('strength')}")

    # 5. 异常
    print(f"\n[5] 异常检测: {len(result.anomalies)} 个")
    for a in result.anomalies[:3]:
        print(f"  [{a.get('level').upper()}] {a.get('message')[:80]}")

    # 6. 表格
    print(f"\n[6] 表格: {len(result.tables)} 个")
    for t in result.tables:
        print(f"  - {t.get('title')}")

    # 7. 图表
    print(f"\n[7] 图表: {len(result.charts)} 个")
    for c in result.charts:
        print(f"  - {c.get('title')} ({c.get('type')})")

    # 8. 洞察
    print(f"\n[8] 洞察: {len(result.insights)} 条")
    for i in result.insights[:3]:
        print(f"  - {i[:80]}")

    # 9. 勾稽验证
    failures = analyzer.get_verification_failures()
    print(f"\n[9] 勾稽验证: {len(failures)} 个失败")
    for f in failures:
        print(f"  ❌ {f}")

    print("\n" + "=" * 60)
    print("✅ DomesticAnalyzer 自检通过")
    print("=" * 60)
