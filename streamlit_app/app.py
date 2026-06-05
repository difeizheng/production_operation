"""
周报自动化 v2 - Streamlit 主入口
=================================

基于 docs/design/business-map-master.md 业务图谱构建
实现 4 维度 × 8 段实战的交互式可视化

运行方式:
    PYTHONPATH=. streamlit run streamlit_app/app.py

设计文档:
    - 业务图谱: docs/design/business-map-master.md
    - 架构设计: docs/design/report-generator-v2-architecture.md
"""

import sys
from pathlib import Path

import streamlit as st

# === 路径设置 ===
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# === Streamlit 页面配置 ===
st.set_page_config(
    page_title="周报分析平台 v2",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "周报自动化系统 v2 - 4 维度全覆盖"
    }
)

# === 导入数据加载器 ===
from streamlit_app.utils.data_loader import (
    load_data_and_analyze,
    get_report_meta,
)


# === 侧边栏：数据源控制 ===
with st.sidebar:
    st.header("⚙️ 数据源")

    # 数据源选择
    data_source = st.radio(
        "选择数据源",
        options=["🎭 演示数据（5/22 周报）", "📁 上传 JSON 文件"],
        index=0,
        help="演示数据使用合并 fixture；上传支持自定义 JSON",
    )

    uploaded_file = None
    use_default = True

    if data_source == "📁 上传 JSON 文件":
        uploaded_file = st.file_uploader(
            "上传周报 JSON",
            type=["json"],
            help="JSON 需包含 group_total/international/market_trading/environmental_assets 等字段",
        )
        use_default = False

    st.divider()

    # 加载数据 + 执行 Analyzer
    with st.spinner("加载数据并执行 4 Analyzer..."):
        bundle = load_data_and_analyze(
            uploaded_file=uploaded_file,
            use_default=use_default,
        )

    # 存入 session_state 供页面间共享
    st.session_state["bundle"] = bundle

    data = bundle["data"]
    results = bundle["results"]
    source = bundle["source"]

    # 显示报告元信息
    if data:
        meta = get_report_meta(data)
        st.success(
            f"✅ 报告: `{meta.get('report_id')}`\n\n"
            f"📅 {meta.get('year')} 年第 {meta.get('week')} 周\n"
            f"({meta.get('start_date')} ~ {meta.get('end_date')})"
        )
        st.caption(f"数据源: {'演示数据' if source == 'default' else '上传文件'}")

    st.divider()

    # 帮助
    with st.expander("ℹ️ 帮助"):
        st.markdown("""
        **5 个页面**:
        1. 🏠 国内分析（段 1-2）
        2. 🌍 国际分析（段 3-4）
        3. 💹 市场化分析（段 5-7）
        4. 🌱 碳资产分析（段 8）
        5. 📄 报告生成

        **关键文档**:
        - `docs/design/business-map-master.md`
        - `docs/design/report-generator-v2-architecture.md`
        - `docs/analysis/domestic-price-analysis-framework.md`
        """)


# === 主区域 ===
st.title("📊 周报分析平台 v2")
st.markdown("""
### 4 维度 × 8 段实战 - 业务图谱全覆盖

- 🏠 **国内** - 段 1-2（89.1 亿度 / 0.311 元 / 以量补价）
- 🌍 **国际** - 段 3-4（0.32 元 / 能力动能）
- 💹 **市场化** - 段 5-7（3 板块 / 3 机制 / 东方不亮西方亮）
- 🌱 **碳资产** - 段 8（4.94 亿家底 / 卖空气换钱）
- 📄 **报告生成** - 一键导出
""")

# 数据加载状态
if data is None:
    st.warning("⚠️ 请在左侧边栏选择数据源")
    st.stop()

# 显示快速概览
st.divider()
st.markdown("### 🎯 4 维度快速概览")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if results.get("domestic"):
        st.metric(
            "🏠 国内",
            f"{results['domestic'].kpis.get('国内上网电量', 0)} 亿度",
            delta=f"同比 {results['domestic'].kpis.get('同比电量', 0):+.1f}%",
        )
    else:
        st.metric("🏠 国内", "—")

with col2:
    if results.get("international"):
        st.metric(
            "🌍 国际",
            f"{results['international'].kpis.get('国际度电均价', 0)} 元",
            delta=f"同比 {results['international'].kpis.get('国际同比度电', 0):+.1f}分",
        )
    else:
        st.metric("🌍 国际", "—")

with col3:
    if results.get("market_trading"):
        st.metric(
            "💹 市场化",
            f"{results['market_trading'].kpis.get('新能源省份数', 0)} 省",
            delta=f"火电环比 {results['market_trading'].kpis.get('火电环比', 0):+.1f}分",
        )
    else:
        st.metric("💹 市场化", "—")

with col4:
    if results.get("environmental"):
        st.metric(
            "🌱 碳资产",
            f"{results['environmental'].kpis.get('总库存价值(亿元)', 0)} 亿元",
            delta=f"库存 {results['environmental'].kpis.get('绿证库存(万张)', 0)} 万张",
        )
    else:
        st.metric("🌱 碳资产", "—")

# 全维度异常概览
st.divider()
st.markdown("### ⚠️ 异常概览")

anomaly_count = {
    "domestic": len(results.get("domestic").anomalies) if results.get("domestic") else 0,
    "international": len(results.get("international").anomalies) if results.get("international") else 0,
    "market_trading": len(results.get("market_trading").anomalies) if results.get("market_trading") else 0,
    "environmental": len(results.get("environmental").anomalies) if results.get("environmental") else 0,
}

cols = st.columns(4)
dimension_names = ["🏠 国内", "🌍 国际", "💹 市场化", "🌱 碳资产"]
dimension_keys = ["domestic", "international", "market_trading", "environmental"]
for col, name, key in zip(cols, dimension_names, dimension_keys):
    with col:
        count = anomaly_count[key]
        if count == 0:
            st.success(f"{name}\n\n✅ 无异常")
        else:
            st.warning(f"{name}\n\n⚠️ {count} 个异常")

# 使用提示
st.divider()
st.info("💡 **使用提示**: 点击左侧导航栏进入各维度分析页面，或前往'报告生成'查看完整分析。")


# === 底部信息 ===
st.divider()
st.caption(f"""
📖 设计文档: `docs/design/business-map-master.md` |
`docs/design/report-generator-v2-architecture.md`
v2.0 - 4 Analyzer + Streamlit UI
""")
