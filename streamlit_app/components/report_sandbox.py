"""报告沙盘组件 — 段落数据卡片 + 证据链 + 行动项

设计原则：
    1. 自顶向下：先看报告段落，再溯源到字段 → 单元格
    2. 交互式：每个数据值可展开查看完整证据链
    3. 可操作：缺失/超范围字段关联到受影响段落
    4. 纯渲染：所有数据从参数传入，不访问 session_state

用法：
    from streamlit_app.components.report_sandbox import render_report_sandbox
    render_report_sandbox(paragraph_traces, trace_report, adapted_data)
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import streamlit as st

from src.collector.trace_builder import (
    CellTrace,
    ParagraphTrace,
    SlotDataRef,
    TraceReport,
)


# ============================================================================
# 反向索引：字段 → 段落
# ============================================================================


def build_field_to_paragraphs(
    paragraph_traces: List[ParagraphTrace],
) -> Dict[str, List[int]]:
    """构建字段名 → 引用该字段的段落索引列表。

    Args:
        paragraph_traces: 段落溯源列表

    Returns:
        字段名 → [v4_index, ...] 映射
    """
    result: Dict[str, List[int]] = defaultdict(list)
    for para in paragraph_traces:
        for ref in para.data_refs:
            for field_name in ref.resolved_fields:
                result[field_name].append(para.v4_index)
    return dict(result)


# ============================================================================
# 行动项检测
# ============================================================================


def detect_action_items(
    trace_report: TraceReport,
    paragraph_traces: List[ParagraphTrace],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """检测缺失和超范围字段及其影响的段落。

    Returns:
        (missing_items, out_of_range_items) 两个列表
        每个 item: {"field_name", "cell_ref", "description_zh", "affected_paragraphs"}
    """
    field_to_paras = build_field_to_paragraphs(paragraph_traces)

    missing_items: List[Dict[str, Any]] = []
    out_of_range_items: List[Dict[str, Any]] = []

    for trace in trace_report.traces:
        if trace.validation_status == "缺值":
            affected = field_to_paras.get(trace.field_name, [])
            missing_items.append(
                {
                    "field_name": trace.field_name,
                    "cell_ref": trace.cell_ref,
                    "description_zh": trace.description_zh,
                    "affected_paragraphs": sorted(set(affected)),
                }
            )
        elif trace.validation_status == "超范围":
            affected = field_to_paras.get(trace.field_name, [])
            out_of_range_items.append(
                {
                    "field_name": trace.field_name,
                    "cell_ref": trace.cell_ref,
                    "description_zh": trace.description_zh,
                    "value": trace.value,
                    "unit": trace.unit,
                    "affected_paragraphs": sorted(set(affected)),
                }
            )

    return missing_items, out_of_range_items


# ============================================================================
# 段落自动化等级渲染辅助
# ============================================================================


def _level_badge(level: str) -> str:
    """自动化等级 → emoji + 标签。"""
    mapping = {
        "HIGH": "🟢 HIGH",
        "MEDIUM": "🟡 MEDIUM",
        "MANUAL": "🔴 MANUAL",
    }
    return mapping.get(level, "❓ 未知")


def _status_icon(status: str) -> str:
    """验证状态 → 图标。"""
    mapping = {
        "正常": "✅",
        "缺值": "❌",
        "超范围": "⚠️",
    }
    return mapping.get(status, "❓")


# ============================================================================
# 段落数据卡片渲染
# ============================================================================


def _find_trace(
    field_name: str, trace_report: TraceReport
) -> Optional[CellTrace]:
    """在 TraceReport 中查找字段的 CellTrace。"""
    for trace in trace_report.traces:
        if trace.field_name == field_name:
            return trace
    return None


def _render_evidence_panel(
    trace: CellTrace,
    adapted_data: Dict[str, Any],
    field_name: str,
) -> None:
    """渲染单个字段的证据链面板。

    证据链：Excel 单元格 → 原始值 → 换算 → 校验
    """
    evidence_lines = [
        f"📍 **来源**: {trace.sheet_name} → `{trace.cell_ref}`",
        f"📐 **原始值**: {trace.value_display} {trace.unit}",
        f"✅ **校验**: {trace.validation_detail}",
    ]

    # 尝试找换算后的值
    adapted_val = _find_adapted_value(field_name, adapted_data)
    if adapted_val is not None:
        evidence_lines.insert(
            2, f"🔄 **换算后**: {adapted_val} (÷10,000 或 ×100)"
        )

    st.markdown("\n".join(evidence_lines))


def _find_adapted_value(
    field_name: str, adapted_data: Dict[str, Any]
) -> Optional[float]:
    """尝试在 adapted_data 中查找换算后的值。

    优先查找 group_total / by_category 中的对应字段。
    """
    # 从 _flat_data 直接查找
    flat = adapted_data.get("_flat_data", {})
    if field_name in flat and flat[field_name] is not None:
        return flat[field_name]

    # 从顶层查找
    if field_name in adapted_data and isinstance(
        adapted_data[field_name], (int, float)
    ):
        return float(adapted_data[field_name])

    return None


def _render_slot_ref_detail(
    ref: SlotDataRef,
    trace_report: TraceReport,
    adapted_data: Dict[str, Any],
    key_prefix: str,
) -> None:
    """渲染单个槽位引用的详细信息。"""
    if ref.slot_type == "reason_text":
        st.markdown(
            f"📝 **{ref.slot_name}** — 原因文本（来自汇总表 H/T 列）"
        )
        if ref.notes:
            st.caption(f"说明: {ref.notes}")
        return

    if ref.slot_type == "unknown":
        st.markdown(f"❓ **{ref.slot_name}** — 未分类槽位")
        return

    # numeric_field: 显示每个解析到的字段值
    for i, field_name in enumerate(ref.resolved_fields):
        trace = _find_trace(field_name, trace_report)
        if trace is None:
            st.markdown(f"- `{field_name}` — 未找到溯源记录")
            continue

        icon = _status_icon(trace.validation_status)
        cell_info = f"`{trace.cell_ref}`" if trace.cell_ref else "—"
        value_str = (
            f"{trace.value_display} {trace.unit}" if trace.value is not None else "—"
        )

        # 证据链展开器
        expander_key = f"{key_prefix}_{ref.slot_name}_{i}"
        label = f"{icon} `{field_name}` = {value_str} ({cell_info})"
        with st.expander(label):
            _render_evidence_panel(trace, adapted_data, field_name)


def render_paragraph_card(
    para: ParagraphTrace,
    trace_report: TraceReport,
    adapted_data: Dict[str, Any],
    key_prefix: str,
) -> None:
    """渲染单个段落的数据卡片。

    卡片结构：
        标题行: P{index} · placeholder · level · polish
        预览文本（如有）
        数据字段列表（可展开证据链）
        原因文本列表
        fallback 文本（如有）
    """
    # 标题行
    polish_icon = "✏️" if para.polish_required else "✅"
    level_badge = _level_badge(para.automation_level)
    title = f"P{para.v4_index} · {para.placeholder} · {level_badge} · {polish_icon}"

    with st.expander(title):
        # 预览文本
        if para.preview:
            st.markdown(f"> {para.preview}")

        # 按类型分组展示 data_refs
        numeric_refs = [r for r in para.data_refs if r.slot_type == "numeric_field"]
        reason_refs = [r for r in para.data_refs if r.slot_type == "reason_text"]
        unknown_refs = [r for r in para.data_refs if r.slot_type == "unknown"]

        if numeric_refs:
            st.markdown("**📊 数据字段**")
            for ref in numeric_refs:
                _render_slot_ref_detail(
                    ref, trace_report, adapted_data, f"{key_prefix}_num"
                )

        if reason_refs:
            st.markdown("**📝 原因来源**")
            for ref in reason_refs:
                _render_slot_ref_detail(
                    ref, trace_report, adapted_data, f"{key_prefix}_reason"
                )

        if unknown_refs:
            st.markdown("**❓ 未分类**")
            for ref in unknown_refs:
                _render_slot_ref_detail(
                    ref, trace_report, adapted_data, f"{key_prefix}_unknown"
                )

        if not para.data_refs:
            st.info("该段落为纯数据驱动生成，无预定义槽位映射")

        # fallback 文本
        if para.fallback_text:
            st.markdown(f"🔄 **Fallback**: {para.fallback_text}")

        # 备注
        if para.notes:
            st.caption(f"💡 {para.notes}")


# ============================================================================
# 行动项渲染
# ============================================================================


def render_action_items(
    paragraph_traces: List[ParagraphTrace],
    trace_report: TraceReport,
) -> None:
    """渲染待处理行动项列表。

    按严重程度分组：
        ❌ 缺失字段 → 受影响段落
        ⚠️ 超范围字段 → 建议确认
    """
    missing_items, out_of_range_items = detect_action_items(
        trace_report, paragraph_traces
    )

    if not missing_items and not out_of_range_items:
        st.success("✅ 所有字段已正常采集，无待处理事项")
        return

    st.subheader("📋 待处理事项")

    # 缺失字段
    for item in missing_items:
        paras_str = ", ".join(f"P{p}" for p in item["affected_paragraphs"])
        impact = f"→ 影响 {paras_str}" if paras_str else "→ 无段落直接引用"
        st.error(
            f"❌ **{item['description_zh']}** ({item['cell_ref']}) 缺失 {impact}"
        )

    # 超范围字段
    for item in out_of_range_items:
        paras_str = ", ".join(f"P{p}" for p in item["affected_paragraphs"])
        impact = f"→ 影响 {paras_str}" if paras_str else "→ 无段落直接引用"
        st.warning(
            f"⚠️ **{item['description_zh']}** = {item.get('value', '?')} "
            f"{item.get('unit', '')} ({item['cell_ref']}) 超出合理范围 {impact}"
        )


# ============================================================================
# 过滤辅助
# ============================================================================


def _filter_paragraphs(
    paragraph_traces: List[ParagraphTrace],
    level_filter: List[str],
    search_text: str,
) -> List[ParagraphTrace]:
    """按自动化等级和搜索文本过滤段落。"""
    result = paragraph_traces

    if level_filter:
        result = [p for p in result if p.automation_level in level_filter]

    if search_text:
        text_lower = search_text.lower()
        result = [
            p
            for p in result
            if text_lower in p.placeholder.lower()
            or text_lower in p.preview.lower()
            or text_lower in str(p.v4_index)
        ]

    return result


# ============================================================================
# 主入口
# ============================================================================


def render_report_sandbox(
    paragraph_traces: List[ParagraphTrace],
    trace_report: TraceReport,
    adapted_data: Dict[str, Any],
    key: str = "sandbox",
) -> None:
    """渲染报告沙盘主视图。

    包含：
        - 过滤控件
        - 15 个段落卡片
        - 行动项列表

    Args:
        paragraph_traces: 段落级溯源列表
        trace_report: 字段级溯源报告
        adapted_data: 适配后的完整数据字典
        key: Streamlit key 前缀
    """
    if not paragraph_traces:
        st.info("📭 暂无段落映射数据，请先加载 reason_map.json")
        return

    # 过滤控件
    st.subheader("📄 报告数据预览")
    col1, col2 = st.columns([1, 2])
    with col1:
        level_filter = st.multiselect(
            "自动化等级",
            options=["HIGH", "MEDIUM", "MANUAL"],
            default=[],
            key=f"{key}_level_filter",
        )
    with col2:
        search_text = st.text_input(
            "搜索段落",
            placeholder="输入段落编号、占位符或关键词...",
            key=f"{key}_search",
        )

    # 过滤
    filtered = _filter_paragraphs(paragraph_traces, level_filter, search_text)
    st.caption(f"共 {len(paragraph_traces)} 个段落，当前显示 {len(filtered)} 个")

    # 渲染段落卡片
    for para in sorted(filtered, key=lambda p: p.v4_index):
        render_paragraph_card(
            para,
            trace_report,
            adapted_data,
            key_prefix=f"{key}_p{para.v4_index}",
        )

    st.divider()

    # 行动项
    render_action_items(paragraph_traces, trace_report)
