"""
InternationalAnalyzer 单元测试
===============================

测试覆盖:
- 输入校验
- KPI 提取
- 三层归因（汇率/合同/真本事）
- 同比 vs 环比对比框架
- 5 区域分析
- 3 运营主体分析
- 汇率分析
- 国家×品类
- 异常检测
- 完整 analyze 流程
"""

import json
import sys
import unittest
from pathlib import Path

# 添加项目根到 sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.analyzer.international import InternationalAnalyzer
from src.analyzer.base import AnalysisResult


FIXTURE_PATH = project_root / "tests" / "fixtures" / "international_sample.json"


def load_sample_data() -> dict:
    """加载样本数据"""
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestInternationalAnalyzerInputs(unittest.TestCase):
    """测试输入校验"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = InternationalAnalyzer(self.sample)

    def test_validate_inputs_complete_data(self):
        """完整数据应通过校验"""
        self.assertTrue(self.analyzer.validate_inputs())
        self.assertEqual(len(getattr(self.analyzer, "missing_fields", [])), 0)

    def test_validate_inputs_missing_international(self):
        """缺少 international 字段应失败"""
        bad_data = self.sample.copy()
        del bad_data["international"]
        analyzer = InternationalAnalyzer(bad_data)
        self.assertFalse(analyzer.validate_inputs())

    def test_validate_inputs_missing_attribution(self):
        """缺少三层归因应失败"""
        bad_data = self.sample.copy()
        bad_data["international"] = self.sample["international"].copy()
        del bad_data["international"]["attribution_three_layer_yoy"]
        analyzer = InternationalAnalyzer(bad_data)
        self.assertFalse(analyzer.validate_inputs())
        self.assertIn("international.attribution_three_layer_yoy", analyzer.missing_fields)

    def test_validate_inputs_missing_exchange_rates(self):
        """缺少汇率应失败"""
        bad_data = self.sample.copy()
        del bad_data["exchange_rates"]
        analyzer = InternationalAnalyzer(bad_data)
        self.assertFalse(analyzer.validate_inputs())

    def test_validate_inputs_missing_by_company(self):
        """缺少运营主体应失败"""
        bad_data = self.sample.copy()
        del bad_data["by_company"]
        analyzer = InternationalAnalyzer(bad_data)
        self.assertFalse(analyzer.validate_inputs())


class TestInternationalAnalyzerKPIs(unittest.TestCase):
    """测试 KPI 提取"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = InternationalAnalyzer(self.sample)
        self.kpis = self.analyzer._extract_kpis()

    def test_kpis_contain_required_keys(self):
        """KPI 应包含所有必需键"""
        required = [
            "国际上网电量", "国际发电收入", "国际度电均价",
            "国际同比度电", "国际环比度电",
            "国际同比电量", "国际环比电量",
            "国际同比收入", "国际环比收入",
        ]
        for key in required:
            self.assertIn(key, self.kpis)

    def test_kpis_values_match_sample(self):
        """KPI 数值应与样本数据一致"""
        self.assertEqual(self.kpis["国际上网电量"], 8.8)
        self.assertEqual(self.kpis["国际度电均价"], 0.32)
        self.assertEqual(self.kpis["国际同比度电"], 3.9)
        self.assertEqual(self.kpis["国际环比度电"], 1.3)


