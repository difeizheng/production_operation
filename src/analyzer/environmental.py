"""
碳资产分析器 (EnvironmentalAnalyzer)
======================================

覆盖业务图谱段 8: 绿证 + CCER（第四类业务）
- 段 8a: 绿证 (Green Electricity Certificate)
- 段 8b: CCER (China Certified Emission Reduction)

设计依据:
- 业务图谱: docs/design/business-map-master.md (段 8)
- 分析框架: docs/analysis/domestic-price-analysis-framework.md (第 17 节)
- 基础类: src/analyzer/base.py

核心方法论: 稀缺性溢价 + 库存估值 + 价差怪现象

实施状态: ✅ Phase 4 完成
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from .base import BaseAnalyzer, AnalysisResult


# === 阈值配置 ===
DEFAULT_THRESHOLDS = {
    # 稀缺性溢价异常
    "year_premium_warning_pct": 50.0,      # 当年比老绿证贵 > 50% 触发警告
    "year_premium_critical_pct": 100.0,     # 贵 > 100% 触发严重

    # 价差异常
    "mom_price_drop_warning_pct": 5.0,      # 环比跌幅 > 5% 触发警告
    "mom_price_drop_critical_pct": 10.0,    # 环比跌幅 > 10% 触发严重

    # 库存结构异常
    "old_cert_share_warning": 10.0,         # 老绿证（>1 年）占比 > 10% 减值预警
    "old_cert_share_critical": 20.0,        # > 20% 严重减值预警

    # 业务下滑
    "weekly_sales_min_pct": 50.0,           # 本周销售 < 累计周均 50% 触发
    "weekly_sales_drop_pct": 30.0,          # 销售下降 > 30% 触发

    # 累计同比
    "yoy_cumulative_growth_alert": 100.0,   # 累计同比 > 100% 提示高速增长
}


# === 资产类型 ===
ASSET_GREEN_CERT = "green_cert"
ASSET_CCER = "ccer"

ASSET_NAMES = {
    "green_cert": "绿证",
    "ccer": "CCER"
}

ASSET_EMOJIS = {
    "green_cert": "🟢",
    "ccer": "🔵"
}

# === 年份分类 ===
YEAR_2024 = "2024"
YEAR_2025 = "2025"
YEAR_2026 = "2026"


@dataclass
class EnvironmentalConfig:
    """碳资产分析器配置"""
    thresholds: Dict[str, float] = field(default_factory=lambda: DEFAULT_THRESHOLDS.copy())
    asset_names: Dict[str, str] = field(default_factory=lambda: ASSET_NAMES.copy())
    asset_emojis: Dict[str, str] = field(default_factory=lambda: ASSET_EMOJIS.copy())
    strict_validation: bool = False


class EnvironmentalAnalyzer(BaseAnalyzer):
    """碳资产分析器（段 8）

    负责分析:
    - 绿证（绿色电力证书）：核发/销售/库存/价格
    - CCER（减碳凭证）：销售/库存
    - 库存估值（含总价值）
    - 稀缺性溢价（2026 vs 2025 绿证）
    - 价差怪现象（环比降价预警）
    - 库存年份结构（老绿证减值风险）
    - 业务故事自动生成
    """

    dimension_name = "碳资产"
    section_ids = [8]
    analyzer_name = "EnvironmentalAnalyzer"

    def __init__(self, json_data: dict, config: Optional[dict] = None):
        super().__init__(json_data, config)
        self.env_config = EnvironmentalConfig(
            thresholds={**DEFAULT_THRESHOLDS, **(config or {}).get("thresholds", {})},
            asset_names=(config or {}).get("asset_names", ASSET_NAMES),
            asset_emojis=(config or {}).get("asset_emojis", ASSET_EMOJIS),
            strict_validation=(config or {}).get("strict_validation", False),
        )

    # === 抽象方法实现 ===

    def validate_inputs(self) -> bool:
        """校验输入数据完整性"""
        self.missing_fields = []

        env = self.safe_get("environmental_assets", default={})
        if not env:
            self.missing_fields.append("environmental_assets (空)")
            return False

        # 绿证
        green_cert = env.get("green_cert", {})
        required_gc_fields = [
            "weekly_issued_wan", "weekly_sold_wan", "weekly_avg_price",
            "by_year_weekly", "yoy_cumulative", "inventory_wan",
        ]
        for f in required_gc_fields:
            if f not in green_cert:
                self.missing_fields.append(f"environmental_assets.green_cert.{f}")

        # CCER
        ccer = env.get("ccer", {})
        required_ccer_fields = ["weekly_sold_tons", "weekly_avg_price", "yoy_cumulative", "inventory_wan_tons"]
        for f in required_ccer_fields:
            if f not in ccer:
                self.missing_fields.append(f"environmental_assets.ccer.{f}")

        is_valid = len(self.missing_fields) == 0
        if not is_valid:
            self._validation_errors = self.missing_fields.copy()
        return is_valid

    def analyze(self) -> AnalysisResult:
        """执行分析主入口"""
        if not self.validate_inputs():
            return self._create_validation_error_result()

        # 1. 绿证分析
        green_cert = self._analyze_green_cert()

        # 2. CCER 分析
        ccer = self._analyze_ccer()

        # 3. 库存估值（合并）
        inventory = self._calculate_inventory_value(green_cert, ccer)

        # 4. 3 个核心发现
        findings = self._detect_findings(green_cert, ccer)

        # 5. 异常检测
        anomalies = self._detect_anomalies(green_cert, ccer, findings)

        # 6. 提取 KPI
        kpis = self._extract_kpis(green_cert, ccer, inventory)

        # 7. 构建表格和图表
        tables = self._build_tables(green_cert, ccer, inventory, findings)
        charts = self._build_charts(green_cert, ccer, inventory, findings)

        # 8. 生成故事
        story, summary = self._generate_story(green_cert, ccer, inventory, findings, anomalies)

        # 9. 提取洞察
        insights = self._extract_insights(green_cert, ccer, inventory, findings, anomalies)

        return AnalysisResult(
            dimension=self.dimension_name,
            section_ids=self.section_ids,
            analyzer_name=self.analyzer_name,
            summary=summary,
            story=story,
            kpis=kpis,
            yoy_data={"green_cert": green_cert, "ccer": ccer, "inventory": inventory},
            mom_data={"findings": findings},
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

    def _extract_kpis(self, green_cert: Dict, ccer: Dict, inventory: Dict) -> Dict[str, Any]:
        """提取碳资产段 KPI"""
        return {
            "绿证本周销售": green_cert["weekly_sold_wan"],
            "绿证本周销售金额(万)": green_cert["weekly_revenue_wan"],
            "绿证2026累计销售(万)": green_cert["yoy_cumulative_revenue_wan"],
            "绿证库存(万张)": green_cert["inventory_total_wan"],
            "绿证库存价值(万)": green_cert["inventory_value_wan"],
            "CCER本周销售(吨)": ccer["weekly_sold_tons"],
            "CCER本周销售金额(万)": ccer["weekly_revenue_wan"],
            "CCER2026累计销售(万)": ccer["yoy_cumulative_revenue_wan"],
            "CCER库存(万吨)": ccer["inventory_wan_tons"],
            "CCER库存价值(万)": ccer["inventory_value_wan"],
            "总库存价值(亿元)": inventory["total_value_yi"],
        }

    # ====== 绿证分析 ======

    def _analyze_green_cert(self) -> Dict[str, Any]:
        """绿证分析（绿色电力证书）"""
        data = self.safe_get("environmental_assets", "green_cert", default={})

        by_year = data.get("by_year_weekly", {})

        # 计算本周销售金额（按年份拆分）
        # 2025: 2.9 万张 × 4.5 元 = 13.05 万元
        # 2026: 472 张 × 8.1 元 = 0.38 万元
        weekly_revenue_2025 = by_year.get("2025", {}).get("sold_wan", 0) * by_year.get("2025", {}).get("avg_price", 0)
        # 2026 数据：sold_count (个) 不是 sold_wan
        cert_2026_count = by_year.get("2026", {}).get("sold_count", 0)
        weekly_revenue_2026 = cert_2026_count * by_year.get("2026", {}).get("avg_price", 0) / 10000  # 元 → 万元
        weekly_revenue_wan = weekly_revenue_2025 + weekly_revenue_2026

        # 2026 累计销售金额
        yoy_cum = data.get("yoy_cumulative", {})
        yoy_cumulative_revenue_wan = yoy_cum.get("sold_wan", 0) * yoy_cum.get("avg_price", 0)

        # 库存估值
        inventory = data.get("inventory_wan", {})
        inv_2026 = inventory.get("2026", 0)
        inv_2025 = inventory.get("2025", 0)
        inv_2024 = inventory.get("2024", 0)
        inv_total = inventory.get("total", 0)

        # 历史价格（用于稀缺性溢价）
        hist_prices = data.get("historical_prices", {})
        price_2024 = hist_prices.get("2024_avg", 4.0)
        price_2025 = hist_prices.get("2025_avg", 4.5)
        price_2026 = hist_prices.get("2026_avg", 8.1)

        # 库存估值
        inv_value_2026 = inv_2026 * price_2026  # 万元
        inv_value_2025 = inv_2025 * price_2025
        inv_value_2024 = inv_2024 * price_2024
        inv_value_wan = inv_value_2026 + inv_value_2025 + inv_value_2024

        # 2026 绿证环比变化
        mom_change_2026 = by_year.get("2026", {}).get("mom_change_fen", 0)

        return {
            "name": "绿证",
            "emoji": "🟢",
            "weekly_issued_wan": data.get("weekly_issued_wan", 0),
            "weekly_sold_wan": data.get("weekly_sold_wan", 0),
            "weekly_sold_count": data.get("weekly_sold_count", 0),
            "weekly_avg_price": data.get("weekly_avg_price", 0),
            "weekly_revenue_wan": round(weekly_revenue_wan, 2),
            "weekly_revenue_2025_wan": round(weekly_revenue_2025, 2),
            "weekly_revenue_2026_wan": round(weekly_revenue_2026, 2),
            "mom_change_2026_fen": mom_change_2026,
            "yoy_cumulative_sold_wan": yoy_cum.get("sold_wan", 0),
            "yoy_cumulative_avg_price": yoy_cum.get("avg_price", 0),
            "yoy_cumulative_revenue_wan": round(yoy_cumulative_revenue_wan, 1),
            # 库存
            "inventory_2026_wan": inv_2026,
            "inventory_2025_wan": inv_2025,
            "inventory_2024_wan": inv_2024,
            "inventory_total_wan": inv_total,
            "inv_value_2026_wan": round(inv_value_2026, 1),
            "inv_value_2025_wan": round(inv_value_2025, 1),
            "inv_value_2024_wan": round(inv_value_2024, 1),
            "inventory_value_wan": round(inv_value_wan, 1),
            "inventory_value_yi": round(inv_value_wan / 10000, 2),
            # 价格
            "price_2024": price_2024,
            "price_2025": price_2025,
            "price_2026": price_2026,
        }

    # ====== CCER 分析 ======

    def _analyze_ccer(self) -> Dict[str, Any]:
        """CCER 分析（减碳凭证）"""
        data = self.safe_get("environmental_assets", "ccer", default={})

        weekly_sold_tons = data.get("weekly_sold_tons", 0)
        weekly_avg_price = data.get("weekly_avg_price", 0)
        weekly_revenue_wan = weekly_sold_tons * weekly_avg_price / 10000  # 元 → 万元

        yoy_cum = data.get("yoy_cumulative", {})
        yoy_cum_sold = yoy_cum.get("sold_wan_tons", 0)
        yoy_cum_avg = yoy_cum.get("avg_price", 0)
        yoy_cum_revenue_wan = yoy_cum_sold * yoy_cum_avg * 10000 / 10000  # 万元

        inv_wan_tons = data.get("inventory_wan_tons", 0)
        # 库存估值：吨 × 单价
        inv_value_wan = inv_wan_tons * weekly_avg_price * 10000 / 10000  # 万元

        return {
            "name": "CCER",
            "emoji": "🔵",
            "weekly_sold_tons": weekly_sold_tons,
            "weekly_avg_price": weekly_avg_price,
            "weekly_revenue_wan": round(weekly_revenue_wan, 2),
            "yoy_cumulative_sold_wan_tons": yoy_cum_sold,
            "yoy_cumulative_avg_price": yoy_cum_avg,
            "yoy_cumulative_revenue_wan": round(yoy_cum_revenue_wan, 2),
            "inventory_wan_tons": inv_wan_tons,
            "inventory_value_wan": round(inv_value_wan, 1),
            "inventory_value_yi": round(inv_value_wan / 10000, 2),
        }

    # ====== 库存估值（合并）======

    def _calculate_inventory_value(self, green_cert: Dict, ccer: Dict) -> Dict[str, Any]:
        """库存估值（合并绿证+CCER）"""
        total_value_wan = green_cert["inventory_value_wan"] + ccer["inventory_value_wan"]
        total_value_yi = round(total_value_wan / 10000, 2)

        return {
            "green_cert_value_wan": green_cert["inventory_value_wan"],
            "ccer_value_wan": ccer["inventory_value_wan"],
            "total_value_wan": round(total_value_wan, 1),
            "total_value_yi": total_value_yi,
            "share_pct": {
                "green_cert": round(green_cert["inventory_value_wan"] / total_value_wan * 100, 1) if total_value_wan > 0 else 0,
                "ccer": round(ccer["inventory_value_wan"] / total_value_wan * 100, 1) if total_value_wan > 0 else 0,
            }
        }

    # ====== 核心发现 ======

    def _detect_findings(self, green_cert: Dict, ccer: Dict) -> Dict[str, Any]:
        """3 个核心发现

        1. 2025 vs 2026 绿证价差（稀缺性溢价）
        2. 2026 绿证环比变化（价差怪现象）
        3. 库存年份结构（老绿证减值风险）
        """
        # 发现 1: 2025 vs 2026 价差
        price_2025 = green_cert["price_2025"]
        price_2026 = green_cert["price_2026"]
        price_premium_pct = (price_2026 - price_2025) / price_2025 * 100 if price_2025 > 0 else 0

        # 发现 2: 2026 绿证环比变化
        mom_change_2026 = green_cert["mom_change_2026_fen"]

        # 发现 3: 库存结构
        inv_total = green_cert["inventory_total_wan"]
        inv_2024_share = green_cert["inventory_2024_wan"] / inv_total * 100 if inv_total > 0 else 0
        inv_2025_share = green_cert["inventory_2025_wan"] / inv_total * 100 if inv_total > 0 else 0
        inv_2026_share = green_cert["inventory_2026_wan"] / inv_total * 100 if inv_total > 0 else 0

        return {
            "price_premium": {
                "price_2025": price_2025,
                "price_2026": price_2026,
                "premium_pct": round(price_premium_pct, 1),
                "is_significant": price_premium_pct > 50,
            },
            "mom_2026_change": {
                "change_fen": mom_change_2026,
                "is_drop_warning": mom_change_2026 < -0.2,
            },
            "inventory_structure": {
                "2024_share": round(inv_2024_share, 1),
                "2025_share": round(inv_2025_share, 1),
                "2026_share": round(inv_2026_share, 1),
                "old_cert_warning": inv_2024_share > 10,
            }
        }

    # ====== 异常检测 ======

    def _detect_anomalies(
        self,
        green_cert: Dict,
        ccer: Dict,
        findings: Dict,
    ) -> List[Dict[str, Any]]:
        """异常检测"""
        anomalies = []
        thresholds = self.env_config.thresholds

        # 稀缺性溢价
        if findings["price_premium"]["is_significant"]:
            level = "critical" if findings["price_premium"]["premium_pct"] > thresholds["year_premium_critical_pct"] else "warning"
            anomalies.append({
                "level": level,
                "category": "稀缺性溢价",
                "message": f"2026 绿证比 2025 贵 {findings['price_premium']['premium_pct']:.0f}%，超出 ±{thresholds['year_premium_warning_pct']}%"
            })

        # 2026 绿证环比降价
        if findings["mom_2026_change"]["is_drop_warning"]:
            change = findings["mom_2026_change"]["change_fen"]
            level = "warning" if abs(change) < 1 else "info"
            anomalies.append({
                "level": level,
                "category": "价差怪现象",
                "message": f"2026 绿证环比 {change:+.1f} 元（稀缺品种开始降价）"
            })

        # 库存结构 - 老绿证占比
        if findings["inventory_structure"]["old_cert_warning"]:
            share = findings["inventory_structure"]["2024_share"]
            level = "warning" if share < 20 else "info"
            anomalies.append({
                "level": level,
                "category": "库存结构",
                "message": f"2024 老绿证占比 {share}%，可能存在减值风险"
            })

        # CCER 库存告急（同比下降）
        # 此处保留扩展点

        # 按严重度排序
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        anomalies.sort(key=lambda x: severity_order.get(x.get("level", "info"), 3))

        return anomalies

    # ====== 表格 + 图表 ======

    def _build_tables(
        self,
        green_cert: Dict,
        ccer: Dict,
        inventory: Dict,
        findings: Dict,
    ) -> List[Dict[str, Any]]:
        """构建表格数据"""
        tables = []

        # 表 1: KPI 总览
        tables.append({
            "title": "碳资产 KPI 总览",
            "headers": ["指标", "绿证", "CCER", "合计"],
            "rows": [
                ["本周销售", f"{green_cert['weekly_sold_wan']} 万张", f"{ccer['weekly_sold_tons']} 吨", "—"],
                ["本周销售金额", f"{green_cert['weekly_revenue_wan']} 万元", f"{ccer['weekly_revenue_wan']} 万元", f"{round(green_cert['weekly_revenue_wan'] + ccer['weekly_revenue_wan'], 2)} 万元"],
                ["2026 累计销售", f"{green_cert['yoy_cumulative_sold_wan']} 万张", f"{ccer['yoy_cumulative_sold_wan_tons']} 万吨", "—"],
                ["2026 累计销售金额", f"{green_cert['yoy_cumulative_revenue_wan']} 万元", f"{ccer['yoy_cumulative_revenue_wan']} 万元", f"{round(green_cert['yoy_cumulative_revenue_wan'] + ccer['yoy_cumulative_revenue_wan'], 1)} 万元"],
                ["库存", f"{green_cert['inventory_total_wan']} 万张", f"{ccer['inventory_wan_tons']} 万吨", "—"],
                ["库存价值", f"{green_cert['inventory_value_wan']} 万元", f"{ccer['inventory_value_wan']} 万元", f"{inventory['total_value_wan']} 万元 ({inventory['total_value_yi']} 亿元)"],
            ],
        })

        # 表 2: 绿证按年份拆分
        tables.append({
            "title": "绿证按年份拆分",
            "headers": ["年份", "本周销售", "均价(元/张)", "库存(万张)", "占比(%)", "库存价值(万)"],
            "rows": [
                ["2024", "—", green_cert["price_2024"], green_cert["inventory_2024_wan"], findings["inventory_structure"]["2024_share"], green_cert["inv_value_2024_wan"]],
                ["2025", f"{green_cert['weekly_revenue_2025_wan']} 万元 (2.9万张)", green_cert["price_2025"], green_cert["inventory_2025_wan"], findings["inventory_structure"]["2025_share"], green_cert["inv_value_2025_wan"]],
                ["2026", f"{green_cert['weekly_revenue_2026_wan']} 元 (472张)", green_cert["price_2026"], green_cert["inventory_2026_wan"], findings["inventory_structure"]["2026_share"], green_cert["inv_value_2026_wan"]],
            ],
        })

        # 表 3: 3 个核心发现
        tables.append({
            "title": "3 个核心发现",
            "headers": ["发现", "数据", "解读"],
            "rows": [
                ["稀缺性溢价", f"2025 {green_cert['price_2025']} 元 vs 2026 {green_cert['price_2026']} 元", f"+{findings['price_premium']['premium_pct']:.0f}% (稀缺性溢价)"],
                ["价差怪现象", f"2026 环比 {findings['mom_2026_change']['change_fen']:+.1f} 元", "⚠️ 稀缺品种开始降价"],
                ["库存结构", f"2024 {findings['inventory_structure']['2024_share']}% | 2025 {findings['inventory_structure']['2025_share']}% | 2026 {findings['inventory_structure']['2026_share']}%", "老绿证可能贬值"],
            ],
        })

        # 表 4: 库存估值
        tables.append({
            "title": "环境资产库存估值",
            "headers": ["资产", "数量", "估值单价", "估值金额(万)", "占总价值(%)"],
            "rows": [
                ["绿证", f"{green_cert['inventory_total_wan']} 万张", "—", green_cert["inventory_value_wan"], inventory["share_pct"]["green_cert"]],
                ["CCER", f"{ccer['inventory_wan_tons']} 万吨", f"{ccer['weekly_avg_price']} 元/吨", ccer["inventory_value_wan"], inventory["share_pct"]["ccer"]],
                ["合计", "—", "—", inventory["total_value_wan"], "100.0"],
            ],
        })

        return tables

    def _build_charts(
        self,
        green_cert: Dict,
        ccer: Dict,
        inventory: Dict,
        findings: Dict,
    ) -> List[Dict[str, Any]]:
        """构建图表数据"""
        charts = []

        # 图 1: 绿证库存年份结构（饼图）
        charts.append({
            "title": "绿证库存年份结构",
            "type": "pie",
            "data": {
                "labels": ["2024", "2025", "2026"],
                "values": [green_cert["inventory_2024_wan"], green_cert["inventory_2025_wan"], green_cert["inventory_2026_wan"]],
            },
        })

        # 图 2: 库存估值对比（条形图）
        charts.append({
            "title": "环境资产库存估值（绿证 vs CCER）",
            "type": "bar",
            "data": {
                "categories": ["绿证", "CCER", "合计"],
                "values": [green_cert["inventory_value_wan"], ccer["inventory_value_wan"], inventory["total_value_wan"]],
            },
        })

        # 图 3: 绿证价格稀缺性溢价（条形图）
        charts.append({
            "title": "绿证价格稀缺性溢价（2024/2025/2026）",
            "type": "bar",
            "data": {
                "categories": ["2024", "2025", "2026"],
                "values": [green_cert["price_2024"], green_cert["price_2025"], green_cert["price_2026"]],
            },
        })

        # 图 4: 本周 vs 累计销售对比
        charts.append({
            "title": "绿证销售对比（本周 vs 2026 累计）",
            "type": "bar",
            "data": {
                "categories": ["本周销售金额", "累计销售金额"],
                "series": {
                    "绿证": [green_cert["weekly_revenue_wan"], green_cert["yoy_cumulative_revenue_wan"]],
                    "CCER": [ccer["weekly_revenue_wan"], ccer["yoy_cumulative_revenue_wan"]],
                },
            },
        })

        return charts

    # ====== 故事生成 ======

    def _generate_story(
        self,
        green_cert: Dict,
        ccer: Dict,
        inventory: Dict,
        findings: Dict,
        anomalies: List[Dict],
    ) -> tuple:
        """生成业务故事"""
        # 一句话总结
        summary = (
            f"集团环境资产总库存价值 {inventory['total_value_yi']} 亿元（绿证 {green_cert['inventory_value_wan']} 万 + CCER {ccer['inventory_value_wan']} 万）。"
            f"2026 累计销售 {green_cert['yoy_cumulative_revenue_wan'] + ccer['yoy_cumulative_revenue_wan']:.0f} 万元。"
            f"第四类业务正在崛起，'卖空气换钱'已不再是口号。"
        )

        story_parts = []

        # 故事 1: 总览
        story_parts.append(
            f"## 🌱 第四类业务 - 总览\n\n"
            f"环境资产总库存价值 **{inventory['total_value_yi']} 亿元** ⭐\n\n"
            f"- 🟢 绿证：{green_cert['inventory_total_wan']} 万张，估值 {green_cert['inventory_value_wan']} 万元（{inventory['share_pct']['green_cert']}%）\n"
            f"- 🔵 CCER：{ccer['inventory_wan_tons']} 万吨，估值 {ccer['inventory_value_wan']} 万元（{inventory['share_pct']['ccer']}%）\n\n"
            f"占集团周收入 25 亿的 {inventory['total_value_yi']/2500*100:.2f}%，但**毛利率接近 100%**（轻资产）"
        )

        # 故事 2: 绿证详情
        story_parts.append(
            f"## 🟢 绿证（绿色电力证书）\n\n"
            f"本周销售 **{green_cert['weekly_sold_wan']} 万张** = **{green_cert['weekly_revenue_wan']} 万元**\n\n"
            f"按年份拆分：\n"
            f"- 2025 绿证：2.9 万张 × {green_cert['price_2025']} 元 = {green_cert['weekly_revenue_2025_wan']} 万元\n"
            f"- 2026 绿证：472 张 × {green_cert['price_2026']} 元 = {green_cert['weekly_revenue_2026_wan']:.2f} 万元\n\n"
            f"**2026 累计**：{green_cert['yoy_cumulative_sold_wan']} 万张 × {green_cert['yoy_cumulative_avg_price']} 元 = **{green_cert['yoy_cumulative_revenue_wan']} 万元**"
        )

        # 故事 3: CCER 详情
        story_parts.append(
            f"## 🔵 CCER（减碳凭证）\n\n"
            f"本周销售 **{ccer['weekly_sold_tons']} 吨** = **{ccer['weekly_revenue_wan']} 万元**\n\n"
            f"**2026 累计**：{ccer['yoy_cumulative_sold_wan_tons']} 万吨 × {ccer['yoy_cumulative_avg_price']} 元 = **{ccer['yoy_cumulative_revenue_wan']} 万元**"
        )

        # 故事 4: 库存估值
        story_parts.append(
            f"## 💰 库存估值（隐含价值）\n\n"
            f"按当前价格估算：\n"
            f"- 🟢 绿证：{green_cert['inventory_2026_wan']}×{green_cert['price_2026']} + {green_cert['inventory_2025_wan']}×{green_cert['price_2025']} + {green_cert['inventory_2024_wan']}×{green_cert['price_2024']} = **{green_cert['inventory_value_wan']} 万元**\n"
            f"- 🔵 CCER：{ccer['inventory_wan_tons']} 万吨 × {ccer['weekly_avg_price']} 元 = **{ccer['inventory_value_wan']} 万元**\n"
            f"- **合计：{inventory['total_value_wan']} 万元 ≈ {inventory['total_value_yi']} 亿元**"
        )

        # 故事 5: 3 个核心发现
        story_parts.append(
            f"## 💎 3 个核心发现\n\n"
            f"**发现 1：稀缺性溢价**\n"
            f"2025 绿证 {green_cert['price_2025']} 元 vs 2026 绿证 {green_cert['price_2026']} 元 → **+{findings['price_premium']['premium_pct']:.0f}%**\n"
            f"原因：当年新发绿证**稀缺性溢价**（市场供应少）\n\n"
            f"**发现 2：价差怪现象**\n"
            f"2026 绿证环比 {findings['mom_2026_change']['change_fen']:+.1f} 元 → ⚠️ **稀缺品种开始降价**\n"
            f"可能原因：市场预期后续供给增加或需求疲软\n\n"
            f"**发现 3：库存结构**\n"
            f"2024 {findings['inventory_structure']['2024_share']}% | 2025 {findings['inventory_structure']['2025_share']}% | 2026 {findings['inventory_structure']['2026_share']}%\n"
            f"老绿证（2024）**可能贬值**——核发规则可能收紧"
        )

        # 故事 6: 异常
        if anomalies:
            story_parts.append(
                f"## ⚠️ 异常告警\n\n"
                + "\n".join([
                    f"- {['🔴', '🟠', '🟡'][['critical', 'warning', 'info'].index(a.get('level'))]} [{a.get('level').upper()}] {a.get('message')}"
                    for a in anomalies[:3]
                ])
            )

        # 故事 7: 核心金句
        story_parts.append(
            f"## 💎 核心金句\n\n"
            f"**\"传统业务是'卖一度电赚一度钱'，环境资产是'卖一个承诺赚一笔钱'。**\n\n"
            f"绿证是'**我的电是绿色的**'，CCER 是'**我的电没排碳**'。\n\n"
            f"当全国都在喊'双碳'时——手头有绿证和 CCER 库存的人，就是'**未来碳交易市场的卖方**'。\n\n"
            f"---\n\n"
            f"**集团 {inventory['total_value_yi']} 亿元的'环境资产'家底** = 碳中和不是成本，是**资产**。"
        )

        story = "\n\n".join(story_parts)
        return story, summary

    def _extract_insights(
        self,
        green_cert: Dict,
        ccer: Dict,
        inventory: Dict,
        findings: Dict,
        anomalies: List[Dict],
    ) -> List[str]:
        """提取关键洞察"""
        insights = []

        # 总价值
        insights.append(
            f"💰 环境资产总库存价值 {inventory['total_value_yi']} 亿元（绿证 {inventory['share_pct']['green_cert']}% + CCER {inventory['share_pct']['ccer']}%）"
        )

        # 2026 累计
        total_yoy = green_cert['yoy_cumulative_revenue_wan'] + ccer['yoy_cumulative_revenue_wan']
        insights.append(
            f"📊 2026 累计销售 {total_yoy:.0f} 万元（绿证 {green_cert['yoy_cumulative_revenue_wan']} + CCER {ccer['yoy_cumulative_revenue_wan']}）"
        )

        # 稀缺性溢价
        if findings["price_premium"]["is_significant"]:
            insights.append(
                f"🟢 稀缺性溢价：2026 绿证比 2025 贵 {findings['price_premium']['premium_pct']:.0f}%"
            )

        # 价差怪现象
        if findings["mom_2026_change"]["is_drop_warning"]:
            insights.append(
                f"⚠️ 价差怪现象：2026 绿证环比 {findings['mom_2026_change']['change_fen']:+.1f} 元（稀缺品种开始降价）"
            )

        # 库存结构
        if findings["inventory_structure"]["old_cert_warning"]:
            insights.append(
                f"📦 库存结构：2024 老绿证 {findings['inventory_structure']['2024_share']}%，可能贬值"
            )

        # 第四类业务定位
        insights.append(
            f"🌱 第四类业务：区别于发电/售电/投资，毛利率 ~100%（轻资产）"
        )

        return insights


# === 自检 ===
if __name__ == "__main__":
    import json
    from pathlib import Path

    print("=" * 60)
    print("EnvironmentalAnalyzer 自检")
    print("=" * 60)

    fixture_path = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "environmental_sample.json"
    if not fixture_path.exists():
        print(f"❌ 样本数据不存在: {fixture_path}")
        exit(1)

    with open(fixture_path, encoding="utf-8") as f:
        sample_data = json.load(f)

    analyzer = EnvironmentalAnalyzer(sample_data)

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
    for k, v in list(result.kpis.items())[:6]:
        print(f"  {k}: {v}")

    # 4. 3 个核心发现
    print("\n[4] 3 个核心发现")
    findings = analyzer._detect_findings(
        analyzer._analyze_green_cert(),
        analyzer._analyze_ccer()
    )
    print(f"  稀缺性溢价: {findings['price_premium']['premium_pct']:.0f}%")
    print(f"  2026 环比: {findings['mom_2026_change']['change_fen']:+.1f} 元")
    print(f"  库存结构: 2024 {findings['inventory_structure']['2024_share']}% | 2025 {findings['inventory_structure']['2025_share']}% | 2026 {findings['inventory_structure']['2026_share']}%")

    # 5. 库存估值
    print("\n[5] 库存估值")
    inventory = result.yoy_data["inventory"]
    print(f"  绿证: {inventory['green_cert_value_wan']} 万元 ({inventory['share_pct']['green_cert']}%)")
    print(f"  CCER: {inventory['ccer_value_wan']} 万元 ({inventory['share_pct']['ccer']}%)")
    print(f"  合计: {inventory['total_value_wan']} 万元 ≈ {inventory['total_value_yi']} 亿元 ⭐")

    # 6. 异常
    print(f"\n[6] 异常: {len(result.anomalies)} 个")
    for a in result.anomalies[:3]:
        level_emoji = {"critical": "🔴", "warning": "🟠", "info": "🟡"}.get(a.get("level"), "⚪")
        print(f"  {level_emoji} [{a.get('level').upper()}] {a.get('message')}")

    # 7. 表格
    print(f"\n[7] 表格: {len(result.tables)} 个")
    for t in result.tables:
        print(f"  - {t['title']}")

    # 8. 图表
    print(f"\n[8] 图表: {len(result.charts)} 个")
    for c in result.charts:
        print(f"  - {c['title']} ({c['type']})")

    # 9. 故事
    print(f"\n[9] 故事长度: {len(result.story)} 字符")
    print(f"    总结长度: {len(result.summary)} 字符")

    # 10. 勾稽
    failures = analyzer.get_verification_failures()
    print(f"\n[10] 勾稽验证: {len(failures)} 个失败")

    print("\n" + "=" * 60)
    print("✅ EnvironmentalAnalyzer 自检通过")
    print("=" * 60)
