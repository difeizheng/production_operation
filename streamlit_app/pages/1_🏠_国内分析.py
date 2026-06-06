"""
Streamlit Page 1: 🏠 国内分析（v2.4 - 4 模式 + 市场化维度）
======================================================

v2.1 新增：3 模式切换器
v2.3 新增：第 4 模式"按公司拆分"
v2.4 新增：双 Tab 结构（每个模式内含"整体"/"市场化"两个 Tab）

模式：
- 🏠 全口径（默认）→ 包含 [全口径] + [市场化] Tab
- 💹 市场化（41% 风险敞口）→ 包含 [市场化] Tab
- 🆚 双口径对比 → 用 6 个 Plotly 图对比
- 🏢 按公司拆分 → 4 家公司横向对比

对应业务图谱: 段 1-2 (国内电量 + 国内电价)
对应 Analyzer: DomesticAnalyzer（v2.4 集成 MarketMetrics）
对应文档: docs/analysis/domestic-price-analysis-framework.md
           docs/design/v24-market-dimension.md
"""

import json
import streamlit as st
from pathlib import Path
import sys

# 路径设置
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="国内分析 - 周报 v2.4",
    page_icon="🏠",
    layout="wide"
)

# 导入组件
from streamlit_app.components import (
    render_analyzer_result,
    render_dual_comparison,
    render_by_company,
    load_plotly_specs,
    # v2.4 新增
    render_market_summary_cards,
    render_market_rate_ranking,
    render_price_diff_scatter,
    render_org_quadrant_distribution,
    render_category_bucket_pie,
)
from src.analyzer import DomesticAnalyzer
from src.analyzer.market_metrics import build_org_metrics, analyze_market_dimension


# === 模式选择器（顶部） ===
st.title("🏠 国内分析")
st.markdown("### 段 1-2: 国内电量 + 国内电价（v2.4 新增市场化维度）")

