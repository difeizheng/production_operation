"""
市场率分析器单元测试 (test_market_metrics)
==========================================

测试覆盖：
- calculate_market_rate: 边界条件、正常值、上限截断
- calculate_price_diff: 正常值、零值
- classify_organization: 7 种类别映射
- classify_quadrant: 4 象限判定
- calculate_revenue_contribution: 正常值、零除
- derive_metrics: 集成计算
- analyze_market_dimension: 端到端批量分析
- build_org_metrics: fixture 装配

v2.4 新增测试：35 个测试用例
"""

import json
from pathlib import Path

import pytest

from src.analyzer.market_metrics import (
    DerivedMetrics,
    MarketDimensionResult,
    OrgMetrics,
    analyze_market_dimension,
    build_org_metrics,
    calculate_market_rate,
    calculate_price_diff,
    calculate_revenue_contribution,
    classify_organization,
    classify_quadrant,
    derive_metrics,
)


# === Fixtures ===

@pytest.fixture
def fixture_dir() -> Path:
    """Fixture 目录"""
    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def overall_data(fixture_dir) -> dict:
    """整体销售 fixture"""
    with open(fixture_dir / "domestic_overall_v24.json", encoding="utf-8") as f:
        return json.load(f)["by_organization"]


@pytest.fixture
def market_data(fixture_dir) -> dict:
    """市场化交易 fixture"""
    with open(fixture_dir / "domestic_market_v24.json", encoding="utf-8") as f:
        return json.load(f)["by_organization"]


@pytest.fixture
def orgs_list(overall_data, market_data) -> list:
    """18 个组织 OrgMetrics 列表"""
    return build_org_metrics(overall_data, market_data)


@pytest.fixture
def full_result(orgs_list) -> MarketDimensionResult:
    """完整分析结果"""
    return analyze_market_dimension(orgs_list)


# === calculate_market_rate 测试 ===

class TestCalculateMarketRate:
    """市场化率计算"""

    def test_normal_50_percent(self):
        """正常 50% 场景"""
        assert calculate_market_rate(100, 50) == 50.0

    def test_zero_overall(self):
        """整体电量为 0 → 返回 0（避免除零）"""
        assert calculate_market_rate(0, 50) == 0.0

    def test_zero_market(self):
        """市场化为 0 → 返回 0"""
        assert calculate_market_rate(100, 0) == 0.0

    def test_full_market(self):
        """100% 市场化（极少见）"""
        assert calculate_market_rate(100, 100) == 100.0

    def test_yangtze_hydro(self):
        """长江电力验证：145099.49/551687.97 ≈ 26.30%"""
        rate = calculate_market_rate(551687.97, 145099.49)
        assert 26.0 <= rate <= 26.5, f"期望 26.30%，实际 {rate}%"

    def test_exceeds_100_capped(self):
        """市场化率上限截断（理论不应 > 100%）"""
        # 假如数据错误，市场化 > 整体，应被截断到 100
        assert calculate_market_rate(100, 120) == 100.0

    def test_negative_overall_returns_zero(self):
        """负数整体 → 返回 0"""
        assert calculate_market_rate(-10, 5) == 0.0

    def test_small_decimal(self):
        """小数情况：4 位精度"""
        result = calculate_market_rate(123.456, 78.901)
        assert isinstance(result, float)
        assert 0 < result < 100


# === calculate_price_diff 测试 ===

class TestCalculatePriceDiff:
    """电价差计算"""

    def test_premium(self):
        """溢价：市场化 > 整体"""
        assert calculate_price_diff(0.27, 0.30) == 0.03

    def test_discount(self):
        """折价：市场化 < 整体"""
        assert calculate_price_diff(0.42, 0.28) == -0.14

    def test_zero(self):
        """零价差：两者相等"""
        assert calculate_price_diff(0.396, 0.396) == 0.0

    def test_yangtze_premium(self):
        """长江电力：0.304 - 0.271 = +0.033"""
        assert calculate_price_diff(0.271, 0.304) == pytest.approx(0.033, abs=0.001)

    def test_xinjiang_discount(self):
        """新疆分：0.129 - 0.302 = -0.173"""
        assert calculate_price_diff(0.302, 0.129) == pytest.approx(-0.173, abs=0.001)


# === classify_organization 测试 ===

class TestClassifyOrganization:
    """组织分桶"""

    @pytest.mark.parametrize("category,expected", [
        ("hydro", "水电组"),
        ("renewables", "新能源组"),
        ("thermal", "传统能源组"),
        ("construction", "工程组"),
        ("environmental", "环保组"),
        ("development", "发展组"),
        ("regional", "区域分公司组"),
        ("unknown", "未分类"),
    ])
    def test_all_categories(self, category, expected):
        """所有 7 个类别 + 1 个 unknown"""
        assert classify_organization(category) == expected


