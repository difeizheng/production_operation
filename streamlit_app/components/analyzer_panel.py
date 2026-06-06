"""
通用 AnalysisResult 渲染器
============================

核心组件：把任意 Analyzer 的 AnalysisResult 渲染为标准化的 Streamlit 页面

渲染结构:
1. 一句话总结（突出）
2. KPI 网格
3. 业务故事
4. 表格
5. 图表
6. 关键洞察
7. 异常告警
"""

import streamlit as st

from .kpi_card import kpi_grid
from .chart_renderer import render_charts
from .table_renderer import render_tables
from .story_panel import render_story, render_summary, render_anomalies, render_insights


def render_analyzer_result(result, dimension_label: str = None, show_kpis: bool = True, key_prefix: str = ""):
    """渲染完整的 AnalysisResult

    Args:
        result: src.analyzer.base.AnalysisResult 实例
        dimension_label: 维度标签（可选）
        show_kpis: 是否显示 KPI 网格
        key_prefix: Streamlit chart key 前缀（同一页面多次调用时用，避免 chart key 冲突）。
                    仅影响 chart 渲染（实际冲突源），其他元素无 key 冲突。
    """
    if result is None:
        st.error("❌ Analyzer 结果为空")
        return

    # 1. 顶部信息条
    if dimension_label:
        st.markdown(f"### {dimension_label}")
    if hasattr(result, "analyzer_name"):
        st.caption(
            f"分析器: `{result.analyzer_name}` | "
            f"段: `{result.section_ids}` | "
            f"时间: `{result.computed_at}`"
        )

    # 2. 一句话总结
    render_summary(result.summary)

    # 3. KPI 网格
    if show_kpis and result.kpis:
        st.markdown("---")
        st.markdown("### 📊 关键指标")
        kpi_grid(result.kpis, cols_per_row=4)

    # 4. 同比/环比数据
    if result.yoy_data or result.mom_data:
        st.markdown("---")
        st.markdown("### 📈 同比/环比")
        _render_yoy_mom(result.yoy_data, result.mom_data)

    # 5. 业务故事
    if result.story:
        st.markdown("---")
        render_story(result.story)

    # 6. 表格
    if result.tables:
        st.markdown("---")
        st.markdown("### 📋 数据明细")
        render_tables(result.tables)

    # 7. 图表（key 冲突源：用 key_prefix 区分）
    if result.charts:
        st.markdown("---")
        st.markdown("### 📊 可视化")
        chart_key_prefix = f"{key_prefix}chart" if key_prefix else "chart"
        render_charts(result.charts, key_prefix=chart_key_prefix)

    # 8. 关键洞察
    if result.insights:
        st.markdown("---")
        render_insights(result.insights)

    # 9. 异常告警
    if result.anomalies:
        st.markdown("---")
        render_anomalies(result.anomalies)


def _render_yoy_mom(yoy_data, mom_data):
    """渲染同比/环比数据"""
    cols = st.columns(2)

    with cols[0]:
        st.markdown("**📈 同比（vs 去年同期）**")
        if isinstance(yoy_data, dict):
            _render_yoy_mom_dict(yoy_data)
        else:
            st.json(yoy_data) if yoy_data else st.info("无数据")

    with cols[1]:
        st.markdown("**📊 环比（vs 上周）**")
        if isinstance(mom_data, dict):
            _render_yoy_mom_dict(mom_data)
        else:
            st.json(mom_data) if mom_data else st.info("无数据")


def _render_yoy_mom_dict(data: dict):
    """递归渲染 dict 数据"""
    if not data:
        st.info("无数据")
        return

    for key, value in data.items():
        if isinstance(value, dict):
            with st.expander(f"📦 {key}", expanded=False):
                _render_yoy_mom_dict(value)
        elif isinstance(value, list):
            if value and isinstance(value[0], dict):
                # 列表嵌套字典（如 by_board）
                import pandas as pd
                rows = []
                for item in value:
                    if isinstance(item, dict):
                        rows.append(item)
                if rows:
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.json(value)
            else:
                st.write(f"**{key}**: {value}")
        else:
            st.write(f"**{key}**: {value}")
