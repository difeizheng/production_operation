"""
Streamlit Page 4: 🌱 碳资产分析
===============================

对应业务图谱: 段 8 (绿证 + CCER)
对应 Analyzer: EnvironmentalAnalyzer
"""

import streamlit as st
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="碳资产分析 - 周报 v2",
    page_icon="🌱",
    layout="wide"
)

from streamlit_app.components import render_analyzer_result

st.title("🌱 碳资产分析")
st.markdown("### 段 8: 绿证 + CCER（卖空气换钱的新业务）")

# v3.1: 使用 data_bridge.ensure_bundle 替代直接读 session_state
from streamlit_app.core.data_bridge import ensure_bundle
bundle = ensure_bundle()
if not bundle or not bundle.get("results"):
    st.warning("⚠️ 请在主页面选择数据源")
    st.stop()

result = bundle["results"].get("environmental")
if not result:
    st.error("❌ 碳资产 Analyzer 执行失败")
    st.stop()

render_analyzer_result(result, dimension_label="🌱 碳资产")

st.caption("""
📖 详细文档:
- `docs/analysis/domestic-price-analysis-framework.md` 第 17 节
- `docs/user_guide/weekly-report-beginner-guide.md` 第十一部分案例 14
""")
