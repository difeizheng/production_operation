"""🤖 生成驾驶舱 - Step 3-7: 7 步交互核心

功能（核心 - 4 个子步骤）：
    3.1: 槽位提取（ReasonCollector 提取原始文本）
    3.2: LLM 润色（ReasonResolver + 调参）
    3.3: 人工编辑（SlotEditor 逐段编辑）
    3.4: 模板渲染（ReportGenerator 生成 docx）

子步骤 3.3 是 ⭐ 最重要的交互：
    - 25 个段位列表（左侧）
    - 选中段位详情（右侧）：
      - 原始数据块
      - LLM 输出（可编辑）
      - 调参面板
      - 操作按钮: [重新润色] [跳过] [保存编辑] [反馈到训练数据]
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

# 路径设置
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# v3.1: 必须在第一个 st 命令之前导入
from streamlit_app.core.safe_page_config import safe_set_page_config

# === 页面配置 ===
safe_set_page_config(
    page_title="生成驾驶舱 - 周报 v3.0",
    page_icon="🤖",
    layout="wide",
)

# === 导入 ===
from src.generator.reason_resolver import ReasonResolver
from src.generator.report_generator_v2 import ReportGeneratorV2
from src.collector.reason_collector import ReasonCollector
from streamlit_app.core import (
    LLMOrchestrator,
    PolishedSlot,
    get_orchestrator,
    get_state_manager,
)
from streamlit_app.components import (
    render_pipeline_stepper,
    render_slot_editor,
)

logger = logging.getLogger(__name__)

def _on_step_click(state_mgr, n: int) -> None:
    """点击步骤导航时的回调。"""
    if 3 <= n <= 7:
        state_mgr.update_field(current_step=n)
        st.rerun()


# ============================================================================
# Step 3: 槽位提取
# ============================================================================

def _render_step_extract(state_mgr, state) -> None:
    """Step 3: 槽位提取（从 Excel 提取原始文本）。"""
    st.subheader("📥 Step 3: 槽位提取")
    st.caption("从 Excel 汇总表提取所有 15 个 ReasonSlot 的原始文本")

    # 检查汇总表路径
    if not state.summary_path:
        st.warning("⚠️ 未提供汇总表路径，将使用 fallback 模式")
        st.info("提示：可返回 Step 1 上传汇总表")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("""
        **提取流程**:
        1. 读取 `data/dictionaries/reason_map.json` 中所有 source_slots
        2. 用 `ReasonCollector.collect()` 从汇总表提取
        3. 缺失槽位标记为 `is_empty=True`
        4. 提取结果存入 `PipelineState.slot_results`
        """)

    with col2:
        if st.button("🚀 开始提取", type="primary", use_container_width=True):
            _do_extract(state_mgr, state)

    # 显示已提取结果
    if state.slot_results:
        st.divider()
        st.subheader("📊 提取结果")
        rows = []
        for slot_id, info in state.slot_results.items():
            rows.append({
                "槽位": slot_id,
                "状态": "✅ 已提取" if not info.get("is_empty") else "❌ 缺失",
                "文本长度": info.get("text_length", 0),
                "来源文件": info.get("source_file", ""),
            })
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        extracted = sum(1 for r in state.slot_results.values() if not r.get("is_empty"))
        empty = len(state.slot_results) - extracted
        st.metric("提取成功率", f"{extracted}/{len(state.slot_results)}", delta=f"-{empty} 缺失")

        st.divider()
        if st.button("➡️ 下一步：LLM 润色", type="primary"):
            state_mgr.update_field(current_step=4)
            st.rerun()


def _do_extract(state_mgr, state) -> None:
    """执行提取。"""
    with st.spinner("⏳ 提取中..."):
        try:
            collector = ReasonCollector()
            summary_file = state.summary_path
            if not summary_file or not Path(summary_file).exists():
                st.warning("⚠️ 无汇总表路径，将使用空提取")
                slot_results = {}
            else:
                slot_results, _ = collector.collect(summary_file)

            # 序列化为 dict
            serialized = {}
            for slot_id, result in slot_results.items():
                serialized[slot_id] = {
                    "raw_text": result.raw_text,
                    "is_empty": result.is_empty,
                    "source_file": result.source_file,
                    "text_length": len(result.raw_text),
                }

            state_mgr.update_field(slot_results=serialized)
            st.success(f"✅ 提取完成: {len(serialized)} 个槽位")
            st.rerun()
        except Exception as e:
            st.error(f"❌ 提取失败: {e}")


# ============================================================================
# Step 4: LLM 润色
# ============================================================================

def _render_step_polish(state_mgr, state) -> None:
    """Step 4: LLM 润色（批量调参）。"""
    st.subheader("🤖 Step 4: LLM 润色")
    st.caption("使用 ReasonResolver 批量润色所有 15 个段位")

    if not state.slot_results:
        st.warning("⚠️ 请先完成 Step 3 提取")
        st.stop()

    # 全局调参
    with st.expander("⚙️ 全局调参", expanded=False):
        from streamlit_app.core import LLMCallParams
        col1, col2 = st.columns(2)
        temperature = col1.slider("🌡️ 温度", 0.0, 2.0, 0.3, 0.1)
        max_tokens = col2.slider("📏 最大 Token", 50, 2000, 500, 50)
        use_few_shot = st.checkbox("💡 启用 Few-shot")

    st.divider()

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("""
        **润色规则**:
        - 只对 `polish_required=True` 且有原文的段位调用 LLM
        - `grounded_category` 模式使用数据驱动生成
        - 空文本/缺失数据自动 fallback
        - 4 重防幻觉（数字保留/禁词/长度/专业度）
        """)
    with col2:
        if st.button("🚀 开始批量润色", type="primary", use_container_width=True):
            _do_polish(state_mgr, state, temperature, max_tokens, use_few_shot)

    # 已润色结果
    if state.polished_slots:
        st.divider()
        st.subheader("📊 润色结果")
        rows = []
        for slot_id, slot in state.polished_slots.items():
            rows.append({
                "占位符": slot.placeholder,
                "模式": slot.generation_mode,
                "等级": slot.automation_level,
                "Token": slot.tokens_used,
                "模型": slot.model_used,
                "Fallback": "🔄" if slot.is_fallback else "",
                "错误": slot.error or "",
            })
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        total_tokens = sum(s.tokens_used for s in state.polished_slots.values())
        polished = sum(1 for s in state.polished_slots.values() if s.llm_output is not None)
        fallback = sum(1 for s in state.polished_slots.values() if s.is_fallback)
        col1, col2, col3 = st.columns(3)
        col1.metric("已润色", polished)
        col2.metric("Fallback", fallback)
        col3.metric("总 Token", total_tokens)

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ 上一步：提取", use_container_width=True):
                state_mgr.update_field(current_step=3)
                st.rerun()
        with col2:
            if st.button("➡️ 下一步：人工编辑", type="primary", use_container_width=True):
                state_mgr.update_field(current_step=5)
                st.rerun()


def _do_polish(state_mgr, state, temperature: float, max_tokens: int, use_few_shot: bool) -> None:
    """执行批量润色。"""
    from streamlit_app.core import LLMCallParams

    orch = get_orchestrator()
    params = LLMCallParams(
        temperature=temperature,
        max_tokens=max_tokens,
        use_few_shot=use_few_shot,
    )

    progress = st.progress(0.0, "开始润色...")
    polished: Dict[str, PolishedSlot] = {}

    for i, mapping in enumerate(state.mappings):
        placeholder = mapping["template_placeholder"]
        progress.progress(
            (i + 1) / len(state.mappings),
            f"润色中 ({i+1}/{len(state.mappings)}): {placeholder}",
        )

        # 构造上下文
        slot_results_for_mapping = {}
        for slot_id in mapping.get("source_slots", []):
            if slot_id in state.slot_results:
                from src.collector.reason_collector import ReasonResult, ReasonSlot
                # 简单重建
                raw_info = state.slot_results[slot_id]
                slot_results_for_mapping[slot_id] = type("R", (), {
                    "raw_text": raw_info["raw_text"],
                    "is_empty": raw_info["is_empty"],
                })()

        # 直接调用 ReasonResolver
        try:
            resolver = ReasonResolver(
                reason_map={"mappings": [mapping], "total_mappings": 1},
                data=state.raw_data,
            )
            # 构造 slot_results 简化版
            from src.collector.reason_collector import ReasonResult
            reason_results = {
                sid: ReasonResult(
                    slot=type("S", (), {"slot_id": sid})(),
                    raw_text=info["raw_text"],
                    source_file=info["source_file"],
                    is_empty=info["is_empty"],
                )
                for sid, info in state.slot_results.items()
            }
            segments = resolver.resolve_all(data=state.raw_data)
            for ph, seg in segments.items():
                polished[ph] = PolishedSlot(
                    slot_id=seg.placeholder,  # 用 placeholder 当 slot_id
                    placeholder=seg.placeholder,
                    raw_text=seg.raw_text,
                    llm_output=seg.final_text if seg.polished else None,
                    final_text=seg.final_text,
                    is_edited_by_human=False,
                    generation_mode=mapping.get("generation_mode", "extract"),
                    automation_level=seg.automation_level,
                    tokens_used=seg.tokens_used,
                    model_used="qwen" if seg.polished else "none",
                    is_fallback=seg.is_fallback,
                    error=seg.error,
                )
        except Exception as e:
            logger.error("润色失败 %s: %s", placeholder, e)
            polished[placeholder] = PolishedSlot(
                slot_id=placeholder,
                placeholder=placeholder,
                raw_text="",
                llm_output=None,
                final_text=mapping.get("fallback_text", "") or "",
                is_edited_by_human=False,
                generation_mode="fallback",
                automation_level="MANUAL",
                tokens_used=0,
                model_used="error",
                is_fallback=True,
                error=str(e),
            )

    state_mgr.update_field(polished_slots=polished)
    progress.empty()
    st.success(f"✅ 润色完成: {len(polished)} 个段位")
    st.rerun()


# ============================================================================
# Step 5: 人工编辑（⭐ 核心交互）
# ============================================================================

def _render_step_edit(state_mgr, state) -> None:
    """Step 5: 人工编辑（最核心）。"""
    st.subheader("✏️ Step 5: 人工编辑（核心）")
    st.caption("逐段位审阅、编辑、调参、反馈到训练数据")

    if not state.polished_slots:
        st.warning("⚠️ 请先完成 Step 4 润色")
        st.stop()

    # 段位列表（左侧）+ 段位详情（右侧）
    list_col, detail_col = st.columns([1, 2])

    with list_col:
        st.markdown("#### 📋 段位列表")
        # 按模式分类
        by_mode: Dict[str, List[PolishedSlot]] = {}
        for slot in state.polished_slots.values():
            mode = slot.generation_mode
            by_mode.setdefault(mode, []).append(slot)

        for mode, slots in by_mode.items():
            with st.expander(
                f"{mode} ({len(slots)})",
                expanded=(mode == "extract"),
            ):
                for slot in slots:
                    marker = ""
                    if slot.is_edited_by_human:
                        marker = "✏️"
                    elif slot.is_fallback:
                        marker = "🔄"
                    elif slot.llm_output is None:
                        marker = "⏭️"
                    else:
                        marker = "🤖"

                    button_label = f"{marker} {slot.placeholder}"
                    if st.button(
                        button_label,
                        key=f"slot_select_{slot.placeholder}",
                        use_container_width=True,
                    ):
                        st.session_state["_selected_slot"] = slot.placeholder

    with detail_col:
        selected_ph = st.session_state.get("_selected_slot")
        if not selected_ph or selected_ph not in state.polished_slots:
            # 默认选第一个
            selected_ph = next(iter(state.polished_slots.keys()), None)
            st.session_state["_selected_slot"] = selected_ph

        if selected_ph:
            slot = state.polished_slots[selected_ph]
            updated = render_slot_editor(
                slot_id=slot.placeholder,
                placeholder=slot.placeholder,
                raw_text=slot.raw_text,
                llm_output=slot.llm_output,
                final_text=slot.final_text,
                generation_mode=slot.generation_mode,
                automation_level=slot.automation_level,
                is_edited_by_human=slot.is_edited_by_human,
                tokens_used=slot.tokens_used,
                model_used=slot.model_used,
                is_fallback=slot.is_fallback,
                error=slot.error,
                key=f"edit_{selected_ph}",
                on_state_change=lambda: None,
            )
            if updated:
                state_mgr.upsert_polished_slot(updated)
                st.rerun()

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ 上一步：LLM 润色", use_container_width=True):
            state_mgr.update_field(current_step=4)
            st.rerun()
    with col2:
        if st.button("➡️ 下一步：模板渲染", type="primary", use_container_width=True):
            state_mgr.update_field(current_step=6)
            st.rerun()


# ============================================================================
# Step 6: 模板渲染
# ============================================================================

def _render_step_render(state_mgr, state) -> None:
    """Step 6: 模板渲染（生成 docx）。"""
    st.subheader("📄 Step 6: 模板渲染")
    st.caption("把 final_text 注入到 docxtpl 模板，生成 Word 报告")

    if not state.polished_slots:
        st.warning("⚠️ 请先完成 Step 5 编辑")
        st.stop()

    # 构造模板变量
    text_dict = {slot.placeholder: slot.final_text for slot in state.polished_slots.values()}
    st.success(f"✅ 已准备 {len(text_dict)} 个模板变量")

    with st.expander("📋 模板变量预览"):
        for ph, text in list(text_dict.items())[:5]:
            st.code(f"{ph} = {text[:100]}...", language="text")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("""
        **渲染说明**:
        - 模板: `data/templates/report_template_jinja.docx`
        - 变量: 所有 ReasonSlot.placeholder → final_text
        - 输出: `archive/<year>/<week>/<name>.docx`
        """)
    with col2:
        if st.button("🚀 生成 Word", type="primary", use_container_width=True):
            _do_render(state_mgr, state, text_dict)

    if state.docx_path:
        st.divider()
        st.success(f"✅ Word 已生成: {state.docx_path}")
        with open(state.docx_path, "rb") as f:
            st.download_button(
                "📥 下载 Word",
                f.read(),
                file_name=Path(state.docx_path).name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ 上一步：人工编辑", use_container_width=True):
            state_mgr.update_field(current_step=5)
            st.rerun()
    with col2:
        if st.button("➡️ 下一步：审计日志", type="primary", use_container_width=True):
            state_mgr.update_field(current_step=7)
            st.rerun()


def _do_render(state_mgr, state, text_dict: Dict[str, str]) -> None:
    """执行模板渲染。"""
    with st.spinner("⏳ 渲染中..."):
        try:
            template_path = project_root / "data" / "templates" / "report_template_jinja.docx"
            if not template_path.exists():
                st.error(f"❌ 模板不存在: {template_path}")
                return

            output_path = project_root / "archive" / "v3_interactive" / f"week{state.raw_data.get('meta', {}).get('week', 'unknown')}.docx"
            output_path.parent.mkdir(parents=True, exist_ok=True)

            generator = ReportGeneratorV2(template_path=str(template_path))
            generator.render(
                output_path=str(output_path),
                text_dict=text_dict,
                data=state.raw_data,
            )
            state_mgr.update_field(docx_path=str(output_path))
            st.success(f"✅ 渲染完成: {output_path.name}")
            st.rerun()
        except Exception as e:
            st.error(f"❌ 渲染失败: {e}")


# ============================================================================
# Step 7: 审计日志
# ============================================================================

def _render_step_audit(state_mgr, state) -> None:
    """Step 7: 审计日志。"""
    st.subheader("📋 Step 7: 审计日志")
    st.caption("本次生成的所有操作、编辑、Token 消耗记录")

    stats = state_mgr.get_stats()

    # 概览
    st.subheader("📊 统计概览")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("总段位数", stats["total_slots"])
    col2.metric("已润色", stats["polished_count"])
    col3.metric("已编辑", stats["edited_count"], delta="人工" if stats["edited_count"] else None)
    col4.metric("Fallback", stats["fallback_count"])
    col5.metric("总 Token", stats["total_tokens"])

    st.divider()

    # 等级分布
    if stats["by_level"]:
        st.subheader("🎯 自动化等级分布")
        col1, col2, col3 = st.columns(3)
        col1.metric("HIGH", stats["by_level"].get("HIGH", 0))
        col2.metric("MEDIUM", stats["by_level"].get("MEDIUM", 0))
        col3.metric("MANUAL", stats["by_level"].get("MANUAL", 0))
        st.metric("自动化率", f"{stats['automation_rate']:.0%}")

    st.divider()

    # 操作记录
    st.subheader("📝 段位详情")
    import pandas as pd
    rows = []
    for slot in state.polished_slots.values():
        rows.append({
            "占位符": slot.placeholder,
            "模式": slot.generation_mode,
            "等级": slot.automation_level,
            "润色": "✅" if slot.llm_output else "—",
            "编辑": "✏️" if slot.is_edited_by_human else "—",
            "Token": slot.tokens_used,
            "时间": slot.timestamp[:19] if slot.timestamp else "",
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()

    # 保存快照
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("💾 保存快照", use_container_width=True):
            path = state_mgr.save_snapshot()
            st.success(f"✅ 快照已保存: {path}")

    st.divider()
    if st.button("🔄 重新开始", use_container_width=True):
        state_mgr.reset()
        st.rerun()


# === Header ===
# v3.1: 版本徽章
from streamlit_app.core.version_router import get_current_version
from streamlit_app.components import render_version_badge
render_version_badge(get_current_version())

st.title("🤖 生成驾驶舱")
st.caption("Step 3-7/7 · 7 步交互核心（LLM 润色 + 人工编辑）")
st.divider()

state_mgr = get_state_manager()
state = state_mgr.get()

# === 顶部步骤导航 ===
sub_step = state.current_step if 3 <= state.current_step <= 7 else 3
render_pipeline_stepper(current_step=sub_step, on_step_click=lambda n: _on_step_click(state_mgr, n))

st.divider()

# === 检查前置条件 ===
if not state.raw_data or not state.mappings:
    st.warning("⚠️ 请先完成 Step 1（数据）+ Step 2（映射）")
    st.info("👈 请点击左侧菜单进入「📊 数据驾驶舱」")
    st.stop()

# === 子页面分发 ===
if sub_step == 3:
    _render_step_extract(state_mgr, state)
elif sub_step == 4:
    _render_step_polish(state_mgr, state)
elif sub_step == 5:
    _render_step_edit(state_mgr, state)
elif sub_step == 6:
    _render_step_render(state_mgr, state)
elif sub_step == 7:
    _render_step_audit(state_mgr, state)
else:
    st.error(f"❌ 未知步骤: {sub_step}")


# ============================================================================
# 回调
# ============================================================================

