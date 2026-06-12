"""📊 报告沙盘 - Step 1: Excel 上传 + 数据溯源 + 报告预览

功能：
    1. 上传 Excel（综合分析表 + 可选汇总表）
    2. 自动构建数据溯源链（字段 → 单元格 → 验证）
    3. 以报告段落为锚点，自顶向下展示数据来源及准确性
    4. 信任度评分 + 待处理事项 + 高级视图

v3.5 重构：合并原 Step 1（数据驾驶舱）+ Step 2（映射驾驶舱）
    - 翻转视角：先看报告预览，再逐个数字溯源到 Excel 单元格
    - 信任度评分条 + 15 个段落卡片 + 行动项
    - 高级视图折叠保留原功能（字段表 + 映射规则 + KPI）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

# 路径设置（必须在 import streamlit_app.* 之前）
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# === 关键：safe_set_page_config 必须在第一个 st 命令之前导入 ===
from streamlit_app.core.safe_page_config import safe_set_page_config

# === 页面配置 ===
safe_set_page_config(
    page_title="报告沙盘 - 周报 v3.5",
    page_icon="📊",
    layout="wide",
)

# === 导入 ===
from src.collector.analysis_collector import AnalysisCollector
from src.collector.summary_collector import SummaryCollector
from src.collector.trace_builder import (
    build_paragraph_traces,
    build_trace_report,
)
from streamlit_app.core import get_state_manager
from streamlit_app.core.v3_data_adapter import adapt_collector_output
from streamlit_app.components import (
    render_excel_preview,
    render_kpi_overview,
    render_pipeline_stepper,
)
from streamlit_app.components.trust_score import (
    compute_trust_score,
    render_trust_score_bar,
)
from streamlit_app.components.report_sandbox import render_report_sandbox
from streamlit_app.components.trace_table import render_trace_table


# ============================================================================
# 数据采集函数（保留自原 Step 1）
# ============================================================================


def collect_analysis_data(excel_path: Path) -> Optional[Dict[str, Any]]:
    """从综合分析表采集数据。

    AnalysisCollector.collect() 返回 Tuple[Dict, List[Dict]]：
        (data_dict, errors_list)
    本函数解包后只返回 data_dict（错误信息通过其他渠道显示）。

    v3.2 新增：调用 adapt_collector_output 把采集器输出转换为 UI 标准格式
              （与演示数据 weekly_report_merged.json 结构一致）
    """
    try:
        collector = AnalysisCollector()
        result = collector.collect(str(excel_path))
        # v3.1 bug fix: 解包 (data, errors) tuple
        if isinstance(result, tuple):
            data, errors = result
            if errors:
                st.warning(f"⚠️ 采集时发现 {len(errors)} 个问题（已忽略）")
            adapted = adapt_collector_output(data)
            return adapted
        return result
    except Exception as e:
        st.error(f"❌ 数据采集失败: {e}")
        return None


def collect_summary_data(summary_path: Path) -> Optional[Dict[str, Any]]:
    """从汇总表采集补充数据。"""
    try:
        collector = SummaryCollector()
        result = collector.collect(str(summary_path))
        if isinstance(result, tuple):
            data, errors = result
            if errors:
                st.info(f"ℹ️ 汇总表采集: {len(errors)} 个非致命问题（已忽略）")
            return data
        return result
    except Exception as e:
        st.warning(f"⚠️ 汇总表采集失败（可忽略）: {e}")
        return None


def load_reason_map() -> Dict[str, Any]:
    """加载 reason_map.json（带缓存）。"""
    map_path = project_root / "data" / "dictionaries" / "reason_map.json"
    if not map_path.exists():
        return {}
    return json.loads(map_path.read_text(encoding="utf-8"))


# ============================================================================
# Header
# ============================================================================

from streamlit_app.core.version_router import get_current_version
from streamlit_app.components import render_version_badge

render_version_badge(get_current_version())

st.title("📊 报告沙盘")
st.caption("Step 1/7 · 上传数据 → 信任度评分 → 报告数据预览 → 溯源校验")
st.divider()

# 步骤导航
state_mgr = get_state_manager()
render_pipeline_stepper(current_step=1)

st.divider()

# ============================================================================
# 数据源选择（保留原 Step 1 完整逻辑）
# ============================================================================

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
if "_active_source" not in st.session_state:
    st.session_state["_active_source"] = None
if "_uploaded_excel_bytes" not in st.session_state:
    st.session_state["_uploaded_excel_bytes"] = None
if "_uploaded_excel_name" not in st.session_state:
    st.session_state["_uploaded_excel_name"] = None
if "_uploaded_summary_bytes" not in st.session_state:
    st.session_state["_uploaded_summary_bytes"] = None
if "_uploaded_summary_name" not in st.session_state:
    st.session_state["_uploaded_summary_name"] = None

# 检测数据源是否变化，变化时清除旧数据
if st.session_state["_active_source"] != source_type:
    st.session_state["_active_source"] = source_type
    st.session_state["_analysis_data"] = None
    st.session_state["_excel_path"] = None
    st.session_state["_uploaded_excel_bytes"] = None
    st.session_state["_uploaded_excel_name"] = None

if source_type == "🎭 演示数据":
    # 加载演示 fixture
    fixture_path = (
        project_root / "tests" / "fixtures" / "weekly_report_merged.json"
    )
    if fixture_path.exists():
        st.session_state["_analysis_data"] = json.loads(
            fixture_path.read_text(encoding="utf-8")
        )
        st.session_state["_excel_path"] = str(fixture_path)
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
    # v3.4 修复：在数据源切换时，优先使用 session_state 中保存的文件字节

    # 如果 session_state 中有保存的文件，自动恢复处理
    if (
        st.session_state["_uploaded_excel_bytes"] is not None
        and st.session_state["_analysis_data"] is None
    ):
        tmp_path = project_root / "files" / "_tmp_analysis.xlsx"
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(st.session_state["_uploaded_excel_bytes"])
        st.session_state["_excel_path"] = str(tmp_path)

        with st.spinner("⏳ 正在恢复之前上传的 Excel..."):
            data = collect_analysis_data(tmp_path)
            if data:
                st.session_state["_analysis_data"] = data
                state_mgr.update_field(
                    raw_data=data, excel_path=str(tmp_path)
                )
                from streamlit_app.core.data_bridge import sync_v3_to_v2

                sync_v3_to_v2()
                st.info(
                    f"📂 已恢复之前上传的 Excel: {st.session_state['_uploaded_excel_name']}"
                )

    # 上传 Excel
    col1, col2 = st.columns(2)
    with col1:
        excel_file = st.file_uploader(
            "📁 上传综合分析表",
            type=["xlsx"],
            help="2026年第21周周数据综合分析报表.xlsx",
            key="excel_uploader",
        )
    with col2:
        summary_file = st.file_uploader(
            "📁 上传汇总表（可选）",
            type=["xlsx"],
            help="周数据汇总表.xlsx",
            key="summary_uploader",
        )

    if excel_file is not None:
        file_bytes = excel_file.read()
        st.session_state["_uploaded_excel_bytes"] = file_bytes
        st.session_state["_uploaded_excel_name"] = excel_file.name

        tmp_path = project_root / "files" / "_tmp_analysis.xlsx"
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(file_bytes)
        st.session_state["_excel_path"] = str(tmp_path)

        with st.spinner("⏳ 正在采集数据..."):
            data = collect_analysis_data(tmp_path)
            if data:
                st.session_state["_analysis_data"] = data
                state_mgr.update_field(
                    raw_data=data, excel_path=str(tmp_path)
                )
                from streamlit_app.core.data_bridge import sync_v3_to_v2

                sync_v3_to_v2()
                st.success(
                    f"✅ 综合分析表采集完成（{len(data)} 个字段，文件: {excel_file.name}）"
                )
            else:
                st.error("❌ 综合分析表采集失败")

    if summary_file is not None:
        st.session_state["_uploaded_summary_bytes"] = summary_file.read()
        st.session_state["_uploaded_summary_name"] = summary_file.name

        tmp_summary = project_root / "files" / "_tmp_summary.xlsx"
        tmp_summary.parent.mkdir(parents=True, exist_ok=True)
        tmp_summary.write_bytes(st.session_state["_uploaded_summary_bytes"])
        st.session_state["_summary_path"] = str(tmp_summary)

        with st.spinner("⏳ 正在采集汇总表..."):
            data = collect_summary_data(tmp_summary)
            if data:
                st.session_state["_summary_data"] = data
                state_mgr.update_field(summary_path=str(tmp_summary))
                st.success(f"✅ 汇总表采集完成（{len(data)} 个字段）")

st.divider()

# ============================================================================
# 报告沙盘主视图（合并原 Step 1+2）
# ============================================================================

data = st.session_state.get("_analysis_data")

if data:
    # --- 构建溯源数据 ---
    trace_report = build_trace_report(data)
    reason_map = load_reason_map()
    mappings = reason_map.get("mappings", [])
    paragraph_traces = (
        build_paragraph_traces(reason_map, trace_report, data)
        if reason_map
        else []
    )

    # --- 2️⃣ 信任度评分 ---
    st.subheader("2️⃣ 数据信任度")
    trust = compute_trust_score(trace_report, paragraph_traces)
    render_trust_score_bar(trust)

    st.divider()

    # --- 3️⃣ 报告数据预览（自顶向下） ---
    render_report_sandbox(
        paragraph_traces, trace_report, data, key="v3_sandbox"
    )

    st.divider()

    # --- 4️⃣ 高级视图（折叠） ---
    with st.expander("▸ 🔬 高级视图（字段表 + 映射规则 + KPI）"):
        adv_tab1, adv_tab2, adv_tab3 = st.tabs(
            ["📋 全字段溯源表", "🗺️ 映射规则", "🎯 关键指标"]
        )

        with adv_tab1:
            render_trace_table(trace_report)

        with adv_tab2:
            st.subheader("🗺️ 映射规则")
            if mappings:
                st.caption(f"共 {len(mappings)} 条映射规则")
                for m in mappings:
                    level = m.get("automation_level", "?")
                    level_badge = {
                        "HIGH": "🟢",
                        "MEDIUM": "🟡",
                        "MANUAL": "🔴",
                    }.get(level, "❓")
                    placeholder = m.get("template_placeholder", "")
                    slots = m.get("source_slots", [])
                    polish = "✏️" if m.get("polish_required") else "✅"
                    st.markdown(
                        f"{level_badge} **{placeholder}** {polish} "
                        f"— {len(slots)} 个槽位 — {m.get('notes', '')}"
                    )
                    if slots:
                        st.code(", ".join(slots))
            else:
                st.info("未加载映射规则")

        with adv_tab3:
            render_kpi_overview(data)

    st.divider()

    # --- 保存 + 进入生成 ---
    if st.button(
        "💾 保存数据 + 进入生成驾驶舱",
        type="primary",
        use_container_width=True,
    ):
        state_mgr.update_field(
            raw_data=data,
            excel_path=st.session_state.get("_excel_path"),
            summary_path=st.session_state.get("_summary_path"),
            mappings=mappings,
            current_step=3,
        )
        st.success("✅ 数据已保存，进入 Step 3: 🤖 生成驾驶舱")
        st.info("👈 请点击左侧菜单进入「🤖 生成驾驶舱」")
else:
    st.info("👆 请先选择数据源")

# ============================================================================
# 侧边栏
# ============================================================================

with st.sidebar:
    st.header("📊 报告沙盘")
    st.caption("Step 1/7")

    if data:
        active_source = st.session_state.get("_active_source", "未知")
        if active_source == "🎭 演示数据":
            st.success("📦 当前数据源：🎭 演示数据")
        elif active_source == "📁 上传 Excel":
            excel_name = st.session_state.get("_uploaded_excel_name", "—")
            st.success(f"📦 当前数据源：📁 {excel_name}")
        else:
            st.info(f"📦 当前数据源：{active_source}")

        st.metric("已加载字段", len(data))

        # 清除数据按钮
        if st.button(
            "🗑️ 清除已加载数据",
            use_container_width=True,
            type="secondary",
        ):
            st.session_state["_analysis_data"] = None
            st.session_state["_summary_data"] = None
            st.session_state["_excel_path"] = None
            st.session_state["_summary_path"] = None
            st.session_state["_uploaded_excel_bytes"] = None
            st.session_state["_uploaded_excel_name"] = None
            st.session_state["_uploaded_summary_bytes"] = None
            st.session_state["_uploaded_summary_name"] = None
            st.session_state["_active_source"] = None
            st.rerun()
    else:
        st.warning("未加载数据")

    st.divider()
    st.caption(
        """
**提示**:
- 演示数据可直接体验完整流程
- 上传 Excel 时确保 sheet 名匹配
- 信任度评分综合了采集率、自动化率、数据校验
- 字段缺失不影响生成（会使用 fallback）
- 点击段落卡片中的数字可查看完整证据链
"""
    )
