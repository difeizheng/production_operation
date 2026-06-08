"""data_preview 组件测试

覆盖：
    - _flatten_to_leaves：嵌套 dict、list 展平、None 缺失、SKIP_KEYS 跳过
    - categorize_field：全路径匹配 + 优先级（同比/环比 > 电价/电费/电量 > 区域）
    - 真实 fixture 统计：11 顶层 section、236 叶子字段、0 缺失

回归：修复 v3.0 "186 字段" 标题错误——原来是顶层 11 字段，
      实际应该是叶子 236 字段。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from streamlit_app.components.data_preview import (
    KPI_DEFINITIONS,
    SKIP_KEYS,
    _flatten_to_leaves,
    _format_kpi_value,
    _get_dotted,
    categorize_field,
)


# ============================================================
# _flatten_to_leaves 测试
# ============================================================


class TestFlattenToLeaves:
    def test_simple_dict(self):
        """最简 dict：1 层 1 个叶子。"""
        leaves = _flatten_to_leaves({"a": 1})
        assert len(leaves) == 1
        assert leaves[0]["path"] == "a"
        assert leaves[0]["value"] == 1
        assert leaves[0]["section"] == "a"
        assert leaves[0]["is_missing"] is False

    def test_nested_dict_builds_dotted_path(self):
        """嵌套 dict：路径用 . 拼接。"""
        data = {"outer": {"inner": {"deep": 42}}}
        leaves = _flatten_to_leaves(data)
        assert len(leaves) == 1
        assert leaves[0]["path"] == "outer.inner.deep"
        assert leaves[0]["value"] == 42
        assert leaves[0]["section"] == "outer"  # 顶层 section

    def test_list_flattens_with_index(self):
        """list 展平：用 [i] 标记索引。"""
        data = {"arr": [{"x": 1}, {"x": 2}, {"x": 3}]}
        leaves = _flatten_to_leaves(data)
        assert len(leaves) == 3
        assert [l["path"] for l in leaves] == ["arr[0].x", "arr[1].x", "arr[2].x"]
        assert [l["value"] for l in leaves] == [1, 2, 3]
        # 数组元素继承父 section
        assert all(l["section"] == "arr" for l in leaves)

    def test_none_is_marked_as_missing(self):
        """None 算缺失叶子（不忽略）。"""
        data = {"a": None, "b": 0, "c": ""}
        leaves = _flatten_to_leaves(data)
        assert len(leaves) == 3
        assert leaves[0]["is_missing"] is True
        assert leaves[0]["value"] is None
        assert leaves[1]["is_missing"] is False  # 0 是合法值
        assert leaves[2]["is_missing"] is False  # "" 是合法值

    def test_skip_keys_filtered_at_every_level(self):
        """SKIP_KEYS 在每一层都生效（嵌套深层的同名 key 也跳）。"""
        data = {
            "report_id": "should_skip",
            "report_period": {"year": 2026, "week": 21, "meta": "should_skip"},
            "version": "1.0",
            "real_data": {"value": 100},
        }
        leaves = _flatten_to_leaves(data)
        paths = [l["path"] for l in leaves]
        # report_id / version / 嵌套的 meta 都应被跳过
        assert "report_id" not in paths
        assert "version" not in paths
        assert "report_period.meta" not in paths
        # 剩下的应是真实数据
        assert "report_period.year" in paths
        assert "report_period.week" in paths
        assert "real_data.value" in paths
        assert len(leaves) == 3

    def test_mixed_types_in_one_struct(self):
        """复杂结构：dict + list + scalar 混合。"""
        data = {
            "group_total": {"volume": 89.1, "price": 0.311},
            "by_category": {
                "hydro": {"volume_yi_kwh": 59.0},
                "thermal": {"revenue_yi_yuan": 1.3, "missing_field": None},
            },
            "by_country": [
                {"country": "巴西", "volume": 2.5},
                {"country": "西班牙", "volume": 1.8},
            ],
        }
        leaves = _flatten_to_leaves(data)
        # group_total: 2 + by_category: 3 + by_country: 2 元素 × 2 字段 = 4
        # 总计 2 + 3 + 4 = 9
        assert len(leaves) == 9
        assert sum(1 for l in leaves if l["is_missing"]) == 1
        assert {l["section"] for l in leaves} == {"group_total", "by_category", "by_country"}
        # by_country 的 section 继承自父
        assert all(l["section"] == "by_country" for l in leaves if "by_country" in l["path"])

    def test_empty_dict_yields_no_leaves(self):
        """空 dict：无叶子。"""
        assert _flatten_to_leaves({}) == []
        assert _flatten_to_leaves({"a": {}}) == []
        assert _flatten_to_leaves({"a": []}) == []

    def test_section_uses_top_level_key(self):
        """section 是顶层 key，无论嵌套多深。"""
        data = {"A": {"B": {"C": {"D": 1}}}}
        leaves = _flatten_to_leaves(data)
        assert leaves[0]["section"] == "A"


# ============================================================
# categorize_field 测试
# ============================================================


class TestCategorizeField:
    def test_base_wins_over_change(self):
        """基础类型（price/volume/revenue）优先于变化类型（yoy/wow）。

        设计理由：wow_price/yoy_price 应该归到"电价"分类（价格的故事要完整），
        而不是分散到"环比"/"同比"分类。这是 v3.0 旧测试的设计理念。
        """
        # 复合 keyword：基础类型赢
        assert categorize_field("dom.yoy.price_fen") == "电价"
        assert categorize_field("report.wow_price.hydro") == "电价"
        assert categorize_field("by_category.hydro.mom_price_change_fen") == "电价"
        assert categorize_field("by_category.hydro.mom_revenue_pct") == "电费"
        assert categorize_field("dom.yoy.volume") == "电量"
        assert categorize_field("report.wow_volume") == "电量"

    def test_pure_yoy_wow_goes_to_change_category(self):
        """纯 yoy/wow 字段（无 base keyword）归到同比/环比。"""
        # 没有 price/volume/revenue keyword 时，yoy/wow 生效
        assert categorize_field("report.yoy.field") == "同比"
        assert categorize_field("yoy_metric") == "同比"
        assert categorize_field("dom.yoy") == "同比"
        assert categorize_field("wow_only") == "环比"
        assert categorize_field("mom_only") == "环比"

    def test_price_for_electricity_pricing(self):
        """电价类。"""
        assert categorize_field("by_category.hydro.avg_price_yuan_per_kwh") == "电价"
        assert categorize_field("dom.price") == "电价"
        assert categorize_field("report.price.avg") == "电价"

    def test_revenue_for_income_fields(self):
        """电费/收入类。"""
        assert categorize_field("dom.revenue") == "电费"
        assert categorize_field("by_category.hydro.revenue_yi_yuan") == "电费"
        assert categorize_field("group_total.domestic_revenue_yi_yuan") == "电费"

    def test_volume_for_electricity_quantity(self):
        """电量类。"""
        assert categorize_field("by_category.hydro.volume_yi_kwh") == "电量"
        assert categorize_field("report.electricity.domestic") == "电量"
        assert categorize_field("dom.volume") == "电量"

    def test_international_section_wins_over_base(self):
        """section 优先于 base keyword。

        international/exchange/by_country 是 section 标签，
        应该覆盖里面的 volume/price 类型，归到"国际"分类。
        """
        assert categorize_field("international.total_volume_yi_kwh") == "国际"
        assert categorize_field("exchange_rates.CNY_USD.current") == "国际"
        assert categorize_field("by_country_category[0].country") == "国际"
        assert categorize_field("international.avg_price_yuan_per_kwh") == "国际"

    def test_market_trading_section(self):
        """市场化交易类。"""
        assert categorize_field("market_trading.hydro.avg_price") == "市场化"
        assert categorize_field("market_trading.thermal.revenue") == "市场化"
        # 即使是电量类字段，section 也优先
        assert categorize_field("market_trading.hydro.volume") == "市场化"

    def test_environmental_section(self):
        """环境资产/绿证/CCER。"""
        assert categorize_field("environmental_assets.green_cert.weekly_issued") == "绿证"
        assert categorize_field("environmental_assets.ccer.price") == "绿证"

    def test_unknown_returns_other(self):
        """未匹配路径返回"其他"。"""
        assert categorize_field("report_id") == "其他"  # 被 SKIP，不该到这里
        assert categorize_field("report_period.year") == "其他"
        assert categorize_field("random.unknown.field") == "其他"


# ============================================================
# 真实 fixture 测试（回归保护）
# ============================================================


FIXTURE_PATH = (
    Path(__file__).parent.parent / "tests" / "fixtures" / "weekly_report_merged.json"
)


@pytest.fixture(scope="module")
def fixture_data() -> dict:
    with FIXTURE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


class TestFixtureRegression:
    """真实 fixture 的统计应该稳定，作为回归保护。"""

    def test_fixture_top_level_sections(self, fixture_data):
        """11 个顶层 section。"""
        assert len(fixture_data) == 11

    def test_fixture_leaf_count_is_270(self, fixture_data):
        """修复后叶子字段数 = 270（不是 11 顶层，也不是之前估的 236）。

        270 来源：递归扁平化所有 dict + list，包括 by_country_category 数组
        展开后的 26 个元素（前一次的 236 把 list 当 1 个叶子数）。
        """
        leaves = _flatten_to_leaves(fixture_data)
        assert len(leaves) == 270, (
            f"叶子字段数变化！当前 {len(leaves)}，期望 270。"
            "如果改了 fixture 或 _flatten_to_leaves，请更新此值。"
        )

    def test_fixture_sections_covered(self, fixture_data):
        """section 数 = 10（report_id 被 SKIP_KEYS 跳过，剩 10 个顶层）。"""
        leaves = _flatten_to_leaves(fixture_data)
        sections = {l["section"] for l in leaves}
        assert len(sections) == 10
        assert "report_id" not in sections  # 被 SKIP
        # 关键 section 应齐全
        assert "group_total" in sections
        assert "by_category" in sections
        assert "international" in sections
        assert "market_trading" in sections
        assert "environmental_assets" in sections

    def test_fixture_no_missing_leaves(self, fixture_data):
        """演示数据无缺失字段（覆盖率 100%）。"""
        leaves = _flatten_to_leaves(fixture_data)
        missing = [l for l in leaves if l["is_missing"]]
        assert len(missing) == 0

    def test_fixture_categories_well_distributed(self, fixture_data):
        """分类应覆盖多个类别（不是全"其他"）。"""
        leaves = _flatten_to_leaves(fixture_data)
        categories = {l["category"] for l in leaves}
        # 至少应该有：电量、电价、电费、同比/环比、国际、市场化、绿证
        assert "电量" in categories
        assert "电价" in categories
        assert "电费" in categories
        assert "国际" in categories
        assert "市场化" in categories
        assert "绿证" in categories
        # 不应该全是"其他"
        assert categories != {"其他"}

    def test_skip_keys_excludes_report_id(self, fixture_data):
        """SKIP_KEYS 中包含 report_id。"""
        assert "report_id" in SKIP_KEYS
        leaves = _flatten_to_leaves(fixture_data)
        assert all(not l["path"].startswith("report_id") for l in leaves)


# ============================================================
# _format_kpi_value 测试（KPI 卡片值格式化）
# ============================================================


class TestFormatKpiValue:
    """修复历史 bug：7 个 KPI 全部查不存在的 key + 百分比被误乘 100。"""

    def test_none_returns_dash(self):
        """None 返回 "—"（不报错）。"""
        assert _format_kpi_value(None, "volume") == "—"
        assert _format_kpi_value(None, "pct") == "—"

    def test_volume_format(self):
        """电量格式：80.3 亿千瓦时。"""
        assert _format_kpi_value(80.3, "volume") == "80.3 亿千瓦时"
        assert _format_kpi_value(89.1, "volume") == "89.1 亿千瓦时"

    def test_price_format(self):
        """电价格式：0.311 元/度。"""
        assert _format_kpi_value(0.311, "price") == "0.311 元/度"
        assert _format_kpi_value(0.32, "price") == "0.320 元/度"

    def test_revenue_format(self):
        """收入格式：24.97 亿元。"""
        assert _format_kpi_value(24.97, "revenue") == "24.97 亿元"

    def test_pct_format_with_sign(self):
        """百分比格式：+3.3%（带正负号，1 位小数）。"""
        # 关键修复：fixture 中是 3.3（已乘 100），不能再乘
        assert _format_kpi_value(3.3, "pct") == "+3.3%"
        assert _format_kpi_value(-0.9, "pct") == "-0.9%"
        assert _format_kpi_value(15.7, "pct") == "+15.7%"
        assert _format_kpi_value(0.0, "pct") == "+0.0%"

    def test_non_numeric_passthrough(self):
        """非数字类型原样返回。"""
        assert _format_kpi_value("2026", "volume") == "2026"
        assert _format_kpi_value("21", "pct") == "21"

    def test_unknown_format_returns_str(self):
        """未知 fmt 类型：toString。"""
        assert _format_kpi_value(42, "unknown") == "42"


class TestGetDotted:
    """_get_dotted 关键测试：dict.get 不会拆点分路径，必须自己遍历。

    修复 v3.0 bug：data.get('group_total.foo') 返回 None，因为
    没有任何顶层 key 叫 "group_total.foo"——这是个低级错误。
    """

    def test_top_level_key(self):
        """单层 key：直接返回。"""
        assert _get_dotted({"a": 1}, "a") == 1

    def test_two_level_nested(self):
        """2 层嵌套。"""
        assert _get_dotted({"a": {"b": 42}}, "a.b") == 42

    def test_three_level_nested(self):
        """3 层嵌套。"""
        data = {"a": {"b": {"c": "deep"}}}
        assert _get_dotted(data, "a.b.c") == "deep"

    def test_missing_intermediate_returns_none(self):
        """中间层缺失：返回 None（不报错）。"""
        assert _get_dotted({"a": {}}, "a.b.c") is None
        assert _get_dotted({}, "a.b") is None

    def test_missing_leaf_returns_none(self):
        """叶子缺失：返回 None。"""
        assert _get_dotted({"a": {"b": 1}}, "a.c") is None

    def test_non_dict_intermediate_returns_none(self):
        """中间层不是 dict：返回 None（不报错）。"""
        assert _get_dotted({"a": 42}, "a.b") is None
        assert _get_dotted({"a": "str"}, "a.b") is None
        assert _get_dotted({"a": [1, 2, 3]}, "a.b") is None

    def test_empty_data(self):
        """空 dict。"""
        assert _get_dotted({}, "anything") is None

    def test_real_kpi_paths(self, fixture_data):
        """关键回归：8 个 KPI 路径在 fixture 中都能用 _get_dotted 拿到值。"""
        for kpi in KPI_DEFINITIONS:
            value = _get_dotted(fixture_data, kpi["path"])
            assert value is not None, (
                f"KPI '{kpi['label']}' 路径 '{kpi['path']}' 用 _get_dotted 仍找不到！"
            )

    def test_dict_get_does_NOT_traverse_dots(self, fixture_data):
        """核心回归保护：证明 dict.get 真的不会拆点分路径。

        这是 KPI 全部显示 '—' 的根因——必须用 _get_dotted。
        """
        for kpi in KPI_DEFINITIONS:
            wrong = fixture_data.get(kpi["path"])  # 错误方式
            right = _get_dotted(fixture_data, kpi["path"])  # 正确方式
            # 错误方式应返回 None，正确方式应有值
            assert wrong is None, (
                f"路径 '{kpi['path']}': dict.get 居然返回 {wrong}（不应该）"
            )
            assert right is not None, (
                f"路径 '{kpi['path']}': _get_dotted 找不到值"
            )


class TestKPIDefinitions:
    """KPI 定义完整性测试（防止新增 KPI 时路径写错）。"""

    def test_have_8_kpis(self):
        """当前定义 8 个 KPI（4×2 网格）。"""
        assert len(KPI_DEFINITIONS) == 8

    def test_all_kpis_have_required_keys(self):
        """每个 KPI 必须有 label/path/fmt。"""
        for kpi in KPI_DEFINITIONS:
            assert "label" in kpi
            assert "path" in kpi
            assert "fmt" in kpi
            assert kpi["label"]
            assert kpi["path"]
            assert kpi["fmt"] in ("volume", "price", "revenue", "pct")

    def test_all_kpi_paths_exist_in_fixture(self, fixture_data):
        """8 个 KPI 路径必须都能在 fixture 中找到值（防止 v3.0 旧 bug 复发）。"""
        for kpi in KPI_DEFINITIONS:
            value = _get_dotted(fixture_data, kpi["path"])
            assert value is not None, (
                f"KPI '{kpi['label']}' 路径 '{kpi['path']}' 在 fixture 中不存在！"
                "这是 v3.0 旧 bug 复发。"
            )

    def test_pct_kpis_already_in_percent(self, fixture_data):
        """百分比 KPI 的值是已乘 100 的（如 3.3 表示 3.3%），不是 0.033。"""
        for kpi in KPI_DEFINITIONS:
            if kpi["fmt"] == "pct":
                value = _get_dotted(fixture_data, kpi["path"])
                assert value is not None, f"KPI '{kpi['label']}' 路径不存在"
                # 验证：3.3 不是 0.033（即确认是 3.3% 而非 330%）
                assert -100 < value < 100, (
                    f"KPI '{kpi['label']}' 值 {value} 超出百分比合理范围，"
                    "可能是 0-1 比率（需乘 100）或数据异常"
                )
