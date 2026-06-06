"""
双口径对比视图组件
========================

专门用于对比"全口径 vs 市场化"等"双口径"数据。
复用 analyzer_panel 的渲染风格 + Plotly 图表。

使用方式:
    from streamlit_app.components import render_dual_comparison
    render_dual_comparison(full_result, market_result, full_label="全口径", market_label="市场化")
"""

import json
from pathlib import Path
from typing import Any

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# === 颜色配置（视觉一致） ===
COLOR_FULL = "#1f77b4"        # 蓝色 - 全口径
COLOR_MARKET = "#ff7f0e"       # 橙色 - 市场化
COLOR_DIFF = "#2ca02c"          # 绿色 - 差异
COLOR_WARN = "#d62728"          # 红色 - 警告


# === KPI 字段映射（支持国内/国际） ===

DOMESTIC_KPI_MAP = {
    "总电量": "国内上网电量",
    "度电均价": "国内度电均价",
    "总电费": "国内发电收入",
    "同比电量": "同比电量",
    "同比度电": "同比度电",
    "同比收入": "同比收入",
    "环比电量": "环比电量",
    "环比度电": "环比度电",
    "总电量单位": "亿度",
    "度电单位": "元/度",
    "电费单位": "亿元",
}

INTERNATIONAL_KPI_MAP = {
    "总电量": "国际上网电量",
    "度电均价": "国际度电均价",
    "总电费": "国际发电收入",
    "同比电量": "国际同比电量",
    "同比度电": "国际同比度电",
    "同比收入": "国际同比收入",
    "环比电量": "国际环比电量",
    "环比度电": "国际环比度电",
    "总电量单位": "亿度",
    "度电单位": "元/度",
    "电费单位": "亿元",
}

KPI_MAPS = {
    "国内": DOMESTIC_KPI_MAP,
    "国际": INTERNATIONAL_KPI_MAP,
}


def render_dual_comparison(
    full_result: Any,
    market_result: Any,
    full_label: str = "🏠 全口径",
    market_label: str = "💹 市场化",
    plotly_specs: dict = None,
):
    """渲染完整的双口径对比视图

    Args:
        full_result: 第一个 AnalysisResult（如全口径）
        market_result: 第二个 AnalysisResult（如市场化）
        full_label: 第一个结果的标签
        market_label: 第二个结果的标签
        plotly_specs: Plotly 图表规范（来自 dual_volume_plotly_specs.json）
    """
    if not full_result or not market_result:
        st.error("❌ 需要 2 个 AnalysisResult 才能对比")
        return

    # === 1. 顶部 KPI 对比卡片 ===
    _render_kpi_comparison(full_result, market_result, full_label, market_label)

    st.markdown("---")

    # === 2. 关键对比指标表 ===
    _render_comparison_table(full_result, market_result, full_label, market_label)

    st.markdown("---")

    # === 3. 5 大品类对比 ===
    _render_category_comparison(full_result, market_result, full_label, market_label)

    st.markdown("---")

    # === 4. Plotly 图表（如果有 specs）===
    if plotly_specs:
        _render_plotly_charts(plotly_specs)
        st.markdown("---")

    # === 5. 关键洞察 ===
    _render_comparison_insights(full_result, market_result, full_label, market_label)


