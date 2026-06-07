"""URL 参数 + session_state 双层版本路由。

设计原则：
    1. URL 参数优先：?version=v2/v3 强制切换（用于深链分享）
    2. session_state 次之：用户上次选择被记住
    3. 默认 v3（生产试用）
    4. 提供侧边栏 radio 切换器

URL 同步：
    - set_version() 自动更新 query_params
    - 浏览器前进/后退按钮会触发页面重载
"""
from __future__ import annotations

import logging
from typing import Optional

import streamlit as st

logger = logging.getLogger(__name__)


# === 常量 ===
VERSION_KEY = "_active_version"
VALID_VERSIONS = ("v2", "v3")
DEFAULT_VERSION = "v3"

VERSION_LABELS = {
    "v3": "🆕 v3.0 驾驶舱（生产试用）",
    "v2": "✅ v2.0 分析平台（稳定版）",
}

VERSION_DESCRIPTIONS = {
    "v3": "人机协同驾驶舱：7 步交互 + 调参 + 反馈环",
    "v2": "4 维度分析 + Markdown 报告导出",
}


# ============================================================================
# 核心 API
# ============================================================================

def get_current_version() -> str:
    """从 URL 或 session_state 读取当前版本。

    优先级：URL 参数 > session_state > DEFAULT_VERSION

    Returns:
        "v2" 或 "v3"
    """
    # 1. 优先 URL 参数（深链）
    try:
        query = st.query_params
        url_version = query.get("version", "").lower()
        if url_version in VALID_VERSIONS:
            return url_version
    except Exception as e:
        logger.debug("URL 参数读取失败: %s", e)

    # 2. 其次 session_state（用户上次选择）
    if VERSION_KEY in st.session_state:
        cached = st.session_state[VERSION_KEY]
        if cached in VALID_VERSIONS:
            return cached

    # 3. 默认
    return DEFAULT_VERSION


def set_version(version: str, update_url: bool = True) -> None:
    """设置当前版本（同时同步到 URL 和 session_state）。

    Args:
        version: "v2" 或 "v3"
        update_url: 是否同步到 URL（默认 True）
    """
    if version not in VALID_VERSIONS:
        raise ValueError(f"Invalid version: {version}. Must be one of {VALID_VERSIONS}.")

    # 更新 session_state
    st.session_state[VERSION_KEY] = version

    # 同步到 URL
    if update_url:
        try:
            st.query_params["version"] = version
        except Exception as e:
            logger.debug("URL 更新失败: %s", e)

    logger.info("版本切换: %s", version)


def switch_to_version(version: str) -> None:
    """切换到指定版本（set_version + rerun 的便捷封装）。"""
    current = get_current_version()
    if current != version:
        set_version(version)
        st.rerun()


# ============================================================================
# UI 组件
# ============================================================================

def render_version_switcher() -> Optional[str]:
    """渲染侧边栏版本切换器。

    Returns:
        当前选中的版本（"v2" 或 "v3"），如果未渲染则返回 None
    """
    with st.sidebar:
        st.divider()
        st.markdown("### 🎯 版本选择")

        current = get_current_version()
        try:
            choice = st.radio(
                "选择版本",
                options=list(VALID_VERSIONS),
                format_func=lambda x: VERSION_LABELS[x],
                index=list(VALID_VERSIONS).index(current),
                key="_version_radio_widget",
                label_visibility="collapsed",
                help="v3 是新版（生产试用），v2 是稳定版",
            )
        except Exception as e:
            logger.warning("版本切换器渲染失败: %s", e)
            return current

        if choice != current:
            set_version(choice)
            st.rerun()

        # 显示当前版本描述
        st.caption(VERSION_DESCRIPTIONS.get(choice, ""))

        return choice


# ============================================================================
# 跨版本跳转辅助
# ============================================================================

def get_switch_url(target_version: str, target_page: Optional[str] = None) -> str:
    """构造跨版本跳转的 URL。

    Args:
        target_version: 目标版本（"v2" 或 "v3"）
        target_page: 目标页面（可选，如 "v2_1" / "v3_3"）

    Returns:
        URL 字符串
    """
    params = [f"version={target_version}"]
    if target_page:
        params.append(f"page={target_page}")
    return "?" + "&".join(params)


def render_cross_version_prompt(current: str) -> None:
    """在页面底部渲染跨版本提示（可选使用）。"""
    if current == "v3":
        st.info(
            f"💡 想用稳定的 v2 平台分析？ "
            f"[跳转到 v2 国内分析]({get_switch_url('v2', 'v2_1')})"
        )
    else:
        st.info(
            f"🆕 想要逐段编辑 + 调参？ "
            f"[试试 v3 驾驶舱]({get_switch_url('v3', 'v3_1')})"
        )
