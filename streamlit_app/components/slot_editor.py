"""段位编辑器组件 - 核心交互

设计原则：
    1. 一站式：单段位所有操作在一个 panel 内（数据/参数/输出/编辑/反馈）
    2. 实时反馈：所有按钮即时显示结果
    3. 多模式：支持 extract / grounded_category / fallback 切换
    4. 调参：温度、模型、prompt 模板可调
    5. 反馈环：编辑后自动写入 corrections 库

使用：
    from streamlit_app.components.slot_editor import render_slot_editor

    render_slot_editor(
        slot_id="dom.elec.yoy.changjiang",
        placeholder="{{ v4_P6_dom_elec_yoy_wow }}",
        raw_text="...",
        llm_output="...",
        generation_mode="extract",
        automation_level="HIGH",
        ...
    )
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

import streamlit as st

from streamlit_app.core import (
    CorrectionsStore,
    LLMCallParams,
    LLMOrchestrator,
    PolishedSlot,
    get_corrections_store,
    get_orchestrator,
)
from streamlit_app.core.corrections_store import Correction
from streamlit_app.components.diff_viewer import render_diff_inline

logger = logging.getLogger(__name__)


# ============================================================================
# 辅助函数
# ============================================================================

def _get_quality_badges(slot: PolishedSlot) -> List[str]:
    """生成质量徽章列表。"""
    badges = []
    if slot.is_edited_by_human:
        badges.append("✏️ 人工编辑")
    if slot.polished:
        badges.append(f"🤖 {slot.model_used}")
    elif slot.llm_output is None:
        badges.append("⏭️ 未润色")
    if slot.is_fallback:
        badges.append("🔄 Fallback")
    if slot.error:
        badges.append(f"⚠️ {slot.error[:20]}")
    return badges


def _get_mode_description(mode: str) -> str:
    """生成模式描述。"""
    return {
        "extract": "📥 提取模式：从 Excel 原始文本提取（可 LLM 润色）",
        "grounded_category": "🎯 品类生成：基于数据 + LLM 生成（防幻觉）",
        "fallback": "🔄 Fallback：使用预设文本",
    }.get(mode, mode)


# ============================================================================
# 调参面板
# ============================================================================

def render_params_panel(
    default_params: LLMCallParams,
    key: str = "params",
) -> LLMCallParams:
    """渲染 LLM 调参面板（折叠式）。

    Returns:
        用户调整后的 LLMCallParams
    """
    with st.expander("⚙️ 调参面板（高级）", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            temperature = st.slider(
                "🌡️ 温度（创造性）",
                min_value=0.0,
                max_value=2.0,
                value=default_params.temperature,
                step=0.1,
                key=f"{key}_temperature",
                help="0=完全确定，2=非常随机",
            )
            max_tokens = st.slider(
                "📏 最大 Token",
                min_value=50,
                max_value=2000,
                value=default_params.max_tokens,
                step=50,
                key=f"{key}_max_tokens",
            )

        with col2:
            use_few_shot = st.checkbox(
                "💡 启用 Few-shot（从历史编辑学习）",
                value=default_params.use_few_shot,
                key=f"{key}_use_few_shot",
                help="启用后会自动从 corrections 库拉取历史编辑作为示例",
            )
            model_name = st.text_input(
                "🤖 模型名（留空用默认）",
                value=default_params.model_name or "",
                key=f"{key}_model_name",
                help="如：qwen3.5-plus / claude-sonnet-4-6",
            )

        with st.expander("🛠️ 自定义 Prompt（可选）", expanded=False):
            custom_system = st.text_area(
                "System Prompt",
                value=default_params.custom_system_prompt or "",
                height=100,
                key=f"{key}_custom_system",
                help="覆盖默认 system prompt（高级）",
            )
            custom_user = st.text_area(
                "User Prompt（{raw_text} 会被替换为原始文本）",
                value=default_params.custom_user_prompt or "",
                height=100,
                key=f"{key}_custom_user",
            )

        return LLMCallParams(
            temperature=temperature,
            max_tokens=max_tokens,
            model_name=model_name if model_name else None,
            use_few_shot=use_few_shot,
            custom_system_prompt=custom_system if custom_system else None,
            custom_user_prompt=custom_user if custom_user else None,
        )


# ============================================================================
# 主编辑器
# ============================================================================

def render_slot_editor(
    slot_id: str,
    placeholder: str,
    raw_text: str,
    llm_output: Optional[str] = None,
    final_text: str = "",
    generation_mode: str = "extract",
    automation_level: str = "MEDIUM",
    is_edited_by_human: bool = False,
    tokens_used: int = 0,
    model_used: str = "none",
    is_fallback: bool = False,
    error: Optional[str] = None,
    orchestrator: Optional[LLMOrchestrator] = None,
    corrections_store: Optional[CorrectionsStore] = None,
    on_state_change: Optional[Callable[[], None]] = None,
    key: str = "slot_editor",
) -> Optional[PolishedSlot]:
    """渲染单段位编辑器（核心组件）。

    Returns:
        更新后的 PolishedSlot（如果用户操作），否则 None
    """
    orch = orchestrator or get_orchestrator()
    store = corrections_store or get_corrections_store()

    # === Header ===
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(f"### 🎯 段位：`{slot_id}`")
        st.caption(f"占位符：`{placeholder}`")
    with col2:
        st.markdown(_get_mode_description(generation_mode))
    with col3:
        # 状态徽章
        badges = []
        if is_edited_by_human:
            badges.append("✏️ 已编辑")
        if llm_output is not None:
            badges.append(f"🤖 {model_used}")
        if is_fallback:
            badges.append("🔄 Fallback")
        for b in badges:
            st.markdown(f"`{b}`")

    # === Token 统计 + 错误提示 ===
    if tokens_used > 0 or error:
        info_col1, info_col2 = st.columns(2)
        with info_col1:
            if tokens_used > 0:
                st.caption(f"🔢 Token 消耗: **{tokens_used}**")
        with info_col2:
            if error:
                st.caption(f"⚠️ {error}")

    st.divider()

    # === 原始数据块（只读）===
    with st.expander("📊 原始数据 / 提取文本", expanded=False):
        st.text_area(
            "原始文本",
            value=raw_text,
            height=120,
            disabled=True,
            key=f"{key}_raw",
            label_visibility="collapsed",
        )

    # === LLM 输出 + 编辑（核心交互）===
    if llm_output is not None and not is_fallback:
        # 有 LLM 输出 → 显示 diff + 编辑
        edited_text, _ = render_diff_inline(
            original=raw_text,
            polished=llm_output,
            key=f"{key}_diff",
        )
    else:
        # 无 LLM 输出 → 直接编辑
        edited_text = st.text_area(
            "📝 文本编辑" + ("（已 fallback，可直接编辑）" if is_fallback else "（暂无 LLM 输出）"),
            value=final_text or raw_text,
            height=200,
            key=f"{key}_edit",
        )

    # === 调参面板 ===
    params = render_params_panel(LLMCallParams(), key=key)

    st.divider()

    # === 操作按钮 ===
    btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)

    updated_slot: Optional[PolishedSlot] = None

    with btn_col1:
        if st.button(
            "🔄 重新润色",
            key=f"{key}_repolish",
            use_container_width=True,
            help="用当前参数重新调用 LLM",
        ):
            with st.spinner("🤖 LLM 润色中..."):
                result = orch.polish(
                    raw_text=raw_text,
                    slot_id=slot_id,
                    params=params,
                )
            new_slot = PolishedSlot(
                slot_id=slot_id,
                placeholder=placeholder,
                raw_text=raw_text,
                llm_output=result.polished_text if not result.is_fallback else None,
                final_text=result.polished_text if not result.is_fallback else raw_text,
                is_edited_by_human=False,
                generation_mode=generation_mode,
                automation_level=automation_level,
                tokens_used=result.tokens_used,
                model_used=result.model_used,
                is_fallback=result.is_fallback,
                error=result.error,
            )
            if on_state_change:
                on_state_change()
            st.success(f"✅ 润色完成（{result.tokens_used} tokens）")
            updated_slot = new_slot
            st.rerun()

    with btn_col2:
        if st.button(
            "⏭️ 跳过润色",
            key=f"{key}_skip",
            use_container_width=True,
            help="使用原始文本（不调 LLM）",
        ):
            new_slot = PolishedSlot(
                slot_id=slot_id,
                placeholder=placeholder,
                raw_text=raw_text,
                llm_output=None,
                final_text=raw_text,
                is_edited_by_human=False,
                generation_mode="fallback",
                automation_level="MANUAL",
                tokens_used=0,
                model_used="skipped",
                is_fallback=True,
            )
            if on_state_change:
                on_state_change()
            st.info("⏭️ 已跳过润色")
            updated_slot = new_slot
            st.rerun()

    with btn_col3:
        if st.button(
            "💾 保存编辑",
            key=f"{key}_save",
            use_container_width=True,
            type="primary",
            help="保存当前编辑到 final_text",
        ):
            new_slot = PolishedSlot(
                slot_id=slot_id,
                placeholder=placeholder,
                raw_text=raw_text,
                llm_output=llm_output,
                final_text=edited_text,
                is_edited_by_human=True,
                generation_mode=generation_mode,
                automation_level=automation_level,
                tokens_used=tokens_used,
                model_used=model_used,
                is_fallback=is_fallback,
                error=error,
            )
            if on_state_change:
                on_state_change()
            st.success(f"✅ 编辑已保存（{len(edited_text)} 字）")
            updated_slot = new_slot
            st.rerun()

    with btn_col4:
        if st.button(
            "📚 反馈到训练数据",
            key=f"{key}_feedback",
            use_container_width=True,
            help="把本次编辑存入 corrections 库（用于未来训练）",
        ):
            if not edited_text or edited_text == raw_text:
                st.warning("⚠️ 编辑内容与原文相同，未保存到训练数据")
            else:
                correction = Correction(
                    slot_id=slot_id,
                    placeholder=placeholder,
                    original_raw=raw_text,
                    llm_output=llm_output,
                    human_edited=edited_text,
                    quality_score=None,
                    model_used=model_used,
                    generation_mode=generation_mode,
                )
                store.save(correction)
                st.success(f"📚 已保存到训练数据（累计 {store.count(slot_id)} 条）")

    # === 训练数据统计 ===
    history = store.load_for_slot(slot_id)
    if history:
        st.caption(
            f"📚 训练数据：本段位已有 {len(history)} 条人工修正"
        )

    return updated_slot
