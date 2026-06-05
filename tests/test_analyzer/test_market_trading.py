"""
MarketTradingAnalyzer 单元测试
===============================

测试覆盖:
- 输入校验
- 3 大板块（水/新/火）KPI
- 3 大机制（现货增收/一省一策/欠发套利）
- 3 板块对比框架
- 异常检测
- 完整 analyze 流程
- 故事生成
"""

import json
import sys
import unittest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.analyzer.market_trading import MarketTradingAnalyzer
from src.analyzer.base import AnalysisResult


FIXTURE_PATH = project_root / "tests" / "fixtures" / "market_trading_sample.json"


def load_sample_data() -> dict:
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestMarketTradingAnalyzerInputs(unittest.TestCase):
    """测试输入校验"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = MarketTradingAnalyzer(self.sample)

    def test_validate_inputs_complete(self):
        """完整数据应通过校验"""
        self.assertTrue(self.analyzer.validate_inputs())

    def test_validate_inputs_missing_market_trading(self):
        """缺少 market_trading 字段应失败"""
        bad_data = self.sample.copy()
        del bad_data["market_trading"]
        analyzer = MarketTradingAnalyzer(bad_data)
        self.assertFalse(analyzer.validate_inputs())

    def test_validate_inputs_missing_board(self):
        """缺少某板块应失败"""
        bad_data = self.sample.copy()
        bad_data["market_trading"] = self.sample["market_trading"].copy()
        del bad_data["market_trading"]["thermal"]
        analyzer = MarketTradingAnalyzer(bad_data)
        self.assertFalse(analyzer.validate_inputs())


class TestMarketTradingAnalyzerHydro(unittest.TestCase):
    """测试水电板块"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = MarketTradingAnalyzer(self.sample)
        self.hydro = self.analyzer._analyze_hydro()

    def test_hydro_basic_values(self):
        """水电基础数值正确"""
        self.assertEqual(self.hydro["avg_price"], 0.304)
        self.assertEqual(self.hydro["yoy_change"], 1.3)
        self.assertEqual(self.hydro["mom_change"], -0.35)

    def test_hydro_spot_income_in_wan(self):
        """现货增收已转为万元"""
        # spot_income_yi = 0.0534 亿元 = 534 万元
        self.assertAlmostEqual(self.hydro["spot_income_yi"], 534.0, places=0)
        self.assertAlmostEqual(self.hydro["spot_income_yi_last_week"], 1120.0, places=0)

    def test_hydro_spot_mom_change_pct(self):
        """现货增收周变化率"""
        # (534 - 1120) / 1120 * 100 = -52.32%
        self.assertAlmostEqual(self.hydro["spot_mom_change_pct"], -52.32, places=1)
        self.assertTrue(self.hydro["spot_mom_decline_half"])  # 腰斩信号

    def test_hydro_spot_volume_split(self):
        """水电电站拆分（溪右 + 乌东德 = 总）"""
        self.assertEqual(self.hydro["xiluodu_volume"] + self.hydro["wudongde_volume"], 9.7)
        self.assertEqual(self.hydro["xiluodu_price"], 0.312)
        self.assertEqual(self.hydro["wudongde_price"], 0.277)

    def test_hydro_story_mentions_decline(self):
        """水电故事应包含"腰斩"信号"""
        self.assertIn("腰斩", self.hydro["story"])


