"""
市场化维度组件 (market_view)
==============================

v2.4 新增组件：3 个 Streamlit 复用组件
- render_market_rate_ranking: 18 组织市场化率排行（柱状图）
- render_price_diff_scatter: 市场化率 vs 电价差 散点象限图
- render_org_quadrant_distribution: 4 象限分布（旭日/桑基图）
- render_market_summary_cards: 4 关键 KPI 卡片

设计原则：
- 纯组件，接收数据 → 渲染图表，不做计算
- 依赖 plotly 实现交互
- 支持 dark/light 主题自适应
"""

from typing import Dict, List, Optional

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from src.analyzer.market_metrics import DerivedMetrics, MarketDimensionResult


# === 1. KPI 卡片 ===

def render_market_summary_cards(
    market_dim: MarketDimensionResult,
    overall_revenue: float = None,
) -> None:
    """渲染 4 个关键 KPI 卡片

    Args:
        market_dim: 市场化维度分析结果
        overall_revenue: 集团整体收入（万元），用于算市场化收入占比
    """
    cols = st.columns(4)

    # 1. 集团市场化率
    with cols[0]:
        st.metric(
            label="🏷️ 集团市场化率",
            value=f"{market_dim.total_market_rate:.2f}%",
            help="市场化电量 / 整体电量，衡量市场化交易占比",
        )

    # 2. 市场化电量
    with cols[1]:
        volume_yi = market_dim.total_market_volume / 10000  # 万 → 亿
        st.metric(
            label="⚡ 市场化电量",
            value=f"{volume_yi:.2f} 亿度",
            help="本周 18 组织市场化交易电量总和",
        )

    # 3. 市场化电费
    with cols[2]:
        revenue_yi = market_dim.total_market_revenue / 10000
        st.metric(
            label="💰 市场化电费",
            value=f"{revenue_yi:.2f} 亿元",
            help="本周 18 组织市场化交易电费总和",
        )

    # 4. 市场化收入占比
    with cols[3]:
        if overall_revenue and overall_revenue > 0:
            ratio = (market_dim.total_market_revenue / overall_revenue) * 100
            st.metric(
                label="📊 收入占比",
                value=f"{ratio:.2f}%",
                help="市场化电费 / 集团整体电费",
            )
        else:
            st.metric(label="📊 收入占比", value="—")


# === 2. 市场化率排行柱状图 ===

def render_market_rate_ranking(
    market_dim: MarketDimensionResult,
    top_n: int = 18,
    height: int = 500,
) -> None:
    """市场化率排行柱状图

    Args:
        market_dim: 市场化维度分析结果
        top_n: 显示前 N 名（默认 18 = 全部）
        height: 图表高度
    """
    # 排序：活跃组织按市场化率降序，不活跃放最后
    active = sorted(
        [d for d in market_dim.orgs if d.is_active_in_market],
        key=lambda d: d.market_rate, reverse=True,
    )[:top_n]
    inactive = [d for d in market_dim.orgs if not d.is_active_in_market]

    rows = []
    for d in active:
        rows.append({
            "组织": d.name,
            "市场化率(%)": d.market_rate,
            "象限": d.quadrant,
            "活跃": True,
        })
    for d in inactive:
        rows.append({
            "组织": d.name,
            "市场化率(%)": 0,
            "象限": "不参与",
            "活跃": False,
        })

    if not rows:
        st.info("无市场化数据")
        return

    # 用 Plotly 画水平柱状图
    categories = [r["组织"] for r in rows]
    values = [r["市场化率(%)"] for r in rows]
    colors = ["#1f77b4" if r["活跃"] else "#cccccc" for r in rows]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=categories[::-1],  # 反转让最高的在顶部
        x=values[::-1],
        orientation="h",
        marker=dict(color=colors[::-1]),
        text=[f"{v:.1f}%" for v in values[::-1]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>市场化率: %{x:.2f}%<extra></extra>",
    ))

    fig.update_layout(
        title=f"各组织市场化率排行（v2.4）— TOP {min(top_n, len(rows))}",
        xaxis_title="市场化率（%）",
        yaxis_title="组织",
        height=height,
        margin=dict(l=120, r=40, t=60, b=40),
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)


# === 3. 电价差散点象限图 ===

