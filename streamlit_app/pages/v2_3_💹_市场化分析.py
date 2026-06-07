"""
Streamlit Page 3: 💹 市场化分析
===============================

对应业务图谱: 段 5-7 (水电/新能源/火电市场化)
对应 Analyzer: MarketTradingAnalyzer
"""

import streamlit as st
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# v3.1: 必须在第一个 st 命令之前导入
from streamlit_app.core.safe_page_config import safe_set_page_config

safe_set_page_config(
    page_title="市场化分析 - 周报 v2",
    page_icon="💹",
    layout="wide"
)

from streamlit_app.components import render_analyzer_result

st.title("💹 市场化分析")
st.markdown("### 段 5-7: 同一周 3 个相反故事")

# v3.1: 使用 data_bridge.ensure_bundle 替代直接读 session_state
from streamlit_app.core.data_bridge import ensure_bundle
bundle = ensure_bundle()
if not bundle or not bundle.get("results"):
    st.warning("⚠️ 请在主页面选择数据源")
    st.stop()

result = bundle["results"].get("market_trading")
if not result:
    st.error("❌ 市场化 Analyzer 执行失败")
    st.stop()

render_analyzer_result(result, dimension_label="💹 市场化")

st.caption("""
📖 详细文档:
- `docs/analysis/domestic-price-analysis-framework.md` 第 16 节
- `docs/user_guide/weekly-report-beginner-guide.md` 第十一部分
""")
