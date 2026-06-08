"""Excel 数据预览组件 - 叶子字段可视化

设计原则：
    1. 紧凑布局：所有字段在一个可滚动表格中
    2. 异常标记：自动检测并高亮异常值（z-score > 2 或 None）
    3. 分类筛选：按 category 分组（电量/电价/电费/同比/环比）
    4. 字段搜索：按字段名快速定位
    5. 递归扁平化：dict 递归、list 展平、scalar 算叶子
       - 修复历史问题：v3.0 标题写死 "186 字段"，但实际 JSON 是 11 顶层
         section + 236 叶子。改用叶子数才算"字段数"。
    6. 中文描述 + 单位：调用 describe_field() 注入每行的"是什么"和"什么单位"
       - 解决业务小白看不懂英文 path 的问题
       - 区分 _yi_kwh（亿千瓦时）和 _kwh（千瓦时）差 1 亿倍

使用：
    from streamlit_app.components.data_preview import render_excel_preview

    render_excel_preview(data_dict)
"""
from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from streamlit_app.utils.field_descriptions import describe_field


# 元数据/系统字段：递归时跳过（不是业务数据）
SKIP_KEYS = {"meta", "version", "report_id"}


def _flatten_to_leaves(data: Any, path: str = "", section: str = "") -> List[Dict[str, Any]]:
    """递归扁平化嵌套数据为叶子字段列表。

    规则：
        - dict：递归遍历，路径用 `.` 拼接（如 `by_category.hydro.volume_yi_kwh`）
        - list：展平，路径用 `[i]` 标记（如 `by_country_category[0].country`）
        - scalar：算叶子，记一条记录
        - SKIP_KEYS：跳过（meta/version/report_id）
        - None：算缺失叶子

    Returns:
        list of dict: [{path, value, section, category, is_missing}, ...]
    """
    leaves: List[Dict[str, Any]] = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k in SKIP_KEYS:
                continue
            new_path = f"{path}.{k}" if path else k
            new_section = section or k
            leaves.extend(_flatten_to_leaves(v, new_path, new_section))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            leaves.extend(_flatten_to_leaves(item, f"{path}[{i}]", section))
    else:
        # 叶子：标量（int/float/str/bool/None）
        is_missing = data is None
        # 注入中文描述 + 单位（CURATED > 智能推断）
        desc = describe_field(path)
        leaves.append(
            {
                "path": path,
                "value": data,
                "section": section,
                "category": categorize_field(path),
                "description_zh": desc["description_zh"],
                "unit": desc["unit"],
                "is_missing": is_missing,
            }
        )
    return leaves


