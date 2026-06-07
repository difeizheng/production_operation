"""7 步导航组件 - 顶部进度条

设计原则：
    1. 可视化进度：每步有 emoji + 状态颜色
    2. 可点击跳转：已完成步骤可点击，未完成步骤灰显
    3. 紧凑布局：7 步横向排列，不占过多空间
    4. 状态语义：pending / current / completed / error

用法：
    from streamlit_app.components.stepper import render_stepper

    render_stepper(
        current_step=3,
        steps=[
            ("数据上传", "上传 Excel"),
            ("数据预览", "186 字段"),
            ...
        ],
    )
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import streamlit as st


# 步骤图标
STEP_ICONS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]


def render_stepper(
    current_step: int,
    steps: List[Tuple[str, str]],
    on_step_click: Optional[callable] = None,
) -> None:
    """渲染 7 步导航。

    Args:
        current_step: 当前步骤（1-based）
        steps: 步骤列表 [(标题, 副标题), ...]
        on_step_click: 点击步骤时的回调函数，签名 (step_num: int) -> None
    """
    if not steps:
        return

    total = len(steps)
    cols = st.columns(total)

    for i, (title, subtitle) in enumerate(steps):
        step_num = i + 1
        with cols[i]:
            _render_step_cell(
                step_num=step_num,
                total=total,
                title=title,
                subtitle=subtitle,
                is_current=(step_num == current_step),
                is_completed=(step_num < current_step),
                on_click=(lambda n=step_num: on_step_click(n)) if on_step_click else None,
            )


def _render_step_cell(
    step_num: int,
    total: int,
    title: str,
    subtitle: str,
    is_current: bool,
    is_completed: bool,
    on_click: Optional[callable],
) -> None:
    """渲染单个步骤单元。"""
    icon = STEP_ICONS[step_num - 1] if step_num <= len(STEP_ICONS) else f"({step_num})"

    if is_current:
        # 当前步骤：高亮
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 12px 8px;
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            ">
                <div style="font-size: 24px;">{icon}</div>
                <div style="font-size: 13px; margin-top: 4px;">{title}</div>
                <div style="font-size: 10px; opacity: 0.85;">{subtitle}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif is_completed:
        # 已完成：绿色
        st.markdown(
            f"""
            <div style="
                background: #d4edda;
                color: #155724;
                padding: 12px 8px;
                border-radius: 8px;
                text-align: center;
                border: 1px solid #c3e6cb;
            ">
                <div style="font-size: 24px;">✅</div>
                <div style="font-size: 13px; margin-top: 4px;">{title}</div>
                <div style="font-size: 10px; opacity: 0.75;">{subtitle}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if on_click and st.button(
            f"↩️ 回到第 {step_num} 步",
            key=f"stepper_goto_{step_num}",
            use_container_width=True,
        ):
            on_click()
    else:
        # 未完成：灰色
        st.markdown(
            f"""
            <div style="
                background: #f8f9fa;
                color: #6c757d;
                padding: 12px 8px;
                border-radius: 8px;
                text-align: center;
                border: 1px solid #dee2e6;
            ">
                <div style="font-size: 24px; opacity: 0.4;">{icon}</div>
                <div style="font-size: 13px; margin-top: 4px;">{title}</div>
                <div style="font-size: 10px; opacity: 0.6;">{subtitle}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# 7 步管线的标准步骤定义
PIPELINE_STEPS: List[Tuple[str, str]] = [
    ("📊 数据采集", "Excel → 数据"),
    ("🧩 槽位映射", "加载映射"),
    ("📥 槽位提取", "提取原始文本"),
    ("🤖 LLM 润色", "调参 + 润色"),
    ("✏️ 人工编辑", "可编辑文本"),
    ("📄 模板渲染", "生成 Word"),
    ("📋 审计日志", "记录操作"),
]


def render_pipeline_stepper(current_step: int, on_step_click: Optional[callable] = None) -> None:
    """渲染标准的 7 步管线导航。"""
    render_stepper(
        current_step=current_step,
        steps=PIPELINE_STEPS,
        on_step_click=on_step_click,
    )
