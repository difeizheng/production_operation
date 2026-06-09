"""v3 数据适配器单元测试（v3.2 重构版）

设计变更（v3.2）：
- 保留 AnalysisCollector 所有原始字段（不丢数据）
- 添加 group_total/by_category/international UI 标准视图
- 添加 report_period + ui_view 标志

测试重点：
1. UI 视图字段正确（KPI 可用）
2. 原始数据完整保留
3. 中文描述路径生效
"""
import unittest
from typing import Any, Dict

from streamlit_app.core.v3_data_adapter import (
    adapt_collector_output,
    _pct_to_number,
    _yuan_to_fen,
    _wan_to_yi,
)


# ============================================================================
# 测试夹具：模拟 AnalysisCollector 完整输出
# ============================================================================
def make_full_collector_output() -> Dict[str, Any]:
    """构造完整的 AnalysisCollector 输出（模拟真实 Excel 采集）。

    包含：
    - domestic.electricity.*（按品类电量）
    - domestic.price.*（按品类电价）
    - domestic.revenue.*（按品类收入）
    - domestic.share.*（按品类占比）
    - domestic.yoy.*（同比，含按品类细分）
    - domestic.wow.*（环比，含按品类细分）
    - domestic.prev_year_*（去年同期）
    - domestic.last_week_*（上周）
    - international.*（国际数据）
    - report_table_1（9 行 × 6 列报告表）
    """
    return {
        "domestic": {
            "electricity": {
                "total": 802763.394481,
                "hydro": 590454.47183,
                "new_energy": 179570.990551,
                "wind": 103630.190204,
                "solar": 75940.800347,
                "thermal": 31183.3975,
            },
            "price": {
                "total": 0.3105009367385891,
                "hydro": 0.28301561441872297,
                "new_energy": 0.38122348150386576,
                "wind": 0.411560816071471,
                "solar": 0.3398246058381115,
                "thermal": 0.420462416771617,
            },
            "revenue": {
                "total": 249258.7859658,
                "hydro": 167107.83513125,
                "new_energy": 68456.67819495,
                "wind": 42650.12565,
                "solar": 25806.55254495,
                "thermal": 13111.446676,
            },
            "share": {
                "hydro": 0.735,
                "new_energy": 0.224,
                "wind": 0.130,
                "solar": 0.095,
                "thermal": 0.039,
            },
            "yoy": {
                "electricity": 0.033161084856036936,
                "revenue": 0.003200235997336971,
                "price_change": -0.009273195222946819,
                "price_impact": -0.0066221960285969455,
                "share_impact": -0.003665422892555079,
                "hydro": {
                    "price_change": -0.0011068059371984469,
                    "share_change": 0.022800581867080606,
                    "combined_impact": -0.0016269658617298177,
                },
                "new_energy": {
                    "price_change": -0.012953971780026295,
                    "share_change": 0.0028329324394080345,
                    "combined_impact": -0.002686908030116762,
                },
                "wind": {
                    "price_change": -0.007026094971211302,
                    "share_change": 0.009782605415678585,
                    "combined_impact": 5.9635017860441595e-05,
                },
                "solar": {
                    "price_change": -0.025674317414612343,
                    "share_change": -0.00694967297627055,
                    "combined_impact": -0.0027465430479772035,
                },
                "thermal": {
                    "price_change": -0.03638949403242915,
                    "share_change": -0.02542398904594438,
                    "combined_impact": -0.004898616265937354,
                },
            },
            "wow": {
                "electricity": 0.1574042821468989,
                "revenue": 0.15948371660428007,
                "price_change": 0.0005568567610369553,
                "hydro": {
                    "price_change": -0.004420982960773687,
                    "share_change": 0.021620643530945918,
                    "combined_impact": -0.0037383803577070813,
                },
                "new_energy": {
                    "price_change": 0.01978804320763473,
                    "share_change": -0.009813399001785328,
                    "combined_impact": 0.003921103015306951,
                },
            },
            "prev_year_electricity": {
                "total": 776000,
                "hydro": 555000,
                "new_energy": 170000,
            },
            "last_week_electricity": {
                "total": 695000,
                "hydro": 495000,
                "new_energy": 165000,
            },
        },
        "international": {
            "electricity": {"total": 88000},
            "price": {"total": 0.32},
            "revenue": {"total": 28200},  # 万元
            "yoy": {
                "electricity": 0.050,
                "price_change": 0.039,
            },
            "wow": {
                "electricity": 0.020,
                "price_change": 0.013,
            },
        },
        "organizations": {},
        "report_table_1": {
            "headers": ["", "水电", "新能源", "风电", "光伏", "火电", "合计"],
            "row_labels": ["国内上网电量", "同比", "环比", "国内上网电价"],
            "row_numbers": [78, 79, 80, 81],
            "data": [
                [59.0, 18.0, 10.4, 7.6, 3.1, 80.3],
                [6.6, 5.0, 11.8, -3.8, -37.6, 3.3],
                [19.2, 10.0, 28.4, -6.6, -10.1, 15.7],
                [0.283, 0.381, 0.412, 0.340, 0.421, 0.311],
            ],
        },
        "meta": {
            "year": 2026,
            "week": 21,
            "source_file": "test.xlsx",
        },
        "validation_report": {
            "status": "pass",
            "field_count": 149,
            "coverage": 95.3,
        },
    }


