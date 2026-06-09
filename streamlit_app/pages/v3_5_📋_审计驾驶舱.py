"""📋 审计驾驶舱 - v3 Phase 3

设计原则：
    1. 数据流入口：state.polished_slots + state.audit_log
    2. 4 大模块：时间线 + 编辑历史 + Token 趋势 + 质量分布
    3. 空 state 友好降级（提示先完成 Step 4）
    4. 不修改任何 src/ 现有代码
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict

import streamlit as st

# 路径设置
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# === 关键：safe_set_page_config 必须在第一个 st 命令之前导入 ===
from streamlit_app.core.safe_page_config import safe_set_page_config

# === 页面配置 ===
safe_set_page_config(
    page_title="审计驾驶舱 - 周报 v3.0",
    page_icon="📋",
    layout="wide",
)

logger = logging.getLogger(__name__)


# ============================================================================
# 入口
# ============================================================================

def main() -> None:
    from streamlit_app.core import get_state_manager
    from streamlit_app.components.audit_timeline import (
        extract_timeline_events,
        render_audit_timeline,
    )
    from streamlit_app.components.edit_history import render_edit_diff
    from streamlit_app.components.version_badge import render_version_badge

    # 顶部：版本徽章 + 标题
    with st.sidebar:
        render_version_badge("v3")
    st.title("📋 审计驾驶舱")
    st.caption("Phase 3 · 时间线追踪 + 编辑历史对比 + Token 趋势分析")

    # 状态
    state_mgr = get_state_manager()
    state = state_mgr.get()

    # === 入口门槛：空 state 友好提示 ===
    if not state.polished_slots:
        st.warning(
            "⚠️ **尚未生成任何段位**\n\n"
            "请先完成以下步骤：\n"
            "1. 📊 进入「数据驾驶舱」上传 Excel\n"
            "2. 🤖 进入「生成驾驶舱」完成 Step 3 提取 + Step 4 润色\n"
            "3. 📋 回到本页面查看审计日志"
        )
        st.stop()

    # === 报告期信息 ===
    meta = (state.raw_data or {}).get("meta", {}) if state.raw_data else {}
    week = meta.get("week", "?")
    year = meta.get("year", "?")
    total_tokens = sum(s.tokens_used for s in state.polished_slots.values())
    st.info(
        f"📅 报告期: {year}-W{week} · "
        f"{len(state.polished_slots)} 段位 · "
        f"{total_tokens:,} tokens"
    )

    # === 1. 时间线视图 ===
    st.divider()
    st.subheader("📜 时间线追踪")
    events = extract_timeline_events(state.polished_slots, state.audit_log)
    render_audit_timeline(events, key="audit_timeline_main")

    # === 2. Token 消耗分析 ===
    st.divider()
    st.subheader("💰 Token 消耗分析")
    _render_token_analysis(state.polished_slots)

    # === 3. 编辑历史对比 ===
    st.divider()
    st.subheader("📝 编辑历史对比")
    _render_edit_history_selector(state.polished_slots)

    # === 4. 质量分布统计 ===
    st.divider()
    st.subheader("🎯 质量分布统计")
    _render_quality_distribution(state.quality_metrics)

    # === 5. 底部操作区 ===
    st.divider()
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    with col_btn1:
        if st.button(
            "⬅️ 返回质量驾驶舱",
            key="back_to_quality",
            use_container_width=True,
        ):
            st.switch_page("streamlit_app/pages/v3_4_🎯_质量驾驶舱.py")
    with col_btn2:
        # 导出审计日志 JSON
        audit_report = _build_audit_report(state, events)
        st.download_button(
            label="📥 导出审计日志 JSON",
            data=json.dumps(audit_report, ensure_ascii=False, indent=2),
            file_name=f"audit_log_{year}_W{week}.json",
            mime="application/json",
            use_container_width=True,
        )
    with col_btn3:
        if st.button(
            "💾 保存快照",
            key="save_snapshot",
            use_container_width=True,
        ):
            snapshot_path = state_mgr.save_snapshot(name="audit")
            st.success(f"✅ 快照已保存: {snapshot_path}")


# ============================================================================
# Token 消耗分析
# ============================================================================

def _render_token_analysis(polished_slots: Dict[str, Any]) -> None:
    """渲染 Token 消耗分析模块。"""
    import pandas as pd

    if not polished_slots:
        st.info("📭 暂无 Token 消耗数据。")
        return

    # 构造 DataFrame
    rows = []
    for slot_id, slot in polished_slots.items():
        rows.append({
            "占位符": slot.placeholder,
            "模式": slot.generation_mode,
            "Tokens": slot.tokens_used,
            "模型": slot.model_used,
            "Fallback": "🔄" if slot.is_fallback else "",
        })

    df = pd.DataFrame(rows)

    # 顶部 KPI
    total_tokens = df["Tokens"].sum()
    avg_tokens = df["Tokens"].mean() if len(df) > 0 else 0
    max_tokens_row = df.loc[df["Tokens"].idxmax()] if len(df) > 0 else None

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 总 Token", f"{total_tokens:,}")
    with col2:
        st.metric("📊 平均 Token", f"{avg_tokens:.0f}")
    with col3:
        st.metric("📈 最大 Token", f"{max_tokens_row['Tokens']:.0f}" if max_tokens_row is not None else "0")
    with col4:
        fallback_count = sum(1 for s in polished_slots.values() if s.is_fallback)
        st.metric("🔄 Fallback", f"{fallback_count}/{len(polished_slots)}")

    st.divider()

    # Token 分布图
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("#### 📊 Token 分布（按段位）")
        if len(df) > 0:
            try:
                import plotly.express as px
                fig = px.bar(
                    df.sort_values("Tokens", ascending=False),
                    x="占位符",
                    y="Tokens",
                    color="模式",
                    title="各段位 Token 消耗",
                    labels={"占位符": "段位", "Tokens": "Token 数"},
                )
                fig.update_layout(height=400, xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                st.warning("⚠️ plotly 未安装，无法渲染图表")
                st.dataframe(df, use_container_width=True, hide_index=True)

    with col_right:
        st.markdown("#### 🥧 模式占比")
        mode_counts = df["模式"].value_counts().reset_index()
        mode_counts.columns = ["模式", "数量"]
        if len(mode_counts) > 0:
            try:
                import plotly.express as px
                fig = px.pie(
                    mode_counts,
                    values="数量",
                    names="模式",
                    title="生成模式分布",
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                st.dataframe(mode_counts, use_container_width=True, hide_index=True)

    # 详细表格
    st.divider()
    st.markdown("#### 📋 Token 明细表")
    st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================================
# 编辑历史对比
# ============================================================================

def _render_edit_history_selector(polished_slots: Dict[str, Any]) -> None:
    """渲染编辑历史对比模块（带段位选择器）。"""
    from streamlit_app.components.edit_history import render_edit_diff

    if not polished_slots:
        st.info("📭 暂无可对比的编辑历史。")
        return

    # 段位选择器
    slot_options = [
        f"{slot.placeholder} ({slot.generation_mode})"
        for slot in polished_slots.values()
    ]
    selected_label = st.selectbox(
        "选择段位查看详情",
        options=slot_options,
        key="audit_edit_history_select",
    )

    # 找到对应的 slot
    selected_slot = next(
        (slot for slot in polished_slots.values()
         if f"{slot.placeholder} ({slot.generation_mode})" == selected_label),
        None
    )

    if selected_slot:
        render_edit_diff(selected_slot, key=f"audit_edit_diff_{selected_slot.placeholder}")
    else:
        st.warning("⚠️ 未找到选中的段位")


# ============================================================================
# 质量分布统计
# ============================================================================

def _render_quality_distribution(quality_metrics: Dict[str, Any]) -> None:
    """渲染质量分布统计模块。"""
    if not quality_metrics:
        st.info("📭 暂无质量分数据。请先完成 Step 4 润色。")
        return

    # 分数段统计
    score_ranges = {
        "优秀 (≥80)": 0,
        "良好 (60-79)": 0,
        "警告 (40-59)": 0,
        "严重 (<40)": 0,
    }

    for metric in quality_metrics.values():
        score = metric.overall_score
        if score >= 80:
            score_ranges["优秀 (≥80)"] += 1
        elif score >= 60:
            score_ranges["良好 (60-79)"] += 1
        elif score >= 40:
            score_ranges["警告 (40-59)"] += 1
        else:
            score_ranges["严重 (<40)"] += 1

    # 顶部 KPI
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("✅ 优秀", score_ranges["优秀 (≥80)"])
    with col2:
        st.metric("🟡 良好", score_ranges["良好 (60-79)"])
    with col3:
        st.metric("🟠 警告", score_ranges["警告 (40-59)"])
    with col4:
        st.metric("🔴 严重", score_ranges["严重 (<40)"])

    st.divider()

    # 质量分布图
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("#### 📊 质量分分布")
        try:
            import plotly.express as px
            import pandas as pd

            df = pd.DataFrame([
                {"分数段": k, "段位数": v}
                for k, v in score_ranges.items()
            ])
            fig = px.bar(
                df,
                x="分数段",
                y="段位数",
                color="分数段",
                title="质量分分布",
                color_discrete_map={
                    "优秀 (≥80)": "green",
                    "良好 (60-79)": "orange",
                    "警告 (40-59)": "darkorange",
                    "严重 (<40)": "red",
                },
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            st.warning("⚠️ plotly 未安装，无法渲染图表")

    with col_right:
        st.markdown("#### 🥧 通过率")
        total = len(quality_metrics)
        passed = sum(1 for m in quality_metrics.values() if m.overall_score >= 80)
        pass_rate = passed / total if total > 0 else 0

        try:
            import plotly.graph_objects as go
            fig = go.Figure(data=[
                go.Pie(
                    labels=["通过", "未通过"],
                    values=[passed, total - passed],
                    hole=0.4,
                    marker=dict(colors=["green", "red"]),
                )
            ])
            fig.update_layout(
                height=400,
                annotations=[dict(text=f"{pass_rate:.0%}", x=0.5, y=0.5, font_size=30, showarrow=False)],
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            st.warning("⚠️ plotly 未安装，无法渲染图表")


# ============================================================================
# 审计报告构建
# ============================================================================

def _build_audit_report(state: Any, events: list) -> Dict[str, Any]:
    """构建审计报告 JSON。"""
    meta = (state.raw_data or {}).get("meta", {}) if state.raw_data else {}

    return {
        "report_info": {
            "year": meta.get("year", "?"),
            "week": meta.get("week", "?"),
            "timestamp": datetime.now().isoformat(),
            "total_slots": len(state.polished_slots),
            "total_tokens": sum(s.tokens_used for s in state.polished_slots.values()),
        },
        "events": [
            {
                "stage": e.stage,
                "slot_id": e.slot_id,
                "timestamp": e.timestamp,
                "status": e.status,
                "detail": e.detail,
                "metadata": e.metadata,
            }
            for e in events
        ],
        "slots": [
            {
                "slot_id": slot.slot_id,
                "placeholder": slot.placeholder,
                "generation_mode": slot.generation_mode,
                "automation_level": slot.automation_level,
                "tokens_used": slot.tokens_used,
                "model_used": slot.model_used,
                "is_fallback": slot.is_fallback,
                "is_edited": slot.is_edited_by_human,
                "quality_score": state.quality_metrics.get(slot.slot_id, {}).overall_score if slot.slot_id in state.quality_metrics else None,
            }
            for slot in state.polished_slots.values()
        ],
    }


if __name__ == "__main__":
    main()
else:
    # Streamlit 多页机制下，模块被 import 时也直接执行 main
    main()
