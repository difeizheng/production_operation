"""质量段位详情表 - 每段 4 维分数 + 总分 + 警告

设计原则：
    1. pandas DataFrame 渲染（st.dataframe）
    2. 颜色编码通过 Styler.applymap（streamlit 1.41+ 支持）
    3. 每行末尾提供"跳到 Step 5 编辑"按钮（用 session_state 触发）
    4. 空数据友好降级
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _score_color(val: int) -> str:
    """根据分值返回 CSS 背景色。"""
    if val >= 80:
        return "background-color: #d4edda; color: #155724"  # 绿
    elif val >= 60:
        return "background-color: #fff3cd; color: #856404"  # 黄
    else:
        return "background-color: #f8d7da; color: #721c24"  # 红


def build_score_dataframe(
    metrics: Dict[str, Any],
    polished_slots: Dict[str, Any] | None = None,
) -> Any | None:
    """构造段位详情 DataFrame。

    列：占位符 | 数字 | 长度 | 禁词 | 专业 | 总分 | 警告
    """
    try:
        import pandas as pd
    except ImportError:
        return None

    if not metrics:
        return None

    rows = []
    for slot_id, m in metrics.items():
        # 占位符（优先从 polished_slots 找，否则用 slot_id）
        placeholder = slot_id
        if polished_slots and slot_id in polished_slots:
            placeholder = polished_slots[slot_id].placeholder or slot_id
        warnings_str = "; ".join(m.warnings) if m.warnings else ""
        rows.append({
            "占位符": placeholder,
            "数字(30)": 30 if m.numbers_consistency else 0,
            "长度(20)": 20 if m.length_reasonable else 0,
            "禁词(20)": 20 if m.no_forbidden_words else 0,
            "专业(20)": m.professionalism,
            "总分": m.overall_score,
            "警告": warnings_str,
        })

    df = pd.DataFrame(rows)
    # 按总分升序（差的在上）
    df = df.sort_values("总分", ascending=True).reset_index(drop=True)
    return df


def render_quality_score_table(
    metrics: Dict[str, Any],
    polished_slots: Dict[str, Any] | None = None,
    key: str = "quality_score_table",
) -> None:
    """Streamlit 渲染入口。"""
    import streamlit as st

    if not metrics:
        st.info("📭 暂无段位质量数据。")
        return

    df = build_score_dataframe(metrics, polished_slots)
    if df is None:
        st.warning("⚠️ pandas 不可用，无法渲染详情表")
        return

    # 颜色编码（仅对分数列）
    try:
        styled = df.style.applymap(
            _score_color,
            subset=["数字(30)", "长度(20)", "禁词(20)", "专业(20)", "总分"],
        )
        st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
            key=key,
        )
    except Exception:
        # 退化：直接渲染
        st.dataframe(df, use_container_width=True, hide_index=True, key=key)

    # 底部"跳到 Step 5 编辑"按钮
    st.divider()
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button(
            "📝 跳到 Step 5 编辑",
            key=f"{key}_jump_to_edit",
            use_container_width=True,
        ):
            from streamlit_app.core import get_state_manager
            state_mgr = get_state_manager()
            state_mgr.update_field(current_step=5)
            st.success("✅ 已切换到 Step 5，请刷新页面")
