"""
按公司拆分视图组件（v2.3 新增）
================================

专门用于"按公司"展示分析结果——同一集团下不同子公司的横向对比。

复用对比视图风格 + Plotly 图表，支持 2 个上下文：
- 国内（4 家公司：长江电力/三峡建工/湖北能源/三峡发展）
- 国际（3 家公司：三峡国际/长江电力/湖北能源）

使用方式:
    from streamlit_app.components import render_by_company
    render_by_company(companies, context="国内", title="国内各单位水电")
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# === 颜色配置 ===
COLOR_PRIMARY = "#1f77b4"        # 蓝色 - 主公司（长江电力/三峡国际）
COLOR_WARN = "#ff7f0e"            # 橙色 - 异常/暴涨
COLOR_GROWTH = "#2ca02c"          # 绿色 - 增长
COLOR_DROP = "#d62728"            # 红色 - 下降
COLOR_NEUTRAL = "#7f7f7f"         # 灰色 - 中性


def render_by_company(
    companies: list[dict[str, Any]],
    context: str = "国内",
    title: str | None = None,
) -> None:
    """渲染按公司拆分视图

    Args:
        companies: 公司列表，每家包含：
            - name: 公司名
            - volume: 电量（亿度）
            - share_pct: 占比（%）
            - price: 度电均价（元/度）
            - yoy_volume_pct: 同比电量（%）
            - yoy_price_fen: 同比度电（分）
            - yoy_revenue_pct: 同比收入（%）
            - anomaly: 异常标记（可选）
        context: "国内" 或 "国际"
        title: 标题（可选）
    """
    if not companies:
        st.error("❌ 无公司数据")
        return

    # === 1. 顶部标题 ===
    if title:
        st.markdown(f"### {title}")

    n = len(companies)
    st.caption(
        f"📊 共 **{n}** 家单位"
        + (" | 按国内业务（含水电 + 风光）" if context == "国内" else " | 按国际业务")
    )

    # === 2. KPI 网格（公司卡片） ===
    _render_company_kpi_grid(companies, context)

    st.markdown("---")

    # === 3. 同比对比表 ===
    _render_yoy_comparison_table(companies, context)

    st.markdown("---")

    # === 4. 图表区：价格柱状图 + 占比饼图 ===
    cols = st.columns(2)
    with cols[0]:
        _render_price_bar_chart(companies, context)
    with cols[1]:
        _render_share_pie_chart(companies, context)

    st.markdown("---")

    # === 5. 同比收入柱状图 ===
    _render_yoy_revenue_chart(companies, context)

    st.markdown("---")

    # === 6. 5 大核心洞察（自动从数据推断） ===
    insights = _generate_company_insights(companies, context)
    if insights:
        st.markdown("### 💎 核心洞察（按公司）")
        for ins in insights:
            st.markdown(ins)


def _render_company_kpi_grid(companies: list[dict], context: str) -> None:
    """公司卡片网格：每家一卡，含电量/占比/价格/同比"""
    st.markdown("### 🏢 各单位 KPI 概览")

    cols = st.columns(len(companies))
    for i, c in enumerate(companies):
        with cols[i]:
            name = c.get("name", "未知")
            vol = c.get("volume", 0)
            share = c.get("share_pct", 0)
            price = c.get("price", 0)
            yoy_vol = c.get("yoy_volume_pct", 0)
            anomaly = c.get("anomaly")

            # 卡片颜色
            if anomaly == "暴增":
                icon = "🚀"
            elif anomaly == "异常":
                icon = "⚠️"
            elif share > 80:
                icon = "👑"
            else:
                icon = "🏢"

            st.metric(
                label=f"{icon} {name}",
                value=f"{vol:.2f} 亿度",
                delta=f"占比 {share:.1f}%" + (f" | 同比 {yoy_vol:+.1f}%" if yoy_vol else ""),
            )
            st.caption(f"度电均价: **{price:.3f}** 元/度")


def _render_yoy_comparison_table(companies: list[dict], context: str) -> None:
    """同比对比表"""
    st.markdown("### 📋 同比对比明细表")

    rows = []
    for c in companies:
        rows.append([
            c.get("name", ""),
            f"{c.get('volume', 0):.2f}",
            f"{c.get('share_pct', 0):.1f}%",
            f"{c.get('price', 0):.3f}",
            f"{c.get('yoy_volume_pct', 0):+.1f}%" if c.get('yoy_volume_pct') is not None else "—",
            f"{c.get('yoy_price_fen', 0):+.1f}" if c.get('yoy_price_fen') is not None else "—",
            f"{c.get('yoy_revenue_pct', 0):+.1f}%" if c.get('yoy_revenue_pct') is not None else "—",
        ])

    df = pd.DataFrame(rows, columns=[
        "公司", "电量(亿度)", "占比(%)", "度电(元/度)",
        "同比电量(%)", "同比度电(分)", "同比收入(%)"
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_price_bar_chart(companies: list[dict], context: str) -> None:
    """度电均价柱状图"""
    st.markdown("#### 💰 度电均价对比")

    names = [c.get("name", "") for c in companies]
    prices = [c.get("price", 0) for c in companies]

    # 颜色规则：最高 = 橙色，其余蓝色
    max_price = max(prices) if prices else 0
    colors = [COLOR_WARN if p == max_price else COLOR_PRIMARY for p in prices]

    fig = go.Figure(data=[go.Bar(
        x=names,
        y=prices,
        marker_color=colors,
        text=[f"{p:.3f}" for p in prices],
        textposition="auto",
    )])

    fig.update_layout(
        yaxis_title="元/度",
        height=350,
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, key=f"price_{context}")


def _render_share_pie_chart(companies: list[dict], context: str) -> None:
    """电量占比饼图"""
    st.markdown("#### 🥧 电量占比分布")

    names = [c.get("name", "") for c in companies]
    shares = [c.get("share_pct", 0) for c in companies]

    # 颜色：最大占比用蓝色突出
    max_idx = shares.index(max(shares)) if shares else 0
    colors = [COLOR_PRIMARY if i == max_idx else COLOR_NEUTRAL for i in range(len(names))]

    fig = go.Figure(data=[go.Pie(
        labels=names,
        values=shares,
        hole=0.3,
        marker=dict(colors=colors),
        textinfo="label+percent",
    )])
    fig.update_layout(
        height=350,
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=True,
    )
    st.plotly_chart(fig, use_container_width=True, key=f"share_{context}")


def _render_yoy_revenue_chart(companies: list[dict], context: str) -> None:
    """同比收入柱状图（带正负色）"""
    st.markdown("### 📈 同比收入对比")

    names = [c.get("name", "") for c in companies]
    yoy_rev = [c.get("yoy_revenue_pct", 0) or 0 for c in companies]

    # 正负色：涨 = 绿，跌 = 红
    colors = [COLOR_GROWTH if r > 0 else COLOR_DROP for r in yoy_rev]

    fig = go.Figure(data=[go.Bar(
        x=names,
        y=yoy_rev,
        marker_color=colors,
        text=[f"{r:+.1f}%" for r in yoy_rev],
        textposition="auto",
    )])

    fig.update_layout(
        yaxis_title="同比收入(%)",
        height=350,
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, key=f"yoy_rev_{context}")


def _generate_company_insights(companies: list[dict], context: str) -> list[str]:
    """根据实际数据动态生成洞察"""
    insights = []

    if not companies:
        return insights

    # 找到最大占比公司
    max_share_co = max(companies, key=lambda c: c.get("share_pct", 0))
    max_share_pct = max_share_co.get("share_pct", 0)
    max_share_name = max_share_co.get("name", "")

    # 找到最高度电公司
    max_price_co = max(companies, key=lambda c: c.get("price", 0))
    max_price = max_price_co.get("price", 0)
    max_price_name = max_price_co.get("name", "")

    # 找到最低度电公司
    min_price_co = min(companies, key=lambda c: c.get("price", 0))
    min_price = min_price_co.get("price", 0)
    min_price_name = min_price_co.get("name", "")

    # 找到最高同比公司
    growth_cos = [c for c in companies if c.get("yoy_volume_pct") is not None]
    if growth_cos:
        max_growth = max(growth_cos, key=lambda c: c.get("yoy_volume_pct", 0))
        max_growth_pct = max_growth.get("yoy_volume_pct", 0)
        max_growth_name = max_growth.get("name", "")

    # 洞察 1: 主公司统治
    if max_share_pct > 80:
        insights.append(f"""
