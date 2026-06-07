"""Excel 数据预览组件 - 186 字段可视化

设计原则：
    1. 紧凑布局：所有字段在一个可滚动表格中
    2. 异常标记：自动检测并高亮异常值（z-score > 2 或 None）
    3. 分类筛选：按 category 分组（电量/电价/电费/同比/环比）
    4. 字段搜索：按字段名快速定位

使用：
    from streamlit_app.components.data_preview import render_excel_preview

    render_excel_preview(data_dict)
"""
from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st


# 字段分类映射（按业务语义）
FIELD_CATEGORIES = {
    "电量": ["electricity"],
    "电价": ["price", "wow_price", "yoy_price"],
    "电费": ["revenue", "wow_revenue", "yoy_revenue"],
    "同比": ["yoy"],
    "环比": ["wow"],
    "国际": ["international"],
    "市场化": ["market"],
    "绿证": ["green_cert", "ccer"],
    "其他": [],
}


def categorize_field(field_name: str) -> str:
    """根据字段名返回分类。"""
    field_lower = field_name.lower()
    for category, keywords in FIELD_CATEGORIES.items():
        for kw in keywords:
            if kw in field_lower:
                return category
    return "其他"


def detect_anomalies(values: List[float]) -> Dict[str, List[int]]:
    """检测异常值（z-score > 2 或 None）。

    Returns:
        {"outlier_indices": [...], "missing_indices": [...]}
    """
    missing_indices = [i for i, v in enumerate(values) if v is None]
    valid_values = [v for v in values if isinstance(v, (int, float))]

    outlier_indices = []
    if len(valid_values) >= 3:
        mean = statistics.mean(valid_values)
        stdev = statistics.stdev(valid_values) if len(valid_values) > 1 else 0
        if stdev > 0:
            for i, v in enumerate(values):
                if isinstance(v, (int, float)) and abs((v - mean) / stdev) > 2.5:
                    outlier_indices.append(i)

    return {
        "outlier_indices": outlier_indices,
        "missing_indices": missing_indices,
    }


def render_excel_preview(
    data: Dict[str, Any],
    max_rows: int = 200,
    title: str = "📊 数据预览",
) -> None:
    """渲染 Excel 数据预览。

    Args:
        data: AnalysisCollector 输出的字典
        max_rows: 最多显示行数
        title: 面板标题
    """
    if not data:
        st.warning("⚠️ 暂无数据")
        return

    st.subheader(title)

    # 转为 DataFrame
    rows = []
    for k, v in data.items():
        if k.startswith("_") or k in ("meta", "version"):
            continue
        category = categorize_field(k)
        is_missing = v is None
        rows.append({
            "字段": k,
            "分类": category,
            "值": v if v is not None else "—",
            "状态": "❌ 缺失" if is_missing else "✅",
        })

    df = pd.DataFrame(rows)
    if df.empty:
        st.info("数据中没有可显示的字段")
        return

    # 顶部过滤栏
    col1, col2, col3 = st.columns(3)
    with col1:
        search = st.text_input("🔍 搜索字段", "", key="data_preview_search")
    with col2:
        categories = ["全部"] + sorted(df["分类"].unique().tolist())
        selected_cat = st.selectbox("📂 分类", categories, key="data_preview_category")
    with col3:
        show_only = st.selectbox(
            "📋 显示",
            ["全部", "仅缺失", "仅正常"],
            key="data_preview_filter",
        )

    # 应用过滤
    filtered = df.copy()
    if search:
        filtered = filtered[filtered["字段"].str.contains(search, case=False, na=False)]
    if selected_cat != "全部":
        filtered = filtered[filtered["分类"] == selected_cat]
    if show_only == "仅缺失":
        filtered = filtered[filtered["状态"] == "❌ 缺失"]
    elif show_only == "仅正常":
        filtered = filtered[filtered["状态"] == "✅"]

    # 统计
    total = len(df)
    valid = (df["状态"] == "✅").sum()
    missing = (df["状态"] == "❌ 缺失").sum()
    coverage = valid / total if total > 0 else 0

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("总字段数", total)
    metric_col2.metric("已采集", valid)
    metric_col3.metric("缺失", missing, delta=None, delta_color="inverse")
    metric_col4.metric("覆盖率", f"{coverage:.1%}")

    # 表格
    st.dataframe(
        filtered.head(max_rows),
        use_container_width=True,
        height=min(500, 35 + len(filtered.head(max_rows)) * 35),
        column_config={
            "字段": st.column_config.TextColumn("字段", width="medium"),
            "分类": st.column_config.TextColumn("分类", width="small"),
            "值": st.column_config.TextColumn("值", width="medium"),
            "状态": st.column_config.TextColumn("状态", width="small"),
        },
        hide_index=True,
    )

    if len(filtered) > max_rows:
        st.caption(f"⚠️ 仅显示前 {max_rows} 行，共 {len(filtered)} 行")


def render_kpi_overview(
    data: Dict[str, Any],
    title: str = "🎯 关键指标概览",
) -> None:
    """渲染关键 KPI 概览。"""
    st.subheader(title)

    if not data:
        st.warning("⚠️ 暂无数据")
        return

    # 关键字段映射
    kpi_map = {
        "国内上网电量(亿千瓦时)": data.get("report.electricity.domestic"),
        "国际上网电量(亿千瓦时)": data.get("report.electricity.international"),
        "集团度电均价(元/千瓦时)": data.get("report.price.avg"),
        "国内度电均价(元/千瓦时)": data.get("report.price.domestic"),
        "国际度电均价(元/千瓦时)": data.get("report.price.international"),
        "国内电量同比(%)": _to_pct(data.get("report.yoy_electricity.domestic")),
        "国际电量同比(%)": _to_pct(data.get("report.yoy_electricity.international")),
    }

    cols = st.columns(3)
    for i, (label, value) in enumerate(kpi_map.items()):
        with cols[i % 3]:
            if value is None:
                st.metric(label, "—")
            elif isinstance(value, float):
                if "(%)" in label:
                    st.metric(label, f"{value*100:+.1f}%")
                else:
                    st.metric(label, f"{value:.3f}")
            else:
                st.metric(label, str(value))


def _to_pct(v: Any) -> Optional[float]:
    """转换为百分比（如果是 0-1 之间的小数）。"""
    if v is None or not isinstance(v, (int, float)):
        return None
    return v
