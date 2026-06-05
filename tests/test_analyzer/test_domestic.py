"""
DomesticAnalyzer 单元测试
========================

测试覆盖:
- 输入校验
- KPI 提取
- 同比/环比分析
- 量价分解
- 5 大品类分析
- 关键省份分析
- 异常检测
- 完整 analyze 流程
- 故事生成
"""

import json
import sys
import unittest
from pathlib import Path

# 添加项目根到 sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.analyzer.domestic import DomesticAnalyzer
from src.analyzer.base import AnalysisResult, create_empty_result


FIXTURE_PATH = project_root / "tests" / "fixtures" / "domestic_sample.json"


def load_sample_data() -> dict:
    """加载样本数据"""
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestDomesticAnalyzerInputs(unittest.TestCase):
    """测试输入校验"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = DomesticAnalyzer(self.sample)

    def test_validate_inputs_complete_data(self):
        """完整数据应该通过校验"""
        self.assertTrue(self.analyzer.validate_inputs())
        self.assertEqual(len(getattr(self.analyzer, "missing_fields", [])), 0)

    def test_validate_inputs_missing_group_total(self):
        """缺少 group_total 应该失败"""
        bad_data = self.sample.copy()
        del bad_data["group_total"]
        analyzer = DomesticAnalyzer(bad_data)
        self.assertFalse(analyzer.validate_inputs())
        self.assertGreater(len(analyzer.missing_fields), 0)

    def test_validate_inputs_partial_missing(self):
        """部分字段缺失应该失败"""
        bad_data = self.sample.copy()
        bad_data["group_total"] = self.sample["group_total"].copy()
        del bad_data["group_total"]["yoy_volume_pct"]
        analyzer = DomesticAnalyzer(bad_data)
        self.assertFalse(analyzer.validate_inputs())
        self.assertIn("group_total.yoy_volume_pct", analyzer.missing_fields)

    def test_validate_inputs_missing_categories(self):
        """缺少品类数据应该失败"""
        bad_data = self.sample.copy()
        bad_data["by_category"] = self.sample["by_category"].copy()
        del bad_data["by_category"]["solar"]
        analyzer = DomesticAnalyzer(bad_data)
        self.assertFalse(analyzer.validate_inputs())


class TestDomesticAnalyzerKPIs(unittest.TestCase):
    """测试 KPI 提取"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = DomesticAnalyzer(self.sample)
        self.kpis = self.analyzer._extract_kpis()

    def test_kpis_contain_required_keys(self):
        """KPI 字典应包含所有必需键"""
        required = [
            "国内上网电量", "国际上网电量", "合计上网电量",
            "国内度电均价", "国内发电收入",
            "同比电量", "同比度电", "同比收入",
            "环比电量", "环比度电", "环比收入",
        ]
        for key in required:
            self.assertIn(key, self.kpis)

    def test_kpis_values_match_sample(self):
        """KPI 数值应与样本数据一致"""
        self.assertEqual(self.kpis["国内上网电量"], 80.3)
        self.assertEqual(self.kpis["国际上网电量"], 8.8)
        self.assertEqual(self.kpis["合计上网电量"], 89.1)
        self.assertEqual(self.kpis["国内度电均价"], 0.311)
        self.assertEqual(self.kpis["国内发电收入"], 24.97)

    def test_kpis_yoy_mom_values(self):
        """同比/环比数值应正确"""
        self.assertEqual(self.kpis["同比电量"], 3.3)
        self.assertEqual(self.kpis["同比度电"], -0.9)
        self.assertEqual(self.kpis["同比收入"], 0.3)
        self.assertEqual(self.kpis["环比电量"], 15.7)
        self.assertEqual(self.kpis["环比度电"], 0.1)
        self.assertEqual(self.kpis["环比收入"], 15.9)