mode = st.radio(
    "📊 数据口径",
    options=[
        "🏠 全口径（默认）",
        "💹 市场化（41% 风险敞口）",
        "🆚 双口径对比",
        "🏢 按公司拆分",
    ],
    index=0,
    horizontal=True,
    help="全口径=集团整体；市场化=短期博弈；对比=看 1 个故事；按公司=看子公司贡献",
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
def load_by_company_data():
    """加载按公司数据"""
    path = project_root / "tests" / "fixtures" / "domestic_by_company_w21.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


@st.cache_data
def load_v24_overall():
    """v2.4: 加载整体销售（18 组织）"""
    path = project_root / "tests" / "fixtures" / "domestic_overall_v24.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


@st.cache_data
def load_v24_market():
    """v2.4: 加载市场化交易（18 组织）"""
    path = project_root / "tests" / "fixtures" / "domestic_market_v24.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


@st.cache_data
def run_full_analysis(data):
    return DomesticAnalyzer(data).analyze()


@st.cache_data
def run_market_analysis(data):
    return DomesticAnalyzer(data).analyze()


@st.cache_data
def build_market_dimension(overall_data, market_data):
    """v2.4: 构建市场化维度分析结果"""
    orgs = build_org_metrics(overall_data["by_organization"], market_data["by_organization"])
    return analyze_market_dimension(orgs)


# === 模式 1: 全口径 ===

if mode == "🏠 全口径（默认）":
    data = load_full_data()
    if not data:
        st.error("❌ 全口径数据未找到")
        st.stop()

    # v2.4: 双 Tab 结构
    tab1, tab2 = st.tabs(["📊 全口径", "💹 市场化维度（v2.4 新）"])

    with tab1:
        result = run_full_analysis(data)
        render_analyzer_result(result, dimension_label="🏠 全口径（国内）")

    with tab2:
        st.info("""
        💹 **v2.4 新增** - 18 组织 × 双口径分析：
        - 集团整体市场化率（41.36%）
        - 18 组织按市场化率排行
        - 市场化率 vs 电价差 象限分布
        - 业务桶分布
        """)

        # 加载 v2.4 双口径数据
        overall_v24 = load_v24_overall()
        market_v24 = load_v24_market()
        if not overall_v24 or not market_v24:
            st.error("❌ v2.4 双口径数据未找到，请检查 fixture")
            st.stop()

        market_dim = build_market_dimension(overall_v24, market_v24)

        # 1. 4 个 KPI 卡片
        render_market_summary_cards(
            market_dim,
            overall_revenue=sum(
                ov["overall_revenue_wk"]
                for ov in overall_v24["by_organization"].values()
            ),
        )

        st.markdown("---")

        # 2. 18 组织市场化率排行
        render_market_rate_ranking(market_dim, top_n=18)

        st.markdown("---")

        # 3. 象限散点图 + 象限分布
        col1, col2 = st.columns([2, 1])
        with col1:
            render_price_diff_scatter(market_dim)
        with col2:
            render_org_quadrant_distribution(market_dim)
            st.markdown("")
            render_category_bucket_pie(market_dim)

        # 4. 业务洞察
        st.markdown("---")
        st.markdown("### 🔍 关键洞察")
        insights_cols = st.columns(2)
        with insights_cols[0]:
            st.success(f"""
            **🏷️ 集团市场化率 {market_dim.total_market_rate:.2f}%**
            - 集团整体 80.28 亿度，市场化 33.20 亿度
            - 高市场化率分公司：{', '.join(market_dim.top_market_rate_orgs[:3])}
            """)
        with insights_cols[1]:
            st.warning(f"""
            **💎 溢价 TOP 3**：{', '.join(market_dim.top_price_premium_orgs[:3])}
            **📉 折价 TOP 3**：{', '.join(market_dim.bottom_price_discount_orgs[:3])}
            """)


# === 模式 2: 市场化 ===

elif mode == "💹 市场化（41% 风险敞口）":
    data = load_market_data()
    if not data:
        st.error("❌ 市场化数据未找到")
        st.stop()
    result = run_market_analysis(data)

    st.info("""
    💡 **市场化模式解读**：
    - 这只是集团在"**短期市场**"上的部分，占全口径约 41%
    - **不含** 中长期合同部分
    - 看的是"**风险敞口**"，不是"整体业绩"
    - 想看整体 → 切换到"全口径"或"双口径对比"
    """)

    render_analyzer_result(result, dimension_label="💹 市场化（国内）")


# === 模式 3: 双口径对比 ===

elif mode == "🆚 双口径对比":
    full_data = load_full_data()
    market_data = load_market_data()
    if not full_data or not market_data:
        st.error("❌ 数据未找到，请检查 fixture 文件")
        st.stop()

    full_result = run_full_analysis(full_data)
    market_result = run_market_analysis(market_data)
    plotly_specs = load_plotly_specs()

    st.info("""
    🆚 **双口径对比模式**：
    - **左/橙色 = 市场化** (短期博弈)
    - **右/蓝色 = 全口径** (集团整体)
    - 同一周、同一集团，**2 个视角** 讲 1 个故事
    """)

    render_dual_comparison(
        full_result=full_result,
        market_result=market_result,
        full_label="🏠 全口径",
        market_label="💹 市场化",
        plotly_specs=plotly_specs,
    )


# === 模式 4: 按公司拆分 ===

elif mode == "🏢 按公司拆分":
    data = load_by_company_data()
    if not data:
        st.error("❌ 按公司数据未找到")
        st.stop()

    st.info("""
    🏢 **按公司拆分模式**：
    - 集团国内 4 家单位横向对比
    - 长江电力 / 三峡建工 / 湖北能源 / 三峡发展
    """)

    render_by_company(
        companies=data["companies"],
        context="国内",
        title="🏢 国内各单位水电数据（4 家）",
    )


# === 底部文档链接 ===
st.caption("""
📖 详细文档:
- `docs/analysis/domestic-price-analysis-framework.md` 第 1-14 节
- `docs/analysis/by-company-13-insights.md` 按公司 13 洞察
- `docs/design/v24-market-dimension.md` v2.4 市场化维度设计
- `docs/user_guide/weekly-report-beginner-guide.md` 第五部分
- `docs/design/business-map-master.md` 业务图谱
""")