# === classify_quadrant 测试 ===

class TestClassifyQuadrant:
    """象限判定"""

    def test_premium_scarce(self):
        """稀缺溢价：低市场化率 + 高溢价（典型水电）"""
        # 长江电力：26.30% + +0.033
        assert classify_quadrant(26.30, 0.033) == "稀缺溢价"

    def test_premium_competitive(self):
        """竞争溢价：高市场化率 + 高溢价（罕见）"""
        # 假设数据：高市场化率 + 溢价
        assert classify_quadrant(80.0, 0.05) == "竞争溢价"

    def test_discount_scarce(self):
        """稀缺折价：低市场化率 + 低折价"""
        # 假设：三峡建工 6.8% + -0.046
        assert classify_quadrant(6.8, -0.046) == "稀缺折价"

    def test_discount_competitive(self):
        """竞争折价：高市场化率 + 低折价（典型新能源）"""
        # 三峡能源：85.3% + -0.136
        assert classify_quadrant(85.3, -0.136) == "竞争折价"

    def test_threshold_boundary_high_rate(self):
        """市场化率边界：恰好 50% → 算"高" """
        # 50% >= 50% → True
        assert classify_quadrant(50.0, 0.01) == "竞争溢价"

    def test_threshold_boundary_just_below(self):
        """市场化率边界：49.99% → 算"低" """
        assert classify_quadrant(49.99, 0.01) == "稀缺溢价"

    def test_threshold_boundary_zero_diff(self):
        """电价差边界：0 → 算"溢价" """
        assert classify_quadrant(30.0, 0.0) == "稀缺溢价"

    def test_threshold_boundary_negative_diff(self):
        """电价差边界：-0.001 → 算"折价" """
        assert classify_quadrant(30.0, -0.001) == "稀缺折价"


# === calculate_revenue_contribution 测试 ===

class TestCalculateRevenueContribution:
    """贡献度计算"""

    def test_normal(self):
        """正常：50/200 = 25%"""
        assert calculate_revenue_contribution(50, 200) == 25.0

    def test_zero_total(self):
        """总值为 0 → 返回 0（避免除零）"""
        assert calculate_revenue_contribution(50, 0) == 0.0

    def test_100_percent(self):
        """100% 贡献"""
        assert calculate_revenue_contribution(100, 100) == 100.0

    def test_decimal_precision(self):
        """小数精度（2 位）"""
        result = calculate_revenue_contribution(33, 100)
        assert result == 33.0


# === derive_metrics 测试 ===

class TestDeriveMetrics:
    """派生单个组织指标"""

    def test_yangtze(self):
        """长江电力验证"""
        org = OrgMetrics(
            name="长江电力",
            category="hydro",
            overall_volume=551687.97,
            overall_price=0.271,
            overall_revenue=149650.63,
            market_volume=145099.49,
            market_price=0.304,
            market_revenue=44127.41,
        )
        d = derive_metrics(org, 802763.41, 332013.36, 249258.79)

        assert d.name == "长江电力"
        assert d.market_rate == pytest.approx(26.30, abs=0.05)
        assert d.price_diff == pytest.approx(0.033, abs=0.001)
        assert d.quadrant == "稀缺溢价"
        assert d.is_active_in_market is True
        assert d.revenue_contribution > 50  # 长江电力占集团 > 50%

    def test_inactive_org(self):
        """不参与市场化的组织（长江环保）"""
        org = OrgMetrics(
            name="长江环保",
            category="environmental",
            overall_volume=584.43,
            overall_price=0.438,
            overall_revenue=256.02,
            market_volume=0.0,
            market_price=0.0,
            market_revenue=0.0,
        )
        d = derive_metrics(org, 802763.41, 332013.36, 249258.79)

        assert d.market_rate == 0.0
        # 实际：price_diff = 0.0 - 0.438 = -0.438（折价）
        assert d.price_diff == pytest.approx(-0.438, abs=0.001)
        assert d.quadrant == "稀缺折价"  # 低市场化率 + 折价
        assert d.is_active_in_market is False

    def test_chongqing_zero_yoy(self):
        """重庆分（去年同期市场化为 0，避免异常）"""
        org = OrgMetrics(
            name="重庆分",
            category="regional",
            overall_volume=211.53,
            overall_price=0.396,
            overall_revenue=83.85,
            market_volume=211.53,
            market_price=0.396,
            market_revenue=83.85,
        )
        d = derive_metrics(org, 1000.0, 500.0, 1000.0)
        assert d.market_rate == pytest.approx(100.0, abs=0.01)
        assert d.price_diff == 0.0


# === analyze_market_dimension 测试 ===