class TestInternationalAnalyzerThreeLayerAttribution(unittest.TestCase):
    """测试三层归因"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = InternationalAnalyzer(self.sample)
        self.yoy = self.analyzer._three_layer_attribution("yoy")
        self.mom = self.analyzer._three_layer_attribution("mom")

    def test_yoy_three_layer_values(self):
        """同比三层归因数值正确"""
        self.assertEqual(self.yoy["exchange_rate_effect"], 1.0)
        self.assertEqual(self.yoy["contract_effect"], 0.2)
        self.assertEqual(self.yoy["real_business_effect"], 2.7)
        # 验算: 1.0 + 0.2 + 2.7 = 3.9 (与 yoy_total 一致)
        self.assertAlmostEqual(self.yoy["total"], 3.9, places=2)

    def test_mom_three_layer_values(self):
        """环比三层归因数值正确"""
        self.assertEqual(self.mom["exchange_rate_effect"], -0.1)
        self.assertEqual(self.mom["contract_effect"], -0.02)
        self.assertEqual(self.mom["real_business_effect"], 1.4)
        # 验算: -0.1 + (-0.02) + 1.4 = 1.28
        self.assertAlmostEqual(self.mom["total"], 1.28, places=2)

    def test_yoy_verification_passed(self):
        """同比三层归因勾稽应通过"""
        self.assertTrue(self.yoy["verification_passed"])

    def test_mom_verification_acceptable(self):
        """环比三层归因在容差内（1.28 vs 1.3）"""
        # 1.28 vs 1.3 差异 0.02 < 0.1
        self.assertTrue(self.mom["verification_passed"])

    def test_yoy_directions(self):
        """同比方向判断"""
        self.assertEqual(self.yoy["exchange_direction"], "帮")
        self.assertTrue(self.yoy["sustainable"])  # 真本事 +2.7

    def test_mom_directions(self):
        """环比方向判断"""
        self.assertEqual(self.mom["exchange_direction"], "拖")  # -0.1
        self.assertTrue(self.mom["sustainable"])  # 真本事 +1.4


class TestInternationalAnalyzerYoYvsMoM(unittest.TestCase):
    """测试同比 vs 环比对比框架（核心方法论）"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = InternationalAnalyzer(self.sample)
        yoy = self.analyzer._three_layer_attribution("yoy")
        mom = self.analyzer._three_layer_attribution("mom")
        self.comparison = self.analyzer._yoy_vs_mom_comparison(yoy, mom)

    def test_capability_dimension(self):
        """能力维度：同比真本事 +2.7 > 0 → 能力积累"""
        self.assertEqual(self.comparison["capability"], "能力积累")

    def test_momentum_dimension(self):
        """动能维度：环比真本事 +1.4 < 同比 +2.7 → 动能减弱"""
        self.assertEqual(self.comparison["momentum"], "动能减弱")

    def test_structure_dimension(self):
        """结构维度：环比引擎数 < 同比 → 结构集中"""
        self.assertEqual(self.comparison["structure"], "结构集中")

    def test_yoy_to_mom_change(self):
        """同比 → 环比真本事变化（容许浮点误差）"""
        self.assertAlmostEqual(self.comparison["yoy_to_mom_change"], -1.3, places=2)  # 1.4 - 2.7

    def test_comparison_summary(self):
        """对比框架应包含完整三维信息"""
        self.assertIn("能力", self.comparison["capability"])
        self.assertIn("动能", self.comparison["momentum"])
        self.assertIn("结构", self.comparison["structure"])


class TestInternationalAnalyzerExchangeRates(unittest.TestCase):
    """测试汇率分析"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = InternationalAnalyzer(self.sample)
        self.exchange = self.analyzer._analyze_exchange_rates()

    def test_three_currencies(self):
        """应包含 3 大币种"""
        self.assertEqual(len(self.exchange["currencies"]), 3)
        currency_codes = [c["币种"] for c in self.exchange["currencies"]]
        self.assertIn("CNY_BRL", currency_codes)
        self.assertIn("CNY_USD", currency_codes)
        self.assertIn("CNY_EUR", currency_codes)

    def test_direction_reversal_detected(self):
        """汇率方向反转应被检测（雷亚尔同比升值但环比贬值）"""
        self.assertTrue(self.exchange["direction_reversal"])

    def test_brl_yoy_positive(self):
        """巴西雷亚尔同比应升值（+7.6%）"""
        brl = next(c for c in self.exchange["currencies"] if c["币种"] == "CNY_BRL")
        self.assertEqual(brl["同比方向"], "升值")
        self.assertEqual(brl["同比(%)"], 7.6)

    def test_eur_yoy_negative(self):
        """欧元同比应贬值（-30%）"""
        eur = next(c for c in self.exchange["currencies"] if c["币种"] == "CNY_EUR")
        self.assertEqual(eur["同比方向"], "贬值")
        self.assertEqual(eur["同比(%)"], -30.0)


class TestInternationalAnalyzerRegions(unittest.TestCase):
    """测试 5 区域分析"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = InternationalAnalyzer(self.sample)
        self.regions_yoy = self.analyzer._analyze_regions("yoy")
        self.regions_mom = self.analyzer._analyze_regions("mom")

    def test_regions_yoy_has_3(self):
        """同比应包含 3 个区域（拉美、欧洲、亚非）"""
        self.assertEqual(len(self.regions_yoy["regions"]), 3)
        region_codes = [r["区域代码"] for r in self.regions_yoy["regions"]]
        self.assertIn("latin_america", region_codes)
        self.assertIn("europe", region_codes)
        self.assertIn("asia_africa", region_codes)

    def test_regions_effect_fen(self):
        """区域影响数值"""
        latin = next(r for r in self.regions_yoy["regions"] if r["区域代码"] == "latin_america")
        self.assertEqual(latin["影响(分)"], 1.5)
        europe = next(r for r in self.regions_yoy["regions"] if r["区域代码"] == "europe")
        self.assertEqual(europe["影响(分)"], 0.4)


