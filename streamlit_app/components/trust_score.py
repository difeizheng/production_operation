"""信任度评分组件 — 数据可信度可视化

设计原则：
    1. 纯计算 + 渲染分离：compute_trust_score 是纯函数
    2. 从 TraceReport + ParagraphTrace 计算综合信任度
    3. 三维评分：覆盖率(60%) + 自动化率(30%) + 基础分(10%)
    4. 渲染为顶部进度条 + 3 个 metric 卡片

用法：
    from streamlit_app.components.trust_score import (
        TrustScoreResult,
        compute_trust_score,
        render_trust_score_bar,
    )
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import streamlit as st

from src.collector.trace_builder import ParagraphTrace, TraceReport


@dataclass(frozen=True)
class TrustScoreResult:
    """信任度评分结果（不可变）。"""

    score: float  # 0-100 综合评分
    coverage_pct: float  # 字段采集覆盖率
    issue_count: int  # 待处理问题数
    high_count: int  # HIGH 自动化段落数
    medium_count: int  # MEDIUM 自动化段落数
    manual_count: int  # MANUAL 自动化段落数
    missing_count: int  # 缺失字段数
    out_of_range_count: int  # 超范围字段数

    @property
    def grade(self) -> str:
        """评级标签。"""
        if self.score >= 90:
            return "A · 高度可信"
        if self.score >= 80:
            return "B · 基本可信"
        if self.score >= 60:
            return "C · 需要关注"
        return "D · 不建议使用"


def compute_trust_score(
    trace_report: TraceReport,
    paragraph_traces: List[ParagraphTrace],
) -> TrustScoreResult:
    """从溯源报告和段落追踪计算信任度评分。

    评分公式：
        coverage_score = coverage_pct × 0.6  (60% 权重)
        auto_score = high_ratio × 30         (30% 权重)
        base = 10                            (基础分 10%)
        penalty = min(out_of_range × 2, 10)  (超范围扣分，最多 10)
        score = min(100, coverage_score + auto_score + base - penalty)

    Args:
        trace_report: 字段级溯源报告
        paragraph_traces: 段落级溯源列表

    Returns:
        TrustScoreResult 不可变评分结果
    """
    total_paras = len(paragraph_traces) or 1
    high_count = sum(
        1 for p in paragraph_traces if p.automation_level == "HIGH"
    )
    medium_count = sum(
        1 for p in paragraph_traces if p.automation_level == "MEDIUM"
    )
    manual_count = sum(
        1 for p in paragraph_traces if p.automation_level == "MANUAL"
    )

    # 覆盖率得分 (60% 权重)
    coverage_score = trace_report.coverage_pct * 0.6

    # 自动化率得分 (30% 权重)
    high_ratio = high_count / total_paras
    auto_score = high_ratio * 30

    # 超范围惩罚 (最多扣 10 分)
    penalty = min(trace_report.out_of_range_fields * 2, 10)

    # 基础分 10
    score = min(100.0, coverage_score + auto_score + 10 - penalty)
    score = max(0.0, score)

    return TrustScoreResult(
        score=round(score, 1),
        coverage_pct=round(trace_report.coverage_pct, 1),
        issue_count=trace_report.missing_fields
        + trace_report.out_of_range_fields,
        high_count=high_count,
        medium_count=medium_count,
        manual_count=manual_count,
        missing_count=trace_report.missing_fields,
        out_of_range_count=trace_report.out_of_range_fields,
    )


def _score_color(score: float) -> str:
    """评分对应颜色。"""
    if score >= 80:
        return "#28a745"  # 绿
    if score >= 60:
        return "#ffc107"  # 黄
    return "#dc3545"  # 红


def render_trust_score_bar(trust: TrustScoreResult) -> None:
    """渲染信任度评分条。

    布局：
        进度条 + 评分 | 采集率 | 自动化 | 待处理
    """
    color = _score_color(trust.score)

    # 进度条 + 评分
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(90deg, {color} {trust.score}%, #e9ecef {trust.score}%);
            height: 8px;
            border-radius: 4px;
            margin-bottom: 8px;
        "></div>
        """,
        unsafe_allow_html=True,
    )

    # 4 个指标卡片
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🎯 信任度", f"{trust.score}/100", trust.grade)
    with col2:
        st.metric("📦 采集率", f"{trust.coverage_pct}%", f"{trust.missing_count} 个缺失")
    with col3:
        st.metric(
            "🤖 自动化",
            f"HIGH {trust.high_count} / MED {trust.medium_count} / 手动 {trust.manual_count}",
        )
    with col4:
        issue_emoji = "✅" if trust.issue_count == 0 else "⚠️"
        st.metric(
            f"{issue_emoji} 待处理",
            f"{trust.issue_count} 个",
            f"缺失 {trust.missing_count} · 超范围 {trust.out_of_range_count}",
        )
