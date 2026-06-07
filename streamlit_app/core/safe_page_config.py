"""零依赖的 safe_set_page_config 工具。

为什么独立模块：
    - 各 pages 脚本必须在第一个 st 命令之前导入
    - data_bridge.py 较重（有 hashlib / streamlit / logger 等依赖）
    - 单独模块可以最早导入，不影响 set_page_config 性能

用法：
    from streamlit_app.core.safe_page_config import safe_set_page_config
    safe_set_page_config(page_title="...", page_icon="...", layout="wide")
"""
from __future__ import annotations

import logging
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)


def safe_set_page_config(**kwargs: Any) -> None:
    """安全调用 st.set_page_config（避免与 app.py 重复调用冲突）。

    只吞 "重复调用" 错误，其他异常照常抛出。

    Args:
        **kwargs: 透传给 st.set_page_config 的参数
            （page_title / page_icon / layout / initial_sidebar_state / menu_items）

    Examples:
        >>> safe_set_page_config(page_title="数据驾驶舱", page_icon="📊", layout="wide")
    """
    try:
        st.set_page_config(**kwargs)
    except Exception as e:
        error_name = type(e).__name__
        # 只吞 streamlit 的 set_page_config 重复调用错误
        if "StreamlitSetPageConfig" in error_name or "SetPageConfig" in str(e):
            logger.debug("set_page_config 已被 app.py 设置过: %s", e)
            return
        # 其他异常照常抛出
        raise
