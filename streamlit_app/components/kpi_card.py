"""
KPI 卡片组件
============

通用 KPI 卡片渲染：标签 / 数值 / 同比 / 环比 / 趋势箭头
"""

import streamlit as st


def kpi_card(
    label: str,
    value,
    yoy_change=None,
    mom_change=None,
    help_text: str = None,
    suffix: str = "",
):
    """渲染单个 KPI 卡片

    Args:
        label: 指标名（如 "国内上网电量"）
        value: 当前值
        yoy_change: 同比变化（% 或 分，可选）
        mom_change: 环比变化（% 或 分，可选）
        help_text: 悬浮提示
        suffix: 单位后缀（如 "亿度"、"元/度"、"%"）
    """
    # 主指标
    st.metric(
        label=label,
        value=f"{value}{suffix}" if value is not None else "—",
        help=help_text,
    )

    # 同比/环比小标签
    cols = st.columns(2) if yoy_change is not None and mom_change is not None else st.columns(1)
    if yoy_change is not None:
        with cols[0]:
            _render_delta("同比", yoy_change)
    if mom_change is not None and len(cols) > 1:
        with cols[1]:
            _render_delta("环比", mom_change)


def _render_delta(label: str, change):
    """渲染同比/环比小标签"""
    if change is None:
        return

    # 判断方向
    if isinstance(change, (int, float)):
        if change > 0:
            emoji = "🟢"
            direction = f"+{change}"
        elif change < 0:
            emoji = "🔴"
            direction = f"{change}"  # 负号自带
        else:
            emoji = "⚪"
            direction = "0"
    else:
        emoji = "⚪"
        direction = str(change)

    st.caption(f"{emoji} {label}: {direction}")


def kpi_grid(kpis: dict, cols_per_row: int = 4):
    """网格布局渲染多个 KPI 卡片

    Args:
        kpis: dict of {label: value} 或 {label: (value, yoy, mom)}
        cols_per_row: 每行卡片数
    """
    items = list(kpis.items())
    for i in range(0, len(items), cols_per_row):
        row_items = items[i:i + cols_per_row]
        cols = st.columns(len(row_items))
        for col, (label, value) in zip(cols, row_items):
            with col:
                # 支持 (value, yoy, mom) 元组格式
                if isinstance(value, tuple) and len(value) == 3:
                    val, yoy, mom = value
                    kpi_card(label, val, yoy_change=yoy, mom_change=mom)
                elif isinstance(value, tuple) and len(value) == 2:
                    val, yoy = value
                    kpi_card(label, val, yoy_change=yoy)
                else:
                    kpi_card(label, value)


def kpi_row(kpis: dict):
    """单行布局渲染 KPI 卡片（不换行）"""
    items = list(kpis.items())
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        with col:
            if isinstance(value, tuple) and len(value) == 3:
                val, yoy, mom = value
                kpi_card(label, val, yoy_change=yoy, mom_change=mom)
            else:
                kpi_card(label, value)
