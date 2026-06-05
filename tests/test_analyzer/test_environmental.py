"""
EnvironmentalAnalyzer 单元测试
================================

测试覆盖:
- 输入校验
- 绿证分析（含年份拆分、库存估值）
- CCER 分析
- 库存估值（合并）
- 3 个核心发现（稀缺性溢价/价差怪现象/库存结构）
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

from src.analyzer.environmental import EnvironmentalAnalyzer
from src.analyzer.base import AnalysisResult


FIXTURE_PATH = project_root / "tests" / "fixtures" / "environmental_sample.json"


def load_sample_data() -> dict:
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestEnvironmentalAnalyzerInputs(unittest.TestCase):
    """测试输入校验"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = EnvironmentalAnalyzer(self.sample)

    def test_validate_inputs_complete(self):
        """完整数据应通过校验"""
        self.assertTrue(self.analyzer.validate_inputs())

    def test_validate_inputs_missing_green_cert(self):
        """缺少 green_cert 应失败"""
        bad_data = self.sample.copy()
        bad_data["environmental_assets"] = self.sample["environmental_assets"].copy()
        del bad_data["environmental_assets"]["green_cert"]
        analyzer = EnvironmentalAnalyzer(bad_data)
        self.assertFalse(analyzer.validate_inputs())

    def test_validate_inputs_missing_ccer(self):
        """缺少 ccer 应失败"""
        bad_data = self.sample.copy()
        bad_data["environmental_assets"] = self.sample["environmental_assets"].copy()
        del bad_data["environmental_assets"]["ccer"]
        analyzer = EnvironmentalAnalyzer(bad_data)
        self.assertFalse(analyzer.validate_inputs())


class TestEnvironmentalAnalyzerGreenCert(unittest.TestCase):
    """测试绿证分析"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = EnvironmentalAnalyzer(self.sample)
        self.green_cert = self.analyzer._analyze_green_cert()

    def test_green_cert_basic_values(self):
        """绿证基础数值"""
        self.assertEqual(self.green_cert["weekly_issued_wan"], 12.4)
        self.assertEqual(self.green_cert["weekly_sold_wan"], 3.0)
        self.assertEqual(self.green_cert["weekly_avg_price"], 4.5)

    def test_weekly_revenue_split(self):
        """本周销售金额拆分（2025 + 2026）"""
        # 2025: 2.9 × 4.5 = 13.05
        # 2026: 472 × 8.1 / 10000 = 0.38
        self.assertAlmostEqual(self.green_cert["weekly_revenue_2025_wan"], 13.05, places=2)
        self.assertAlmostEqual(self.green_cert["weekly_revenue_2026_wan"], 0.38, places=2)
        self.assertAlmostEqual(self.green_cert["weekly_revenue_wan"], 13.43, places=2)

    def test_yoy_cumulative_revenue(self):
        """2026 累计销售金额 = 448 × 4.7 = 2105.6"""
        self.assertAlmostEqual(self.green_cert["yoy_cumulative_revenue_wan"], 2105.6, places=1)

    def test_inventory_split(self):
        """库存按年份拆分"""
        self.assertEqual(self.green_cert["inventory_2024_wan"], 66)
        self.assertEqual(self.green_cert["inventory_2025_wan"], 767)
        self.assertEqual(self.green_cert["inventory_2026_wan"], 330)
        self.assertEqual(self.green_cert["inventory_total_wan"], 1163)

    def test_inventory_value_calculation(self):
        """库存估值（按历史价格）"""
        # 330×8.1 + 767×4.5 + 66×4 = 2673 + 3451.5 + 264 = 6388.5
        self.assertAlmostEqual(self.green_cert["inventory_value_wan"], 6388.5, places=1)
        self.assertAlmostEqual(self.green_cert["inventory_value_yi"], 0.64, places=2)

    def test_mom_change_2026(self):
        """2026 绿证环比变化"""
        self.assertEqual(self.green_cert["mom_change_2026_fen"], -0.4)


class TestEnvironmentalAnalyzerCCER(unittest.TestCase):
    """测试 CCER 分析"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = EnvironmentalAnalyzer(self.sample)
        self.ccer = self.analyzer._analyze_ccer()

    def test_ccer_basic_values(self):
        """CCER 基础数值"""
        self.assertEqual(self.ccer["weekly_sold_tons"], 2100)
        self.assertEqual(self.ccer["weekly_avg_price"], 85)
        self.assertAlmostEqual(self.ccer["weekly_revenue_wan"], 17.85, places=2)  # 2100 × 85 / 10000

    def test_ccer_yoy_cumulative(self):
        """2026 累计销售"""
        # 43.4 万吨 × 83.7 元/吨 = 434000 × 83.7 / 10000 = 3632.58 万元
        self.assertAlmostEqual(self.ccer["yoy_cumulative_revenue_wan"], 3632.58, places=1)

    def test_ccer_inventory_value(self):
        """CCER 库存估值（506 万吨 × 85 元/吨 = 4.3 亿元）"""
        # 506 × 10000 × 85 / 10000 = 4301 万元 in code
        # Wait: code uses 506 * 85 * 10000 / 10000 = 506 * 85 = 43,010 万元 = 4.3 亿元
        self.assertAlmostEqual(self.ccer["inventory_value_wan"], 43010.0, places=1)
        self.assertAlmostEqual(self.ccer["inventory_value_yi"], 4.30, places=2)


