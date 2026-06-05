"""
图表渲染器
==========

通用图表渲染：把 Analyzer 输出的 charts 数据 → Plotly 图
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px


def render_chart(chart_data: dict, key: str = None):
    """根据 chart_data 渲染图表

    Args:
        chart_data: {
            "title": str,
            "type": "bar" / "pie" / "line",
            "data": {...}
        }
        key: Streamlit 唯一 key
    """
    chart_type = chart_data.get("type", "bar")
    title = chart_data.get("title", "")
    data = chart_data.get("data", {})

    if chart_type == "bar":
        fig = _render_bar(data, title)
    elif chart_type == "pie":
        fig = _render_pie(data, title)
    elif chart_type == "line":
        fig = _render_line(data, title)
    else:
        st.warning(f"不支持的图表类型: {chart_type}")
        return

    if fig:
        st.plotly_chart(fig, use_container_width=True, key=key)


def _render_bar(data: dict, title: str) -> go.Figure:
    """渲染柱状图（支持多 series）"""
    categories = data.get("categories", [])
    series = data.get("series", {})

    if not categories or not series:
        return None

    fig = go.Figure()

    if isinstance(series, dict):
        # 多 series（如 "同比" 和 "环比"）
        for name, values in series.items():
            fig.add_trace(go.Bar(
                name=name,
                x=categories,
                y=values,
            ))
    else:
        # 单 series
        fig.add_trace(go.Bar(
            x=categories,
            y=series,
        ))

    fig.update_layout(
        title=title,
        barmode="group",
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def _render_pie(data: dict, title: str) -> go.Figure:
    """渲染饼图"""
    labels = data.get("labels", [])
    values = data.get("values", [])

    if not labels or not values:
        return None

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.3,  # 环形图
    )])
    fig.update_layout(
        title=title,
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def _render_line(data: dict, title: str) -> go.Figure:
    """渲染折线图"""
    x = data.get("x", [])
    series = data.get("series", {})

    if not x or not series:
        return None

    fig = go.Figure()
    for name, values in series.items():
        fig.add_trace(go.Scatter(
            x=x, y=values,
            mode="lines+markers",
            name=name,
        ))

    fig.update_layout(
        title=title,
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def render_charts(charts_data: list, key_prefix: str = "chart"):
    """批量渲染多个图表"""
    if not charts_data:
        st.info("暂无图表数据")
        return

    for i, chart in enumerate(charts_data):
        key = f"{key_prefix}_{i}"
        render_chart(chart, key=key)


def render_simple_bar(
    title: str,
    categories: list,
    values: list,
    key: str = None,
    y_label: str = "数值",
):
    """简单柱状图（直接传数据）"""
    fig = go.Figure(data=[go.Bar(x=categories, y=values)])
    fig.update_layout(
        title=title,
        yaxis_title=y_label,
        height=350,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True, key=key)
