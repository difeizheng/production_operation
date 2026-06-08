"""📊 数据驾驶舱 - Step 1: Excel 上传 + 186 字段预览

功能：
    1. 上传 Excel（综合分析表）
    2. 调用 AnalysisCollector 采集
    3. 显示字段覆盖率 + KPI 概览
    4. 进入下一步
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st

# 路径设置（必须在 import streamlit_app.* 之前）
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# === 关键：safe_set_page_config 必须在第一个 st 命令之前导入 ===
from streamlit_app.core.safe_page_config import safe_set_page_config

# === 页面配置 ===
safe_set_page_config(
    page_title="数据驾驶舱 - 周报 v3.0",
    page_icon="📊",
    layout="wide",
)

# === 页面内的其他 import（在 set_page_config 之后） ===
import pandas as pd

# === 导入 ===
from src.collector.analysis_collector import AnalysisCollector
from src.collector.summary_collector import SummaryCollector
from streamlit_app.core import get_state_manager
from streamlit_app.components import (
    render_excel_preview,
    render_kpi_overview,
    render_pipeline_stepper,
)


# === 工具函数 ===
def collect_analysis_data(excel_path: Path) -> Optional[Dict[str, Any]]:
    """从综合分析表采集数据。

    AnalysisCollector.collect() 返回 Tuple[Dict, List[Dict]]：
        (data_dict, errors_list)
    本函数解包后只返回 data_dict（错误信息通过其他渠道显示）。
    """
    try:
        collector = AnalysisCollector()
        result = collector.collect(str(excel_path))
        # v3.1 bug fix: 解包 (data, errors) tuple
        if isinstance(result, tuple):
            data, errors = result
            if errors:
                st.warning(f"⚠️ 采集时发现 {len(errors)} 个问题（已忽略）")
            return data
        # 向后兼容：老版本可能直接返回 dict
        return result
    except Exception as e:
        st.error(f"❌ 数据采集失败: {e}")
        return None


def collect_summary_data(summary_path: Path) -> Optional[Dict[str, Any]]:
    """从汇总表采集补充数据。

    SummaryCollector.collect() 返回 Tuple[Dict, List[Dict]]：
        (data_dict, errors_list)
    本函数解包后只返回 data_dict。
    """
    try:
        collector = SummaryCollector()
        result = collector.collect(str(summary_path))
        # v3.1 bug fix: 解包 (data, errors) tuple
        if isinstance(result, tuple):
            data, errors = result
            if errors:
                st.info(f"ℹ️ 汇总表采集: {len(errors)} 个非致命问题（已忽略）")
            return data
        return result
    except Exception as e:
        st.warning(f"⚠️ 汇总表采集失败（可忽略）: {e}")
        return None


# === Header ===
# v3.1: 版本徽章 + 标题
from streamlit_app.core.version_router import get_current_version
from streamlit_app.components import render_version_badge
render_version_badge(get_current_version())

st.title("📊 数据驾驶舱")
st.caption("Step 1/7 · 上传 Excel + 字段预览 + 异常检测")
st.divider()

# 步骤导航
state_mgr = get_state_manager()
render_pipeline_stepper(current_step=1)

st.divider()

# === 数据源选择 ===
st.subheader("1️⃣ 选择数据源")

source_type = st.radio(
    "数据来源",
    options=["🎭 演示数据", "📁 上传 Excel"],
    index=0,
    horizontal=True,
    help="演示数据使用 tests/fixtures/weekly_report_merged.json",
)

# 初始化 session 中的数据
if "_analysis_data" not in st.session_state:
    st.session_state["_analysis_data"] = None
if "_summary_data" not in st.session_state:
    st.session_state["_summary_data"] = None
if "_excel_path" not in st.session_state:
    st.session_state["_excel_path"] = None
if "_summary_path" not in st.session_state:
    st.session_state["_summary_path"] = None


if source_type == "🎭 演示数据":
    # 加载演示 fixture
    fixture_path = project_root / "tests" / "fixtures" / "weekly_report_merged.json"
    if fixture_path.exists():
        import json
        st.session_state["_analysis_data"] = json.loads(fixture_path.read_text(encoding="utf-8"))
        st.session_state["_excel_path"] = str(fixture_path)
        # v3.1: 同步到 v3 pipeline_state + v2 bundle
        state_mgr.update_field(
            raw_data=st.session_state["_analysis_data"],
            excel_path=str(fixture_path),
        )
        from streamlit_app.core.data_bridge import sync_v3_to_v2
        sync_v3_to_v2()
        st.success(f"✅ 演示数据已加载: {fixture_path.name}")
    else:
        st.error(f"❌ 演示数据文件不存在: {fixture_path}")
else:
    # 上传 Excel
    col1, col2 = st.columns(2)
    with col1:
        excel_file = st.file_uploader(
            "📁 上传综合分析表",
            type=["xlsx"],
            help="2026年第21周周数据综合分析报表.xlsx",
        )
    with col2:
        summary_file = st.file_uploader(
            "📁 上传汇总表（可选）",
            type=["xlsx"],
            help="周数据汇总表.xlsx",
        )

    if excel_file is not None:
        # 保存到临时路径
        tmp_path = project_root / "files" / "_tmp_analysis.xlsx"
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(excel_file.read())
        st.session_state["_excel_path"] = str(tmp_path)

        with st.spinner("⏳ 正在采集数据..."):
            data = collect_analysis_data(tmp_path)
            if data:
                st.session_state["_analysis_data"] = data
                # v3.1: 同步到 v3 pipeline_state + v2 bundle
                state_mgr.update_field(raw_data=data, excel_path=str(tmp_path))
                from streamlit_app.core.data_bridge import sync_v3_to_v2
                sync_v3_to_v2()
                st.success(f"✅ 综合分析表采集完成（{len(data)} 个字段）")
            else:
                st.error("❌ 综合分析表采集失败")

    if summary_file is not None:
        tmp_summary = project_root / "files" / "_tmp_summary.xlsx"
        tmp_summary.parent.mkdir(parents=True, exist_ok=True)
        tmp_summary.write_bytes(summary_file.read())
        st.session_state["_summary_path"] = str(tmp_summary)

        with st.spinner("⏳ 正在采集汇总表..."):
            data = collect_summary_data(tmp_summary)
            if data:
                st.session_state["_summary_data"] = data
                # ⭐ 关键：把 summary_path 写入 state，否则 Step 4 拿不到
                state_mgr.update_field(summary_path=str(tmp_summary))
                st.success(f"✅ 汇总表采集完成（{len(data)} 个字段）")

st.divider()

# === 字段预览 ===
data = st.session_state.get("_analysis_data")
if data:
    st.subheader("2️⃣ 字段预览")
    render_excel_preview(data, title="综合分析表")

    st.divider()

    # === KPI 概览 ===
    render_kpi_overview(data)

    st.divider()

    # === 保存到 PipelineState ===
    if st.button("💾 保存数据 + 进入下一步", type="primary", use_container_width=True):
        state_mgr.update_field(
            raw_data=data,
            excel_path=st.session_state.get("_excel_path"),
            summary_path=st.session_state.get("_summary_path"),
            current_step=2,
        )
        st.success("✅ 数据已保存，进入 Step 2: 🧩 映射驾驶舱")
        st.info("👈 请点击左侧菜单进入「🧩 映射驾驶舱」")
else:
    st.info("👆 请先选择数据源")

# === 侧边栏 ===
with st.sidebar:
    st.header("📊 数据驾驶舱")
    st.caption("Step 1/7")

    if data:
        st.metric("已加载字段", len(data))
        st.metric("Excel 路径", st.session_state.get("_excel_path", "—") or "—")
    else:
        st.warning("未加载数据")

    st.divider()
    st.caption("""
    **提示**:
    - 演示数据可直接体验
    - 上传 Excel 时确保 sheet 名匹配
    - 字段缺失不影响生成（fallback）
    """)
