"""
周报分析平台 - 主入口（v3.1 路由重构）
====================================

使用 Streamlit 1.41+ 的 st.navigation + st.Page 实现：
    - 侧边栏按版本分组（v2 稳定版 / v3 生产试用）
    - URL 参数 ?version=v2/v3 支持深链
    - 数据在 v2/v3 之间自动桥接

启动方式:
    PYTHONPATH=. streamlit run streamlit_app/app.py

设计文档:
    - v3.1 路由设计: docs/design/v3.1-menu-routing.md
    - v3.0 驾驶舱: docs/design/report-generator-v3-architecture.md
    - 业务图谱: docs/design/business-map-master.md
"""

import sys
from pathlib import Path

import streamlit as st

# === 路径设置 ===
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# === Streamlit 页面配置（必须在最前） ===
st.set_page_config(
    page_title="周报分析平台",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "周报自动化系统 v3.1 - 路由重构 + v2/v3 数据共享"
    },
)

# === 延迟导入（确保 set_page_config 已执行） ===
from streamlit_app.core.version_router import (
    get_current_version,
    render_version_switcher,
    set_version,
    switch_to_version,
)
from streamlit_app.core.data_bridge import auto_sync
from streamlit_app.components.version_badge import (
    render_home_hero,
    render_v3_title_gradient,
    render_version_badge,
)


# ============================================================================
# 主页
# ============================================================================

def _home_page() -> None:
    """主页：版本概览 + 切换 CTA。"""
    current = get_current_version()
    render_home_hero(current)


# Streamlit 1.41+ 推荐用 st.Page 包装
home = st.Page(
    _home_page,
    title="首页",
    icon="🏠",
    default=True,
    url_path="",
)


# ============================================================================
# v3 页面（生产试用）
# ============================================================================

v3_pages = [
    st.Page(
        "pages/v3_1_📊_数据驾驶舱.py",
        title="数据驾驶舱",
        icon="📊",
        url_path="v3_data",
    ),
    st.Page(
        "pages/v3_2_🧩_映射驾驶舱.py",
        title="映射驾驶舱",
        icon="🧩",
        url_path="v3_mapping",
    ),
    st.Page(
        "pages/v3_3_🤖_生成驾驶舱.py",
        title="生成驾驶舱",
        icon="🤖",
        url_path="v3_generate",
    ),
]


# ============================================================================
# v2 页面（稳定版）
# ============================================================================

v2_pages = [
    st.Page(
        "pages/v2_1_🏠_国内分析.py",
        title="国内分析",
        icon="🏠",
        url_path="v2_domestic",
    ),
    st.Page(
        "pages/v2_2_🌍_国际分析.py",
        title="国际分析",
        icon="🌍",
        url_path="v2_international",
    ),
    st.Page(
        "pages/v2_3_💹_市场化分析.py",
        title="市场化分析",
        icon="💹",
        url_path="v2_market",
    ),
    st.Page(
        "pages/v2_4_🌱_碳资产分析.py",
        title="碳资产分析",
        icon="🌱",
        url_path="v2_environmental",
    ),
    st.Page(
        "pages/v2_5_📄_报告生成.py",
        title="报告生成",
        icon="📄",
        url_path="v2_report",
    ),
]


# ============================================================================
# 路由决策
# ============================================================================

current_version = get_current_version()

# v3 默认在前，v2 在后（生产试用优先）
if current_version == "v3":
    nav_structure = {
        "🏠 首页": [home],
        "🎯 v3.0 驾驶舱（生产试用）🆕": v3_pages,
        "📦 v2.0 分析平台（稳定版）": v2_pages,
    }
else:
    # v2 用户：v2 在前，v3 折叠在底部
    nav_structure = {
        "🏠 首页": [home],
        "📦 v2.0 分析平台（稳定版）✅": v2_pages,
        "🎯 v3.0 驾驶舱（生产试用）🆕": v3_pages,
    }


# ============================================================================
# 侧边栏版本切换器（在 st.navigation 渲染后覆盖）
# ============================================================================

# 渲染版本徽章 + 切换器（侧边栏顶部）
with st.sidebar:
    render_version_badge(current_version)
    if current_version == "v3":
        render_v3_title_gradient()

# 渲染 st.navigation
nav = st.navigation(nav_structure)

# 渲染侧边栏版本切换器（在导航下方）
render_version_switcher()

# === 数据自动同步（v2/v3 之间） ===
auto_sync()

# === 运行当前页面 ===
nav.run()
