"""质量汇总卡片 - 4 KPI + 状态徽章

设计原则：
    1. 4 个 st.metric 卡片（总段数/平均分/达标率/最低分）
    2. 状态徽章（PASS/WARN/BLOCK/CRITICAL）按 verdict 着色
    3. 与现有 kpi_card 组件保持一致（用 st.metric）
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# 状态徽章文案
VERDICT_BADGE: dict[str, tuple[str, str]] = {
    "pass": ("✅ 通过", "🟢"),
    "warn": ("⚠️ 警告", "🟡"),
    "block": ("❌ 阻断", "🔴"),
    "critical": ("🚨 严重", "🔴🔴"),
}


def render_quality_summary(
    avg: float,
    pass_rate: float,
    min_score: int,
    count: int,
    verdict: str,
    key: str = "quality_summary",
) -> None:
    """Streamlit 渲染入口。

    Args:
        avg: 平均分
        pass_rate: 通过率（0-1）
        min_score: 最低分
        count: 段位数
        verdict: 'pass' | 'warn' | 'block' | 'critical'
        key: 唯一 key
    """
    import streamlit as st

    # 4 个 KPI 卡片
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="📊 总段数",
            value=count,
            help="当前 PipelineState 中已润色的段位总数",
        )
    with col2:
        st.metric(
            label="⭐ 平均分",
            value=f"{avg:.1f}",
            delta=f"{avg - 80:.1f} vs 80 阈值" if avg < 80 else "✓ 达标",
            delta_color="normal" if avg >= 80 else "inverse",
            help="所有段位 4 维总分加权平均",
        )
    with col3:
        st.metric(
            label="🎯 达标率",
            value=f"{pass_rate:.0%}",
            help="总分 >= 80 分的段位占比",
        )
    with col4:
        st.metric(
            label="📉 最低分",
            value=min_score,
            delta=f"{min_score - 80} vs 80 阈值" if min_score < 80 else "✓ 达标",
            delta_color="normal" if min_score >= 80 else "inverse",
            help="所有段位中总分最低的",
        )

    # 状态徽章
    label, icon = VERDICT_BADGE.get(verdict, ("❓ 未知", "⚪"))
    if verdict == "pass":
        st.success(f"{icon} **质量门禁：{label}** - 报告可放心生成")
    elif verdict == "warn":
        st.warning(f"{icon} **质量门禁：{label}** - 建议先在 Step 5 编辑低分段位")
    elif verdict == "block":
        st.error(f"{icon} **质量门禁：{label}** - 必须先编辑（可强制继续）")
    else:  # critical
        st.error(f"{icon} **质量门禁：{label}** - 禁止生成（必须先编辑）")