def _render_kpi_comparison(full, market, full_label, market_label, kpi_map):
    """顶部 8 个 KPI 对比卡片"""
    st.markdown("### 🎯 8 大核心指标对比")

    f = full.kpis
    m = market.kpis

    k_total_vol = kpi_map["总电量"]
    k_price = kpi_map["度电均价"]
    k_revenue = kpi_map["总电费"]
    k_yoy_vol = kpi_map["同比电量"]
    k_yoy_price = kpi_map["同比度电"]
    k_yoy_rev = kpi_map["同比收入"]
    u_vol = kpi_map["总电量单位"]
    u_price = kpi_map["度电单位"]
    u_rev = kpi_map["电费单位"]

    # 4 列 2 行
    cols1 = st.columns(4)
    with cols1[0]:
        st.metric(
            f"{full_label} 总电量",
            f"{f.get(k_total_vol, 0)} {u_vol}",
            help="本周度电总量"
        )
    with cols1[1]:
        st.metric(
            f"{market_label} 总电量",
            f"{m.get(k_total_vol, 0)} {u_vol}",
            delta=f"{m.get(k_total_vol, 0)/f.get(k_total_vol, 1)*100:.1f}% of {full_label}",
        )
    with cols1[2]:
        st.metric(
            f"{full_label} 度电均价",
            f"{f.get(k_price, 0)} {u_price}",
        )
    with cols1[3]:
        st.metric(
            f"{market_label} 度电均价",
            f"{m.get(k_price, 0)} {u_price}",
            delta=f"{m.get(k_price, 0)-f.get(k_price, 0):+.3f}",
        )

    cols2 = st.columns(4)
    with cols2[0]:
        st.metric(
            "同比电量 差异",
            f"{f.get(k_yoy_vol, 0):+.2f}%",
            delta=f"{market.get(k_yoy_vol, 0)-f.get(k_yoy_vol, 0):+.2f} pp",
            delta_color="inverse",
        )
    with cols2[1]:
        st.metric(
            "同比度电 差异",
            f"{f.get(k_yoy_price, 0):+.1f} 分",
            delta=f"{market.get(k_yoy_price, 0)-f.get(k_yoy_price, 0):+.1f} 分",
        )
    with cols2[2]:
        st.metric(
            "同比收入 差异",
            f"{f.get(k_yoy_rev, 0):+.2f}%",
            delta=f"{market.get(k_yoy_rev, 0)-f.get(k_yoy_rev, 0):+.2f} pp",
            delta_color="inverse",
        )
    with cols2[3]:
        st.metric(
            "总电费 市场化占比",
            f"{m.get(k_revenue, 0)/f.get(k_revenue, 1)*100:.1f}%",
        )