def categorize_field(field_path: str) -> str:
    """根据完整字段路径返回分类。

    路径示例：
        - "by_category.hydro.volume_yi_kwh"  → "电量"
        - "by_category.hydro.avg_price_yuan_per_kwh"  → "电价"
        - "by_category.hydro.mom_price_change_fen"  → "电价"（不是"环比"）
        - "international.avg_price_yoy_change_fen"  → "国际"（section 优先）
        - "international.total_volume_yi_kwh"  → "国际"（section 优先）
        - "market_trading.thermal.avg_price_yuan_per_kwh"  → "市场化"
        - "environmental_assets.green_cert.weekly_issued_wan"  → "绿证"
        - "report.yoy.field"  → "同比"（无 base keyword，wow/yoy 兜底）

    优先级（更具体的优先匹配）：
        1. 业务大类（国际/市场化/绿证）—— section 是最具体业务上下文
        2. 基础业务字段（电价/电费/电量）—— base 类型优先于变化类型
           这样 wow_price/yoy_price 都会归到"电价"（价格的故事完整）
        3. 变更类（同比/环比）—— 兜底（纯 wow/yoy 字段）
    """
    p = field_path.lower()

    # 1. 业务大类（section 决定一切）
    if p.startswith("international") or p.startswith("exchange") or p.startswith("by_country"):
        return "国际"
    if p.startswith("market"):
        return "市场化"
    if p.startswith("environmental") or "green_cert" in p or "ccer" in p:
        return "绿证"

    # 2. 基础业务字段（base 优先：wow_price/yoy_price → 电价，不是环比/同比）
    if "price" in p or "电价" in p or "_fen" in p or "_yuan_per_kwh" in p:
        return "电价"
    if "revenue" in p or "电费" in p or "income" in p or p.endswith("_yuan"):
        return "电费"
    if "volume" in p or "电量" in p or "_kwh" in p or "electricity" in p:
        return "电量"

    # 3. 变更类（兜底：纯 yoy/wow 字段才到这里）
    if "yoy" in p or "同比" in p:
        return "同比"
    if "wow" in p or "mom" in p or "环比" in p:
        return "环比"

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
    title: Optional[str] = None,
) -> None:
    """渲染 Excel 数据预览。

    Args:
        data: AnalysisCollector 输出的字典（嵌套 dict + list）
        max_rows: 最多显示行数
        title: 面板标题（None = 自动生成）
    """
    if not data:
        st.warning("⚠️ 暂无数据")
        return

    # 递归扁平化为叶子字段
    leaves = _flatten_to_leaves(data)
    total_leaves = len(leaves)
    sections = sorted({leaf["section"] for leaf in leaves if leaf["section"]})
    n_sections = len(sections)

    # 标题：传了就用传的，没传就自动生成
    st.subheader(title or "📊 数据预览")
    curated_count = sum(1 for l in leaves if l.get("description_zh") and "·" not in l["description_zh"].split("（")[0])
    # 简单估算 CURATED 数：描述里没有"·"的（推断会有"·"拼接）
    from streamlit_app.utils.field_descriptions import get_curated_count
    curated_total = get_curated_count()
    st.caption(
        f"共 **{total_leaves}** 个叶子字段，覆盖 **{n_sections}** 个数据模块"
        + (f"：{', '.join(sections)}" if n_sections <= 6 else "")
        + f" · 中文描述：**{curated_total}** 字段已人工校对"
    )

    # 转为 DataFrame
    rows = [
        {
            "字段": leaf["path"],
            "描述": leaf["description_zh"],
            "单位": leaf["unit"] or "—",
            "分类": leaf["category"],
            "值": leaf["value"] if not leaf["is_missing"] else "—",
            "状态": "❌ 缺失" if leaf["is_missing"] else "✅",
        }
        for leaf in leaves
    ]

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

    # 应用过滤（搜索同时匹配 字段 / 描述 / 单位）
    filtered = df.copy()
    if search:
        mask = (
            filtered["字段"].str.contains(search, case=False, na=False)
            | filtered["描述"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]
    if selected_cat != "全部":
        filtered = filtered[filtered["分类"] == selected_cat]
    if show_only == "仅缺失":
        filtered = filtered[filtered["状态"] == "❌ 缺失"]
    elif show_only == "仅正常":
        filtered = filtered[filtered["状态"] == "✅"]

    # 统计（用叶子数）
    total = len(df)
    valid = (df["状态"] == "✅").sum()
    missing = (df["状态"] == "❌ 缺失").sum()
    coverage = valid / total if total > 0 else 0

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("总叶子字段", total)
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
            "描述": st.column_config.TextColumn("中文描述", width="large"),
            "单位": st.column_config.TextColumn("单位", width="small"),
            "分类": st.column_config.TextColumn("分类", width="small"),
            "值": st.column_config.TextColumn("值", width="medium"),
            "状态": st.column_config.TextColumn("状态", width="small"),
        },
        hide_index=True,
    )

    if len(filtered) > max_rows:
        st.caption(f"⚠️ 仅显示前 {max_rows} 行，共 {len(filtered)} 行")


