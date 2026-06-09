"""审计时间线组件 - 段位生命周期事件可视化

设计原则：
    1. 从 PipelineState.polished_slots 提取事件时间戳
    2. 4 阶段：提取 → 润色 → 编辑 → 渲染
    3. 用 Streamlit 原生组件（st.expander + st.markdown）渲染
    4. 空事件友好降级

事件来源：
    - 提取：slot.raw_text 存在时（时间戳从 slot.timestamp 推断）
    - 润色：slot.llm_output 存在时
    - 编辑：slot.is_edited_by_human == True 时
    - 渲染：从 audit_log["rendered_at"] 获取
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# 数据类
# ============================================================================

@dataclass(frozen=True)
class TimelineEvent:
    """单个时间线事件。

    Attributes:
        stage: 阶段名称（extract/polish/edit/render）
        slot_id: 段位 ID
        timestamp: 事件时间（ISO 格式或 datetime）
        status: 状态（success/fallback/skipped）
        detail: 详情描述
        metadata: 额外元数据（如 tokens_used, model_used）
    """
    stage: str
    slot_id: str
    timestamp: str
    status: str
    detail: str
    metadata: Dict[str, Any]


# ============================================================================
# 事件提取
# ============================================================================

def extract_timeline_events(
    polished_slots: Dict[str, Any],
    audit_log: Optional[Dict[str, Any]] = None,
) -> List[TimelineEvent]:
    """从 polished_slots 和 audit_log 提取时间线事件。

    Args:
        polished_slots: {slot_id: PolishedSlot} 字典
        audit_log: PipelineState.audit_log（可选）

    Returns:
        按时间排序的事件列表
    """
    events: List[TimelineEvent] = []
    audit_log = audit_log or {}

    for slot_id, slot in polished_slots.items():
        # 1. 提取阶段（有 raw_text 即视为已提取）
        if slot.raw_text:
            events.append(TimelineEvent(
                stage="extract",
                slot_id=slot_id,
                timestamp=slot.timestamp,
                status="success",
                detail=f"从 Excel 提取 {len(slot.raw_text)} 字",
                metadata={"source_file": getattr(slot, "source_file", "")},
            ))

        # 2. 润色阶段
        if slot.llm_output is not None:
            events.append(TimelineEvent(
                stage="polish",
                slot_id=slot_id,
                timestamp=slot.timestamp,
                status="success",
                detail=f"LLM 润色完成（{slot.tokens_used} tokens, {slot.model_used}）",
                metadata={
                    "tokens_used": slot.tokens_used,
                    "model_used": slot.model_used,
                    "automation_level": slot.automation_level,
                },
            ))
        elif slot.is_fallback:
            events.append(TimelineEvent(
                stage="polish",
                slot_id=slot_id,
                timestamp=slot.timestamp,
                status="fallback",
                detail="Fallback 模式（未调用 LLM）",
                metadata={"error": slot.error},
            ))

        # 3. 人工编辑阶段
        if slot.is_edited_by_human:
            events.append(TimelineEvent(
                stage="edit",
                slot_id=slot_id,
                timestamp=slot.timestamp,
                status="success",
                detail=f"人工编辑完成（{len(slot.final_text)} 字）",
                metadata={"edited_length": len(slot.final_text)},
            ))

    # 4. 渲染阶段（全局事件，非段位级别）
    rendered_at = audit_log.get("rendered_at")
    if rendered_at:
        events.append(TimelineEvent(
            stage="render",
            slot_id="__global__",
            timestamp=rendered_at,
            status="success",
            detail=f"Word 报告生成完成（{audit_log.get('docx_path', '')}）",
            metadata={"docx_path": audit_log.get("docx_path")},
        ))

    # 按时间排序（ISO 格式字符串可直接比较）
    events.sort(key=lambda e: e.timestamp)
    return events


# ============================================================================
# 分组聚合
# ============================================================================

def group_events_by_stage(
    events: List[TimelineEvent],
) -> Dict[str, List[TimelineEvent]]:
    """按阶段分组事件。

    Returns:
        {stage: [events]} 字典
    """
    grouped: Dict[str, List[TimelineEvent]] = {}
    for event in events:
        grouped.setdefault(event.stage, []).append(event)
    return grouped


def compute_stage_stats(
    events: List[TimelineEvent],
) -> Dict[str, Dict[str, Any]]:
    """计算各阶段统计信息。

    Returns:
        {stage: {count, success_count, fallback_count, total_tokens}}
    """
    grouped = group_events_by_stage(events)
    stats: Dict[str, Dict[str, Any]] = {}

    for stage, stage_events in grouped.items():
        count = len(stage_events)
        success_count = sum(1 for e in stage_events if e.status == "success")
        fallback_count = sum(1 for e in stage_events if e.status == "fallback")
        total_tokens = sum(
            e.metadata.get("tokens_used", 0) for e in stage_events
        )

        stats[stage] = {
            "count": count,
            "success_count": success_count,
            "fallback_count": fallback_count,
            "total_tokens": total_tokens,
        }

    return stats


# ============================================================================
# Streamlit 渲染
# ============================================================================

# 阶段图标 + 颜色映射
STAGE_META: Dict[str, Tuple[str, str]] = {
    "extract": ("📥", "蓝色"),
    "polish": ("🤖", "绿色"),
    "edit": ("✏️", "橙色"),
    "render": ("📄", "紫色"),
}


def render_audit_timeline(
    events: List[TimelineEvent],
    key: str = "audit_timeline",
) -> None:
    """Streamlit 渲染入口：时间线视图。

    Args:
        events: 时间线事件列表
        key: Streamlit 组件唯一 key
    """
    import streamlit as st

    if not events:
        st.info("📭 暂无审计事件。请先完成 Step 3 提取。")
        return

    # 按阶段分组
    grouped = group_events_by_stage(events)
    stats = compute_stage_stats(events)

    # 顶部统计卡片
    st.subheader("📊 阶段统计")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        extract_stats = stats.get("extract", {})
        st.metric(
            label="📥 提取",
            value=extract_stats.get("count", 0),
            help="从 Excel 提取的段位数",
        )
    with col2:
        polish_stats = stats.get("polish", {})
        st.metric(
            label="🤖 润色",
            value=polish_stats.get("count", 0),
            delta=f"{polish_stats.get('total_tokens', 0):,} tokens",
            help=f"LLM 润色段位数（{polish_stats.get('fallback_count', 0)} fallback）",
        )
    with col3:
        edit_stats = stats.get("edit", {})
        st.metric(
            label="✏️ 编辑",
            value=edit_stats.get("count", 0),
            help="人工编辑段位数",
        )
    with col4:
        render_stats = stats.get("render", {})
        st.metric(
            label="📄 渲染",
            value=render_stats.get("count", 0),
            help="Word 渲染次数",
        )

    st.divider()

    # 时间线详情（按阶段 expander）
    st.subheader("📜 事件时间线")
    for stage in ["extract", "polish", "edit", "render"]:
        stage_events = grouped.get(stage, [])
        if not stage_events:
            continue

        icon, color = STAGE_META.get(stage, ("❓", "灰色"))
        with st.expander(f"{icon} {stage.upper()} ({len(stage_events)} 事件)", expanded=(stage == "polish")):
            for event in stage_events:
                # 状态图标
                status_icon = {
                    "success": "✅",
                    "fallback": "🔄",
                    "skipped": "⏭️",
                }.get(event.status, "❓")

                # 时间格式化
                try:
                    dt = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
                    time_str = dt.strftime("%H:%M:%S")
                except Exception:
                    time_str = event.timestamp[:19]

                # 渲染事件行
                st.markdown(
                    f"{status_icon} **{event.slot_id}** "
                    f"<span style='color: gray; font-size: 0.9em;'>[{time_str}]</span> "
                    f"— {event.detail}",
                    unsafe_allow_html=True,
                )

                # 元数据（如有）
                if event.metadata:
                    meta_items = [
                        f"{k}: {v}" for k, v in event.metadata.items() if v
                    ]
                    if meta_items:
                        st.caption("  ".join(meta_items))
