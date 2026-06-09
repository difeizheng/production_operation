"""编辑历史对比组件 - 原文 vs LLM vs 人工编辑 diff 可视化

设计原则：
    1. 3 版本对比：raw_text → llm_output → final_text
    2. 用 difflib 计算 diff，高亮变更部分
    3. 编辑距离 + 相似度指标
    4. 空版本友好降级

使用：
    from streamlit_app.components.edit_history import render_edit_diff
    render_edit_diff(slot)
"""
from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# 数据类
# ============================================================================

@dataclass(frozen=True)
class DiffResult:
    """diff 计算结果。

    Attributes:
        old_text: 旧文本
        new_text: 新文本
        similarity: 相似度（0-1）
        added_chars: 新增字符数
        removed_chars: 删除字符数
        diff_lines: diff 行列表（用于渲染）
    """
    old_text: str
    new_text: str
    similarity: float
    added_chars: int
    removed_chars: int
    diff_lines: List[str]


# ============================================================================
# diff 计算
# ============================================================================

def compute_similarity(old: str, new: str) -> float:
    """计算两段文本的相似度（0-1）。

    使用 difflib.SequenceMatcher。
    """
    if not old and not new:
        return 1.0
    if not old or not new:
        return 0.0
    return difflib.SequenceMatcher(None, old, new).ratio()


def compute_diff(old: str, new: str, context_lines: int = 3) -> DiffResult:
    """计算两段文本的 diff。

    Args:
        old: 旧文本
        new: 新文本
        context_lines: 上下文行数

    Returns:
        DiffResult
    """
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)

    # 计算 diff
    diff = list(difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile="旧版本",
        tofile="新版本",
        n=context_lines,
    ))

    # 计算相似度
    similarity = compute_similarity(old, new)

    # 统计增删字符数
    added = sum(len(line[1:]) for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(len(line[1:]) for line in diff if line.startswith("-") and not line.startswith("---"))

    return DiffResult(
        old_text=old,
        new_text=new,
        similarity=round(similarity, 3),
        added_chars=added,
        removed_chars=removed,
        diff_lines=[line.rstrip() for line in diff],
    )


def compute_edit_chain(slot: Any) -> List[Tuple[str, str, DiffResult]]:
    """计算编辑链：raw → llm → final 的 2 次 diff。

    Returns:
        [(label, old, new, diff), ...]
    """
    chain: List[Tuple[str, str, DiffResult]] = []

    raw = slot.raw_text or ""
    llm = slot.llm_output or ""
    final = slot.final_text or ""

    # 1. raw → llm
    if llm:
        diff1 = compute_diff(raw, llm)
        chain.append(("raw → llm", raw, llm, diff1))

    # 2. llm → final（或 raw → final 如果无 llm）
    if final and final != (llm or raw):
        base = llm or raw
        diff2 = compute_diff(base, final)
        chain.append(("llm → final" if llm else "raw → final", base, final, diff2))

    return chain


# ============================================================================
# Streamlit 渲染
# ============================================================================

def render_diff_block(diff: DiffResult, label: str) -> None:
    """渲染单个 diff 块。

    Args:
        diff: DiffResult
        label: 标签（如 "raw → llm"）
    """
    import streamlit as st

    # 相似度徽章
    sim_pct = f"{diff.similarity * 100:.1f}%"
    if diff.similarity >= 0.8:
        badge_color = "green"
    elif diff.similarity >= 0.5:
        badge_color = "orange"
    else:
        badge_color = "red"

    st.markdown(f"#### {label} `相似度: {sim_pct}`")
    st.caption(f"+{diff.added_chars} 字符 / -{diff.removed_chars} 字符")

    # diff 渲染（用 code block）
    if diff.diff_lines:
        diff_text = "\n".join(diff.diff_lines[:50])  # 限制行数
        if len(diff.diff_lines) > 50:
            diff_text += f"\n... (省略 {len(diff.diff_lines) - 50} 行)"
        st.code(diff_text, language="diff")
    else:
        st.info("（无差异）")


def render_edit_diff(
    slot: Any,
    key: str = "edit_diff",
) -> None:
    """Streamlit 渲染入口：3 版本 diff 对比。

    Args:
        slot: PolishedSlot 实例
        key: Streamlit 组件唯一 key
    """
    import streamlit as st

    # 计算编辑链
    chain = compute_edit_chain(slot)

    if not chain:
        st.info("📭 无编辑历史（该段位未经润色或编辑）")
        return

    # 顶部：3 版本摘要
    st.subheader("📝 编辑历史")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📄 原文", f"{len(slot.raw_text or '')} 字")
    with col2:
        llm_len = len(slot.llm_output or "")
        st.metric("🤖 LLM 输出", f"{llm_len} 字" if llm_len else "—")
    with col3:
        final_len = len(slot.final_text or "")
        st.metric("✨ 最终文本", f"{final_len} 字")

    st.divider()

    # 逐个 diff 渲染
    for label, old, new, diff in chain:
        render_diff_block(diff, label)
        st.divider()

    # 底部：3 版本并排预览（前 200 字）
    st.subheader("👀 文本预览（前 200 字）")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**📄 原文**")
        st.code((slot.raw_text or "")[:200], language="text")
    with col2:
        st.markdown("**🤖 LLM**")
        st.code((slot.llm_output or "")[:200], language="text")
    with col3:
        st.markdown("**✨ 最终**")
        st.code((slot.final_text or "")[:200], language="text")
