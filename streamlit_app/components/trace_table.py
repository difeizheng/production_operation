"""数据溯源表格组件 - 渲染 CELL_MAP 字段的溯源信息

在数据驾驶舱（Step 1）中展示每个字段的来源单元格、采集值、验证状态，
让用户无需打开 Excel/JSON 就能校核数据。

设计原则：
    1. 纯函数构造 + 渲染分离
    2. 空安全降级（空 TraceReport 显示友好提示）
    3. 支持搜索和过滤
    4. 复用 data_preview.py 的 st.dataframe 模式
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from src.collector.trace_builder import TraceReport, CellTrace

logger = logging.getLogger(__name__)


# ============================================================================
# 数据转换
# ============================================================================


def _traces_to_dataframe(traces: tuple[CellTrace, ...]) -> pd.DataFrame:
    """将 CellTrace 元组转换为 DataFrame。

    Args:
        traces: CellTrace 元组

    Returns:
        包含所有溯源信息的 DataFrame
    """
    if not traces:
        return pd.DataFrame()

    rows = []
    for trace in traces:
        rows.append({
            "分组": trace.section,
            "字段名": trace.field_name,
            "中文描述": trace.description_zh,
            "单元格": trace.cell_ref,
            "采集值": trace.value_display,
            "单位": trace.unit,
            "状态": _status_emoji(trace.validation_status),
            "验证详情": trace.validation_detail,
        })

    return pd.DataFrame(rows)


def _status_emoji(status: str) -> str:
    """将验证状态转换为表情符号。"""
    emoji_map = {
        "正常": "✅",
        "缺值": "❌",
        "超范围": "⚠️",
    }
    return emoji_map.get(status, "❓")


def _filter_traces(
    traces: tuple[CellTrace, ...],
    search: str = "",
    section_filter: str = "全部",
    status_filter: str = "全部",
) -> tuple[CellTrace, ...]:
    """过滤溯源记录。

    Args:
        traces: 原始溯源记录
        search: 搜索关键词（匹配字段名、描述、单元格）
        section_filter: 分组过滤（"全部" / "国内" / "国际" / "报告表"）
        status_filter: 状态过滤（"全部" / "正常" / "缺值" / "超范围"）

    Returns:
        过滤后的溯源记录
    """
    filtered = traces

    # 分组过滤
    if section_filter != "全部":
        filtered = tuple(t for t in filtered if t.section == section_filter)

    # 状态过滤
    if status_filter != "全部":
        filtered = tuple(t for t in filtered if t.validation_status == status_filter)

    # 搜索过滤（去除首尾空格）
    if search:
        search_lower = search.strip().lower()
        filtered = tuple(
            t for t in filtered
            if search_lower in t.field_name.lower()
            or search_lower in t.description_zh.lower()
            or search_lower in t.cell_ref.lower()
        )

    return filtered


# ============================================================================
# 渲染函数
# ============================================================================


def render_trace_table(
    trace_report: TraceReport,
    key: str = "trace_table",
) -> None:
    """渲染数据溯源表格。

    Args:
        trace_report: 溯源报告
        key: Streamlit 组件唯一键
    """
    # 空安全降级
    if not trace_report or not trace_report.traces:
        st.info("📭 暂无溯源数据（请先上传 Excel 或加载演示数据）")
        return

    # 标题和统计
    st.subheader(f"📍 数据溯源（共 {trace_report.total_fields} 字段，覆盖率 {trace_report.coverage_pct:.1f}%）")

    # 统计卡片
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总字段", trace_report.total_fields)
    col2.metric("✅ 正常", trace_report.collected_fields)
    col3.metric("❌ 缺值", trace_report.missing_fields)
    col4.metric("⚠️ 超范围", trace_report.out_of_range_fields)

    st.divider()

    # 过滤控件
    filter_col1, filter_col2, filter_col3 = st.columns(3)

    with filter_col1:
        search = st.text_input(
            "🔍 搜索字段",
            placeholder="输入字段名、描述或单元格...",
            key=f"{key}_search",
        )

    with filter_col2:
        section_options = ["全部"] + sorted(set(t.section for t in trace_report.traces))
        section_filter = st.selectbox(
            "📂 分组过滤",
            options=section_options,
            key=f"{key}_section",
        )

    with filter_col3:
        status_options = ["全部", "正常", "缺值", "超范围"]
        status_filter = st.selectbox(
            "📋 状态过滤",
            options=status_options,
            key=f"{key}_status",
        )

    # 应用过滤
    filtered_traces = _filter_traces(
        trace_report.traces,
        search=search,
        section_filter=section_filter,
        status_filter=status_filter,
    )

    # 过滤结果统计
    st.caption(f"显示 {len(filtered_traces)} / {trace_report.total_fields} 字段")

    # 转换为 DataFrame
    df = _traces_to_dataframe(filtered_traces)

    if df.empty:
        st.warning("📭 没有匹配的字段（请调整过滤条件）")
        return

    # 渲染表格
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "分组": st.column_config.TextColumn("分组", width="small"),
            "字段名": st.column_config.TextColumn("字段名", width="medium"),
            "中文描述": st.column_config.TextColumn("中文描述", width="medium"),
            "单元格": st.column_config.TextColumn("单元格", width="small"),
            "采集值": st.column_config.TextColumn("采集值", width="small"),
            "单位": st.column_config.TextColumn("单位", width="small"),
            "状态": st.column_config.TextColumn("状态", width="small"),
            "验证详情": st.column_config.TextColumn("验证详情", width="large"),
        },
    )

    # 分区统计（直接渲染，避免在父级 expander 内嵌套 expander）
    st.markdown("##### 📊 分区统计")
    st.write("**按分组统计**:")
    section_df = pd.DataFrame([
        {"分组": k, "字段数": v}
        for k, v in sorted(trace_report.by_section.items())
    ])
    st.dataframe(section_df, use_container_width=True, hide_index=True)

    st.write("**按指标类型统计**:")
    metric_df = pd.DataFrame([
        {"指标类型": k, "字段数": v}
        for k, v in sorted(trace_report.by_metric_type.items())
    ])
    st.dataframe(metric_df, use_container_width=True, hide_index=True)