class TestHelperFunctions(unittest.TestCase):
    """测试辅助函数"""

    def test_pct_to_number(self):
        self.assertEqual(_pct_to_number(0.033), 3.3)
        self.assertEqual(_pct_to_number(0.066), 6.6)
        self.assertEqual(_pct_to_number(-0.038), -3.8)
        self.assertIsNone(_pct_to_number(None))

    def test_yuan_to_fen(self):
        self.assertEqual(_yuan_to_fen(0.009), 0.9)
        self.assertEqual(_yuan_to_fen(-0.001), -0.1)
        self.assertEqual(_yuan_to_fen(0.039), 3.9)
        self.assertIsNone(_yuan_to_fen(None))

    def test_wan_to_yi(self):
        self.assertEqual(_wan_to_yi(803000), 80.3)
        self.assertEqual(_wan_to_yi(88000), 8.8)
        self.assertIsNone(_wan_to_yi(None))


class TestAdaptGroupTotal(unittest.TestCase):
    """测试 group_total 转换（13 个核心 KPI）"""

    def setUp(self):
        self.raw = make_full_collector_output()
        self.result = adapt_collector_output(self.raw)

    def test_domestic_volume(self):
        gt = self.result["group_total"]
        self.assertEqual(gt["domestic_ongrid_volume_yi_kwh"], 80.28)

    def test_international_volume(self):
        gt = self.result["group_total"]
        self.assertEqual(gt["international_ongrid_volume_yi_kwh"], 8.8)

    def test_total_volume(self):
        gt = self.result["group_total"]
        self.assertEqual(gt["total_ongrid_volume_yi_kwh"], 89.08)

    def test_domestic_price(self):
        gt = self.result["group_total"]
        self.assertAlmostEqual(gt["domestic_avg_price_yuan_per_kwh"], 0.3105, places=4)

    def test_domestic_revenue(self):
        gt = self.result["group_total"]
        self.assertEqual(gt["domestic_revenue_yi_yuan"], 24.93)

    def test_yoy_volume_pct(self):
        gt = self.result["group_total"]
        self.assertEqual(gt["yoy_volume_pct"], 3.3)

    def test_mom_volume_pct(self):
        gt = self.result["group_total"]
        self.assertEqual(gt["mom_volume_pct"], 15.7)

    def test_yoy_price_change_fen(self):
        gt = self.result["group_total"]
        self.assertEqual(gt["yoy_price_change_fen"], -0.9)

    def test_mom_price_change_fen(self):
        gt = self.result["group_total"]
        self.assertEqual(gt["mom_price_change_fen"], 0.1)


class TestAdaptByCategory(unittest.TestCase):
    """测试 by_category 转换"""

    def setUp(self):
        self.raw = make_full_collector_output()
        self.result = adapt_collector_output(self.raw)

    def test_hydro_volume(self):
        cat = self.result["by_category"]["hydro"]
        self.assertEqual(cat["volume_yi_kwh"], 59.05)

    def test_hydro_price(self):
        cat = self.result["by_category"]["hydro"]
        self.assertAlmostEqual(cat["avg_price_yuan_per_kwh"], 0.283, places=3)

    def test_hydro_revenue(self):
        cat = self.result["by_category"]["hydro"]
        self.assertEqual(cat["revenue_yi_yuan"], 16.71)

    def test_hydro_share_pct(self):
        cat = self.result["by_category"]["hydro"]
        self.assertEqual(cat["share_pct"], 73.5)

    def test_hydro_yoy_price_change_fen(self):
        cat = self.result["by_category"]["hydro"]
        self.assertEqual(cat["yoy_price_change_fen"], -0.1)

    def test_hydro_yoy_volume_pct_is_none(self):
        """AnalysisCollector 没有按品类的电量同比，应该为 None（不编造数据）"""
        cat = self.result["by_category"]["hydro"]
        self.assertIsNone(cat["yoy_volume_pct"])

    def test_renewables_name_mapping(self):
        """new_energy → renewables"""
        self.assertIn("renewables", self.result["by_category"])
        self.assertNotIn("new_energy", self.result["by_category"])

    def test_renewables_volume(self):
        cat = self.result["by_category"]["renewables"]
        self.assertEqual(cat["volume_yi_kwh"], 17.96)

    def test_thermal_volume(self):
        cat = self.result["by_category"]["thermal"]
        self.assertEqual(cat["volume_yi_kwh"], 3.12)

    def test_all_5_categories_present(self):
        """5 大品类都存在"""
        cats = self.result["by_category"]
        self.assertIn("hydro", cats)
        self.assertIn("renewables", cats)
        self.assertIn("wind", cats)
        self.assertIn("solar", cats)
        self.assertIn("thermal", cats)