class TestInternationalAnalyzerCompanies(unittest.TestCase):
    """测试 3 运营主体分析"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = InternationalAnalyzer(self.sample)
        self.companies = self.analyzer._analyze_companies()

    def test_three_companies(self):
        """应包含 3 个运营主体"""
        self.assertEqual(len(self.companies["companies"]), 3)
        comp_names = [c["公司名称"] for c in self.companies["companies"]]
        self.assertIn("三峡国际", comp_names)
        self.assertIn("长电国际", comp_names)
        self.assertIn("湖北能源", comp_names)

    def test_three_gorges_intl_main_force(self):
        """三峡国际同比影响 +3.8 → 主力"""
        tgi = next(c for c in self.companies["companies"] if c["公司名称"] == "三峡国际")
        self.assertEqual(tgi["角色"], "主力")
        self.assertEqual(tgi["同比影响集团(分)"], 3.8)

    def test_hubei_energy_negative_impact(self):
        """湖北能源同比影响 -0.02 → 拖累"""
        hbe = next(c for c in self.companies["companies"] if c["公司名称"] == "湖北能源")
        self.assertEqual(hbe["角色"], "拖累")
        self.assertLess(hbe["同比影响集团(分)"], 0)


class TestInternationalAnalyzerAnomalies(unittest.TestCase):
    """测试异常检测"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = InternationalAnalyzer(self.sample)
        # 触发 analyze
        self.result = self.analyzer.analyze()

    def test_eur_yoy_alert(self):
        """欧元同比 -30% 超过 ±20% 阈值，应触发警告"""
        eur_alerts = [a for a in self.result.anomalies if "CNY_EUR" in a.get("message", "")]
        self.assertGreater(len(eur_alerts), 0)
        self.assertEqual(eur_alerts[0]["level"], "warning")

    def test_three_gorges_concentration(self):
        """三峡国际同比影响 3.8 分超过 2.0，应触发集中度提示"""
        concentration = [a for a in self.result.anomalies if "三峡国际" in a.get("message", "")]
        self.assertGreater(len(concentration), 0)

    def test_anomalies_sorted_by_severity(self):
        """异常按严重度排序"""
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        severities = [severity_order.get(a.get("level", "info"), 3) for a in self.result.anomalies]
        self.assertEqual(severities, sorted(severities))


class TestInternationalAnalyzerFullFlow(unittest.TestCase):
    """测试完整 analyze 流程"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = InternationalAnalyzer(self.sample)

    def test_analyze_returns_analysis_result(self):
        """analyze 应返回 AnalysisResult 实例"""
        result = self.analyzer.analyze()
        self.assertIsInstance(result, AnalysisResult)

    def test_result_dimension_and_sections(self):
        """结果维度和段应正确"""
        result = self.analyzer.analyze()
        self.assertEqual(result.dimension, "国际")
        self.assertEqual(result.section_ids, [3, 4])

    def test_result_contains_all_fields(self):
        """结果应包含所有必要字段"""
        result = self.analyzer.analyze()
        self.assertIsNotNone(result.summary)
        self.assertIsNotNone(result.story)
        self.assertIsInstance(result.kpis, dict)
        self.assertIsInstance(result.yoy_data, dict)
        self.assertIsInstance(result.mom_data, dict)
        self.assertIsInstance(result.tables, list)
        self.assertIsInstance(result.charts, list)
        self.assertIsInstance(result.insights, list)
        self.assertIsInstance(result.anomalies, list)

    def test_result_summary_contains_key_numbers(self):
        """summary 应包含关键数字"""
        result = self.analyzer.analyze()
        self.assertIn("0.32", result.summary)  # 国际均价
        self.assertIn("3.9", result.summary)  # 同比
        self.assertIn("1.3", result.summary)  # 环比

    def test_result_tables_count(self):
        """应包含 5 个表格（KPI/三层归因/汇率/区域/公司）"""
        result = self.analyzer.analyze()
        self.assertEqual(len(result.tables), 5)
        table_titles = [t["title"] for t in result.tables]
        self.assertIn("国际段 KPI 总览", table_titles)
        self.assertIn("三层归因 (汇率 / 合同 / 真本事)", table_titles)

    def test_result_charts_count(self):
        """应包含 3 个图表"""
        result = self.analyzer.analyze()
        self.assertEqual(len(result.charts), 3)

    def test_story_and_summary_lengths(self):
        """回归测试：story 应比 summary 长（防顺序颠倒）"""
        result = self.analyzer.analyze()
        self.assertGreater(len(result.story), 500,
                            f"story 长度 {len(result.story)} 过短")
        self.assertLess(len(result.summary), 300,
                         f"summary 长度 {len(result.summary)} 过长")
        self.assertIn("##", result.story, "story 应包含 Markdown 标题")


class TestInternationalAnalyzerInvalidInput(unittest.TestCase):
    """测试无效输入"""

    def test_analyze_with_invalid_data(self):
        """无效数据应返回错误结果"""
        bad_data = {"report_id": "test"}
        analyzer = InternationalAnalyzer(bad_data)
        result = analyzer.analyze()
        self.assertIsInstance(result, AnalysisResult)
        self.assertGreater(len(result.anomalies), 0)
        self.assertEqual(result.anomalies[0]["level"], "error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