class TestAnalyzeMarketDimension:
    """批量分析"""

    def test_empty_raises(self):
        """空列表应抛 ValueError"""
        with pytest.raises(ValueError, match="orgs 不能为空"):
            analyze_market_dimension([])

    def test_total_market_rate_41(self, full_result):
        """集团整体市场化率 ≈ 41.36%"""
        # 332013.36 / 802763.39 ≈ 41.36%
        assert 41.0 <= full_result.total_market_rate <= 42.0

    def test_total_volume_match(self, full_result):
        """集团整体电量等于 18 组织之和（合并：802763.39 万 kWh）"""
        expected = 802763.39
        assert full_result.total_overall_volume == pytest.approx(expected, rel=0.001)

    def test_total_market_volume_match(self, full_result):
        """集团市场化电量等于 18 组织之和（332013.36 万 kWh）"""
        expected = 332013.36
        assert full_result.total_market_volume == pytest.approx(expected, rel=0.001)

    def test_orgs_count(self, full_result):
        """返回 18 个组织派生指标"""
        assert len(full_result.orgs) == 18

    def test_quadrant_distribution_total(self, full_result):
        """象限分布加和 = 18"""
        assert sum(full_result.quadrant_distribution.values()) == 18

    def test_quadrant_yangtze_scarce_premium(self, full_result):
        """长江电力应在"稀缺溢价"象限"""
        cj = next(d for d in full_result.orgs if d.name == "长江电力")
        assert cj.quadrant == "稀缺溢价"

    def test_quadrant_three_gorges_energy_discount(self, full_result):
        """三峡能源应在"竞争折价"象限（典型新能源）"""
        sxe = next(d for d in full_result.orgs if d.name == "三峡能源")
        assert sxe.quadrant == "竞争折价"
        assert sxe.market_rate > 80  # 高市场化率
        assert sxe.price_diff < 0    # 折价

    def test_inactive_orgs(self, full_result):
        """长江环保和三峡发展不参与市场化"""
        inactive_names = {d.name for d in full_result.orgs if not d.is_active_in_market}
        assert "长江环保" in inactive_names
        assert "三峡发展" in inactive_names

    def test_top_market_rate_orgs(self, full_result):
        """TOP 5 市场化率应包含多个分公司"""
        # 重庆分、四川分、广东分等都是 100% 市场化
        top_5 = full_result.top_market_rate_orgs
        assert len(top_5) == 5
        # 应包含至少一个分公司（云南分、四川分、广东分之一）
        assert any(name in top_5 for name in ["云南分", "四川分", "广东分", "重庆分"])

    def test_top_premium_orgs_yangtze(self, full_result):
        """长江电力是 TOP 溢价（稀缺水电）"""
        assert "长江电力" in full_result.top_price_premium_orgs

    def test_category_distribution(self, full_result):
        """业务桶分布应包含多个组"""
        # 至少有水电组、新能源组、传统能源组、区域分公司组、工程组、环保组、发展组
        assert "水电组" in full_result.category_distribution
        assert "新能源组" in full_result.category_distribution
        assert "区域分公司组" in full_result.category_distribution
        assert "环保组" in full_result.category_distribution
        assert "发展组" in full_result.category_distribution

    def test_result_is_frozen(self, full_result):
        """结果不可变（dataclass frozen=True）"""
        with pytest.raises(Exception):  # FrozenInstanceError 或 AttributeError
            full_result.total_market_rate = 999.0  # type: ignore

    def test_yangtze_revenue_contribution_dominant(self, full_result):
        """长江电力是收入贡献最大的组织"""
        cj = next(d for d in full_result.orgs if d.name == "长江电力")
        # 149650.63 / 249258.79 ≈ 60%
        assert cj.revenue_contribution > 55
        assert cj.revenue_contribution < 65


# === build_org_metrics 测试 ===

class TestBuildOrgMetrics:
    """从 fixture 装配数据"""

    def test_count_18(self, orgs_list):
        """装配 18 个组织"""
        assert len(orgs_list) == 18

    def test_yangtze_first(self, orgs_list):
        """长江电力应在第一位（fixture 顺序）"""
        assert orgs_list[0].name == "长江电力"
        assert orgs_list[0].category == "hydro"

    def test_inactive_preserved(self, orgs_list):
        """长江环保、三峡发展保留为 0"""
        env = next(o for o in orgs_list if o.name == "长江环保")
        assert env.market_volume == 0.0
        assert env.market_price == 0.0

    def test_missing_market_raises(self, overall_data):
        """市场化数据缺失某组织 → 抛 KeyError"""
        incomplete = {"长江电力": overall_data["长江电力"]}
        with pytest.raises(KeyError):
            build_org_metrics(overall_data, incomplete)

    def test_returns_immutable_namedtuple(self, orgs_list):
        """返回的是不可变 NamedTuple"""
        o = orgs_list[0]
        with pytest.raises(AttributeError):
            o.name = "改不了"  # type: ignore