def _render_comparison_table(full, market, full_label, market_label, kpi_map):
    """关键对比指标表"""
    st.markdown("### 📋 关键指标对比表")

    f = full.kpis
    m = market.kpis

    k_total_vol = kpi_map["总电量"]
    k_price = kpi_map["度电均价"]
    k_revenue = kpi_map["总电费"]
    k_yoy_vol = kpi_map["同比电量"]
    k_yoy_price = kpi_map["同比度电"]
    k_yoy_rev = kpi_map["同比收入"]
    k_mom_vol = kpi_map["环比电量"]
    k_mom_price = kpi_map["环比度电"]

    import pandas as pd

    rows = [
        [f"总电量 ({kpi_map['总电量单位']})", f"{f.get(k_total_vol, 0)}", f"{m.get(k_total_vol, 0)}",
         f"{m.get(k_total_vol, 0)/f.get(k_total_vol, 1)*100:.1f}%"],
        [f"度电均价 ({kpi_map['度电单位']})", f"{f.get(k_price, 0):.3f}", f"{m.get(k_price, 0):.3f}",
         f"{m.get(k_price, 0)-f.get(k_price, 0):+.3f}"],
        [f"总电费 ({kpi_map['电费单位']})", f"{f.get(k_revenue, 0):.2f}", f"{m.get(k_revenue, 0):.2f}",
         f"{m.get(k_revenue, 0)/f.get(k_revenue, 1)*100:.1f}%"],
        ["同比电量", f"{f.get(k_yoy_vol, 0):+.2f}%", f"{m.get(k_yoy_vol, 0):+.2f}%",
         f"{m.get(k_yoy_vol, 0)-f.get(k_yoy_vol, 0):+.2f} pp"],
        ["同比度电 (分)", f"{f.get(k_yoy_price, 0):+.1f}", f"{m.get(k_yoy_price, 0):+.1f}",
         f"{m.get(k_yoy_price, 0)-f.get(k_yoy_price, 0):+.1f}"],
        ["同比收入", f"{f.get(k_yoy_rev, 0):+.2f}%", f"{m.get(k_yoy_rev, 0):+.2f}%",
         f"{m.get(k_yoy_rev, 0)-f.get(k_yoy_rev, 0):+.2f} pp"],
        ["环比电量", f"{f.get(k_mom_vol, 0):+.2f}%", f"{m.get(k_mom_vol, 0):+.2f}%",
         f"{m.get(k_mom_vol, 0)-f.get(k_mom_vol, 0):+.2f} pp"],
        ["环比度电 (分)", f"{f.get(k_mom_price, 0):+.1f}", f"{m.get(k_mom_price, 0):+.1f}",
         f"{m.get(k_mom_price, 0)-f.get(k_mom_price, 0):+.1f}"],
    ]

    df = pd.DataFrame(rows, columns=["指标", full_label, market_label, "差异"])
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_category_comparison(full, market, full_label, market_label):
    """5 大品类对比"""
    st.markdown("### 📊 5 大品类同比收入对比")

    # 从 tables[1] 提取（"5 大品类明细"）
    if len(full.tables) > 1 and len(market.tables) > 1:
        f_cats = {row[0]: dict(zip(full.tables[1]["headers"], row)) for row in full.tables[1]["rows"]}
        m_cats = {row[0]: dict(zip(market.tables[1]["headers"], row)) for row in market.tables[1]["rows"]}
    else:
        st.warning("无品类数据")
        return

    import pandas as pd

    rows = []
    for cat in ["hydro", "renewables", "thermal", "wind", "solar"]:
        if cat in f_cats and cat in m_cats:
            rows.append([
                cat,
                f"{f_cats[cat].get('电量(亿度)', 0):.2f}",
                f"{m_cats[cat].get('电量(亿度)', 0):.2f}",
                f"{f_cats[cat].get('度电(元)', 0):.3f}",
                f"{m_cats[cat].get('度电(元)', 0):.3f}",
                f"{f_cats[cat].get('同比收入(%)', 0):+.2f}%",
                f"{m_cats[cat].get('同比收入(%)', 0):+.2f}%",
            ])

    df = pd.DataFrame(rows, columns=[
        "品类", f"{full_label}电量", f"{market_label}电量",
        f"{full_label}度电", f"{market_label}度电",
        f"{full_label}同比收入", f"{market_label}同比收入"
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

    # 动态生成品类洞察（基于实际数据）
    insights = _generate_category_insights(f_cats, m_cats, full_label, market_label)
    if insights:
        st.info("\n".join(insights))


def _generate_category_insights(f_cats, m_cats, full_label, market_label):
    """根据实际数据动态生成品类洞察"""
    insights = []

    # 检查水电倒挂
    if "hydro" in f_cats and "hydro" in m_cats:
        f_hydro_price = f_cats["hydro"].get("度电(元)", 0)
        m_hydro_price = m_cats["hydro"].get("度电(元)", 0)
        if m_hydro_price > f_hydro_price:
            diff_fen = (m_hydro_price - f_hydro_price) * 100
            insights.append(
                f"💡 **关键观察 1 - 水电倒挂**: {market_label}水电度电（{m_hydro_price:.3f}）> {full_label}（{f_hydro_price:.3f}），现货市场水电能卖更贵（+{diff_fen:.1f}分）"
            )

    # 检查风电双增
    if "wind" in f_cats and "wind" in m_cats:
        f_wind_rev = f_cats["wind"].get("同比收入(%)", 0)
        m_wind_rev = m_cats["wind"].get("同比收入(%)", 0)
        if m_wind_rev > f_wind_rev * 1.5 and m_wind_rev > 0:
            ratio = m_wind_rev / f_wind_rev if f_wind_rev > 0 else 0
            insights.append(
                f"💡 **关键观察 2 - 风电双增**: {market_label}同比 {m_wind_rev:+.1f}% > {full_label} {f_wind_rev:+.1f}%，风电是市场化赢家（约 {ratio:.1f}倍）"
            )

    # 检查火电同步退场
    if "thermal" in f_cats and "thermal" in m_cats:
        f_thermal_rev = f_cats["thermal"].get("同比收入(%)", 0)
        m_thermal_rev = m_cats["thermal"].get("同比收入(%)", 0)
        if f_thermal_rev < -30 and m_thermal_rev < -30:
            insights.append(
                f"💡 **关键观察 3 - 火电同步退场**: {full_label} {f_thermal_rev:+.1f}% ≈ {market_label} {m_thermal_rev:+.1f}%，两腿都短"
            )

    # 检查国际特点：水电是主业
    if "hydro" in f_cats and "hydro" in m_cats:
        f_hydro_share = f_cats["hydro"].get("占比(%)", 0)
        m_hydro_share = m_cats["hydro"].get("占比(%)", 0)
        if f_hydro_share > 70 and m_hydro_share > 70:
            insights.append(
                f"💡 **国际特点 - 水电主业极集中**: {full_label}水电 {f_hydro_share:.1f}%, {market_label} {m_hydro_share:.1f}%，国际业务水电是绝对主业"
            )

    # 检查新能源崛起（国际）
    if "renewables" in f_cats and "renewables" in m_cats:
        f_new_rev = f_cats["renewables"].get("同比收入(%)", 0)
        m_new_rev = m_cats["renewables"].get("同比收入(%)", 0)
        if f_new_rev > 20 and m_new_rev > 30:
            insights.append(
                f"💡 **国际特点 - 新能源强势崛起**: {full_label} {f_new_rev:+.1f}%, {market_label} {m_new_rev:+.1f}%，新能源在国际市场比国内增长更猛"
            )

    # 检查度电价差
    if "hydro" in f_cats and "hydro" in m_cats:
        f_price = f_cats["hydro"].get("度电(元)", 0)
        m_price = m_cats["hydro"].get("度电(元)", 0)
        diff = (f_price - m_price) * 100
        if abs(diff) > 5:
            insights.append(
                f"💡 **国际特点 - 价差更大**: {full_label}水电 {f_price:.3f} vs {market_label} {m_price:.3f}，差距 {diff:+.1f} 分（比国内 1.6 分差距大）"
            )

    return insights


def _render_plotly_charts(specs: dict):
    """渲染 Plotly 图表（来自 dual_volume_plotly_specs.json）"""
    st.markdown("### 📊 6 个对比图表")

    # 6 个图表：2 行 3 列
    cols = st.columns(3)

    chart_keys = [
        "yoy_volume_compare",
        "yoy_price_compare",
        "yoy_revenue_direction",
        "avg_price_compare",
        "category_revenue_yoy",
        "category_fate_compare",
    ]

    for i, key in enumerate(chart_keys):
        with cols[i % 3]:
            if i // 3 == 1 and i % 3 == 0:  # 换行时创建新行
                cols = st.columns(3)
            spec = specs.get(key)
            if not spec:
                continue
            _render_single_chart(spec, key)


def _render_single_chart(spec: dict, key: str):
    """渲染单个 Plotly 图表"""
    chart_type = spec.get("type", "bar")
    title = spec.get("title", "")
    data = spec.get("data", {})

    if chart_type == "bar":
        fig = _make_bar_chart(data, title, key)
    elif chart_type == "pie":
        fig = _make_pie_chart(data, title, key)
    else:
        st.warning(f"不支持的图表类型: {chart_type}")
        return

    if fig:
        st.plotly_chart(fig, use_container_width=True, key=f"comp_{key}")


def _make_bar_chart(data: dict, title: str, key: str) -> go.Figure:
    """生成柱状图"""
    categories = data.get("categories", [])
    series = data.get("series", {})

    if not categories:
        return None

    fig = go.Figure()

    if isinstance(series, dict) and series:
        for name, values in series.items():
            color = COLOR_FULL if "全口径" in name or "full" in name.lower() else (
                COLOR_MARKET if "市场化" in name or "market" in name.lower() else None
            )
            fig.add_trace(go.Bar(
                name=name,
                x=categories,
                y=values,
                marker_color=color,
            ))
    elif "values" in data:
        fig.add_trace(go.Bar(
            x=categories,
            y=data["values"],
        ))

    fig.update_layout(
        title=title,
        barmode="group",
        height=350,
        margin=dict(l=20, r=20, t=40, b=20),
        showlegend=True,
    )
    return fig


def _make_pie_chart(data: dict, title: str, key: str) -> go.Figure:
    """生成饼图"""
    labels = data.get("labels", [])
    values = data.get("values", [])

    if not labels or not values:
        return None

    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.3)])
    fig.update_layout(
        title=title,
        height=350,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def _render_comparison_insights(full, market, full_label, market_label):
    """对比核心洞察"""
    st.markdown("### 💎 5 个核心洞察（双口径对比）")

    f_yoy_vol = full.kpis.get("同比电量", 0)
    m_yoy_vol = market.kpis.get("同比电量", 0)
    f_yoy_rev = full.kpis.get("同比收入", 0)
    m_yoy_rev = market.kpis.get("同比收入", 0)
    f_hydro_price = 0
    m_hydro_price = 0

    # 从 tables 提取水电度电
    if len(full.tables) > 1 and len(market.tables) > 1:
        for row in full.tables[1]["rows"]:
            if row[0] == "hydro":
                f_hydro_price = row[3]
        for row in market.tables[1]["rows"]:
            if row[0] == "hydro":
                m_hydro_price = row[3]

    insights = []

    # 洞察 1: 方向相反
    direction_opp = (f_yoy_vol > 0) != (m_yoy_vol > 0)
    if direction_opp:
        insights.append(f"""
🔥 **洞察 1：方向反转**
- {full_label}: 同比 **{f_yoy_vol:+.2f}%**
- {market_label}: 同比 **{m_yoy_vol:+.2f}%**
- **方向相反** → 长协是压舱石，市场化是波动源
- 反推：长协部分 **{((f_yoy_rev * 100) - (m_yoy_vol * 100))/(100 - m_yoy_vol):.1f}%** 填补市场化损失（估算）
""")

    # 洞察 2: 水电倒挂
    if m_hydro_price > f_hydro_price:
        diff = m_hydro_price - f_hydro_price
        insights.append(f"""
💧 **洞察 2：水电的"两副面孔"**
- {full_label} 水电度电：{f_hydro_price:.3f} 元（同比微跌）
- {market_label} 水电度电：{m_hydro_price:.3f} 元（同比上涨）
- 现货比长协贵 **{diff*100:.1f} 分** ⭐
- 解读：**水电在"现货市场"反而能涨价**——这才是水电的真正价值
""")

    # 洞察 3: 火电同步退场
    if f_yoy_vol > 0 and m_yoy_vol < 0:
        # 计算火电同比
        f_thermal = next((row[5] for row in full.tables[1]["rows"] if row[0] == "thermal"), 0)
        m_thermal = next((row[5] for row in market.tables[1]["rows"] if row[0] == "thermal"), 0)
        if f_thermal < -30 and m_thermal < -30:
            insights.append(f"""
🔥 **洞察 3：火电"双线退场"路径同步**
- {full_label} 火电同比：{f_thermal:+.2f}% (占 3.88%)
- {market_label} 火电同比：{m_thermal:+.2f}% (占 9.24%)
- 两条路径几乎同步退场
- 解读：**火电不是"搬市场"，而是"真退场"**——两腿都短
""")

    # 洞察 4: 风电 vs 光伏
    f_wind = next((row[5] for row in full.tables[1]["rows"] if row[0] == "wind"), 0)
    m_wind = next((row[5] for row in market.tables[1]["rows"] if row[0] == "wind"), 0)
    f_solar = next((row[5] for row in full.tables[1]["rows"] if row[0] == "solar"), 0)
    m_solar = next((row[5] for row in market.tables[1]["rows"] if row[0] == "solar"), 0)
    if m_wind > f_wind * 2:
        insights.append(f"""
🌬️ **洞察 4：风电"双口径两栖"赢家**
- {full_label} 风电：+{f_wind:.2f}%
- {market_label} 风电：**+{m_wind:.2f}%** ({m_wind/f_wind:.1f}倍于{full_label})
- 解读：风电是"市场化赢家"——现货市场最受欢迎
""")

    if f_solar < 0 and m_solar > 0:
        insights.append(f"""
☀️ **洞察 5：光伏"路径分化"**
- {full_label} 光伏：{f_solar:+.2f}% ← 整体疲软
- {market_label} 光伏：**+{m_solar:.2f}%** ← 现货抢眼
- 两个口径方向相反
- 解读：**光伏"现货 > 长协"的拐点出现**——补贴退坡完成
""")

    for ins in insights:
        st.markdown(ins)


def load_plotly_specs(specs_path: Path = None) -> dict:
    """加载 Plotly 图表规范"""
    if specs_path is None:
        # 默认路径
        specs_path = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "dual_volume_plotly_specs.json"

    if not specs_path.exists():
        return {}

    with open(specs_path, encoding="utf-8") as f:
        return json.load(f)
