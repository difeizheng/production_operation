"""
Streamlit Page 1: 🏠 国内分析（v2.4.1 - 双层单选 + 内含 Tab）
========================================================

v2.4.1 重构：原 4 模式单选 → 双层单选 + 内含 Tab

新结构：
  第一层：数据范围（单选）
    ○ 🏠 整体销售
    ○ 💹 市场化交易
  第二层：视图形式（单选，动态选项）
    - 整体销售下：[📊 全景 | 🎯 象限 | 🏢 按公司 | 🆚 对比]
    - 市场化下：[📊 全景 | 🎯 象限 | 🆚 对比]
  共 7 种 (数据范围, 视图形式) 组合，每种内含 2-3 Tab

设计目标：
- 概念正交：数据范围（业务） × 视图形式（分析）
- 能力最大化：v2.4 象限分析在 2 数据范围下都可用
- 心智成本低：用户只问 2 个问题："看什么数据？"+"怎么看？"

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

# v3.1: 用 safe_set_page_config 避免与 app.py 重复调用
from streamlit_app.core.data_bridge import safe_set_page_config

safe_set_page_config(
    page_title="国内分析 - 周报 v2.4.1",
    page_icon="🏠",
    layout="wide"
)

# 导入组件
from streamlit_app.components import (
    render_analyzer_result,
    render_dual_comparison,
    render_by_company,
    load_plotly_specs,
    # v2.4 组件
    render_market_summary_cards,
    render_market_rate_ranking,
    render_price_diff_scatter,
    render_org_quadrant_distribution,
    render_category_bucket_pie,
)
from src.analyzer import DomesticAnalyzer
from src.analyzer.market_metrics import build_org_metrics, analyze_market_dimension


# === 标题 ===
st.title("🏠 国内分析")
st.markdown("### 段 1-2: 国内电量 + 国内电价（v2.4.1 双层导航）")

# ============================================================
# 第一层：数据范围（业务维度）
# ============================================================
st.markdown("#### 📊 第一步：选择数据范围")

data_scope = st.radio(
    "数据范围",
    options=["🏠 整体销售", "💹 市场化交易"],
    index=0,
    horizontal=True,
    key="data_scope",
    help="整体销售=集团完整业绩；市场化交易=短期博弈（41% 风险敞口）",
    label_visibility="collapsed",
)

st.markdown("---")

# ============================================================
# 第二层：视图形式（分析维度，依赖第一层）
# ============================================================
st.markdown("#### 📐 第二步：选择视图形式")

if data_scope == "🏠 整体销售":
    view_options = [
        "📊 全景",
        "🎯 象限分析（v2.4）",
        "🏢 按公司拆分",
        "🆚 整体 vs 市场化对比",
    ]
    view_help = (
        "全景=5 大品类+省份；象限=18 组织市场化分布；"
        "按公司=4 家核心；对比=与市场化并列看"
    )
else:  # 市场化交易
    view_options = [
        "📊 全景",
        "🎯 象限分析（v2.4）",
        "🆚 整体 vs 市场化对比",
    ]
    view_help = "全景=市场化总览；象限=市场化高风险组织；对比=与整体并列"

view_mode = st.radio(
    "视图形式",
    options=view_options,
    index=0,
    horizontal=True,
    key="view_mode",
    help=view_help,
    label_visibility="collapsed",
)

st.markdown("---")


# ============================================================
# 辅助函数（必须在使用前定义）
# ============================================================

def _analyzer_overall_18() -> list:
    """整体销售 18 组织（用 v2.4 merged fixture 跑 DomesticAnalyzer）"""
    merged_path = project_root / "tests" / "fixtures" / "domestic_v24_merged.json"
    if not merged_path.exists():
        return []
    with open(merged_path, encoding="utf-8") as f:
        data = json.load(f)
    result = run_analyzer(data)
    return result.tables


def _build_overall_vs_market_table(overall_data: dict, market_data: dict) -> "pd.DataFrame":
    """构建 18 组织 × 双口径完整对比表

    列：组织 | 业务桶 | 整体电量 | 整体电价 | 整体电费 | 市场化率 | 市场化电量 | 市场化电价 | 市场化电费 | 电价差
    """
    import pandas as pd
    rows = []
    for name, ov in overall_data["by_organization"].items():
        mkt = market_data["by_organization"].get(name, {})
        ov_vol = ov.get("overall_volume_wk", 0)
        mkt_vol = mkt.get("market_volume_wk", 0)
        market_rate = (mkt_vol / ov_vol * 100) if ov_vol > 0 else 0.0
        ov_price = ov.get("overall_price_wk", 0)
        mkt_price = mkt.get("market_price_wk", 0)
        price_diff = mkt_price - ov_price

        rows.append({
            "组织": name,
            "业务桶": ov.get("category", "—"),
            "整体电量(万kWh)": round(ov_vol, 2),
            "整体电价(元/度)": round(ov_price, 3),
            "整体电费(万元)": round(ov.get("overall_revenue_wk", 0), 2),
            "市场化率(%)": round(market_rate, 2),
            "市场化电量(万kWh)": round(mkt_vol, 2),
            "市场化电价(元/度)": round(mkt_price, 3),
            "市场化电费(万元)": round(mkt.get("market_revenue_wk", 0), 2),
            "电价差(元/度)": round(price_diff, 4),
        })
    df = pd.DataFrame(rows)
    # 按市场化率降序
    return df.sort_values("市场化率(%)", ascending=False).reset_index(drop=True)


# ============================================================
# 数据加载函数
# ============================================================

@st.cache_data
def load_full_overall_data():
    """加载整体销售数据（v2.0 旧 fixture）"""
    path = project_root / "tests" / "fixtures" / "domestic_full_volume_w21.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


@st.cache_data
def load_market_v20_data():
    """加载市场化数据（v2.0 旧 fixture）"""
    path = project_root / "tests" / "fixtures" / "domestic_market_volume_w21.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


@st.cache_data
def load_by_company_data():
    """加载按公司数据（v2.3 fixture）"""
    path = project_root / "tests" / "fixtures" / "domestic_by_company_w21.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


@st.cache_data
def load_v24_overall():
    """v2.4: 18 组织整体销售"""
    path = project_root / "tests" / "fixtures" / "domestic_overall_v24.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


@st.cache_data
def load_v24_market():
    """v2.4: 18 组织市场化交易"""
    path = project_root / "tests" / "fixtures" / "domestic_market_v24.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


@st.cache_data
def build_market_dimension(overall_data, market_data):
    """构建市场化维度分析结果"""
    if not overall_data or not market_data:
        return None
    orgs = build_org_metrics(overall_data["by_organization"], market_data["by_organization"])
    return analyze_market_dimension(orgs)


@st.cache_data
def run_analyzer(data):
    return DomesticAnalyzer(data).analyze()


# ============================================================
# 组合 ID 与内容渲染
# ============================================================

# 组合 ID
COMBO_ID = f"{data_scope}|{view_mode}"


# ===== 组合 ①：整体销售 × 全景 =====
if COMBO_ID == "🏠 整体销售|📊 全景":
    data = load_full_overall_data()
    if not data:
        st.error("❌ 整体销售数据未找到")
        st.stop()
    result = run_analyzer(data)

    tab1, tab2, tab3 = st.tabs([
        "📊 集团总览",
        "⚡ 5 大品类",
        "🗺️ 关键省份",
    ])

    with tab1:
        st.info("""
        📊 **集团总览**：上周集团合计上网电量 + 度电均价 + 同比/环比
        """)
        render_analyzer_result(result, dimension_label="🏠 整体销售·集团总览", key_prefix="combo1_")

    with tab2:
        st.info("""
        ⚡ **5 大品类**：水/新/火/风/光 的电量/电价/收入占比
        """)
        # 仅展示品类相关
        from streamlit_app.components import render_charts, render_tables
        for chart in [c for c in result.charts if "品类" in c.get("title", "")]:
            from streamlit_app.components import render_chart
            render_chart(chart)
        for table in [t for t in result.tables if "品类" in t.get("title", "")]:
            from streamlit_app.components import render_table
            render_table(table)

    with tab3:
        st.info("""
        🗺️ **关键省份**：湖北/山东/陕西/江苏 4 省策略
        """)
        from streamlit_app.components import render_table
        for table in [t for t in result.tables if "省份" in t.get("title", "")]:
            render_table(table)


# ===== 组合 ②：整体销售 × 象限分析 =====
elif COMBO_ID == "🏠 整体销售|🎯 象限分析（v2.4）":
    overall_v24 = load_v24_overall()
    market_v24 = load_v24_market()
    if not overall_v24 or not market_v24:
        st.error("❌ v2.4 双口径数据未找到")
        st.stop()
    market_dim = build_market_dimension(overall_v24, market_v24)

    tab1, tab2, tab3 = st.tabs([
        "📋 18 组织市场化率排行",
        "🎯 象限散点图",
        "📊 业务桶分布",
    ])

    with tab1:
        st.info("""
        📋 **18 组织市场化率排行**：从高到低
        - 100% 市场化：重庆/四川/广东/云南（极端）
        - 0% 市场化：长江环保/三峡发展（不参与）
        - 26% 长江电力（稀缺水电）
        """)
        # 顶部 KPI
        render_market_summary_cards(
            market_dim,
            overall_revenue=sum(
                ov["overall_revenue_wk"]
                for ov in overall_v24["by_organization"].values()
            ),
        )
        st.markdown("---")
        render_market_rate_ranking(market_dim, top_n=18)

    with tab2:
        st.info("""
        🎯 **象限散点图**：市场化率（X）× 电价差（Y）
        - 4 象限：稀缺溢价/竞争溢价/稀缺折价/竞争折价
        - 气泡大小 = 收入贡献
        """)
        render_price_diff_scatter(market_dim)
        st.markdown("---")
        # 象限分布
        render_org_quadrant_distribution(market_dim)

    with tab3:
        st.info("""
        📊 **业务桶分布**：7 类组织（水电/新能源/传统/工程/环保/发展/区域）
        """)
        render_category_bucket_pie(market_dim)


# ===== 组合 ③：整体销售 × 按公司拆分 =====
elif COMBO_ID == "🏠 整体销售|🏢 按公司拆分":
    by_company_data = load_by_company_data()
    overall_v24 = load_v24_overall()
    market_v24 = load_v24_market()
    if not by_company_data:
        st.error("❌ 按公司数据未找到")
        st.stop()

    tab1, tab2, tab3 = st.tabs([
        "🏢 4 家核心（v2.3）",
        "📋 18 家全量（v2.4）",
        "🗂️ 业务模式分组",
    ])

    with tab1:
        st.info("""
        🏢 **4 家核心公司对比**（v2.3 模式）
        - 长江电力 / 三峡建工 / 湖北能源 / 三峡发展
        - 看 1 个故事：单家独大 + 异常公司识别
        """)
        render_by_company(
            companies=by_company_data["companies"],
            context="国内",
            title="🏢 4 家核心公司",
        )

    with tab2:
        st.info("""
        📋 **18 家全量**（v2.4 新）
        - 完整覆盖集团所有组织（6 直属 + 12 分公司）
        - 同时展示整体销售 + 市场化双口径
        """)
        if overall_v24 and market_v24:
            market_dim = build_market_dimension(overall_v24, market_v24)

            # 1. 18 组织 × 双口径 完整对比表
            st.markdown("#### 📊 18 组织 × 双口径完整对比")
            st.dataframe(_build_overall_vs_market_table(overall_v24, market_v24), use_container_width=True, hide_index=True)

            # 2. 4 象限分布（v2.4 核心）
            st.markdown("---")
            st.markdown("#### 🎯 18 组织市场化维度（v2.4）")
            render_org_quadrant_distribution(market_dim)

            # 3. 2 个关键图：市场化率排行 + 电价差
            st.markdown("---")
            st.markdown("#### 📈 关键可视化")
            render_market_rate_ranking(market_dim, top_n=18)
        else:
            st.error("❌ v2.4 数据未找到")

    with tab3:
        st.info("""
        🗂️ **业务模式分组**：按业务桶聚合
        - 水电组 / 新能源组 / 传统能源组 / 工程组 / 环保组 / 发展组 / 区域分公司组
        """)
        if overall_v24 and market_v24:
            market_dim = build_market_dimension(overall_v24, market_v24)
            render_category_bucket_pie(market_dim)


# ===== 组合 ④：整体销售 × 对比分析 =====
elif COMBO_ID == "🏠 整体销售|🆚 整体 vs 市场化对比":
    full_data = load_full_overall_data()
    market_data = load_market_v20_data()
    if not full_data or not market_data:
        st.error("❌ 对比数据未找到")
        st.stop()

    full_result = run_analyzer(full_data)
    market_result = run_analyzer(market_data)
    plotly_specs = load_plotly_specs()

    tab1, tab2, tab3 = st.tabs([
        "🏠 整体全貌",
        "💹 市场化全貌",
        "🆚 差异分析（6 图）",
    ])

    with tab1:
        st.info("🏠 **整体销售全貌**：集团完整业绩")
        render_analyzer_result(full_result, dimension_label="🏠 整体", key_prefix="combo4_full_")

    with tab2:
        st.info("💹 **市场化全貌**：41% 风险敞口")
        render_analyzer_result(market_result, dimension_label="💹 市场化", key_prefix="combo4_mkt_")

    with tab3:
        st.info("""
        🆚 **差异分析**：6 个 Plotly 对比图
        - 左/橙色 = 市场化
        - 右/蓝色 = 全口径
        """)
        render_dual_comparison(
            full_result=full_result,
            market_result=market_result,
            full_label="🏠 整体",
            market_label="💹 市场化",
            plotly_specs=plotly_specs,
        )


# ===== 组合 ⑤：市场化交易 × 全景 =====
elif COMBO_ID == "💹 市场化交易|📊 全景":
    market_data = load_market_v20_data()
    if not market_data:
        st.error("❌ 市场化数据未找到")
        st.stop()
    result = run_analyzer(market_data)

    tab1, tab2 = st.tabs([
        "📊 集团市场化总览",
        "⚠️ 风险敞口",
    ])

    with tab1:
        st.info("""
        📊 **集团市场化总览**：上周市场化交易部分
        - 市场化率 ≈ 41.36%
        - 不含中长期合同
        """)
        render_analyzer_result(result, dimension_label="💹 市场化全景", key_prefix="combo5_")

    with tab2:
        st.info("""
        ⚠️ **风险敞口**：市场化交易的波动性
        - 电价波动大
        - 竞争激烈
        """)
        # 复用 v2.4 象限的高风险组织
        overall_v24 = load_v24_overall()
        market_v24 = load_v24_market()
        if overall_v24 and market_v24:
            market_dim = build_market_dimension(overall_v24, market_v24)
            st.markdown("**高风险组织**（竞争折价象限 + 高市场化率）:")
            for d in market_dim.orgs:
                if d.quadrant == "竞争折价" and d.market_rate >= 50:
                    st.write(
                        f"- {d.name}: 市场化率 {d.market_rate:.1f}%, "
                        f"电价差 {d.price_diff:+.3f} 元/度"
                    )


# ===== 组合 ⑥：市场化交易 × 象限分析 =====
elif COMBO_ID == "💹 市场化交易|🎯 象限分析（v2.4）":
    overall_v24 = load_v24_overall()
    market_v24 = load_v24_market()
    if not overall_v24 or not market_v24:
        st.error("❌ v2.4 双口径数据未找到")
        st.stop()
    market_dim = build_market_dimension(overall_v24, market_v24)

    tab1, tab2, tab3 = st.tabs([
        "🎯 4 象限分类",
        "📍 散点图",
        "⚠️ 高风险组织",
    ])

    with tab1:
        st.info("""
        🎯 **4 象限分类**：市场化高风险组织识别
        - 重点关注"竞争折价"象限
        """)
        render_org_quadrant_distribution(market_dim)
        st.markdown("---")
        # 按象限分组列出组织
        for q in ["稀缺溢价", "竞争溢价", "稀缺折价", "竞争折价"]:
            orgs_in_q = [d for d in market_dim.orgs if d.quadrant == q]
            if orgs_in_q:
                with st.expander(f"📂 {q}（{len(orgs_in_q)} 个组织）"):
                    for d in orgs_in_q:
                        st.write(
                            f"- **{d.name}**: 市场化率 {d.market_rate:.1f}%, "
                            f"电价差 {d.price_diff:+.3f} 元/度"
                        )

    with tab2:
        render_price_diff_scatter(market_dim)

    with tab3:
        st.info("""
        ⚠️ **高风险组织**：
        - 竞争折价 + 市场化率 ≥ 50%
        - 这些组织在市场化交易中处于不利位置
        """)
        high_risk = [
            d for d in market_dim.orgs
            if d.quadrant == "竞争折价" and d.market_rate >= 50
        ]
        if high_risk:
            from streamlit_app.components import render_market_rate_ranking
            # 临时构造一个只含高风险组织的视图（简化：直接用原 dim 展示）
            st.metric("高风险组织数", len(high_risk))
            for d in sorted(high_risk, key=lambda x: x.market_rate, reverse=True):
                st.write(
                    f"- **{d.name}**: 市场化率 {d.market_rate:.1f}%, "
                    f"电价差 {d.price_diff:+.3f} 元/度, "
                    f"收入贡献 {d.revenue_contribution:.1f}%"
                )
        else:
            st.success("✅ 当前无高风险组织")


# ===== 组合 ⑦：市场化交易 × 对比分析 =====
elif COMBO_ID == "💹 市场化交易|🆚 整体 vs 市场化对比":
    # 与组合 ④ 相同内容（对比是不分数据范围的）
    full_data = load_full_overall_data()
    market_data = load_market_v20_data()
    if not full_data or not market_data:
        st.error("❌ 对比数据未找到")
        st.stop()

    full_result = run_analyzer(full_data)
    market_result = run_analyzer(market_data)
    plotly_specs = load_plotly_specs()

    tab1, tab2, tab3 = st.tabs([
        "💹 市场化全貌",
        "🏠 整体全貌",
        "🆚 价差与折溢价",
    ])

    with tab1:
        st.info("💹 **市场化全貌**")
        render_analyzer_result(market_result, dimension_label="💹 市场化")

    with tab2:
        st.info("🏠 **整体全貌**")
        render_analyzer_result(full_result, dimension_label="🏠 整体")

    with tab3:
        st.info("""
        🆚 **价差与折溢价**：同一周 2 视角
        - 重点看"价差"和"折溢价"
        """)
        # 6 图对比
        render_dual_comparison(
            full_result=full_result,
            market_result=market_result,
            full_label="🏠 整体",
            market_label="💹 市场化",
            plotly_specs=plotly_specs,
        )
        st.markdown("---")
        # 补充 v2.4 价差表
        overall_v24 = load_v24_overall()
        market_v24 = load_v24_market()
        if overall_v24 and market_v24:
            market_dim = build_market_dimension(overall_v24, market_v24)
            st.markdown("#### 18 组织电价差（市场化 - 整体）")
            for d in sorted(
                [x for x in market_dim.orgs if x.is_active_in_market],
                key=lambda x: x.price_diff, reverse=True
            ):
                emoji = "🟢" if d.price_diff >= 0 else "🔴"
                st.write(
                    f"- {emoji} **{d.name}**: {d.price_diff:+.4f} 元/度 "
                    f"（{d.quadrant}）"
                )


# === 辅助函数：避免重复逻辑 ===
# （已在文件顶部定义 _analyzer_overall_18）


# === 底部文档链接 ===
st.markdown("---")
st.caption("""
📖 详细文档:
- `docs/analysis/domestic-price-analysis-framework.md` 第 1-14 节
- `docs/analysis/by-company-13-insights.md` 按公司 13 洞察
- `docs/design/v24-market-dimension.md` v2.4 市场化维度设计
- `docs/user_guide/weekly-report-beginner-guide.md` 第五部分
- `docs/design/business-map-master.md` 业务图谱

🆕 v2.4.1 新结构：双层单选（数据范围 × 视图形式） + 内含 Tab，共 7 种有意义的能力组合
""")