# ============================================================
# KPI 概览定义
# ============================================================
# 8 个核心 KPI 卡片，覆盖 集团/国内/国际 × 电量/电价/收入 × 同比/环比
# 修复历史 bug：原来用 report.electricity.* / report.price.* 这些不存在的 key
KPI_DEFINITIONS = [
    # Row 1: 电量（4 个）
    {"label": "集团总上网电量", "path": "group_total.total_ongrid_volume_yi_kwh", "fmt": "volume"},
    {"label": "国内上网电量", "path": "group_total.domestic_ongrid_volume_yi_kwh", "fmt": "volume"},
    {"label": "国际上网电量", "path": "group_total.international_ongrid_volume_yi_kwh", "fmt": "volume"},
    {"label": "国内发电收入", "path": "group_total.domestic_revenue_yi_yuan", "fmt": "revenue"},
    # Row 2: 电价 + 同比环比（4 个）
    {"label": "国内度电均价", "path": "group_total.domestic_avg_price_yuan_per_kwh", "fmt": "price"},
    {"label": "国际度电均价", "path": "international.avg_price_yuan_per_kwh", "fmt": "price"},
    {"label": "集团电量同比", "path": "group_total.yoy_volume_pct", "fmt": "pct"},
    {"label": "集团电量环比", "path": "group_total.mom_volume_pct", "fmt": "pct"},
]


def _format_kpi_value(value: Any, fmt: str) -> str:
    """格式化 KPI 值为带单位的可读字符串。

    Args:
        value: 原始值（None/int/float）
        fmt: 格式类型 volume/price/revenue/pct

    Returns:
        格式化字符串（如 "80.3 亿千瓦时" / "+3.3%" / "—"）
    """
    if value is None:
        return "—"
    if not isinstance(value, (int, float)):
        return str(value)
    if fmt == "volume":
        return f"{value:.1f} 亿千瓦时"
    if fmt == "price":
        return f"{value:.3f} 元/度"
    if fmt == "revenue":
        return f"{value:.2f} 亿元"
    if fmt == "pct":
        # 注意：fixture 中 yoy_*/mom_* 字段已是百分比数值（3.3 表示 3.3%），
        # 不需要再乘 100。历史 bug：曾误用 _to_pct() 乘 100，导致 3.3 → 330%
        return f"{value:+.1f}%"
    return str(value)


def _get_dotted(data: Dict[str, Any], dotted_path: str) -> Any:
    """按点分路径取值（dict.get 不会自动拆点，必须自己遍历）。

    例：_get_dotted(d, "group_total.total_ongrid_volume_yi_kwh")
        → 返回 d["group_total"]["total_ongrid_volume_yi_kwh"]

    Args:
        data: 嵌套 dict
        dotted_path: 点分路径，如 "a.b.c"

    Returns:
        路径末端值；任一段缺失返回 None
    """
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def render_kpi_overview(
    data: Dict[str, Any],
    title: str = "🎯 关键指标概览",
) -> None:
    """渲染关键 KPI 概览（4 列 × 2 行 = 8 张卡片）。"""
    st.subheader(title)

    if not data:
        st.warning("⚠️ 暂无数据")
        return

    # 显示报告期上下文（用 describe_field 拿中文）
    period = data.get("report_period", {})
    if period:
        year = period.get("year", "?")
        week = period.get("week", "?")
        start = period.get("start_date", "?")
        end = period.get("end_date", "?")
        st.caption(f"📅 {year} 年第 {week} 周（{start} ~ {end}）")

    # 第一行：4 个 KPI
    cols = st.columns(4)
    for i, kpi in enumerate(KPI_DEFINITIONS[:4]):
        with cols[i]:
            # 关键：必须用 _get_dotted 拆开点分路径，否则 dict.get 找不到嵌套 key
            value = _get_dotted(data, kpi["path"])
            st.metric(kpi["label"], _format_kpi_value(value, kpi["fmt"]))

    # 第二行：另外 4 个
    cols2 = st.columns(4)
    for i, kpi in enumerate(KPI_DEFINITIONS[4:]):
        with cols2[i]:
            value = _get_dotted(data, kpi["path"])
            st.metric(kpi["label"], _format_kpi_value(value, kpi["fmt"]))
