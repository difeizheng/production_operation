"""质量雷达图组件 - Plotly Scatterpolar 4 维均值可视化

设计原则：
    1. 4 维：数字保留/长度合理/禁词扫描/专业度（不含 deviation）
    2. 聚合：对所有段位 4 维分值取均值
    3. 配色：高分绿、中分黄、低分红（按整体 verdict 着色）
    4. 空 metrics 安全降级
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


# 4 维度定义（顺序固定）
RADAR_CATEGORIES: tuple[str, ...] = (
    "数字保留(30)",
    "长度合理(20)",
    "禁词扫描(20)",
    "专业度(20)",
)


def build_radar_figure(
    metrics: Dict[str, Any],
) -> Any | None:
    """构造 Plotly 雷达图 Figure。

    Args:
        metrics: {slot_id: QualityMetrics} 字典

    Returns:
        plotly.graph_objects.Figure 或 None（空 metrics）
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        logger.warning("plotly 未安装，无法渲染雷达图")
        return None

    if not metrics:
        return None

    # 4 维聚合均值
    n = len(metrics)
    numbers_avg = sum(
        30 if m.numbers_consistency else 0 for m in metrics.values()
    ) / n
    length_avg = sum(
        20 if m.length_reasonable else 0 for m in metrics.values()
    ) / n
    forbidden_avg = sum(
        20 if m.no_forbidden_words else 0 for m in metrics.values()
    ) / n
    prof_avg = sum(m.professionalism for m in metrics.values()) / n

    values = [numbers_avg, length_avg, forbidden_avg, prof_avg]
    # 闭合多边形（首尾相接）
    categories_closed = list(RADAR_CATEGORIES) + [RADAR_CATEGORIES[0]]
    values_closed = values + [values[0]]

    # 配色：按平均分定色阶
    avg_score = sum(m.overall_score for m in metrics.values()) / n
    if avg_score >= 80:
        line_color = "rgb(46, 160, 67)"  # 绿
        fill_color = "rgba(46, 160, 67, 0.35)"
    elif avg_score >= 60:
        line_color = "rgb(255, 191, 0)"  # 黄
        fill_color = "rgba(255, 191, 0, 0.35)"
    else:
        line_color = "rgb(220, 53, 69)"  # 红
        fill_color = "rgba(220, 53, 69, 0.35)"

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=values_closed,
            theta=categories_closed,
            fill="toself",
            fillcolor=fill_color,
            line=dict(color=line_color, width=2),
            name=f"平均分 {avg_score:.1f}",
            hovertemplate="<b>%{theta}</b><br>平均: %{r:.1f} 分<extra></extra>",
        )
    )

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 30],  # 最大维度 30
                tickfont=dict(size=10),
            ),
            angularaxis=dict(tickfont=dict(size=11)),
        ),
        showlegend=True,
        title=dict(
            text=f"4 维质量雷达（{n} 段位聚合）",
            x=0.5,
            font=dict(size=14),
        ),
        height=400,
        margin=dict(l=60, r=60, t=60, b=40),
    )

    return fig


def render_quality_radar(
    metrics: Dict[str, Any],
    key: str = "quality_radar",
) -> None:
    """Streamlit 渲染入口。

    用法：
        from streamlit_app.components.quality_radar import render_quality_radar
        render_quality_radar(state.quality_metrics)
    """
    import streamlit as st

    if not metrics:
        st.info("📭 暂无质量数据。请先完成 Step 4 润色生成段位。")
        return

    fig = build_radar_figure(metrics)
    if fig is None:
        st.warning("⚠️ 雷达图初始化失败（plotly 不可用或数据为空）")
        return

    st.plotly_chart(fig, use_container_width=True, key=key)
