"""LLM 原文/润色对比组件

设计原则：
    1. 并排对比：左侧原文（不可编辑），右侧润色后（可编辑）
    2. 高亮差异：变化的部分用颜色标记
    3. 数字标记：所有数字单独高亮，便于核对
    4. 紧凑布局：不超过 2/3 屏幕高度

使用：
    from streamlit_app.components.diff_viewer import render_diff

    new_text = render_diff(
        original=raw_text,
        polished=llm_output,
        editable=True,
        key="my_diff",
    )
"""
from __future__ import annotations

import difflib
import re
from typing import Optional, Tuple

import streamlit as st


# 数字正则（整数、小数、负数、百分比）
NUMBER_PATTERN = re.compile(r"-?\d+\.?\d*%?")


def extract_numbers(text: str) -> list[str]:
    """提取文本中所有数字。"""
    return NUMBER_PATTERN.findall(text)


def highlight_numbers(text: str) -> str:
    """在文本中标记所有数字为黄色背景。"""
    def repl(m: re.Match) -> str:
        n = m.group(0)
        return f'<span style="background: #fff3cd; color: #856404; padding: 1px 4px; border-radius: 3px; font-weight: bold;">{n}</span>'
    return NUMBER_PATTERN.sub(repl, text)


def compute_diff_stats(original: str, polished: str) -> dict:
    """计算原文/润色后差异统计。"""
    if not original or not polished:
        return {
            "similarity": 0.0,
            "added_chars": 0,
            "removed_chars": 0,
            "added_numbers": 0,
            "removed_numbers": 0,
        }

    # 字符相似度（SequenceMatcher）
    matcher = difflib.SequenceMatcher(None, original, polished)
    similarity = matcher.ratio()

    # 数字差异
    orig_nums = set(extract_numbers(original))
    polish_nums = set(extract_numbers(polished))
    added_numbers = polish_nums - orig_nums
    removed_numbers = orig_nums - polish_nums

    return {
        "similarity": similarity,
        "added_chars": len(polished) - len(original),
        "added_numbers": sorted(added_numbers),
        "removed_numbers": sorted(removed_numbers),
        "preserved_numbers": sorted(orig_nums & polish_nums),
    }


def render_diff(
    original: str,
    polished: str,
    editable: bool = True,
    key: str = "diff",
    label: str = "📝 编辑润色结果",
    height: int = 250,
) -> str:
    """渲染原文/润色对比。

    Args:
        original: 原始文本（不可编辑）
        polished: LLM 润色后文本（可编辑）
        editable: 是否允许编辑右侧
        key: Streamlit 组件 key
        label: 标签文字
        height: textarea 高度

    Returns:
        用户编辑后的文本（如果 editable=True）
    """
    col_left, col_right = st.columns(2)

    with col_left:
        st.caption("📄 原始文本（不可编辑）")
        st.markdown(
            f"""
            <div style="
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 12px;
                font-size: 13px;
                line-height: 1.6;
                max-height: {height}px;
                overflow-y: auto;
            ">
                {highlight_numbers(original)}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_right:
        st.caption(label)
        if editable:
            edited = st.text_area(
                label=label,
                value=polished,
                height=height,
                key=key,
                label_visibility="collapsed",
            )
            return edited
        else:
            st.markdown(
                f"""
                <div style="
                    background: #d4edda;
                    border: 1px solid #c3e6cb;
                    border-radius: 6px;
                    padding: 12px;
                    font-size: 13px;
                    line-height: 1.6;
                    max-height: {height}px;
                    overflow-y: auto;
                ">
                    {highlight_numbers(polished)}
                </div>
                """,
                unsafe_allow_html=True,
            )
            return polished


def render_diff_summary(
    original: str,
    polished: str,
    key: str = "diff_summary",
) -> None:
    """渲染差异统计信息（紧贴在 diff 下方）。"""
    stats = compute_diff_stats(original, polished)

    cols = st.columns(5)
    cols[0].metric("字符相似度", f"{stats['similarity']:.0%}")
    cols[1].metric(
        "字符数变化",
        f"{stats['added_chars']:+d}",
        delta=f"{stats['added_chars']:+d}",
    )
    cols[2].metric(
        "新增数字",
        len(stats["added_numbers"]),
        delta=None,
        delta_color="inverse" if stats["added_numbers"] else "off",
    )
    cols[3].metric(
        "缺失数字",
        len(stats["removed_numbers"]),
        delta=None,
        delta_color="inverse" if stats["removed_numbers"] else "off",
    )
    cols[4].metric("保留数字", len(stats["preserved_numbers"]))

    # 警告
    if stats["added_numbers"]:
        st.warning(
            f"⚠️ LLM 新增了 {len(stats['added_numbers'])} 个原文未有的数字："
            f"{', '.join(stats['added_numbers'][:5])}"
            + ("..." if len(stats["added_numbers"]) > 5 else "")
        )
    if stats["removed_numbers"]:
        st.warning(
            f"⚠️ LLM 删除了 {len(stats['removed_numbers'])} 个原文有的数字："
            f"{', '.join(stats['removed_numbers'][:5])}"
            + ("..." if len(stats["removed_numbers"]) > 5 else "")
        )


def render_diff_inline(
    original: str,
    polished: str,
    key: str = "diff_inline",
) -> Tuple[str, dict]:
    """一体化渲染：上面 diff 视图 + 下面统计 + 编辑框。

    Returns:
        (edited_text, stats)
    """
    edited = render_diff(original, polished, editable=True, key=key)
    render_diff_summary(original, polished, key=f"{key}_summary")
    return edited, compute_diff_stats(original, edited)