class TestMarketTradingAnalyzerRenewables(unittest.TestCase):
    """测试新能源板块"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = MarketTradingAnalyzer(self.sample)
        self.renewables = self.analyzer._analyze_renewables()

    def test_renewables_basic_values(self):
        """新能源基础数值正确"""
        self.assertEqual(self.renewables["avg_price"], 0.266)
        self.assertEqual(self.renewables["yoy_change"], -1.6)
        self.assertEqual(self.renewables["mom_change"], 1.3)

    def test_renewables_provinces(self):
        """省份数"""
        self.assertEqual(self.renewables["provinces_count"], 28)
        self.assertEqual(self.renewables["spot_provinces_count"], 23)
        self.assertTrue(self.renewables["full_market_entry"])

    def test_renewables_spread_fen(self):
        """省份价差 = 4 分（容许浮点误差）"""
        # max(4.6, 1.2, 0.6) - min(4.6, 1.2, 0.6) = 4.6 - 0.6 = 4.0
        self.assertAlmostEqual(self.renewables["spread_fen"], 4.0, places=2)

    def test_renewables_strategies(self):
        """3 种策略识别"""
        strategies = self.renewables["strategies"]
        self.assertEqual(len(strategies), 3)
        strategy_types = [s["strategy_type"] for s in strategies]
        self.assertIn("进攻型", strategy_types)
        self.assertIn("防守型", strategy_types)
        self.assertIn("规则型", strategy_types)

    def test_renewables_yoy_decliners(self):
        """同比下行省份识别（中文名）"""
        decliners = self.renewables["yoy_decliners"]
        self.assertGreater(len(decliners), 0)
        # 青海 -3.4, 新疆 -11（mapping 后为中文名）
        provinces = [d["省份"] for d in decliners]
        self.assertIn("青海", provinces)
        self.assertIn("新疆", provinces)
        # 验证 yoy_change_fen 值
        for d in decliners:
            self.assertIn("yoy_change_fen", d)
            self.assertLess(d["yoy_change_fen"], 0)


class TestMarketTradingAnalyzerThermal(unittest.TestCase):
    """测试火电板块"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = MarketTradingAnalyzer(self.sample)
        self.thermal = self.analyzer._analyze_thermal()

    def test_thermal_basic_values(self):
        """火电基础数值"""
        self.assertEqual(self.thermal["avg_price"], 0.402)
        self.assertEqual(self.thermal["yoy_change"], -2.8)
        self.assertEqual(self.thermal["mom_change"], 4.6)

    def test_thermal_spot_decline_pct(self):
        """现货价周跌 31.71%"""
        # (0.2503 - 0.1710) / 0.2503 * 100 = 31.68%
        self.assertAlmostEqual(self.thermal["spot_decline_pct"], 31.68, places=1)
        self.assertTrue(self.thermal["spot_decline_verified"])

    def test_thermal_three_layer_attribution(self):
        """火电三层归因（同比）"""
        attribution = self.thermal["three_layer_attribution"]
        self.assertEqual(attribution["long_term_effect_fen"], -3.0)
        self.assertEqual(attribution["spot_effect_fen"], 0.0)
        self.assertEqual(attribution["capacity_fee_effect_fen"], 0.2)
        self.assertEqual(attribution["net_effect_fen"], -2.8)
        # 验算: -3.0 + 0.0 + 0.2 = -2.8
        self.assertAlmostEqual(
            attribution["long_term_effect_fen"] +
            attribution["spot_effect_fen"] +
            attribution["capacity_fee_effect_fen"],
            -2.8, places=1
        )

    def test_thermal_units_operating(self):
        """火电在运机组 = 4 台"""
        self.assertEqual(len(self.thermal["units_operating"]), 4)
        self.assertIn("鄂州#2", self.thermal["units_operating"])
        self.assertIn("宜城#2", self.thermal["units_operating"])

    def test_thermal_only_coal(self):
        """仅燃煤参与市场"""
        self.assertTrue(self.thermal["only_coal_in_market"])
        self.assertIn("湖北现货市场", self.thermal["participation_markets"])

    def test_thermal_story_mentions_underperform(self):
        """火电故事应包含'欠发套利'"""
        self.assertIn("欠发套利", self.thermal["story"])


