"""
Streamlit Page 1: 🏠 国内分析
=============================

对应业务图谱: 段 1-2 (国内电量 + 国内电价)
对应 Analyzer: DomesticAnalyzer
"""

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
from streamlit_app.components import render_analyzer_result

st.title("🏠 国内分析")
st.markdown("### 段 1-2: 国内电量 + 国内电价")

# 从 session_state 读取已分析结果
bundle = st.session_state.get("bundle")
if not bundle or not bundle.get("results"):
    st.warning("⚠️ 请在主页面选择数据源")
    st.stop()

result = bundle["results"].get("domestic")
if not result:
    st.error("❌ 国内 Analyzer 执行失败")
    st.stop()

# 渲染完整结果
render_analyzer_result(result, dimension_label="🏠 国内")

st.caption("""
📖 详细文档:
- `docs/analysis/domestic-price-analysis-framework.md` 第 1-14 节
- `docs/user_guide/weekly-report-beginner-guide.md` 第五部分
""")