👑 **洞察 1：{max_share_name} 统治级地位**
- 占比 **{max_share_pct:.1f}%**（> 80% 绝对主导）
- 解读：集团{context}业务**严重依赖单家公司**——风险集中度高
- 行动建议：关注其他公司的"非水电"业务（风电/光伏）布局
""")

    # 洞察 2: 价差悬殊
    if max_price > 0 and min_price > 0:
        price_diff = (max_price - min_price) * 100
        if price_diff > 10:
            insights.append(f"""
💰 **洞察 2：度电价差悬殊**
- 最高：{max_price_name} = **{max_price:.3f}** 元/度
- 最低：{min_price_name} = **{min_price:.3f}** 元/度
- 价差：**{price_diff:.1f} 分**（{price_diff/10:.1f} 倍）
- 解读：{max_price_name} 走"高溢价"路线（{context}结构特殊性）
""")

    # 洞察 3: 异常公司（暴增）
    for c in companies:
        yoy = c.get("yoy_volume_pct") or 0
        anomaly = c.get("anomaly")
        if anomaly == "暴增" or yoy > 50:
            insights.append(f"""
🚀 **洞察 3：{c.get('name')} 暴增警告**
- 同比 **{yoy:+.1f}%**（异常高位）
- 解读：可能存在**新机组投产 / 收购并表 / 一次性事件**
- 行动建议：核实是否可持续（避免高基数效应）
""")
            break

    # 洞察 4: 异常公司（异常单价）
    for c in companies:
        anomaly = c.get("anomaly")
        if anomaly == "异常" or anomaly == "单价异常":
            insights.append(f"""
⚠️ **洞察 4：{c.get('name')} 异常标记**
- 度电 {c.get('price', 0):.3f} 元/度（占比 {c.get('share_pct', 0):.2f}%）
- 解读：单价显著偏离均值 → **样本量小或临时合同**导致的统计噪声
- 行动建议：与公司财务核对是否漏报/错报
""")
            break

    # 洞察 5: 同比分化
    if growth_cos and len(growth_cos) >= 2:
        yoy_values = [c.get("yoy_volume_pct", 0) for c in growth_cos]
        min_growth = min(growth_cos, key=lambda c: c.get("yoy_volume_pct", 0))
        max_yoy = max(yoy_values)
        min_yoy = min(yoy_values)
        if max_yoy - min_yoy > 30:
            insights.append(f"""
📊 **洞察 5：同比剧烈分化**
- 最高：{max_growth_name} = {max_growth_pct:+.1f}%
- 最低：{min_growth.get('name', '')} = {min_yoy:+.1f}%
- 分化幅度：**{max_yoy - min_yoy:.1f} pp**
- 解读：{context}业务呈现"**赢家通吃**"模式——强者愈强
""")

    return insights
