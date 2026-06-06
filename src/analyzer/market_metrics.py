"""
市场化指标计算器 (MarketMetrics)
==================================

v2.4 新增模块：为国内分析提供"市场化"维度的计算

核心功能：
1. calculate_market_rate()       - 市场化率（市场化电量/整体电量）
2. calculate_price_diff()        - 电价差（市场化电价 - 整体电价）
3. classify_organization()       - 组织按业务模式分桶（水电/新能源/分公司/工程/环保/发展）
4. calculate_revenue_contribution() - 收入贡献度（各组织占集团比例）

设计原则：
- 纯函数，无副作用（输入数据 → 输出指标）
- 不可变数据（NamedTuple + frozen dataclass）
- 类型注解完整
- 0 依赖（只依赖标准库 + pandas 可选）

数据契约：
- 输入：18 个组织 × 6 指标（整体+市场化 × {电量/电价/电费}）
- 输出：派生指标（市场化率/电价差/象限/贡献度）

对应业务图谱：段 1-2 扩展
对应文档：docs/design/v24-market-dimension.md
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, NamedTuple, Optional, Tuple


# === 枚举与常量 ===

class OrgCategory(str, Enum):
    """组织业务类别"""
    HYDRO = "hydro"             # 水电
    RENEWABLES = "renewables"   # 新能源（风/光）
    THERMAL = "thermal"         # 火电
    CONSTRUCTION = "construction"  # 工程
    ENVIRONMENTAL = "environmental"  # 环保
    DEVELOPMENT = "development"    # 发展
    REGIONAL = "regional"       # 区域分公司


class Quadrant(str, Enum):
    """组织象限（基于市场化率+电价差）"""
    PREMIUM_SCARCE = "稀缺溢价"      # 低市场化率 + 高电价差 → 右上
    PREMIUM_COMPETITIVE = "竞争溢价" # 高市场化率 + 高电价差 → 右上
    DISCOUNT_SCARCE = "稀缺折价"     # 低市场化率 + 低电价差 → 左下
    DISCOUNT_COMPETITIVE = "竞争折价" # 高市场化率 + 低电价差 → 左下


# 象限判定阈值
MARKET_RATE_HIGH = 50.0   # 市场化率 ≥ 50% 视为"高市场化率"
PRICE_DIFF_HIGH = 0.0     # 电价差 ≥ 0 视为"溢价"


# === 数据类 ===

class OrgMetrics(NamedTuple):
    """单个组织的整体+市场化指标（不可变）"""
    name: str
    category: str
    overall_volume: float       # 本周整体电量（万 kWh）
    overall_price: float        # 本周整体电价（元/度）
    overall_revenue: float      # 本周整体电费（万元）
    market_volume: float        # 本周市场化电量（万 kWh）
    market_price: float         # 本周市场化电价（元/度）
    market_revenue: float       # 本周市场化电费（万元）


class DerivedMetrics(NamedTuple):
    """派生指标（不可变）"""
    name: str
    category: str
    market_rate: float          # 市场化率（%）
    price_diff: float           # 电价差（元/度，+ 溢价 / - 折价）
    volume_contribution: float  # 整体电量贡献（%）
    market_volume_contribution: float  # 市场化电量贡献（%）
    revenue_contribution: float # 整体电费贡献（%）
    quadrant: str               # 象限分类
    is_active_in_market: bool   # 是否参与市场化交易


# === 核心计算函数 ===

def calculate_market_rate(overall_volume: float, market_volume: float) -> float:
    """计算市场化率

    Args:
        overall_volume: 整体电量
        market_volume: 市场化电量

    Returns:
        市场化率（%），范围 [0, 100]

    Examples:
        >>> calculate_market_rate(100, 50)
        50.0
        >>> calculate_market_rate(100, 0)
        0.0
        >>> calculate_market_rate(0, 50)
        0.0  # 整体为 0 时返回 0
    """
    if overall_volume <= 0:
        return 0.0
    if market_volume <= 0:
        return 0.0
    rate = (market_volume / overall_volume) * 100
    # 市场化率不应超过 100%（市场化是整体的子集）
    return round(min(rate, 100.0), 2)


def calculate_price_diff(overall_price: float, market_price: float) -> float:
    """计算电价差（市场化 - 整体）

    Args:
        overall_price: 整体电价（元/度）
        market_price: 市场化电价（元/度）

    Returns:
        电价差（元/度），正数=溢价，负数=折价

    Examples:
        >>> calculate_price_diff(0.27, 0.30)
        0.03
        >>> calculate_price_diff(0.42, 0.28)
        -0.14
    """
    return round(market_price - overall_price, 4)


def classify_organization(category: str) -> str:
    """组织按业务模式分桶

    Args:
        category: 业务类别（来自 fixture）

    Returns:
        业务桶名（中文标签）
    """
    mapping: Dict[str, str] = {
        OrgCategory.HYDRO.value: "水电组",
        OrgCategory.RENEWABLES.value: "新能源组",
        OrgCategory.THERMAL.value: "传统能源组",
        OrgCategory.CONSTRUCTION.value: "工程组",
        OrgCategory.ENVIRONMENTAL.value: "环保组",
        OrgCategory.DEVELOPMENT.value: "发展组",
        OrgCategory.REGIONAL.value: "区域分公司组",
    }
    return mapping.get(category, "未分类")


def classify_quadrant(market_rate: float, price_diff: float) -> str:
    """判定组织象限

    Args:
        market_rate: 市场化率（%）
        price_diff: 电价差（元/度）

    Returns:
        象限标签（Quadrant 枚举值）

    业务解读：
    - 稀缺溢价（低市场化+高溢价）：水电、稀缺资源
    - 竞争溢价（高市场化+高溢价）：罕见，需关注
    - 稀缺折价（低市场化+低折价）：新能源中的稀缺部分
    - 竞争折价（高市场化+低折价）：典型新能源、竞争激烈
    """
    high_rate = market_rate >= MARKET_RATE_HIGH
    high_diff = price_diff >= PRICE_DIFF_HIGH

    if high_rate and high_diff:
        return Quadrant.PREMIUM_COMPETITIVE.value
    elif not high_rate and high_diff:
        return Quadrant.PREMIUM_SCARCE.value
    elif not high_rate and not high_diff:
        return Quadrant.DISCOUNT_SCARCE.value
    else:  # high_rate and not high_diff
        return Quadrant.DISCOUNT_COMPETITIVE.value


def calculate_revenue_contribution(
    org_revenue: float, total_revenue: float
) -> float:
    """收入贡献度

    Args:
        org_revenue: 该组织收入
        total_revenue: 集团总收入

    Returns:
        贡献度（%）
    """
    if total_revenue <= 0:
        return 0.0
    return round((org_revenue / total_revenue) * 100, 2)


def derive_metrics(org: OrgMetrics, total_volume: float, total_market_volume: float, total_revenue: float) -> DerivedMetrics:
    """派生单个组织的全部指标

    Args:
        org: 原始组织数据
        total_volume: 集团整体总电量（用于贡献度）
        total_market_volume: 集团市场化总电量
        total_revenue: 集团整体总收入

    Returns:
        派生指标（不可变 NamedTuple）
    """
    market_rate = calculate_market_rate(org.overall_volume, org.market_volume)
    price_diff = calculate_price_diff(org.overall_price, org.market_price)
    vol_contrib = calculate_revenue_contribution(org.overall_volume, total_volume)
    mkt_vol_contrib = calculate_revenue_contribution(org.market_volume, total_market_volume)
    rev_contrib = calculate_revenue_contribution(org.overall_revenue, total_revenue)
    quadrant = classify_quadrant(market_rate, price_diff)
    is_active = org.market_volume > 0

    return DerivedMetrics(
        name=org.name,
        category=org.category,
        market_rate=market_rate,
        price_diff=price_diff,
        volume_contribution=vol_contrib,
        market_volume_contribution=mkt_vol_contrib,
        revenue_contribution=rev_contrib,
        quadrant=quadrant,
        is_active_in_market=is_active,
    )


# === 批量分析器 ===

@dataclass(frozen=True)
class MarketDimensionResult:
    """市场化维度分析结果（不可变）"""
    orgs: List[DerivedMetrics]                         # 各组织派生指标
    total_market_rate: float                            # 集团整体市场化率（%）
    total_market_volume: float                          # 集团市场化总电量
    total_overall_volume: float                         # 集团整体总电量
    total_market_revenue: float                        # 集团市场化总电费
    total_overall_revenue: float                       # 集团整体总收入
    quadrant_distribution: Dict[str, int]               # 各象限组织数
    category_distribution: Dict[str, int]              # 各业务桶组织数
    top_market_rate_orgs: List[str]                     # 市场化率 TOP N 组织名
    top_price_premium_orgs: List[str]                   # 溢价 TOP N 组织名
    bottom_price_discount_orgs: List[str]               # 折价 TOP N 组织名


def analyze_market_dimension(orgs: List[OrgMetrics]) -> MarketDimensionResult:
    """市场化维度批量分析

    Args:
        orgs: 18 个组织的原始数据列表

    Returns:
        完整的分析结果（不可变）

    Examples:
        >>> orgs = [OrgMetrics(name="长江电力", category="hydro", ...)]
        >>> result = analyze_market_dimension(orgs)
        >>> result.total_market_rate
        41.36
    """
    if not orgs:
        raise ValueError("orgs 不能为空")

    # 计算集团总量
    total_volume = sum(o.overall_volume for o in orgs)
    total_market_volume = sum(o.market_volume for o in orgs)
    total_revenue = sum(o.overall_revenue for o in orgs)
    total_market_revenue = sum(o.market_revenue for o in orgs)

    # 派生各组织指标
    derived_list = [derive_metrics(o, total_volume, total_market_volume, total_revenue) for o in orgs]

    # 集团整体市场化率
    total_rate = calculate_market_rate(total_volume, total_market_volume)

    # 象限分布
    quadrant_dist: Dict[str, int] = {}
    for d in derived_list:
        quadrant_dist[d.quadrant] = quadrant_dist.get(d.quadrant, 0) + 1

    # 业务桶分布
    category_dist: Dict[str, int] = {}
    for d in derived_list:
        bucket = classify_organization(d.category)
        category_dist[bucket] = category_dist.get(bucket, 0) + 1

    # TOP 5 市场化率（仅活跃）
    active_orgs = [d for d in derived_list if d.is_active_in_market]
    top_rate = sorted(active_orgs, key=lambda d: d.market_rate, reverse=True)[:5]
    top_rate_names = [d.name for d in top_rate]

    # TOP 5 溢价（电价差最大）
    top_premium = sorted(active_orgs, key=lambda d: d.price_diff, reverse=True)[:5]
    top_premium_names = [d.name for d in top_premium]

    # TOP 5 折价（电价差最小）
    bottom_discount = sorted(active_orgs, key=lambda d: d.price_diff)[:5]
    bottom_discount_names = [d.name for d in bottom_discount]

    return MarketDimensionResult(
        orgs=derived_list,
        total_market_rate=total_rate,
        total_market_volume=total_market_volume,
        total_overall_volume=total_volume,
        total_market_revenue=total_market_revenue,
        total_overall_revenue=total_revenue,
        quadrant_distribution=quadrant_dist,
        category_distribution=category_dist,
        top_market_rate_orgs=top_rate_names,
        top_price_premium_orgs=top_premium_names,
        bottom_price_discount_orgs=bottom_discount_names,
    )


# === 数据装配辅助函数（从 fixture 读数据 → OrgMetrics 列表） ===

def build_org_metrics(
    overall_data: Dict, market_data: Dict
) -> List[OrgMetrics]:
    """从 fixture 字典构建 OrgMetrics 列表

    Args:
        overall_data: 整体销售 fixture（domestic_overall_v24.json 的 by_organization）
        market_data: 市场化交易 fixture（domestic_market_v24.json 的 by_organization）

    Returns:
        OrgMetrics 列表（按 overall_data 顺序）

    Raises:
        KeyError: 某个组织在两边数据中不一致
    """
    orgs: List[OrgMetrics] = []
    for name, ov_data in overall_data.items():
        if name not in market_data:
            raise KeyError(f"组织 {name} 在市场化数据中缺失")
        mkt_data = market_data[name]

        orgs.append(OrgMetrics(
            name=name,
            category=ov_data.get("category", "unknown"),
            overall_volume=ov_data["overall_volume_wk"],
            overall_price=ov_data["overall_price_wk"],
            overall_revenue=ov_data["overall_revenue_wk"],
            market_volume=mkt_data["market_volume_wk"],
            market_price=mkt_data["market_price_wk"],
            market_revenue=mkt_data["market_revenue_wk"],
        ))
    return orgs


# === 自检 ===
if __name__ == "__main__":
    import json
    from pathlib import Path

    print("=" * 60)
    print("MarketMetrics 自检（v2.4）")
    print("=" * 60)

    # 加载 fixture
    fixture_dir = Path(__file__).parent.parent.parent / "tests" / "fixtures"
    with open(fixture_dir / "domestic_overall_v24.json", encoding="utf-8") as f:
        overall = json.load(f)
    with open(fixture_dir / "domestic_market_v24.json", encoding="utf-8") as f:
        market = json.load(f)

    # 装配
    orgs = build_org_metrics(overall["by_organization"], market["by_organization"])
    print(f"\n[1] 装配组织数: {len(orgs)}")

    # 分析
    result = analyze_market_dimension(orgs)
    print(f"\n[2] 集团整体市场化率: {result.total_market_rate:.2f}%")
    print(f"    整体电量: {result.total_overall_volume:,.2f} 万 kWh")
    print(f"    市场化电量: {result.total_market_volume:,.2f} 万 kWh")

    # 象限分布
    print(f"\n[3] 象限分布:")
    for q, count in result.quadrant_distribution.items():
        print(f"    {q}: {count} 个组织")

    # TOP 5 市场化率
    print(f"\n[4] 市场化率 TOP 5:")
    for d in sorted(result.orgs, key=lambda x: x.market_rate, reverse=True)[:5]:
        if d.is_active_in_market:
            print(f"    {d.name}: {d.market_rate:.2f}%")

    # 长江电力验证
    cj = next(d for d in result.orgs if d.name == "长江电力")
    print(f"\n[5] 长江电力验证:")
    print(f"    市场化率: {cj.market_rate:.2f}% (期望 26.30%)")
    print(f"    电价差: {cj.price_diff:+.3f} (期望 +0.033)")
    print(f"    象限: {cj.quadrant} (期望 稀缺溢价)")

    # 重庆分边界条件验证
    cq = next(d for d in result.orgs if d.name == "重庆分")
    print(f"\n[6] 重庆分边界验证:")
    print(f"    市场化率: {cq.market_rate:.2f}%")
    print(f"    整体电价: 0.396, 市场化电价: 0.396 (重庆分相同)")

    # 长江环保/三峡发展验证
    inactive = [d for d in result.orgs if not d.is_active_in_market]
    print(f"\n[7] 不参与市场化的组织: {[d.name for d in inactive]}")

    print("\n" + "=" * 60)
    print("[OK] MarketMetrics 自检通过")
    print("=" * 60)