class TestAdaptInternational(unittest.TestCase):
    """测试 international 转换"""

    def setUp(self):
        self.raw = make_full_collector_output()
        self.result = adapt_collector_output(self.raw)

    def test_volume_wan_to_yi(self):
        intl = self.result["international"]
        self.assertEqual(intl["total_volume_yi_kwh"], 8.8)

    def test_price_unchanged(self):
        intl = self.result["international"]
        self.assertEqual(intl["avg_price_yuan_per_kwh"], 0.32)

    def test_revenue_wan_to_yi(self):
        intl = self.result["international"]
        self.assertEqual(intl["total_revenue_yi_yuan"], 2.82)

    def test_yoy_price_change_fen(self):
        intl = self.result["international"]
        self.assertEqual(intl["avg_price_yoy_change_fen"], 3.9)

    def test_yoy_volume_pct(self):
        intl = self.result["international"]
        self.assertEqual(intl["yoy_volume_pct"], 5.0)


class TestOriginalDataPreserved(unittest.TestCase):
    """测试原始数据保留（v3.2 关键设计：不丢字段）"""

    def setUp(self):
        self.raw = make_full_collector_output()
        self.result = adapt_collector_output(self.raw)

    def test_domestic_preserved(self):
        """domestic 整个 section 保留"""
        self.assertIn("domestic", self.result)
        self.assertIn("electricity", self.result["domestic"])
        self.assertIn("prev_year_electricity", self.result["domestic"])
        self.assertIn("last_week_electricity", self.result["domestic"])

    def test_report_table_1_preserved(self):
        """报告表 1 保留"""
        self.assertIn("report_table_1", self.result)
        self.assertEqual(len(self.result["report_table_1"]["data"]), 4)

    def test_organizations_preserved(self):
        self.assertIn("organizations", self.result)

    def test_meta_preserved(self):
        self.assertIn("meta", self.result)
        self.assertEqual(self.result["meta"]["year"], 2026)

    def test_validation_report_preserved(self):
        self.assertIn("validation_report", self.result)

    def test_by_category_subfields_preserved(self):
        """domestic.yoy.electricity 等细分子字段保留"""
        domestic = self.result["domestic"]
        self.assertIn("yoy", domestic)
        self.assertIn("hydro", domestic["yoy"])
        self.assertIn("price_change", domestic["yoy"]["hydro"])
        self.assertIn("share_change", domestic["yoy"]["hydro"])


class TestFieldCount(unittest.TestCase):
    """测试字段数（用户最关心的指标）"""

    def setUp(self):
        self.raw = make_full_collector_output()
        self.result = adapt_collector_output(self.raw)

    def _count_leaves(self, data, skip=("meta", "version", "report_id", "ui_view", "validation_report")):
        """递归统计叶子数"""
        n = 0
        if isinstance(data, dict):
            for k, v in data.items():
                if k in skip:
                    continue
                n += self._count_leaves(v, skip)
        elif isinstance(data, list):
            for item in data:
                n += self._count_leaves(item, skip)
        else:
            n += 1
        return n

    def test_field_count_not_decreased(self):
        """Adapter 后字段数应该 >= 原始字段数（v3.2 关键）"""
        raw_count = self._count_leaves(self.raw)
        ui_count = self._count_leaves(self.result)
        # 原始 + 新增 UI 视图（group_total + by_category + report_period + international 覆盖）
        self.assertGreaterEqual(ui_count, raw_count,
            f"Adapter 后字段数 {ui_count} 不应少于原始 {raw_count}")

    def test_real_data_field_count(self):
        """用真实 Excel 测试：字段数应该接近 149 + 13 = 162"""
        from pathlib import Path
        from src.collector.analysis_collector import AnalysisCollector

        excel_path = Path("files/2026年第21周周数据综合分析报表.xlsx")
        if not excel_path.exists():
            self.skipTest(f"真实文件不存在: {excel_path}")

        collector = AnalysisCollector()
        raw_data, _ = collector.collect(str(excel_path))
        ui_data = adapt_collector_output(raw_data)

        raw_count = self._count_leaves(raw_data)
        ui_count = self._count_leaves(ui_data)

        print(f"\n[真实数据] 原始字段: {raw_count}, Adapter 后: {ui_count}, 增量: +{ui_count - raw_count}")
        # 增量应该 = group_total(13) + by_category(5×9-原值) + report_period(4) + ui_view(3)
        # 至少应该 >= raw_count
        self.assertGreaterEqual(ui_count, raw_count)