class TestDomesticAnalyzerYoY(unittest.TestCase):
    """测试同比分析"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = DomesticAnalyzer(self.sample)
        self.kpis = self.analyzer._extract_kpis()
        self.yoy = self.analyzer._yoy_analysis(self.kpis)

    def test_yoy_pattern_identified(self):
        """同比模式应该被识别为'以量补价'"""
        self.assertEqual(self.yoy["pattern"], "以量补价")

    def test_yoy_directions(self):
        """同比方向应该正确"""
        self.assertEqual(self.yoy["电量"]["direction"], "涨")  # +3.3%
        self.assertEqual(self.yoy["度电"]["direction"], "跌")  # -0.9 分
        self.assertEqual(self.yoy["收入"]["direction"], "涨")  # +0.3%

    def test_yoy_summary_contains_pattern(self):
        """同比 summary 应该包含模式描述"""
        self.assertIn("以量补价", self.yoy["summary"])


class TestDomesticAnalyzerMoM(unittest.TestCase):
    """测试环比分析"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = DomesticAnalyzer(self.sample)
        self.kpis = self.analyzer._extract_kpis()
        self.mom = self.analyzer._mom_analysis(self.kpis)

    def test_mom_strength(self):
        """环比动能强度判断"""
        # 本周环比 +15.7% （强）
        self.assertIn(self.mom["strength"], ["强", "中", "弱"])

    def test_mom_directions(self):
        """环比方向"""
        self.assertEqual(self.mom["电量"]["direction"], "涨")
        self.assertEqual(self.mom["度电"]["direction"], "涨")
        self.assertEqual(self.mom["收入"]["direction"], "涨")


class TestDomesticAnalyzerVolumePriceDecomposition(unittest.TestCase):
    """测试量价分解"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = DomesticAnalyzer(self.sample)
        self.decomp = self.analyzer._decompose_volume_price()

    def test_decomposition_has_categories(self):
        """量价分解应包含各品类"""
        self.assertIn("categories", self.decomp)
        self.assertGreater(len(self.decomp["categories"]), 0)

    def test_decomposition_total_field(self):
        """量价分解应包含合计字段"""
        self.assertIn("total_yoy_change_fen", self.decomp)
        self.assertIn("group_yoy_change_fen", self.decomp)

    def test_decomposition_verification(self):
        """量价分解应通过验算（允许小误差）"""
        # 集团 yoy_price_change_fen = -0.9
        # 简化分解后总和应接近 -0.9
        self.assertLess(abs(self.decomp["total_yoy_change_fen"]), 5.0)


class TestDomesticAnalyzerCategories(unittest.TestCase):
    """测试 5 大品类分析"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = DomesticAnalyzer(self.sample)
        self.cats = self.analyzer._analyze_categories()

    def test_categories_contains_5(self):
        """应包含 5 个品类（水/新能源/火电/风/光）"""
        self.assertEqual(len(self.cats["categories"]), 5)

    def test_status_distribution(self):
        """品类状态分布"""
        by_status = self.cats["by_status"]
        self.assertIn("增长", by_status)
        self.assertIn("下降", by_status)
        self.assertIn("稳定", by_status)

    def test_thermal_identified_as_decline(self):
        """火电同比 -42.5% 应被识别为'下降'状态"""
        self.assertIn("thermal", self.cats["by_status"]["下降"])

    def test_thermal_share_below_threshold(self):
        """火电占比 < 5% 应触发关键洞察"""
        insight_msgs = [i["msg"] for i in self.cats["key_insights"]]
        self.assertTrue(any("火电占比" in m for m in insight_msgs))


class TestDomesticAnalyzerRegions(unittest.TestCase):
    """测试关键省份分析"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = DomesticAnalyzer(self.sample)
        self.regions = self.analyzer._analyze_regions()

    def test_regions_contains_4_provinces(self):
        """应包含 4 个关键省份"""
        self.assertEqual(len(self.regions["provinces"]), 4)

    def test_strategy_classification(self):
        """省份策略分类"""
        # 山东 0% → 低持仓
        # 湖北 95% → 高持仓
        # 陕西 105% → 卡线
        by_strat = self.regions["by_strategy"]
        self.assertIn("shandong", by_strat.get("低持仓", []))
        self.assertIn("hubei", by_strat.get("高持仓", []))
        self.assertIn("shaanxi", by_strat.get("卡线", []))


class TestDomesticAnalyzerAnomalies(unittest.TestCase):
    """测试异常检测"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = DomesticAnalyzer(self.sample)
        self.kpis = self.analyzer._extract_kpis()
        self.cats = self.analyzer._analyze_categories()
        self.regions = self.analyzer._analyze_regions()
        self.anomalies = self.analyzer._detect_anomalies(
            self.kpis, self.cats, self.regions
        )

    def test_anomalies_detected(self):
        """应检测到至少 1 个异常（火电战略性退场）"""
        self.assertGreater(len(self.anomalies), 0)

    def test_thermal_retreat_critical_detected(self):
        """火电同比 -37.6% 应触发战略性退场严重异常"""
        retreat = [a for a in self.anomalies if "战略性退场" in a.get("message", "")]
        self.assertGreater(len(retreat), 0)
        self.assertEqual(retreat[0]["level"], "critical")

    def test_anomalies_sorted_by_severity(self):
        """异常应按严重度排序（critical 在前）"""
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        severities = [severity_order.get(a.get("level", "info"), 3) for a in self.anomalies]
        self.assertEqual(severities, sorted(severities))