def render_price_diff_scatter(
    market_dim: MarketDimensionResult,
    height: int = 600,
) -> None:
    """市场化率 vs 电价差 散点象限图

    X 轴：市场化率（%）
    Y 轴：电价差（元/度，+ 溢价 / - 折价）
    气泡大小：本周整体电量（万 kWh）
    颜色：象限

    4 象限解读：
    - 稀缺溢价（右上）：低市场化 + 溢价，水电稀缺资源
    - 竞争溢价（右下少见）：高市场化 + 溢价
    - 稀缺折价（左上）：低市场化 + 折价
    - 竞争折价（左下）：高市场化 + 折价，典型新能源
    """
    rows = []
    for d in market_dim.orgs:
        # 用本周整体电量算气泡大小（开方后归一化）
        size = max(d.revenue_contribution, 0.5) * 8  # 按收入贡献算气泡
        rows.append({
            "组织": d.name,
            "市场化率": d.market_rate,
            "电价差": d.price_diff,
            "象限": d.quadrant if d.is_active_in_market else "不参与",
            "收入贡献(%)": d.revenue_contribution,
            "气泡大小": size,
            "活跃": d.is_active_in_market,
        })

    if not rows:
        st.info("无市场化数据")
        return

    # 4 象限背景色
    quadrant_colors = {
        "稀缺溢价": "#2ecc71",      # 绿
        "竞争溢价": "#3498db",      # 蓝
        "稀缺折价": "#f39c12",      # 橙
        "竞争折价": "#e74c3c",      # 红
        "不参与": "#95a5a6",        # 灰
    }

    fig = go.Figure()

    # 按象限分组绘制（避免图例混乱）
    quadrants = sorted(set(r["象限"] for r in rows))
    for q in quadrants:
        q_rows = [r for r in rows if r["象限"] == q]
        fig.add_trace(go.Scatter(
            x=[r["市场化率"] for r in q_rows],
            y=[r["电价差"] for r in q_rows],
            mode="markers+text",
            marker=dict(
                size=[r["气泡大小"] for r in q_rows],
                color=quadrant_colors.get(q, "#999"),
                line=dict(width=1, color="white"),
                opacity=0.85,
            ),
            text=[r["组织"] for r in q_rows],
            textposition="top center",
            name=f"{q}（{len(q_rows)} 个）",
            hovertemplate=(
                "<b>%{text}</b><br>"
                "市场化率: %{x:.2f}%<br>"
                "电价差: %{y:+.4f} 元/度<br>"
                "<extra></extra>"
            ),
        ))

    # 添加象限分隔线
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig.add_vline(x=50, line_dash="dash", line_color="gray", opacity=0.5)

    # 添加象限标签
    fig.add_annotation(x=25, y=0.1, text="稀缺溢价", showarrow=False,
                       font=dict(size=12, color="gray"), opacity=0.6)
    fig.add_annotation(x=75, y=0.1, text="竞争溢价", showarrow=False,
                       font=dict(size=12, color="gray"), opacity=0.6)
    fig.add_annotation(x=25, y=-0.15, text="稀缺折价", showarrow=False,
                       font=dict(size=12, color="gray"), opacity=0.6)
    fig.add_annotation(x=75, y=-0.15, text="竞争折价", showarrow=False,
                       font=dict(size=12, color="gray"), opacity=0.6)

    fig.update_layout(
        title="市场化率 vs 电价差 象限分布（v2.4）<br>"
              "<sub>气泡大小 = 收入贡献 | 虚线 = 象限边界（50% 市场化率, 0 元/度电价差）</sub>",
        xaxis_title="市场化率（%）",
        yaxis_title="电价差（市场化 - 整体，元/度）",
        height=height,
        margin=dict(l=40, r=40, t=80, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
    )

    st.plotly_chart(fig, use_container_width=True)


# === 4. 象限分布柱状图 ===

def render_org_quadrant_distribution(
    market_dim: MarketDimensionResult,
    height: int = 400,
) -> None:
    """4 象限组织数分布

    Args:
        market_dim: 市场化维度分析结果
        height: 图表高度
    """
    quadrant_order = ["稀缺溢价", "竞争溢价", "稀缺折价", "竞争折价"]
    counts = [market_dim.quadrant_distribution.get(q, 0) for q in quadrant_order]
    colors = ["#2ecc71", "#3498db", "#f39c12", "#e74c3c"]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=quadrant_order,
        y=counts,
        marker=dict(color=colors),
        text=counts,
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>组织数: %{y}<extra></extra>",
    ))

    fig.update_layout(
        title="组织象限分布（v2.4）",
        xaxis_title="象限",
        yaxis_title="组织数",
        height=height,
        showlegend=False,
        margin=dict(l=40, r=40, t=60, b=40),
    )

    st.plotly_chart(fig, use_container_width=True)


# === 5. 整体 vs 市场化 电价对比柱状图 ===

def render_overall_vs_market_price(
    market_dim: MarketDimensionResult,
    height: int = 500,
) -> None:
    """各组织整体电价 vs 市场化电价 对比柱状图

    Args:
        market_dim: 市场化维度分析结果
        height: 图表高度
    """
    active = [d for d in market_dim.orgs if d.is_active_in_market]
    # 按整体电价降序
    active.sort(key=lambda d: d.price_diff, reverse=True)

    rows = []
    for d in active:
        # 从 DerivedMetrics 还原原始价格
        # 实际价格 = price_diff + overall_price_wk（但 DerivedMetrics 没保留 overall_price）
        # 因此我们用 price_diff 排序 + 名称，调用方需传 overall_price 数据
        rows.append({"name": d.name, "diff": d.price_diff})

    # 此组件需配合外部数据使用（不在这里实现整体价格）
    # 仅作为占位
    st.info("请使用 render_dual_comparison 组件进行整体 vs 市场化对比")


# === 6. 业务桶分布饼图 ===

def render_category_bucket_pie(
    market_dim: MarketDimensionResult,
    height: int = 400,
) -> None:
    """按业务桶（7 类）分组的组织数饼图"""
    labels = list(market_dim.category_distribution.keys())
    values = list(market_dim.category_distribution.values())

    fig = go.Figure()
    fig.add_trace(go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        textinfo="label+value",
        hovertemplate="<b>%{label}</b><br>组织数: %{value}<br>占比: %{percent}<extra></extra>",
    ))

    fig.update_layout(
        title="业务桶组织分布（v2.4）",
        height=height,
        margin=dict(l=40, r=40, t=60, b=40),
    )

    st.plotly_chart(fig, use_container_width=True)