class TestEnvironmentalAnalyzerInventory(unittest.TestCase):
    """测试库存估值（合并）"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = EnvironmentalAnalyzer(self.sample)
        green_cert = self.analyzer._analyze_green_cert()
        ccer = self.analyzer._analyze_ccer()
        self.inventory = self.analyzer._calculate_inventory_value(green_cert, ccer)

    def test_total_value_combination(self):
        """总价值 = 绿证 + CCER"""
        # 6388.5 + 43010 = 49398.5 万元 = 4.94 亿元
        self.assertAlmostEqual(self.inventory["total_value_wan"], 49398.5, places=1)
        self.assertAlmostEqual(self.inventory["total_value_yi"], 4.94, places=2)

    def test_share_pct(self):
        """绿证 vs CCER 占比"""
        # 绿证 6388.5 / 49398.5 = 12.9%
        # CCER 43010 / 49398.5 = 87.1%
        self.assertAlmostEqual(self.inventory["share_pct"]["green_cert"], 12.9, places=1)
        self.assertAlmostEqual(self.inventory["share_pct"]["ccer"], 87.1, places=1)


class TestEnvironmentalAnalyzerFindings(unittest.TestCase):
    """测试 3 个核心发现"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = EnvironmentalAnalyzer(self.sample)
        green_cert = self.analyzer._analyze_green_cert()
        ccer = self.analyzer._analyze_ccer()
        self.findings = self.analyzer._detect_findings(green_cert, ccer)

    def test_price_premium(self):
        """稀缺性溢价: 2025 4.5 vs 2026 8.1 = +80%"""
        self.assertEqual(self.findings["price_premium"]["price_2025"], 4.5)
        self.assertEqual(self.findings["price_premium"]["price_2026"], 8.1)
        self.assertAlmostEqual(self.findings["price_premium"]["premium_pct"], 80.0, places=0)
        self.assertTrue(self.findings["price_premium"]["is_significant"])

    def test_mom_2026_change(self):
        """2026 绿证环比 -0.4 元"""
        self.assertEqual(self.findings["mom_2026_change"]["change_fen"], -0.4)
        self.assertTrue(self.findings["mom_2026_change"]["is_drop_warning"])

    def test_inventory_structure(self):
        """库存结构"""
        # 2024: 66/1163 = 5.7%
        # 2025: 767/1163 = 66.0%
        # 2026: 330/1163 = 28.4%
        self.assertAlmostEqual(self.findings["inventory_structure"]["2024_share"], 5.7, places=1)
        self.assertAlmostEqual(self.findings["inventory_structure"]["2025_share"], 66.0, places=1)
        self.assertAlmostEqual(self.findings["inventory_structure"]["2026_share"], 28.4, places=1)
        self.assertFalse(self.findings["inventory_structure"]["old_cert_warning"])  # 5.7% < 10%


