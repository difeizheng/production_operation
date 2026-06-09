"""🎯 质量驾驶舱 - v3 Phase 2

设计原则：
    1. 数据流入口：state.quality_metrics（Step 4/5 自动填充）
    2. 4 KPI 卡片 + 4 维雷达图 + 段位详情表 + 4 重检测规则说明
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
    page_title="质量驾驶舱 - 周报 v3.0",
    page_icon="🎯",
    layout="wide",
)

logger = logging.getLogger(__name__)


# ============================================================================
# 入口
# ============================================================================

def main() -> None:
    from streamlit_app.core import (
        get_state_manager, evaluate, aggregate_overall,
    )
    from streamlit_app.components import (
        render_quality_radar, render_quality_score_table,
        render_quality_summary,
    )
    from streamlit_app.components.version_badge import render_version_badge

    # 顶部：版本徽章 + 标题
    with st.sidebar:
        render_version_badge("v3")
    st.title("🎯 质量驾驶舱")
    st.caption("Phase 2 · 4 重检测（数字/长度/禁词/专业度）+ 段位雷达 + 4 档门禁")

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
            "3. 🎯 回到本页面查看质量分"
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

    # === 1. KPI 卡片 + 状态徽章 ===
    st.divider()
    aggregate = aggregate_overall(state.quality_metrics)
    gate_result = evaluate(state)

    render_quality_summary(
        avg=aggregate["avg_score"],
        pass_rate=aggregate["pass_rate"],
        min_score=aggregate["min_score"],
        count=aggregate["count"],
        verdict=gate_result.verdict.value,
        key="quality_summary_top",
    )

    # === 2. 雷达图 + 段位详情表（左右布局） ===
    st.divider()
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("📡 4 维质量雷达（聚合）")
        render_quality_radar(
            state.quality_metrics,
            key="quality_radar_main",
        )

    with col_right:
        st.subheader("📋 段位详情")
        render_quality_score_table(
            state.quality_metrics,
            state.polished_slots,
            key="quality_score_table_main",
        )

    # === 3. 4 重检测规则说明（4 个 expander）===
    st.divider()
    st.subheader("📖 4 重检测规则")
    col_a, col_b = st.columns(2)
    with col_a:
        with st.expander("🔢 数字保留（30 分）", expanded=False):
            st.markdown("""
**检测目标**：LLM 输出中所有 ≥2 位数字必须出现在原始文本中（容差 ±0.011）。

**复用**：`streamlit_app/core/llm_orchestrator.py:337-354` 的 `_validate_numbers` 算法。

**通过条件**：`output_significant ⊆ input_significant`

**未通过 → 警告**：`数字与原文不一致`（说明 LLM 瞎编了数字）
""")
        with st.expander("📏 长度合理（20 分）", expanded=False):
            st.markdown("""
**检测目标**：polished 文本长度相对于原文在合理范围内。

**算法**：`ratio = len(polished) / len(raw)`，要求 `0.5 ≤ ratio ≤ 1.8`

**复用**：`src/generator/reason_polisher.py:390-393` 的 1.8x 阈值。

**未通过 → 警告**：
- `过长(原文 X 字→改写 Y 字, Zx)` - LLM 注水
- `过短(原文 X 字→改写 Y 字, Zx)` - LLM 偷懒
""")
    with col_b:
        with st.expander("🚫 禁词扫描（20 分）", expanded=False):
            st.markdown("""
**检测目标**：polished 文本不含推测性措辞。

**禁词表**（6 个）：`预计将 / 据预测 / 有望 / 可能会 / 或将 / 可能将`

**复用**：`src/generator/reason_polisher.py:383-388` 的 forbidden 列表。

**未通过 → 警告**：`含禁词: <word>`
""")
        with st.expander("💼 专业度（20 分）", expanded=False):
            st.markdown("""
**检测目标**：polished 文本符合电力/能源行业写作规范。

**4 维度评分**：
- A. **行业术语命中**（从 `data/dictionaries/*.json` 加载 30+ 术语）
- B. **结构化句式**（"一是…二是…" / "1、2、3、" / "主因…影响"）
- C. **段落长度区间**（50-600 字为专业段落）
- D. **无口语化**（避免"我们/我觉得/其实/挺/蛮"）

**离散化**：0 / 10 / 20 三档。

**未通过 → 警告**：`行业术语稀疏(命中N/M)` / `缺乏并列/因果结构标记` / `段落过短/过长` / `含口语化表达`
""")

    # === 4. 底部操作区 ===
    st.divider()
    col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
    with col_btn1:
        if st.button(
            "⬅️ 返回生成驾驶舱",
            key="back_to_generate",
            use_container_width=True,
        ):
            state_mgr.update_field(current_step=4)
            st.success("✅ 已切回 Step 4")
    with col_btn2:
        if st.button(
            "🔄 重新计算质量分",
            key="recompute_quality",
            use_container_width=True,
        ):
            from streamlit_app.core.quality_metrics import (
                clear_industry_terms_cache, compute_batch_metrics,
            )
            clear_industry_terms_cache()  # 强制重读词典
            new_metrics = compute_batch_metrics(state.polished_slots)
            state_mgr.update_field(quality_metrics=new_metrics)
            st.success("✅ 质量分已重新计算")
            st.rerun()
    with col_btn3:
        # 导出 JSON
        report = {
            "year": year,
            "week": week,
            "timestamp": datetime.now().isoformat(),
            "gate": {
                "verdict": gate_result.verdict.value,
                "avg_score": gate_result.avg_score,
                "fallback_ratio": gate_result.fallback_ratio,
                "reasons": gate_result.reasons,
                "can_generate": gate_result.can_generate,
            },
            "aggregate": aggregate,
            "slots": [
                {
                    "slot_id": m.slot_id,
                    "numbers": 30 if m.numbers_consistency else 0,
                    "length": 20 if m.length_reasonable else 0,
                    "forbidden": 20 if m.no_forbidden_words else 0,
                    "professionalism": m.professionalism,
                    "deviation": m.original_deviation,
                    "total": m.overall_score,
                    "warnings": m.warnings,
                }
                for m in state.quality_metrics.values()
            ],
        }
        st.download_button(
            label="📥 导出质量报告 JSON",
            data=json.dumps(report, ensure_ascii=False, indent=2),
            file_name=f"quality_report_{year}_W{week}.json",
            mime="application/json",
            use_container_width=True,
        )
    with col_btn4:
        if gate_result.verdict.value in ("block", "critical"):
            if st.button(
                "📝 跳到 Step 5 编辑",
                key="jump_to_step5",
                type="primary",
                use_container_width=True,
            ):
                state_mgr.update_field(current_step=5)
                st.success("✅ 已切换到 Step 5")


if __name__ == "__main__":
    main()
else:
    # Streamlit 多页机制下，模块被 import 时也直接执行 main
    main()
