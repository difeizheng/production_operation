"""
Streamlit Page 2: 🌍 国际分析
=============================

对应业务图谱: 段 3-4 (国际电价同比 + 环比)
对应 Analyzer: InternationalAnalyzer
"""

import streamlit as st
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="国际分析 - 周报 v2",
    page_icon="🌍",
    layout="wide"
)

from streamlit_app.components import render_analyzer_result

st.title("🌍 国际分析")
st.markdown("### 段 3-4: 国际电价（同比 + 环比）")

bundle = st.session_state.get("bundle")
if not bundle or not bundle.get("results"):
    st.warning("⚠️ 请在主页面选择数据源")
    st.stop()

result = bundle["results"].get("international")
if not result:
    st.error("❌ 国际 Analyzer 执行失败")
    st.stop()

render_analyzer_result(result, dimension_label="🌍 国际")

st.caption("""
📖 详细文档:
- `docs/analysis/domestic-price-analysis-framework.md` 第 15 节
- `docs/user_guide/weekly-report-beginner-guide.md` 第八部分
""")
