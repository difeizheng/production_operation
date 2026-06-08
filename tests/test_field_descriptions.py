"""field_descriptions 描述生成器测试

覆盖：
    - CURATED_OVERRIDES：58 个核心字段的人工校对
    - _extract_unit：所有单位后缀的识别
    - _translate_subsection：10+ section 的子节翻译
    - _extract_meaning：业务关键词的匹配
    - describe_field：完整流程 + 优先级 + fallback
    - 真实 fixture：覆盖率统计 + 描述非空
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from streamlit_app.utils.field_descriptions import (
    CURATED_OVERRIDES,
    LEAF_KEYWORD_ZH,
    UNIT_SUFFIX_MAP,
    _extract_meaning,
    _extract_unit,
    _translate_subsection,
    describe_field,
    get_curated_count,
)


# ============================================================
# _extract_unit 测试
# ============================================================


class TestExtractUnit:
    @pytest.mark.parametrize(
        "leaf_name,expected_unit",
        [
            ("volume_yi_kwh", "亿千瓦时"),
            ("total_volume_yi_kwh", "亿千瓦时"),
            ("avg_price_yuan_per_kwh", "元/千瓦时"),
            ("yoy_price_change_fen", "分"),
            ("mom_price_change_fen", "分"),
            ("revenue_yi_yuan", "亿元"),
            ("volume_kwh", "千瓦时"),
            ("revenue_yuan", "元"),
            ("yoy_volume_pct", "%"),
            ("weekly_sold_tons", "吨"),
            ("weekly_sold_count", "张"),
            ("weekly_issued_wan", "万"),
        ],
    )
    def test_known_suffixes(self, leaf_name, expected_unit):
        assert _extract_unit(leaf_name) == expected_unit

    def test_long_suffix_wins_over_short(self):
        """_yi_kwh 必须赢过 _kwh（顺序匹配保证）。"""
        assert _extract_unit("volume_yi_kwh") == "亿千瓦时"
        assert _extract_unit("volume_kwh") == "千瓦时"

    def test_no_suffix_returns_empty(self):
        """无后缀返回空字符串。"""
        assert _extract_unit("name") == ""
        assert _extract_unit("current") == ""
        assert _extract_unit("") == ""


# ============================================================
# _translate_subsection 测试
# ============================================================


class TestTranslateSubsection:
    def test_by_category_translates_to_chinese(self):
        zh, rest = _translate_subsection("by_category", ["hydro", "volume_yi_kwh"])
        assert zh == "水电"
        assert rest == ["volume_yi_kwh"]

    def test_by_region_translates_province(self):
        zh, rest = _translate_subsection("by_region", ["hubei", "yoy_price_change_fen"])
        assert zh == "湖北"
        assert rest == ["yoy_price_change_fen"]

    def test_by_company_translates_company(self):
        zh, rest = _translate_subsection("by_company", ["three_gorges_intl", "name"])
        assert zh == "三峡国际"
        assert rest == ["name"]

    def test_by_country_category_keeps_index(self):
        """by_country_category[0] → "国家[0]"。"""
        zh, rest = _translate_subsection("by_country_category", ["0", "country"])
        assert zh == "国家[0]"
        assert rest == ["country"]

    def test_exchange_rates_translates_currency_pair(self):
        zh, rest = _translate_subsection("exchange_rates", ["CNY_USD", "current"])
        assert zh == "人民币兑美元"
        assert rest == ["current"]

    def test_market_trading_adds_market_suffix(self):
        zh, rest = _translate_subsection("market_trading", ["hydro", "avg_price"])
        assert zh == "水电市场化"
        assert rest == ["avg_price"]

    def test_environmental_assets_translates(self):
        zh, rest = _translate_subsection("environmental_assets", ["green_cert", "weekly_sold"])
        assert zh == "绿证"
        assert rest == ["weekly_sold"]

    def test_unknown_section_passthrough(self):
        zh, rest = _translate_subsection("unknown_section", ["a", "b"])
        assert zh == ""
        assert rest == ["a", "b"]


# ============================================================
# _extract_meaning 测试
# ============================================================


class TestExtractMeaning:
    @pytest.mark.parametrize(
        "leaf_name,expected_meaning",
        [
            ("volume_yi_kwh", "上网电量"),
            ("avg_price_yuan_per_kwh", "平均上网电价"),
            ("revenue_yi_yuan", "发电收入"),
            ("yoy_volume_pct", "电量同比"),
            ("mom_volume_pct", "电量环比"),
            ("yoy_revenue_pct", "收入同比"),
            ("yoy_price_change_fen", "电价同比变化"),
            ("mom_price_change_fen", "电价环比变化"),
            ("share_pct", "电量占比"),
            ("weekly_issued_wan", "本周核发量"),
            ("weekly_sold_wan", "本周销售量"),
            ("currency_name", "币种"),
            ("year", "年份"),
            ("start_date", "开始日期"),
        ],
    )
    def test_known_keywords(self, leaf_name, expected_meaning):
        assert _extract_meaning(leaf_name) == expected_meaning

    def test_long_keyword_wins_over_short(self):
        """weekly_issued 必须赢过 issued。"""
        assert _extract_meaning("weekly_issued_wan") == "本周核发量"
        assert _extract_meaning("issued_wan") == "核发"

    def test_unknown_returns_empty(self):
        assert _extract_meaning("xyz_unknown") == ""
        assert _extract_meaning("") == ""


# ============================================================
# describe_field 端到端测试
# ============================================================


class TestDescribeField:
    # === CURATED 优先（人工校对字段）===
    def test_curated_group_total_volume(self):
        result = describe_field("group_total.total_ongrid_volume_yi_kwh")
        assert result["description_zh"] == "本周集团总上网电量"
        assert result["unit"] == "亿千瓦时"

    def test_curated_exchange_rate(self):
        result = describe_field("exchange_rates.CNY_USD.current")
        assert result["description_zh"] == "人民币兑美元当前汇率"
        assert result["unit"] == ""

    def test_curated_green_cert_sold(self):
        """绿证销售单位是"万张"不是"万"——CURATED 修正智能推断。"""
        result = describe_field("environmental_assets.green_cert.weekly_sold_wan")
        assert "绿证" in result["description_zh"]
        assert "本周销售量" in result["description_zh"]
        assert result["unit"] == "万张"

    def test_curated_overrides_win_over_inference(self):
        """CURATED 必须赢过智能推断。"""
        # CURATED: "本周国内总上网电量"
        # 智能推断可能输出: "集团汇总·国内上网电量（亿千瓦时）"
        result = describe_field("group_total.domestic_ongrid_volume_yi_kwh")
        assert result["description_zh"] == "本周国内总上网电量"

    # === 智能推断（推断字段）===
    def test_inferred_by_region(self):
        result = describe_field("by_region.hubei.yoy_price_change_fen")
        assert "湖北" in result["description_zh"]
        assert "电价" in result["description_zh"]
        assert "同比" in result["description_zh"]
        assert result["unit"] == "分"

    def test_inferred_by_category(self):
        """CURATED 字段直接走人工校对（"本周水电度电均价"）。"""
        result = describe_field("by_category.hydro.avg_price_yuan_per_kwh")
        # CURATED 优先
        assert result["description_zh"] == "本周水电度电均价"
        assert result["unit"] == "元/千瓦时"

    def test_inferred_by_category_falls_through_when_not_curated(self):
        """非 CURATED 字段走智能推断。"""
        # hydro 的 share_pct 不在 CURATED
        result = describe_field("by_category.renewables.mom_volume_pct")
        assert "新能源" in result["description_zh"]
        assert "电量环比" in result["description_zh"]
        assert result["unit"] == "%"

    def test_inferred_market_trading(self):
        result = describe_field("market_trading.thermal.avg_price_yuan_per_kwh")
        assert "火电市场化" in result["description_zh"]
        assert result["unit"] == "元/千瓦时"

    def test_inferred_array_index(self):
        """数组路径推断：by_country_category[0].country。"""
        result = describe_field("by_country_category[0].country")
        assert "国家[0]" in result["description_zh"]
        assert "国家" in result["description_zh"]

    def test_inferred_by_company(self):
        result = describe_field("by_company.three_gorges_intl.name")
        assert "三峡国际" in result["description_zh"]

    # === Fallback（兜底行为）===
    def test_unknown_path_still_returns_something(self):
        """未识别路径必须返回 description（不能是空）。"""
        result = describe_field("totally.unknown.path.xyz")
        assert result["description_zh"]  # 非空
        # 兜底应该保留原路径或 section+leaf
        assert len(result["description_zh"]) > 0

    def test_empty_path(self):
        result = describe_field("")
        # 兜底不报错
        assert "description_zh" in result
        assert "unit" in result


# ============================================================
# CURATED 数据质量测试
# ============================================================


class TestCuratedQuality:
    def test_curated_count_is_reasonable(self):
        """CURATED 数量应在合理范围（30-100）。"""
        n = get_curated_count()
        assert 30 <= n <= 100, f"CURATED 数量 {n} 超出预期范围"

    def test_all_curated_have_description_and_unit(self):
        """每条 CURATED 必须有 description_zh 和 unit。"""
        for path, info in CURATED_OVERRIDES.items():
            assert "description_zh" in info, f"{path} 缺 description_zh"
            assert "unit" in info, f"{path} 缺 unit"
            assert info["description_zh"], f"{path} description_zh 为空"

    def test_curated_paths_cover_core_sections(self):
        """CURATED 路径应覆盖核心 sections。"""
        sections = {p.split(".")[0] for p in CURATED_OVERRIDES.keys()}
        assert "group_total" in sections
        assert "by_category" in sections
        assert "international" in sections
        assert "exchange_rates" in sections
        assert "environmental_assets" in sections


# ============================================================
# 真实 fixture 回归保护
# ============================================================


FIXTURE_PATH = (
    Path(__file__).parent.parent / "tests" / "fixtures" / "weekly_report_merged.json"
)


@pytest.fixture(scope="module")
def fixture_data() -> dict:
    with FIXTURE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def fixture_descriptions(fixture_data) -> list:
    """对 fixture 中所有叶子调用 describe_field。"""

    def get_paths(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("meta", "version", "report_id"):
                    continue
                yield from get_paths(v, f"{prefix}.{k}" if prefix else k)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                yield from get_paths(item, f"{prefix}[{i}]")
        else:
            yield prefix

    return [(p, describe_field(p)) for p in get_paths(fixture_data)]


class TestFixtureDescriptions:
    def test_all_leaves_have_descriptions(self, fixture_descriptions):
        """所有叶子字段都必须有中文描述（非空）。"""
        for path, info in fixture_descriptions:
            assert info["description_zh"], f"{path} 描述为空"
            assert isinstance(info["description_zh"], str)
            assert isinstance(info["unit"], str)

    def test_all_leaves_have_unit_field(self, fixture_descriptions):
        """unit 字段必须存在（即使为空字符串）。"""
        for path, info in fixture_descriptions:
            assert "unit" in info, f"{path} 缺 unit 字段"

    def test_curated_coverage_at_least_15_percent(self, fixture_descriptions):
        """CURATED 覆盖至少 15%（保证重点字段有人工把关）。"""
        n_total = len(fixture_descriptions)
        n_curated = len(CURATED_OVERRIDES)
        ratio = n_curated / n_total
        assert ratio >= 0.15, f"CURATED 覆盖 {ratio:.1%} < 15%"

    def test_no_description_contains_placeholder(self, fixture_descriptions):
        """描述里不应有占位符（···/TODO/None 等）。"""
        placeholders = ["···", "TODO", "TBD", "None", "null"]
        for path, info in fixture_descriptions:
            for p in placeholders:
                assert p not in info["description_zh"], (
                    f"{path} 描述含占位符 '{p}': {info['description_zh']}"
                )

    def test_critical_fields_all_curated(self, fixture_descriptions):
        """最关键的 8 个字段必须都是 CURATED。"""
        critical = [
            "group_total.total_ongrid_volume_yi_kwh",
            "group_total.domestic_ongrid_volume_yi_kwh",
            "group_total.domestic_revenue_yi_yuan",
            "group_total.domestic_avg_price_yuan_per_kwh",
            "by_category.hydro.volume_yi_kwh",
            "by_category.hydro.avg_price_yuan_per_kwh",
            "international.total_volume_yi_kwh",
            "international.avg_price_yuan_per_kwh",
        ]
        for path in critical:
            assert path in CURATED_OVERRIDES, f"关键字段未校对: {path}"

    def test_unit_values_are_consistent(self, fixture_descriptions):
        """单位值应该是预定义的中文单位（不能是乱七八糟的字符串）。"""
        valid_units = {
            "",  # 空（无单位）
            "亿千瓦时", "万千瓦时", "千瓦时",
            "亿元", "元", "分",
            "%", "万", "万张", "张", "只", "吨",
            "元/千瓦时", "元/张", "元/吨",
        }
        for path, info in fixture_descriptions:
            unit = info["unit"]
            assert unit in valid_units, f"{path} 单位 '{unit}' 不在预定义列表中"


# ============================================================
# 关键字表结构测试
# ============================================================


class TestKeywordTableStructure:
    def test_unit_suffixes_are_tuples(self):
        assert all(isinstance(t, tuple) and len(t) == 2 for t in UNIT_SUFFIX_MAP)

    def test_leaf_keywords_are_tuples(self):
        assert all(isinstance(t, tuple) and len(t) == 2 for t in LEAF_KEYWORD_ZH)

    def test_no_duplicate_unit_suffixes(self):
        suffixes = [s for s, _ in UNIT_SUFFIX_MAP]
        assert len(suffixes) == len(set(suffixes)), "单位后缀有重复"

    def test_no_duplicate_leaf_keywords(self):
        keywords = [k for k, _ in LEAF_KEYWORD_ZH]
        assert len(keywords) == len(set(keywords)), "业务关键词有重复"