class TestEnvironmentalAnalyzerAnomalies(unittest.TestCase):
    """测试异常检测"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = EnvironmentalAnalyzer(self.sample)
        self.result = self.analyzer.analyze()

    def test_price_premium_warning(self):
        """稀缺性溢价 80% 应触发 warning"""
        warnings = [a for a in self.result.anomalies if a.get("category") == "稀缺性溢价"]
        self.assertGreater(len(warnings), 0)
        self.assertEqual(warnings[0]["level"], "warning")

    def test_mom_drop_warning(self):
        """2026 绿证环比 -0.4 元应触发 warning"""
        warnings = [a for a in self.result.anomalies if a.get("category") == "价差怪现象"]
        self.assertGreater(len(warnings), 0)

    def test_no_critical_anomalies(self):
        """本次不应有 critical 异常（仅 warning + info）"""
        critical = [a for a in self.result.anomalies if a.get("level") == "critical"]
        self.assertEqual(len(critical), 0)


class TestEnvironmentalAnalyzerFullFlow(unittest.TestCase):
    """测试完整 analyze 流程"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = EnvironmentalAnalyzer(self.sample)

    def test_analyze_returns_analysis_result(self):
        result = self.analyzer.analyze()
        self.assertIsInstance(result, AnalysisResult)

    def test_result_dimension_and_sections(self):
        result = self.analyzer.analyze()
        self.assertEqual(result.dimension, "碳资产")
        self.assertEqual(result.section_ids, [8])

    def test_result_contains_all_fields(self):
        result = self.analyzer.analyze()
        self.assertIsNotNone(result.summary)
        self.assertIsNotNone(result.story)
        self.assertIsInstance(result.kpis, dict)
        self.assertIsInstance(result.tables, list)
        self.assertIsInstance(result.charts, list)
        self.assertIsInstance(result.anomalies, list)
        self.assertIsInstance(result.insights, list)

    def test_result_kpis_contain_key_metrics(self):
        """KPI 应包含关键指标"""
        result = self.analyzer.analyze()
        self.assertIn("总库存价值(亿元)", result.kpis)
        self.assertIn("绿证库存价值(万)", result.kpis)
        self.assertIn("CCER库存价值(万)", result.kpis)

    def test_result_tables_count(self):
        """应包含 4 个表格"""
        result = self.analyzer.analyze()
        self.assertEqual(len(result.tables), 4)

    def test_result_charts_count(self):
        """应包含 4 个图表"""
        result = self.analyzer.analyze()
        self.assertEqual(len(result.charts), 4)

    def test_story_and_summary_lengths(self):
        """story 应比 summary 长"""
        result = self.analyzer.analyze()
        self.assertGreater(len(result.story), 500)
        self.assertLess(len(result.summary), 300)
        self.assertIn("##", result.story)

    def test_story_mentions_4th_business(self):
        """故事应包含'第四类业务'"""
        result = self.analyzer.analyze()
        self.assertIn("第四类业务", result.story)

    def test_story_mentions_price_premium(self):
        """故事应包含'稀缺性溢价'"""
        result = self.analyzer.analyze()
        self.assertIn("稀缺性溢价", result.story)


class TestEnvironmentalAnalyzerInvalidInput(unittest.TestCase):
    """测试无效输入"""

    def test_analyze_with_invalid_data(self):
        bad_data = {"report_id": "test"}
        analyzer = EnvironmentalAnalyzer(bad_data)
        result = analyzer.analyze()
        self.assertIsInstance(result, AnalysisResult)
        self.assertEqual(result.anomalies[0]["level"], "error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
