"""
Streamlit Page 5: 📄 报告生成
=============================

汇总 4 维度分析结果，生成 Markdown 报告
"""

import streamlit as st
from pathlib import Path
import sys
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="报告生成 - 周报 v2",
    page_icon="📄",
    layout="wide"
)

from streamlit_app.utils.data_loader import get_report_meta

st.title("📄 报告生成")
st.markdown("### 汇总 4 维度分析 → Markdown 报告")

# v3.1: 使用 data_bridge.ensure_bundle 替代直接读 session_state
from streamlit_app.core.data_bridge import ensure_bundle
bundle = ensure_bundle()
if not bundle or not bundle.get("results"):
    st.warning("⚠️ 请在主页面选择数据源")
    st.stop()

results = bundle["results"]
data = bundle["data"]
meta = get_report_meta(data) if data else {}

# === 报告生成选项 ===
st.subheader("⚙️ 生成选项")
col1, col2 = st.columns(2)
with col1:
    include_summary = st.checkbox("包含一句话总结", value=True)
    include_kpis = st.checkbox("包含关键指标", value=True)
    include_story = st.checkbox("包含业务故事", value=True)
with col2:
    include_tables = st.checkbox("包含数据表格", value=True)
    include_charts_info = st.checkbox("包含图表说明", value=False)
    include_anomalies = st.checkbox("包含异常告警", value=True)

# 选择维度
st.subheader("📊 选择维度")
selected_dims = st.multiselect(
    "要包含哪些维度",
    options=["domestic", "international", "market_trading", "environmental"],
    default=["domestic", "international", "market_trading", "environmental"],
    format_func=lambda x: {
        "domestic": "🏠 国内",
        "international": "🌍 国际",
        "market_trading": "💹 市场化",
        "environmental": "🌱 碳资产",
    }.get(x, x),
)

# === 生成报告 ===
st.divider()
st.subheader("📄 报告内容预览")

def generate_markdown_report() -> str:
    """生成 Markdown 格式报告"""
    lines = []

    # 标题
    lines.append(f"# 周报分析报告 - {meta.get('year', '?')}年第{meta.get('week', '?')}周")
    lines.append("")
    lines.append(f"> **报告ID**: `{meta.get('report_id', '?')}`")
    lines.append(f"> **周期**: {meta.get('start_date', '?')} ~ {meta.get('end_date', '?')}")
    lines.append(f"> **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> **数据源**: {'演示数据' if bundle.get('source') == 'default' else '上传文件'}")
    lines.append("")
    lines.append("---")
    lines.append("")

    dim_names = {
        "domestic": "🏠 国内分析",
        "international": "🌍 国际分析",
        "market_trading": "💹 市场化分析",
        "environmental": "🌱 碳资产分析",
    }

    for dim_key in selected_dims:
        result = results.get(dim_key)
        if not result:
            continue

        lines.append(f"## {dim_names.get(dim_key, dim_key)}")
        lines.append("")

        # 总结
        if include_summary and result.summary:
            lines.append(f"### 💎 一句话总结")
            lines.append("")
            lines.append(f"> {result.summary}")
            lines.append("")

        # KPI
        if include_kpis and result.kpis:
            lines.append(f"### 📊 关键指标")
            lines.append("")
            lines.append("| 指标 | 数值 |")
            lines.append("|------|------|")
            for k, v in result.kpis.items():
                lines.append(f"| {k} | {v} |")
            lines.append("")

        # 故事
        if include_story and result.story:
            lines.append(f"### 📖 业务故事")
            lines.append("")
            lines.append(result.story)
            lines.append("")

        # 表格
        if include_tables and result.tables:
            lines.append(f"### 📋 数据明细")
            lines.append("")
            for table in result.tables:
                lines.append(f"**{table.get('title', '')}**")
                lines.append("")
                headers = table.get("headers", [])
                rows = table.get("rows", [])
                if headers and rows:
                    lines.append("| " + " | ".join(headers) + " |")
                    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                    for row in rows:
                        lines.append("| " + " | ".join(str(c) for c in row) + " |")
                lines.append("")

        # 图表说明
        if include_charts_info and result.charts:
            lines.append(f"### 📊 图表说明")
            lines.append("")
            for chart in result.charts:
                lines.append(f"- **{chart.get('title', '')}** ({chart.get('type', 'bar')})")
            lines.append("")

        # 异常
        if include_anomalies and result.anomalies:
            lines.append(f"### ⚠️ 异常告警 ({len(result.anomalies)} 个)")
            lines.append("")
            for a in result.anomalies:
                lines.append(f"- **[{a.get('level', 'info').upper()}]** {a.get('message', '')}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # 总结
    lines.append("## 📋 报告生成信息")
    lines.append("")
    lines.append(f"- 包含维度: {len(selected_dims)} 个")
    lines.append(f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*本报告由 周报自动化 v2 系统自动生成*")

    return "\n".join(lines)

# 实时预览
report_content = generate_markdown_report()

# 统计信息
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("报告长度", f"{len(report_content)} 字符")
with col2:
    st.metric("包含维度", f"{len(selected_dims)} 个")
with col3:
    total_anomalies = sum(
        len(results[k].anomalies) for k in selected_dims
        if results.get(k) and hasattr(results.get(k), 'anomalies')
    )
    st.metric("总异常数", f"{total_anomalies} 个")

# 预览
with st.expander("👀 报告内容预览", expanded=True):
    st.markdown(report_content[:3000] + ("\n\n..." if len(report_content) > 3000 else ""))

# 下载按钮
st.divider()
st.subheader("📥 下载报告")

st.download_button(
    label="📥 下载 Markdown 报告",
    data=report_content,
    file_name=f"weekly_report_{meta.get('year', '2026')}_W{meta.get('week', '21')}.md",
    mime="text/markdown",
    type="primary",
    use_container_width=True,
)

st.caption("💡 Word 报告导出需要 python-docx 库支持，将在 Phase 5 优化版本中提供。")
