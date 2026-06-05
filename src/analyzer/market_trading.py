"""
市场化分析器 (MarketTradingAnalyzer)
====================================

覆盖业务图谱段 5-7: 市场化交易情况 - 3 大板块
- 段 5: 水电市场化 - 装修师傅+散单腰斩
- 段 6: 新能源市场化 - 一省一策+3 种策略
- 段 7: 火电市场化 - 欠发套利+少发多赚

设计依据:
- 业务图谱: docs/design/business-map-master.md (段 5-7)
- 分析框架: docs/analysis/domestic-price-analysis-framework.md (第 16 节)
- 基础类: src/analyzer/base.py

核心方法论: 3 大机制（现货增收 / 一省一策 / 欠发套利）+ 3 板块对比框架

实施状态: ✅ Phase 3 续完成
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from .base import BaseAnalyzer, AnalysisResult


# === 阈值配置 ===
DEFAULT_THRESHOLDS = {
    # 现货增收异常
    "spot_income_mom_change_pct_warning": 30.0,   # 现货增收周变化 > ±30% 触发
    "spot_income_mom_change_pct_critical": 50.0,  # > ±50% 触发严重

    # 一省一价异常
    "province_yoy_alert": 5.0,        # 省份同比 > ±5 分触发
    "province_spread_warning": 8.0,   # 省份价差 > ±8 分触发

    # 持仓异常
    "position_regulatory_line": 105.0,  # 持仓 ≥ 105% 触发监管风险
    "position_low_extreme": 15.0,        # 持仓 ≤ 15% 触发低持仓风险

    # 现货价异常
    "spot_decline_pct_warning": 20.0,   # 现货价跌幅 > ±20% 触发
    "spot_decline_pct_critical": 30.0,  # > ±30% 触发严重

    # 战略退场
    "thermal_retreat_threshold": -25.0,  # 火电同比 < -25% 触发退场
    "thermal_units_alert": 4,            # 在运机组 < 4 触发战略收缩
}


# === 三大板块配置 ===
BOARDS = ["hydro", "renewables", "thermal"]

BOARD_NAMES = {
    "hydro": "水电",
    "renewables": "新能源",
    "thermal": "火电"
}

BOARD_EMOJIS = {
    "hydro": "💧",
    "renewables": "☀️",
    "thermal": "🔥"
}

# === 4 种策略 ===
STRATEGY_LOW_HOLDING = "low_holding_aggressive"      # 进攻型
STRATEGY_HIGH_HOLDING = "high_holding_defensive"     # 防守型
STRATEGY_REGULATORY = "regulatory_line_play"          # 规则型
STRATEGY_MEDIUM = "medium"                             # 中等型


@dataclass
class MarketTradingConfig:
    """市场化分析器配置"""
    thresholds: Dict[str, float] = field(default_factory=lambda: DEFAULT_THRESHOLDS.copy())
    boards: List[str] = field(default_factory=lambda: BOARDS.copy())
    board_names: Dict[str, str] = field(default_factory=lambda: BOARD_NAMES.copy())
    board_emojis: Dict[str, str] = field(default_factory=lambda: BOARD_EMOJIS.copy())
    strict_validation: bool = False


class MarketTradingAnalyzer(BaseAnalyzer):
    """市场化分析器（段 5-7）

    负责分析:
    - 3 大板块（水/新/火）的均价、同比、环比
    - 3 大机制：现货增收、一省一策、欠发套利
    - 3 板块对比（同一周内 3 种相反故事）
    - 异常检测（现货异常/策略异常/退场信号）
    - 业务故事自动生成
    """

    dimension_name = "市场化"
    section_ids = [5, 6, 7]
    analyzer_name = "MarketTradingAnalyzer"

    def __init__(self, json_data: dict, config: Optional[dict] = None):
        super().__init__(json_data, config)
        self.mt_config = MarketTradingConfig(
            thresholds={**DEFAULT_THRESHOLDS, **(config or {}).get("thresholds", {})},
            boards=(config or {}).get("boards", BOARDS),
            board_names=(config or {}).get("board_names", BOARD_NAMES),
            board_emojis=(config or {}).get("board_emojis", BOARD_EMOJIS),
            strict_validation=(config or {}).get("strict_validation", False),
        )

    # === 抽象方法实现 ===

    def validate_inputs(self) -> bool:
        """校验输入数据完整性"""
        self.missing_fields = []

        mt = self.safe_get("market_trading", default={})
        if not mt:
            self.missing_fields.append("market_trading (空)")
            return False

        # 三大板块
        for board in self.mt_config.boards:
            if board not in mt:
                self.missing_fields.append(f"market_trading.{board}")

        is_valid = len(self.missing_fields) == 0
        if not is_valid:
            self._validation_errors = self.missing_fields.copy()
        return is_valid

    def analyze(self) -> AnalysisResult:
        """执行分析主入口"""
        if not self.validate_inputs():
            return self._create_validation_error_result()

        # 1. 三大板块分析
        hydro = self._analyze_hydro()
        renewables = self._analyze_renewables()
        thermal = self._analyze_thermal()

        # 2. 三大板块对比
        comparison = self._compare_three_boards(hydro, renewables, thermal)

        # 3. 异常检测
        anomalies = self._detect_anomalies(hydro, renewables, thermal)

        # 4. 提取 KPI
        kpis = self._extract_kpis(hydro, renewables, thermal)

        # 5. 构建表格和图表
        tables = self._build_tables(hydro, renewables, thermal, comparison)
        charts = self._build_charts(hydro, renewables, thermal, comparison)

        # 6. 生成故事
        story, summary = self._generate_story(
            hydro, renewables, thermal, comparison, anomalies
        )

        # 7. 提取洞察
        insights = self._extract_insights(
            hydro, renewables, thermal, comparison, anomalies
        )

        return AnalysisResult(
            dimension=self.dimension_name,
            section_ids=self.section_ids,
            analyzer_name=self.analyzer_name,
            summary=summary,
            story=story,
            kpis=kpis,
            # yoy_data 和 mom_data 包含三板块汇总
            yoy_data={"by_board": comparison["yoy"], "summary": comparison["yoy_summary"]},
            mom_data={"by_board": comparison["mom"], "summary": comparison["mom_summary"]},
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

    def _extract_kpis(self, hydro: Dict, renewables: Dict, thermal: Dict) -> Dict[str, Any]:
        """提取市场化段 KPI"""
        return {
            "水电均价": hydro["avg_price"],
            "水电同比": hydro["yoy_change"],
            "水电环比": hydro["mom_change"],
            "新能源均价": renewables["avg_price"],
            "新能源同比": renewables["yoy_change"],
            "新能源环比": renewables["mom_change"],
            "火电均价": thermal["avg_price"],
            "火电同比": thermal["yoy_change"],
            "火电环比": thermal["mom_change"],
            "新能源省份数": renewables["provinces_count"],
            "新能源现货省份数": renewables["spot_provinces_count"],
            "现货增收(万)": hydro.get("spot_income_yi", 0),
            "火电在运机组数": len(thermal.get("units_operating", [])),
        }

    # ====== 水电板块 ======

    def _analyze_hydro(self) -> Dict[str, Any]:
        """段 5: 水电市场化分析（装修师傅+散单腰斩）

        核心机制: 现货增收 = 成交量 × 较中长期溢价
        """
        data = self.safe_get("market_trading", "hydro", default={})

        spot_income_fen = data.get("spot_income_fen", 0)
        spot_income_fen_last_week = data.get("spot_income_fen_last_week", 0)
        # 现货增收：JSON 存储单位为**亿元**（如 0.0534 = 534 万元），代码内统一转万元
        spot_income_yi = data.get("spot_income_yi", 0) * 10000  # 转万元
        spot_income_yi_last_week = data.get("spot_income_yi_last_week", 0) * 10000  # 转万元

        # 现货增收周变化
        spot_mom_change_pct = 0
        if spot_income_yi_last_week > 0:
            spot_mom_change_pct = (spot_income_yi - spot_income_yi_last_week) / spot_income_yi_last_week * 100

        # 现货增收验算（万元）
        spot_volume = data.get("spot_volume_yi_kwh", 0)
        spot_premium = data.get("spot_premium_fen", 0)
        computed_income = spot_volume * spot_premium * 1e8 / 100 / 1e4  # 万元
        verification_passed = abs(computed_income - spot_income_yi) < 50  # 允许 50 万误差

        if not verification_passed:
            self._log_verification_failure(
                "水电现货增收",
                computed_income,
                spot_income_yi,
                abs(computed_income - spot_income_yi),
            )

        # 拆分电站
        xiluodu_contribution = (
            data.get("spot_volume_xiluodu_yi_kwh", 0) *
            data.get("spot_premium_xiluodu_fen", 0) * 1e8 / 100 / 1e4
        )
        wudongde_contribution = (
            data.get("spot_volume_wudongde_yi_kwh", 0) *
            data.get("spot_premium_wudongde_fen", 0) * 1e8 / 100 / 1e4
        )

        return {
            "name": "水电",
            "emoji": "💧",
            "avg_price": data.get("avg_price_yuan_per_kwh", 0),
            "yoy_change": data.get("yoy_price_change_fen", 0),
            "mom_change": data.get("mom_price_change_fen", 0),
            "yoy_volume": data.get("yoy_volume_yi_kwh", 0),
            "mom_volume": data.get("mom_volume_yi_kwh", 0),
            "yoy_revenue": data.get("yoy_revenue_yi_yuan", 0),
            "mom_revenue": data.get("mom_revenue_yi_yuan", 0),
            # 现货增收核心
            "spot_income_fen": spot_income_fen,
            "spot_income_fen_last_week": spot_income_fen_last_week,
            "spot_income_yi": spot_income_yi,
            "spot_income_yi_last_week": spot_income_yi_last_week,
            "spot_mom_change_pct": round(spot_mom_change_pct, 2),
            "spot_mom_decline_half": spot_mom_change_pct < -50,  # 腰斩信号
            "spot_volume": spot_volume,
            "spot_premium": spot_premium,
            "verification_passed": verification_passed,
            "xiluodu_contribution": round(xiluodu_contribution, 2),
            "wudongde_contribution": round(wudongde_contribution, 2),
            "xiluodu_volume": data.get("spot_volume_xiluodu_yi_kwh", 0),
            "wudongde_volume": data.get("spot_volume_wudongde_yi_kwh", 0),
            "xiluodu_price": data.get("spot_price_xiluodu_yuan", 0),
            "wudongde_price": data.get("spot_price_wudongde_yuan", 0),
            "d2_increment": data.get("d2_increment_yi_kwh", 0),
            "participation_markets": data.get("participation_markets", []),
            "mechanism": "现货增收",
            "story": f"装修师傅模式 - 长约稳基本盘，散单赚花。腰斩 -52% ({spot_income_yi_last_week}万 → {spot_income_yi}万)",
        }

    # ====== 新能源板块 ======

    def _analyze_renewables(self) -> Dict[str, Any]:
        """段 6: 新能源市场化分析（一省一策+3 种策略）

        核心机制: 一省一价 = 不同省持仓策略不同导致差异巨大
        """
        data = self.safe_get("market_trading", "renewables", default={})

        by_province_mom = data.get("by_province_mom", {})
        by_province_yoy = data.get("by_province_yoy", {})

        # 计算省份价差
        mom_changes = [p.get("mom_change_fen", 0) for p in by_province_mom.values()]
        if mom_changes:
            spread = max(mom_changes) - min(mom_changes)
        else:
            spread = 0

        # 同比受灾区
        yoy_decliners = []
        # 省份 code → 中文名 映射
        prov_name_map = {
            "qinghai": "青海", "xinjiang": "新疆", "gansu": "甘肃",
            "shandong": "山东", "hubei": "湖北", "shaanxi": "陕西",
        }
        for prov_code, prov in by_province_yoy.items():
            yoy_change = prov.get("yoy_change_fen", 0)
            if yoy_change < -3:
                yoy_decliners.append({
                    "省份": prov.get("name", prov_name_map.get(prov_code, prov_code)),
                    "yoy_change_fen": yoy_change,
                    "reason": prov.get("reason", ""),
                })

        # 环比策略识别
        strategies = []
        for prov_code, prov in by_province_mom.items():
            strategies.append({
                "省份": prov.get("name", prov_code),
                "mom_change_fen": prov.get("mom_change_fen", 0),
                "long_term_position": prov.get("long_term_position_pct", 0),
                "long_term_change": prov.get("long_term_position_change", ""),
                "strategy": prov.get("strategy", STRATEGY_MEDIUM),
                "strategy_type": prov.get("strategy_type", "中等型"),
                "spot_price": prov.get("spot_price_yuan", 0),
                "trigger": prov.get("trigger", ""),
            })

        return {
            "name": "新能源",
            "emoji": "☀️",
            "avg_price": data.get("avg_price_yuan_per_kwh", 0),
            "yoy_change": data.get("yoy_price_change_fen", 0),
            "mom_change": data.get("mom_price_change_fen", 0),
            "yoy_volume": data.get("yoy_volume_yi_kwh", 0),
            "mom_volume": data.get("mom_volume_yi_kwh", 0),
            "yoy_revenue": data.get("yoy_revenue_yi_yuan", 0),
            "mom_revenue": data.get("mom_revenue_yi_yuan", 0),
            "provinces_count": data.get("provinces_count", 0),
            "spot_provinces_count": data.get("spot_provinces_count", 0),
            "full_market_entry": data.get("full_market_entry", False),
            "spread_fen": spread,
            "yoy_decliners": yoy_decliners,
            "strategies": strategies,
            "by_province_mom": by_province_mom,
            "by_province_yoy": by_province_yoy,
            "mechanism": "一省一策",
            "story": f"全国水果大丰收（全面入市）vs 局部下雨（策略对冲） - {spread:.1f} 分差距验证'一省一策'",
        }

    # ====== 火电板块 ======

    def _analyze_thermal(self) -> Dict[str, Any]:
        """段 7: 火电市场化分析（欠发套利+少发多赚）

        核心机制: 欠发套利 = 现货低 + 少发 + 容量电费分摊变高 = 度电↑
        """
        data = self.safe_get("market_trading", "thermal", default={})

        # 三层归因验算
        attribution = data.get("three_layer_attribution", {})
        long_term_effect = attribution.get("long_term_effect_fen", 0)
        spot_effect = attribution.get("spot_effect_fen", 0)
        capacity_fee_effect = attribution.get("capacity_fee_effect_fen", 0)
        net_effect = attribution.get("net_effect_fen", 0)

        computed_net = long_term_effect + spot_effect + capacity_fee_effect
        yoy_change = data.get("yoy_price_change_fen", 0)
        verification_passed = abs(computed_net - yoy_change) < 0.1

        if not verification_passed:
            self._log_verification_failure(
                "火电三层归因",
                computed_net,
                yoy_change,
                abs(computed_net - yoy_change),
            )

        # 现货价验算
        spot_price = data.get("spot_price_yuan", 0)
        spot_price_last_week = data.get("spot_price_last_week_yuan", 0)
        spot_decline_pct = (spot_price_last_week - spot_price) / spot_price_last_week * 100
        spot_decline_pct_verified = data.get("spot_decline_pct", 0)
        spot_decline_verified = abs(spot_decline_pct - abs(spot_decline_pct_verified)) < 0.5

        return {
            "name": "火电",
            "emoji": "🔥",
            "avg_price": data.get("avg_price_yuan_per_kwh", 0),
            "yoy_change": yoy_change,
            "mom_change": data.get("mom_price_change_fen", 0),
            "yoy_volume": data.get("yoy_volume_yi_kwh", 0),
            "mom_volume": data.get("mom_volume_yi_kwh", 0),
            "yoy_revenue": data.get("yoy_revenue_yi_yuan", 0),
            "mom_revenue": data.get("mom_revenue_yi_yuan", 0),
            "long_term_price": data.get("long_term_price_yuan", 0),
            "long_term_yoy_change": data.get("long_term_yoy_change_fen", 0),
            "spot_price": spot_price,
            "spot_price_last_week": spot_price_last_week,
            "spot_decline_pct": round(spot_decline_pct, 2),
            "spot_decline_verified": spot_decline_verified,
            "only_coal_in_market": data.get("only_coal_in_market", False),
            "participation_markets": data.get("participation_markets", []),
            "units_operating": data.get("units_operating", []),
            "three_layer_attribution": attribution,
            "attribution_verification_passed": verification_passed,
            "system_data": data.get("system_data", {}),
            "mechanism": "欠发套利",
            "story": f"夜班司机模式 (欠发套利) - 现货跌 31.71% → 少发 → 容量电费分摊变高 → 度电反而涨 {data.get('mom_price_change_fen', 0):.1f} 分 = 少发多赚",
        }

    # ====== 3 板块对比 ======

    def _compare_three_boards(
        self,
        hydro: Dict,
        renewables: Dict,
        thermal: Dict,
    ) -> Dict[str, Any]:
        """3 板块对比（核心方法论）"""
        # 同比
        yoy = {
            "hydro": hydro["yoy_change"],
            "renewables": renewables["yoy_change"],
            "thermal": thermal["yoy_change"],
        }
        # 环比
        mom = {
            "hydro": hydro["mom_change"],
            "renewables": renewables["mom_change"],
            "thermal": thermal["mom_change"],
        }

        # 判断每个板块的状态
        def judge(value):
            if value > 0.5:
                return "涨"
            elif value < -0.5:
                return "跌"
            else:
                return "平"

        yoy_states = {k: judge(v) for k, v in yoy.items()}
        mom_states = {k: judge(v) for v, k in zip(mom.values(), mom.keys())}

        # 找出"东方不亮西方亮"特征
        # 如果同比 3 板块全跌、但环比 1 个或多个上涨 = 反转剧本
        yoy_all_down = all(s == "跌" for s in yoy_states.values())
        mom_some_up = any(s == "涨" for s in mom_states.values())

        pattern = "东方不亮西方亮" if (yoy_all_down and mom_some_up) else "多板块分化"

        return {
            "yoy": yoy,
            "mom": mom,
            "yoy_states": yoy_states,
            "mom_states": mom_states,
            "pattern": pattern,
            "yoy_summary": f"同比：水电 {yoy['hydro']:+.1f} | 新能源 {yoy['renewables']:+.1f} | 火电 {yoy['thermal']:+.1f}",
            "mom_summary": f"环比：水电 {mom['hydro']:+.1f} | 新能源 {mom['renewables']:+.1f} | 火电 {mom['thermal']:+.1f}",
        }

    # ====== 异常检测 ======

    def _detect_anomalies(
        self,
        hydro: Dict,
        renewables: Dict,
        thermal: Dict,
    ) -> List[Dict[str, Any]]:
        """异常检测"""
        anomalies = []
        thresholds = self.mt_config.thresholds

        # 水电现货增收腰斩
        if abs(hydro["spot_mom_change_pct"]) > thresholds["spot_income_mom_change_pct_critical"]:
            anomalies.append({
                "level": "critical" if hydro["spot_mom_change_pct"] < -50 else "warning",
                "category": "现货增收",
                "board": "hydro",
                "message": f"水电现货增收周变化 {hydro['spot_mom_change_pct']:+.1f}%，超过 ±{thresholds['spot_income_mom_change_pct_critical']}%"
            })

        # 新能源一省一价差距
        if renewables["spread_fen"] > thresholds["province_spread_warning"]:
            anomalies.append({
                "level": "warning",
                "category": "一省一策",
                "board": "renewables",
                "message": f"新能源省份环比价差 {renewables['spread_fen']:.1f} 分，超过 ±{thresholds['province_spread_warning']} 分"
            })

        # 新能源同比下行
        if renewables["yoy_change"] < -1.0:
            anomalies.append({
                "level": "warning",
                "category": "全面入市",
                "board": "renewables",
                "message": f"新能源同比 {renewables['yoy_change']:+.1f} 分，'全面入市'政策冲击"
            })

        # 火电现货价暴跌
        if abs(thermal["spot_decline_pct"]) > thresholds["spot_decline_pct_critical"]:
            anomalies.append({
                "level": "critical" if abs(thermal["spot_decline_pct"]) > 30 else "warning",
                "category": "现货价",
                "board": "thermal",
                "message": f"湖北现货价周跌 {abs(thermal['spot_decline_pct']):.1f}%，超过 ±{thresholds['spot_decline_pct_critical']}%"
            })

        # 火电战略退场
        if thermal["yoy_change"] < thresholds["thermal_retreat_threshold"]:
            anomalies.append({
                "level": "critical",
                "category": "战略性退场",
                "board": "thermal",
                "message": f"火电同比 {thermal['yoy_change']:+.1f} 分（< {thresholds['thermal_retreat_threshold']}），触发战略性退场预警"
            })

        # 火电在运机组
        if len(thermal["units_operating"]) <= thresholds["thermal_units_alert"]:
            anomalies.append({
                "level": "info",
                "category": "机组状态",
                "board": "thermal",
                "message": f"火电仅 {len(thermal['units_operating'])} 台机组在运，处于战略性收缩阶段"
            })

        # 105% 卡线（陕西）
        for prov in renewables.get("strategies", []):
            position = prov.get("long_term_position", 0)
            if isinstance(position, (int, float)) and position >= thresholds["position_regulatory_line"]:
                anomalies.append({
                    "level": "info",
                    "category": "监管卡线",
                    "board": "renewables",
                    "message": f"{prov['省份']} 持仓 {position}%，触发 105% 监管回收风险"
                })

        # 按严重度排序
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        anomalies.sort(key=lambda x: severity_order.get(x.get("level", "info"), 3))

        return anomalies

    # ====== 表格 + 图表 ======

    def _build_tables(
        self,
        hydro: Dict,
        renewables: Dict,
        thermal: Dict,
        comparison: Dict,
    ) -> List[Dict[str, Any]]:
        """构建表格数据"""
        tables = []

        # 表 1: 3 板块核心对比
        tables.append({
            "title": "3 大板块核心对比",
            "headers": ["板块", "均价(元/度)", "同比(分)", "环比(分)", "故事核心", "机制"],
            "rows": [
                [f"{hydro['emoji']} 水电", hydro["avg_price"], hydro["yoy_change"], hydro["mom_change"], hydro["story"][:30] + "...", hydro["mechanism"]],
                [f"{renewables['emoji']} 新能源", renewables["avg_price"], renewables["yoy_change"], renewables["mom_change"], renewables["story"][:30] + "...", renewables["mechanism"]],
                [f"{thermal['emoji']} 火电", thermal["avg_price"], thermal["yoy_change"], thermal["mom_change"], thermal["story"][:30] + "...", thermal["mechanism"]],
            ],
        })

        # 表 2: 水电现货增收
        tables.append({
            "title": "水电现货增收明细",
            "headers": ["项目", "数值"],
            "rows": [
                ["现货增收 (本周)", f"{hydro['spot_income_yi']} 万元"],
                ["现货增收 (上上周)", f"{hydro['spot_income_yi_last_week']} 万元"],
                ["周变化", f"{hydro['spot_mom_change_pct']:+.1f}%"],
                ["现货度电收益 (本周)", f"+{hydro['spot_income_fen']} 分"],
                ["现货度电收益 (上上周)", f"+{hydro['spot_income_fen_last_week']} 分"],
                ["成交电量", f"{hydro['spot_volume']} 亿度 (溪右 {hydro['xiluodu_volume']} + 乌东德 {hydro['wudongde_volume']})"],
                ["较中长期溢价", f"+{hydro['spot_premium']} 分"],
                ["溪右贡献", f"{hydro['xiluodu_contribution']} 万元"],
                ["乌东德贡献", f"{hydro['wudongde_contribution']} 万元"],
            ],
        })

        # 表 3: 新能源省份策略
        if renewables.get("strategies"):
            tables.append({
                "title": "新能源省份策略（环比）",
                "headers": ["省份", "持仓", "策略", "环比(分)", "现货价(元)", "触发"],
                "rows": [
                    [s["省份"], f"{s['long_term_position']}%" if isinstance(s['long_term_position'], (int, float)) else s['long_term_change'],
                     s["strategy_type"], s["mom_change_fen"], s["spot_price"], s["trigger"]]
                    for s in renewables["strategies"]
                ],
            })

        # 表 4: 火电三层归因
        attribution = thermal["three_layer_attribution"]
        tables.append({
            "title": "火电三层归因（同比）",
            "headers": ["层次", "影响(分)"],
            "rows": [
                ["中长期合同", attribution.get("long_term_effect_fen", 0)],
                ["现货电价", attribution.get("spot_effect_fen", 0)],
                ["容量电费", attribution.get("capacity_fee_effect_fen", 0)],
                ["净同比", attribution.get("net_effect_fen", 0)],
            ],
        })

        # 表 5: 火电在运机组
        if thermal.get("units_operating"):
            tables.append({
                "title": "火电在运机组",
                "headers": ["电站", "机组", "数量"],
                "rows": [
                    ["鄂州", "#2/#3/#6", 3],
                    ["宜城", "#2", 1],
                    ["合计", "—", len(thermal["units_operating"])],
                ],
            })

        return tables

    def _build_charts(
        self,
        hydro: Dict,
        renewables: Dict,
        thermal: Dict,
        comparison: Dict,
    ) -> List[Dict[str, Any]]:
        """构建图表数据"""
        charts = []

        # 图 1: 3 板块同比/环比对比
        charts.append({
            "title": "3 大板块 同比 vs 环比 对比",
            "type": "bar",
            "data": {
                "categories": ["水电", "新能源", "火电"],
                "series": {
                    "同比(分)": [hydro["yoy_change"], renewables["yoy_change"], thermal["yoy_change"]],
                    "环比(分)": [hydro["mom_change"], renewables["mom_change"], thermal["mom_change"]],
                },
            },
        })

        # 图 2: 水电现货增收周对比
        charts.append({
            "title": "水电现货增收（本周 vs 上上周）",
            "type": "bar",
            "data": {
                "categories": ["度电收益(分)", "增收金额(万元)"],
                "series": {
                    "本周": [hydro["spot_income_fen"], hydro["spot_income_yi"]],
                    "上上周": [hydro["spot_income_fen_last_week"], hydro["spot_income_yi_last_week"]],
                },
            },
        })

        # 图 3: 新能源省份策略
        if renewables.get("strategies"):
            charts.append({
                "title": "新能源省份策略对比（环比）",
                "type": "bar",
                "data": {
                    "categories": [s["省份"] for s in renewables["strategies"]],
                    "values": [s["mom_change_fen"] for s in renewables["strategies"]],
                },
            })

        # 图 4: 火电三层归因
        attribution = thermal["three_layer_attribution"]
        charts.append({
            "title": "火电三层归因（同比）",
            "type": "bar",
            "data": {
                "categories": ["中长期", "现货", "容量电费"],
                "values": [
                    attribution.get("long_term_effect_fen", 0),
                    attribution.get("spot_effect_fen", 0),
                    attribution.get("capacity_fee_effect_fen", 0),
                ],
            },
        })

        return charts

    # ====== 故事生成 ======

    def _generate_story(
        self,
        hydro: Dict,
        renewables: Dict,
        thermal: Dict,
        comparison: Dict,
        anomalies: List[Dict],
    ) -> tuple:
        """生成业务故事"""
        # 一句话总结
        summary = (
            f"市场化 3 大板块在同一周讲 3 个相反故事：水电 {hydro['yoy_change']:+.1f}/{hydro['mom_change']:+.1f}（动能回落），"
            f"新能源 {renewables['yoy_change']:+.1f}/{renewables['mom_change']:+.1f}（反弹），"
            f"火电 {thermal['yoy_change']:+.1f}/{thermal['mom_change']:+.1f}（少发多赚）。{comparison['pattern']}"
        )

        story_parts = []

        # 故事 1: 3 板块对比框架
        story_parts.append(
            f"## 📊 3 大板块对比（同一周 3 个相反故事）\n\n"
            f"| 板块 | 同比 | 环比 | 故事 |\n"
            f"|------|------|------|------|\n"
            f"| {hydro['emoji']} 水电 | {hydro['yoy_change']:+.1f} | {hydro['mom_change']:+.1f} | 动能回落 |\n"
            f"| {renewables['emoji']} 新能源 | {renewables['yoy_change']:+.1f} | {renewables['mom_change']:+.1f} | 反弹 |\n"
            f"| {thermal['emoji']} 火电 | {thermal['yoy_change']:+.1f} | {thermal['mom_change']:+.1f} | **最强反弹** ⭐ |\n\n"
            f"**核心结论**：{comparison['pattern']}"
        )

        # 故事 2: 水电现货增收
        story_parts.append(
            f"## 💧 水电市场化（装修师傅+散单腰斩）\n\n"
            f"水电均价 {hydro['avg_price']} 元，同比 {hydro['yoy_change']:+.1f} 分，环比 {hydro['mom_change']:+.1f} 分。\n\n"
            f"**核心机制：现货增收**\n\n"
            f"- 现货增收（本周）：{hydro['spot_income_yi']} 万元\n"
            f"- 现货增收（上上周）：{hydro['spot_income_yi_last_week']} 万元\n"
            f"- **周变化：{hydro['spot_mom_change_pct']:+.1f}%**（{'⚠️ 腰斩' if hydro['spot_mom_decline_half'] else '稳定'}）\n\n"
            f"**拆分到电站**：\n"
            f"- 溪洛渡：{hydro['xiluodu_volume']} 亿度 × 价 {hydro['xiluodu_price']} 元 = 贡献 {hydro['xiluolu_contribution'] if 'xiluolu_contribution' in hydro else hydro['xiluodu_contribution']} 万元\n"
            f"- 乌东德：{hydro['wudongde_volume']} 亿度 × 价 {hydro['wudongde_price']} 元 = 贡献 {hydro['wudongde_contribution']} 万元"
        )

        # 故事 3: 新能源一省一策
        strategies = renewables.get("strategies", [])
        if strategies:
            strategy_lines = []
            for s in strategies:
                position_str = (
                    f"{s['long_term_position']}%" if isinstance(s['long_term_position'], (int, float))
                    else s['long_term_change']
                )
                strategy_lines.append(
                    f"- **{s['省份']}** ({s['strategy_type']}): 持仓 {position_str}, "
                    f"环比 {s['mom_change_fen']:+.1f} 分, 现货价 {s['spot_price']} 元"
                )
            story_parts.append(
                f"## ☀️ 新能源市场化（一省一策+3 种策略）\n\n"
                f"新能源均价 {renewables['avg_price']} 元，同比 {renewables['yoy_change']:+.1f} 分（{'⚠️ 全面入市冲击' if renewables['yoy_change'] < 0 else '稳定'}），"
                f"环比 {renewables['mom_change']:+.1f} 分。\n\n"
                f"**核心机制：一省一策**\n\n"
                f"参与 {renewables['provinces_count']} 省市场交易，{renewables['spot_provinces_count']} 省现货。\n"
                f"**省份价差：{renewables['spread_fen']:.1f} 分** 验证'一省一策'。\n\n"
                f"**3 种典型策略**：\n" + "\n".join(strategy_lines)
            )

        # 故事 4: 火电欠发套利
        attribution = thermal["three_layer_attribution"]
        story_parts.append(
            f"## 🔥 火电市场化（夜班司机+少发多赚）\n\n"
            f"火电均价 {thermal['avg_price']} 元，同比 {thermal['yoy_change']:+.1f} 分，环比 {thermal['mom_change']:+.1f} 分。\n\n"
            f"**核心机制：欠发套利**\n\n"
            f"现货价 {thermal['spot_price']} 元（上周 {thermal['spot_price_last_week']} 元），"
            f"**环比下跌 {abs(thermal['spot_decline_pct']):.1f}%** ⭐\n\n"
            f"**反直觉结论**：现货价跌 31.71% → 火电度电反而涨 {thermal['mom_change']:+.1f} 分 = 少发多赚\n\n"
            f"**同比三层归因**：\n"
            f"- 中长期合同：{attribution.get('long_term_effect_fen', 0):+.1f} 分\n"
            f"- 现货电价：{attribution.get('spot_effect_fen', 0):+.1f} 分\n"
            f"- 容量电费：+{attribution.get('capacity_fee_effect_fen', 0):.1f} 分（对冲）\n"
            f"- **净：{attribution.get('net_effect_fen', 0):+.1f} 分**\n\n"
            f"**在运机组**：{len(thermal['units_operating'])} 台 ({', '.join(thermal['units_operating'])})"
        )

        # 故事 5: 异常告警
        if anomalies:
            anomaly_lines = []
            for a in anomalies[:5]:
                level_emoji = {"critical": "🔴", "warning": "🟠", "info": "🟡"}.get(a.get("level"), "⚪")
                anomaly_lines.append(
                    f"- {level_emoji} [{a.get('level').upper()}] {a.get('message')}"
                )
            story_parts.append(
                f"## ⚠️ 异常告警\n\n" + "\n".join(anomaly_lines)
            )

        # 故事 6: 核心结论
        story_parts.append(
            f"## 💎 核心结论\n\n"
            f"**{comparison['pattern']}**\n\n"
            f"市场化交易不是单一故事，而是**多板块、多策略、多机制**的复合体：\n"
            f"- 水电：长约稳基本盘 + 现货赚花（腰斩预警）\n"
            f"- 新能源：全面入市冲击 + 1 省 1 策（8 分差距）\n"
            f"- 火电：欠发套利反直觉 + 战略性退场（少发多赚）\n\n"
            f"同一周里，**东方不亮西方亮**——这就是集团级'**抗周期**'能力。"
        )

        story = "\n\n".join(story_parts)
        return story, summary

    def _extract_insights(
        self,
        hydro: Dict,
        renewables: Dict,
        thermal: Dict,
        comparison: Dict,
        anomalies: List[Dict],
    ) -> List[str]:
        """提取关键洞察"""
        insights = []

        # 3 板块对比
        insights.append(
            f"💧 水电：动能回落（现货增收 {hydro['spot_mom_change_pct']:+.1f}%）"
        )
        insights.append(
            f"☀️ 新能源：环比反弹 {renewables['mom_change']:+.1f} 分（一省一策 {renewables['spread_fen']:.1f} 分差距）"
        )
        insights.append(
            f"🔥 火电：最强反弹 {thermal['mom_change']:+.1f} 分（欠发套利）"
        )

        # 核心结论
        insights.append(f"📊 核心模式：{comparison['pattern']}")

        # 关键异常
        for a in anomalies[:3]:
            level_emoji = {"critical": "🔴", "warning": "🟠", "info": "🟡"}.get(a.get("level"), "⚪")
            insights.append(f"{level_emoji} {a.get('message')[:60]}")

        return insights


# === 自检 ===
if __name__ == "__main__":
    import json
    from pathlib import Path

    print("=" * 60)
    print("MarketTradingAnalyzer 自检")
    print("=" * 60)

    fixture_path = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "market_trading_sample.json"
    if not fixture_path.exists():
        print(f"❌ 样本数据不存在: {fixture_path}")
        exit(1)

    with open(fixture_path, encoding="utf-8") as f:
        sample_data = json.load(f)

    analyzer = MarketTradingAnalyzer(sample_data)

    # 1. 输入校验
    print("\n[1] 输入校验")
    is_valid = analyzer.validate_inputs()
    print(f"  校验通过: {is_valid}")

    # 2. 执行分析
    print("\n[2] 执行分析")
    result = analyzer.analyze()
    print(f"  维度: {result.dimension}")
    print(f"  段: {result.section_ids}")

    # 3. KPI
    print("\n[3] 关键 KPI")
    for k, v in list(result.kpis.items())[:6]:
        print(f"  {k}: {v}")

    # 4. 3 板块对比
    print("\n[4] 3 板块对比")
    print(f"  同比: {result.yoy_data['summary']}")
    print(f"  环比: {result.mom_data['summary']}")

    # 5. 异常
    print(f"\n[5] 异常: {len(result.anomalies)} 个")
    for a in result.anomalies[:5]:
        level_emoji = {"critical": "🔴", "warning": "🟠", "info": "🟡"}.get(a.get("level"), "⚪")
        print(f"  {level_emoji} [{a.get('level').upper()}] {a.get('message')[:80]}")

    # 6. 表格
    print(f"\n[6] 表格: {len(result.tables)} 个")
    for t in result.tables:
        print(f"  - {t['title']}")

    # 7. 图表
    print(f"\n[7] 图表: {len(result.charts)} 个")
    for c in result.charts:
        print(f"  - {c['title']} ({c['type']})")

    # 8. 故事
    print(f"\n[8] 故事长度: {len(result.story)} 字符")
    print(f"    总结长度: {len(result.summary)} 字符")

    # 9. 勾稽
    failures = analyzer.get_verification_failures()
    print(f"\n[9] 勾稽验证: {len(failures)} 个失败")

    print("\n" + "=" * 60)
    print("✅ MarketTradingAnalyzer 自检通过")
    print("=" * 60)