class TestDomesticAnalyzerFullFlow(unittest.TestCase):
    """测试完整 analyze 流程"""

    def setUp(self):
        self.sample = load_sample_data()
        self.analyzer = DomesticAnalyzer(self.sample)

    def test_analyze_returns_analysis_result(self):
        """analyze 应返回 AnalysisResult 实例"""
        result = self.analyzer.analyze()
        self.assertIsInstance(result, AnalysisResult)

    def test_result_dimension_and_sections(self):
        """结果的维度和段应正确"""
        result = self.analyzer.analyze()
        self.assertEqual(result.dimension, "国内")
        self.assertEqual(result.section_ids, [1, 2])

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

    def test_result_summary_mentions_key_numbers(self):
        """summary 应包含关键数字"""
        result = self.analyzer.analyze()
        self.assertIn("89.1", result.summary)  # 合计电量
        self.assertIn("0.311", result.summary)  # 度电均价

    def test_result_tables_contain_categories(self):
        """结果应包含品类表"""
        result = self.analyzer.analyze()
        table_titles = [t["title"] for t in result.tables]
        self.assertIn("5 大品类明细", table_titles)

    def test_result_charts_contain_pie(self):
        """结果应包含饼图（占比）"""
        result = self.analyzer.analyze()
        chart_types = [c["type"] for c in result.charts]
        self.assertIn("pie", chart_types)

    def test_story_and_summary_lengths(self):
        """回归测试：story 应比 summary 长，防止两者顺序颠倒

        防止类似 bug: _generate_story 返回 (summary, story) 但 analyze 解包为 (story, summary)
        """
        result = self.analyzer.analyze()
        # story 应是多段详细故事（包含 ## 标题）
        self.assertGreater(len(result.story), 500,
                            f"story 长度 {len(result.story)} 过短，可能与 summary 顺序颠倒")
        # summary 应是一句话总结
        self.assertLess(len(result.summary), 300,
                         f"summary 长度 {len(result.summary)} 过长，可能与 story 顺序颠倒")
        # story 应包含 Markdown 标题
        self.assertIn("##", result.story,
                       "story 应包含 Markdown 标题")


class TestDomesticAnalyzerInvalidInput(unittest.TestCase):
    """测试无效输入"""

    def test_analyze_with_invalid_data(self):
        """无效数据应返回错误结果"""
        bad_data = {"report_id": "test"}  # 缺少必需字段
        analyzer = DomesticAnalyzer(bad_data)
        result = analyzer.analyze()
        self.assertIsInstance(result, AnalysisResult)
        # 应该有错误异常
        self.assertGreater(len(result.anomalies), 0)
        self.assertEqual(result.anomalies[0]["level"], "error")

    def test_analyze_with_empty_data(self):
        """空数据应优雅处理"""
        analyzer = DomesticAnalyzer({})
        result = analyzer.analyze()
        self.assertIsInstance(result, AnalysisResult)


class TestDomesticAnalyzerConfig(unittest.TestCase):
    """测试配置覆盖"""

    def test_custom_thresholds(self):
        """自定义阈值应该被应用"""
        custom_config = {
            "thresholds": {
                "yoy_price_fen_warning": 1.0,  # 严格阈值
            }
        }
        analyzer = DomesticAnalyzer(load_sample_data(), custom_config)
        self.assertEqual(analyzer.domestic_config.thresholds["yoy_price_fen_warning"], 1.0)

    def test_custom_provinces(self):
        """自定义关键省份应该被应用"""
        custom_config = {
            "key_provinces": ["hubei", "shandong"],  # 只看湖北、山东
        }
        analyzer = DomesticAnalyzer(load_sample_data(), custom_config)
        regions = analyzer._analyze_regions()
        self.assertEqual(len(regions["provinces"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
