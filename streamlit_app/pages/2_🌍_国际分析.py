"""
Streamlit Page 2: 🌍 国际分析（支持 3 模式切换）
==========================================

v2.2 新增：3 模式切换器
- 🌍 国际全口径：完整 InternationalAnalyzer 渲染（默认）
- 💹 国际化市场：单独渲染市场化部分
- 🆚 国际双口径对比：用 6 个 Plotly 图对比

对应业务图谱: 段 3-4 (国际电价同比 + 环比)
对应 Analyzer: InternationalAnalyzer
对应文档: docs/analysis/domestic-price-analysis-framework.md 第 15 节
"""

import json
import streamlit as st
from pathlib import Path
import sys

# 路径设置
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="国际分析 - 周报 v2",
    page_icon="🌍",
    layout="wide"
)

# 导入组件
from streamlit_app.components import (
    render_analyzer_result,
    render_dual_comparison,
    load_plotly_specs,
)
from src.analyzer import InternationalAnalyzer


# === 模式选择器（顶部） ===
st.title("🌍 国际分析")
st.markdown("### 段 3-4: 国际电价（同比 + 环比）")

mode = st.radio(
    "🌍 数据口径",
    options=[
        "🌍 国际全口径（默认）",
        "💹 国际化市场（49% 风险敞口）",
        "🆚 国际双口径对比",
    ],
    index=0,
    horizontal=True,
    help="国际全口径=集团整体海外业务；国际化市场=短期博弈；对比=看 1 个故事",
)

st.markdown("---")


# === 数据加载函数 ===
@st.cache_data
def load_full_intl_data():
    """加载国际全口径数据"""
    path = project_root / "tests" / "fixtures" / "international_full_volume_w21.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


@st.cache_data
def load_market_intl_data():
    """加载国际化市场数据"""
    path = project_root / "tests" / "fixtures" / "international_market_volume_w21.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


@st.cache_data
def run_intl_full_analysis(data):
    """跑国际全口径 InternationalAnalyzer"""
    return InternationalAnalyzer(data).analyze()


@st.cache_data
def run_intl_market_analysis(data):
    """跑国际化市场 InternationalAnalyzer"""
    return InternationalAnalyzer(data).analyze()


@st.cache_data
def load_intl_plotly_specs():
    """加载国际 Plotly 规范"""
    path = project_root / "tests" / "fixtures" / "international_plotly_specs.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


# === 根据模式渲染 ===
if mode == "🌍 国际全口径（默认）":
    data = load_full_intl_data()
    if not data:
        st.error("❌ 国际全口径数据未找到")
        st.stop()
    result = run_intl_full_analysis(data)
    render_analyzer_result(result, dimension_label="🌍 国际全口径")

elif mode == "💹 国际化市场（49% 风险敞口）":
    data = load_market_intl_data()
    if not data:
        st.error("❌ 国际化市场数据未找到")
        st.stop()
    result = run_intl_market_analysis(data)

    # 顶部提示
    st.info("""
    💡 **国际化市场模式解读**：
    - 这只是集团在"**海外短期市场**"上的部分，占国际全口径约 **49%**（比国内 41% 更高）
    - **不含** 国际长协（卡洛特等合同）
    - 看的是"**海外风险敞口**"
    - 与国内市场化不同：**国际市场化是"赢家"模式**（同比 +8.62% > 全口径 +2.36%）
    - 想看整体 → 切换到"国际全口径"或"国际双口径对比"
    """)

    render_analyzer_result(result, dimension_label="💹 国际化市场")

elif mode == "🆚 国际双口径对比":
    full_data = load_full_intl_data()
    market_data = load_market_intl_data()
    if not full_data or not market_data:
        st.error("❌ 数据未找到，请检查 fixture 文件")
        st.stop()

    full_result = run_intl_full_analysis(full_data)
    market_result = run_intl_market_analysis(market_data)

    # 加载国际 Plotly 规范
    plotly_specs = load_intl_plotly_specs()

    # 顶部提示
    st.info("""
    🆚 **国际双口径对比模式**：
    - **左/橙色 = 国际化市场** (海外短期博弈)
    - **右/蓝色 = 国际全口径** (集团海外整体)
    - 同一周、同一集团海外业务，**2 个视角** 讲 1 个故事
    - 与国内不同：**国际是"方向同向 + 市场化更猛"模式**
    """)

    # 渲染国际双口径对比
    render_dual_comparison(
        full_result=full_result,
        market_result=market_result,
        full_label="🌍 国际全口径",
        market_label="💹 国际化市场",
        plotly_specs=plotly_specs,
        kpi_map_name="国际",  # 关键：使用国际 kpi 字段名
    )


# === 底部文档链接 ===
st.caption("""
📖 详细文档:
- `docs/analysis/domestic-price-analysis-framework.md` 第 15 节
- `docs/user_guide/weekly-report-beginner-guide.md` 第八部分
- `docs/design/business-map-master.md` 业务图谱
""")
