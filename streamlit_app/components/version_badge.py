"""v2/v3 视觉徽章 + 跨版本跳转。

设计原则：
    1. 一眼区分：v3 用紫色渐变（生产试用），v2 用绿色（稳定）
    2. 不干扰：徽章小而精，不抢主标题
    3. 跨版本引导：底部放置跳转链接
"""
from __future__ import annotations

from typing import Optional

import streamlit as st


# === 徽章 HTML 模板 ===

V3_BADGE_HTML = """
<div style="
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 6px 14px;
    border-radius: 6px;
    margin-bottom: 12px;
    display: inline-block;
    font-size: 13px;
    box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
">
    🆕 <b>v3.0 驾驶舱</b> · 生产试用版
</div>
"""

V2_BADGE_HTML = """
<div style="
    background: #d4edda;
    color: #155724;
    padding: 6px 14px;
    border-radius: 6px;
    margin-bottom: 12px;
    display: inline-block;
    font-size: 13px;
    border: 1px solid #c3e6cb;
">
    ✅ <b>v2.0 分析平台</b> · 稳定版
</div>
"""

V3_HEADER_GRADIENT = """
<style>
    h1 {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }}
</style>
"""


# ============================================================================
# 徽章渲染
# ============================================================================

def render_version_badge(version: str) -> None:
    """在页面顶部渲染版本徽章。

    Args:
        version: "v2" 或 "v3"
    """
    if version == "v3":
        st.markdown(V3_BADGE_HTML, unsafe_allow_html=True)
    elif version == "v2":
        st.markdown(V2_BADGE_HTML, unsafe_allow_html=True)


def render_v3_title_gradient() -> None:
    """为 v3 页面主标题添加紫色渐变（可选美化）。"""
    st.markdown(V3_HEADER_GRADIENT, unsafe_allow_html=True)


# ============================================================================
# 跨版本跳转
# ============================================================================

def render_cross_version_link(
    current: str,
    target_version: Optional[str] = None,
    target_page: Optional[str] = None,
    label: Optional[str] = None,
) -> None:
    """渲染跨版本跳转链接。

    Args:
        current: 当前版本（"v2" 或 "v3"）
        target_version: 目标版本（默认反向）
        target_page: 目标页面 ID
        label: 自定义提示文字
    """
    if target_version is None:
        target_version = "v2" if current == "v3" else "v3"

    from streamlit_app.core.version_router import get_switch_url
    url = get_switch_url(target_version, target_page)

    if label is None:
        if target_version == "v3":
            label = "🆕 想要逐段编辑 + 调参？试试 v3 驾驶舱"
        else:
            label = "💡 想用稳定的 v2 平台分析？"

    st.info(f"{label} [立即跳转]({url})")


def render_switch_button(current: str) -> None:
    """渲染跨版本切换按钮（更显眼的 CTA）。"""
    from streamlit_app.core.version_router import set_version, switch_to_version

    col1, col2 = st.columns([3, 1])
    with col2:
        if current == "v3":
            if st.button("📦 切到 v2 稳定版", use_container_width=True):
                switch_to_version("v2")
        else:
            if st.button(
                "🆕 体验 v3 驾驶舱",
                use_container_width=True,
                type="primary",
            ):
                switch_to_version("v3")


# ============================================================================
# 主页用组件
# ============================================================================

def render_home_hero(current: str) -> None:
    """渲染主页 hero 区（标题 + 简介 + 切换 CTA）。"""
    render_version_badge(current)

    if current == "v3":
        st.title("📊 周报分析平台")
        st.markdown("""
        ### 🎯 v3.0 驾驶舱（生产试用版）

        **7 步交互流程**：
        1️⃣ **数据采集** — Excel → 186 字段预览
        2️⃣ **槽位映射** — 15 个 ReasonSlot 映射规则
        3️⃣ **槽位提取** — 从汇总表提取原始文本
        4️⃣ **LLM 润色** — 调参 + 多 Provider
        5️⃣ **人工编辑** — 逐段审阅 + 反馈到训练数据
        6️⃣ **模板渲染** — 生成 docx
        7️⃣ **审计日志** — Token 统计 + 修正样本库

        **核心特性**：
        - ✏️ **人机协同**：管理员能 100% 控制每段报告
        - 🎛️ **LLM 调参**：温度/模型/Prompt 模板可即时调整
        - 📚 **反馈环**：人工修正自动沉淀为训练数据
        - 🛡️ **防幻觉**：4 重检测（数字/长度/禁词/专业度）
        """)
    else:
        st.title("📊 周报分析平台")
        st.markdown("""
        ### 📦 v2.0 分析平台（稳定版）

        **4 维度分析**：
        - 🏠 **国内** — 段 1-2（89.1 亿度 / 0.311 元）
        - 🌍 **国际** — 段 3-4（0.32 元 / 能力动能）
        - 💹 **市场化** — 段 5-7（3 板块 / 东方不亮西方亮）
        - 🌱 **碳资产** — 段 8（4.94 亿家底 / 卖空气换钱）

        **导出选项**：
        - 📥 Markdown 报告下载
        - 📊 KPI / 异常 / 业务故事
        - 📋 4 维度自定义选择
        """)

    st.divider()
    render_switch_button(current)