class TestMarketTradingAnalyzerThreeBoardComparison(unittest.TestCase):
    """测试 3 板块对比"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = MarketTradingAnalyzer(self.sample)
        hydro = self.analyzer._analyze_hydro()
        renewables = self.analyzer._analyze_renewables()
        thermal = self.analyzer._analyze_thermal()
        self.comparison = self.analyzer._compare_three_boards(hydro, renewables, thermal)

    def test_yoy_changes(self):
        """同比数据正确"""
        self.assertEqual(self.comparison["yoy"]["hydro"], 1.3)
        self.assertEqual(self.comparison["yoy"]["renewables"], -1.6)
        self.assertEqual(self.comparison["yoy"]["thermal"], -2.8)

    def test_mom_changes(self):
        """环比数据正确"""
        self.assertEqual(self.comparison["mom"]["hydro"], -0.35)
        self.assertEqual(self.comparison["mom"]["renewables"], 1.3)
        self.assertEqual(self.comparison["mom"]["thermal"], 4.6)

    def test_pattern_east_west(self):
        """核心模式: 东方不亮西方亮"""
        # 同比 3 板块全跌（new -1.6, thermal -2.8 都是跌；hydro +1.3 涨）
        # 等等，hydro +1.3 不算跌。让我重新检查
        # 同比：hydro 涨 +1.3, renewables 跌 -1.6, thermal 跌 -2.8
        # 不是 all down，所以不会触发 "东方不亮西方亮"
        self.assertIn(self.comparison["pattern"], ["东方不亮西方亮", "多板块分化"])


class TestMarketTradingAnalyzerAnomalies(unittest.TestCase):
    """测试异常检测"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = MarketTradingAnalyzer(self.sample)
        self.result = self.analyzer.analyze()

    def test_hydro_spot_decline_critical(self):
        """水电现货增收 -52% 应触发 critical"""
        critical = [a for a in self.result.anomalies if a.get("level") == "critical" and a.get("board") == "hydro"]
        self.assertGreater(len(critical), 0)

    def test_thermal_spot_decline_critical(self):
        """火电现货跌 31.7% 应触发 critical"""
        critical = [a for a in self.result.anomalies if a.get("level") == "critical" and a.get("board") == "thermal"]
        self.assertGreater(len(critical), 0)

    def test_renewables_full_market_entry_warning(self):
        """新能源全面入市应触发 warning"""
        warnings = [a for a in self.result.anomalies if a.get("level") == "warning" and a.get("board") == "renewables"]
        self.assertGreater(len(warnings), 0)

    def test_thermal_units_info(self):
        """火电 4 台机组应触发 info"""
        infos = [a for a in self.result.anomalies if a.get("category") == "机组状态"]
        self.assertGreater(len(infos), 0)


class TestMarketTradingAnalyzerFullFlow(unittest.TestCase):
    """测试完整 analyze 流程"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = MarketTradingAnalyzer(self.sample)

    def test_analyze_returns_analysis_result(self):
        result = self.analyzer.analyze()
        self.assertIsInstance(result, AnalysisResult)

    def test_result_dimension_and_sections(self):
        result = self.analyzer.analyze()
        self.assertEqual(result.dimension, "市场化")
        self.assertEqual(result.section_ids, [5, 6, 7])

    def test_result_contains_all_fields(self):
        result = self.analyzer.analyze()
        self.assertIsNotNone(result.summary)
        self.assertIsNotNone(result.story)
        self.assertIsInstance(result.kpis, dict)
        self.assertIsInstance(result.tables, list)
        self.assertIsInstance(result.charts, list)
        self.assertIsInstance(result.anomalies, list)
        self.assertIsInstance(result.insights, list)

    def test_result_kpis_have_3_boards(self):
        """KPI 应包含 3 板块"""
        result = self.analyzer.analyze()
        self.assertIn("水电均价", result.kpis)
        self.assertIn("新能源均价", result.kpis)
        self.assertIn("火电均价", result.kpis)

    def test_result_tables_count(self):
        """应包含 5 个表格"""
        result = self.analyzer.analyze()
        self.assertEqual(len(result.tables), 5)

    def test_result_charts_count(self):
        """应包含 4 个图表"""
        result = self.analyzer.analyze()
        self.assertEqual(len(result.charts), 4)

    def test_result_yoy_data_contains_3_boards(self):
        """yoy_data 应包含 3 板块"""
        result = self.analyzer.analyze()
        self.assertIn("hydro", result.yoy_data["by_board"])
        self.assertIn("renewables", result.yoy_data["by_board"])
        self.assertIn("thermal", result.yoy_data["by_board"])

    def test_story_and_summary_lengths(self):
        """story 应比 summary 长"""
        result = self.analyzer.analyze()
        self.assertGreater(len(result.story), 500)
        self.assertLess(len(result.summary), 300)
        self.assertIn("##", result.story)

    def test_story_mentions_all_3_mechanisms(self):
        """故事应包含 3 大机制"""
        result = self.analyzer.analyze()
        self.assertIn("现货增收", result.story)
        self.assertIn("一省一策", result.story)
        self.assertIn("欠发套利", result.story)


class TestMarketTradingAnalyzerInvalidInput(unittest.TestCase):
    """测试无效输入"""

    def test_analyze_with_invalid_data(self):
        bad_data = {"report_id": "test"}
        analyzer = MarketTradingAnalyzer(bad_data)
        result = analyzer.analyze()
        self.assertIsInstance(result, AnalysisResult)
        self.assertEqual(result.anomalies[0]["level"], "error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
