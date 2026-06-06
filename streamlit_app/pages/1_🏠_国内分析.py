"""
Streamlit Page 1: 🏠 国内分析（支持 3 模式切换）
==========================================

v2.1 新增：3 模式切换器
- 🏠 全口径：完整 DomesticAnalyzer 渲染（默认）
- 💹 市场化：单独渲染市场化部分
- 🆚 双口径对比：用 6 个 Plotly 图对比

对应业务图谱: 段 1-2 (国内电量 + 国内电价)
对应 Analyzer: DomesticAnalyzer
对应文档: docs/analysis/domestic-price-analysis-framework.md
"""

import json
import streamlit as st
from pathlib import Path
import sys

# 路径设置
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="国内分析 - 周报 v2",
    page_icon="🏠",
    layout="wide"
)

# 导入组件
from streamlit_app.components import (
    render_analyzer_result,
    render_dual_comparison,
    load_plotly_specs,
)
from src.analyzer import DomesticAnalyzer


# === 模式选择器（顶部） ===
st.title("🏠 国内分析")
st.markdown("### 段 1-2: 国内电量 + 国内电价")

mode = st.radio(
    "📊 数据口径",
    options=[
        "🏠 全口径（默认）",
        "💹 市场化（41% 风险敞口）",
        "🆚 双口径对比",
    ],
    index=0,
    horizontal=True,
    help="全口径=集团整体；市场化=短期博弈；对比=看 1 个故事",
)

st.markdown("---")


# === 数据加载函数 ===
@st.cache_data
def load_full_data():
    """加载全口径数据"""
    path = project_root / "tests" / "fixtures" / "domestic_full_volume_w21.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


@st.cache_data
def load_market_data():
    """加载市场化数据"""
    path = project_root / "tests" / "fixtures" / "domestic_market_volume_w21.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


@st.cache_data
def run_full_analysis(data):
    """跑全口径 DomesticAnalyzer"""
    return DomesticAnalyzer(data).analyze()


@st.cache_data
def run_market_analysis(data):
    """跑市场化 DomesticAnalyzer"""
    return DomesticAnalyzer(data).analyze()


# === 根据模式渲染 ===
if mode == "🏠 全口径（默认）":
    data = load_full_data()
    if not data:
        st.error("❌ 全口径数据未找到")
        st.stop()
    result = run_full_analysis(data)
    render_analyzer_result(result, dimension_label="🏠 全口径（国内）")

elif mode == "💹 市场化（41% 风险敞口）":
    data = load_market_data()
    if not data:
        st.error("❌ 市场化数据未找到")
        st.stop()
    result = run_market_analysis(data)

    # 顶部提示
    st.info("""
    💡 **市场化模式解读**：
    - 这只是集团在"**短期市场**"上的部分，占全口径约 41%
    - **不含** 中长期合同部分
    - 看的是"**风险敞口**"，不是"整体业绩"
    - 想看整体 → 切换到"全口径"或"双口径对比"
    """)

    render_analyzer_result(result, dimension_label="💹 市场化（国内）")

elif mode == "🆚 双口径对比":
    full_data = load_full_data()
    market_data = load_market_data()
    if not full_data or not market_data:
        st.error("❌ 数据未找到，请检查 fixture 文件")
        st.stop()

    full_result = run_full_analysis(full_data)
    market_result = run_market_analysis(market_data)

    # 加载 Plotly 规范
    plotly_specs = load_plotly_specs()

    # 顶部提示
    st.info("""
    🆚 **双口径对比模式**：
    - **左/橙色 = 市场化** (短期博弈)
    - **右/蓝色 = 全口径** (集团整体)
    - 同一周、同一集团，**2 个视角** 讲 1 个故事
    - 6 个 Plotly 图表 + 5 个核心洞察
    """)

    # 渲染双口径对比
    render_dual_comparison(
        full_result=full_result,
        market_result=market_result,
        full_label="🏠 全口径",
        market_label="💹 市场化",
        plotly_specs=plotly_specs,
    )


# === 底部文档链接 ===
st.caption("""
📖 详细文档:
- `docs/analysis/domestic-price-analysis-framework.md` 第 1-14 节
- `docs/user_guide/weekly-report-beginner-guide.md` 第五部分
- `docs/design/business-map-master.md` 业务图谱
""")