class TestUiViewFlag(unittest.TestCase):
    """测试 ui_view 标志"""

    def setUp(self):
        self.raw = make_full_collector_output()
        self.result = adapt_collector_output(self.raw)

    def test_ui_view_present(self):
        self.assertIn("ui_view", self.result)

    def test_ui_view_adapted_true(self):
        self.assertTrue(self.result["ui_view"]["adapted"])

    def test_ui_view_version(self):
        self.assertEqual(self.result["ui_view"]["adapter_version"], "v3.2")

    def test_ui_view_original_section_count(self):
        self.assertEqual(self.result["ui_view"]["original_section_count"], 6)


class TestKpiCompatibility(unittest.TestCase):
    """测试与 KPI_DEFINITIONS 路径完全兼容"""

    def setUp(self):
        from streamlit_app.components.data_preview import _get_dotted
        self._get_dotted = _get_dotted
        self.raw = make_full_collector_output()
        self.result = adapt_collector_output(self.raw)

    def test_kpi_total_volume(self):
        value = self._get_dotted(self.result, "group_total.total_ongrid_volume_yi_kwh")
        self.assertEqual(value, 89.08)

    def test_kpi_domestic_volume(self):
        value = self._get_dotted(self.result, "group_total.domestic_ongrid_volume_yi_kwh")
        self.assertEqual(value, 80.28)

    def test_kpi_international_volume(self):
        value = self._get_dotted(self.result, "group_total.international_ongrid_volume_yi_kwh")
        self.assertEqual(value, 8.8)

    def test_kpi_domestic_revenue(self):
        value = self._get_dotted(self.result, "group_total.domestic_revenue_yi_yuan")
        self.assertEqual(value, 24.93)

    def test_kpi_domestic_price(self):
        value = self._get_dotted(self.result, "group_total.domestic_avg_price_yuan_per_kwh")
        self.assertIsNotNone(value)

    def test_kpi_international_price(self):
        value = self._get_dotted(self.result, "international.avg_price_yuan_per_kwh")
        self.assertEqual(value, 0.32)

    def test_kpi_yoy_volume_pct(self):
        value = self._get_dotted(self.result, "group_total.yoy_volume_pct")
        self.assertEqual(value, 3.3)

    def test_kpi_mom_volume_pct(self):
        value = self._get_dotted(self.result, "group_total.mom_volume_pct")
        self.assertEqual(value, 15.7)


class TestEdgeCases(unittest.TestCase):
    """测试边界情况"""

    def test_empty_domestic(self):
        raw_data = {
            "domestic": {},
            "international": {},
            "meta": {},
        }
        result = adapt_collector_output(raw_data)
        self.assertIn("group_total", result)
        self.assertIn("by_category", result)
        self.assertIn("international", result)

    def test_missing_meta(self):
        """meta 缺失时 report_period 字段为 None"""
        raw_data = {
            "domestic": {"electricity": {"total": 100000}},
            "international": {},
        }
        result = adapt_collector_output(raw_data)
        self.assertIsNone(result["report_period"]["year"])
        self.assertIsNone(result["report_period"]["week"])

    def test_raw_data_not_mutated(self):
        """Adapter 不修改原始数据（深拷贝）"""
        raw_data = make_full_collector_output()
        original_domestic = raw_data["domestic"].copy()
        _ = adapt_collector_output(raw_data)
        # 原始数据应保持不变
        self.assertEqual(raw_data["domestic"], original_domestic)


if __name__ == "__main__":
    unittest.main()
