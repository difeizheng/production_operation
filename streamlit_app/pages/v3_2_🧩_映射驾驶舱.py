"""🧩 映射驾驶舱 - Step 2: 15 个 ReasonSlot 映射可视化

功能：
    1. 加载 reason_map.json
    2. 展示 15 个映射规则
    3. 每个映射可展开查看 source_slots / fallback_text
    4. 支持编辑 fallback_text（高级）
    5. 进入 Step 3
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

# 路径设置
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# === 页面配置 ===
st.set_page_config(
    page_title="映射驾驶舱 - 周报 v3.0",
    page_icon="🧩",
    layout="wide",
)

# === 导入 ===
from streamlit_app.core import get_state_manager
from streamlit_app.components import render_pipeline_stepper


# === 加载 reason_map.json ===
REASON_MAP_PATH = project_root / "data" / "dictionaries" / "reason_map.json"


@st.cache_data
def load_reason_map() -> Dict[str, Any]:
    """加载 reason_map.json（带缓存）。"""
    if not REASON_MAP_PATH.exists():
        return {}
    return json.loads(REASON_MAP_PATH.read_text(encoding="utf-8"))


# === Header ===
# v3.1: 版本徽章
from streamlit_app.core.version_router import get_current_version
from streamlit_app.components import render_version_badge
render_version_badge(get_current_version())

st.title("🧩 映射驾驶舱")
st.caption("Step 2/7 · 15 个 ReasonSlot 映射规则")
st.divider()

state_mgr = get_state_manager()
render_pipeline_stepper(current_step=2)

st.divider()

# === 检查前置条件 ===
state = state_mgr.get()
if not state.raw_data:
    st.warning("⚠️ 请先在 Step 1 加载数据")
    st.info("👈 请点击左侧菜单进入「📊 数据驾驶舱」")
    st.stop()

# === 加载映射 ===
reason_map = load_reason_map()
if not reason_map:
    st.error(f"❌ reason_map.json 不存在: {REASON_MAP_PATH}")
    st.stop()

mappings = reason_map.get("mappings", [])
total = reason_map.get("total_mappings", len(mappings))

st.success(f"✅ 已加载 {total} 个映射规则（version {reason_map.get('version', '?')}）")

# === 统计概览 ===
st.subheader("1️⃣ 映射概览")

by_level: Dict[str, int] = {}
by_mode: Dict[str, int] = {}
for m in mappings:
    lvl = m.get("automation_level", "MANUAL")
    mode = m.get("generation_mode", "extract")
    by_level[lvl] = by_level.get(lvl, 0) + 1
    by_mode[mode] = by_mode.get(mode, 0) + 1

col1, col2, col3, col4 = st.columns(4)
col1.metric("总映射数", total)
col2.metric("HIGH 等级", by_level.get("HIGH", 0))
col3.metric("MEDIUM 等级", by_level.get("MEDIUM", 0))
col4.metric("MANUAL 等级", by_level.get("MANUAL", 0))

st.divider()

# === 过滤 + 表格 ===
st.subheader("2️⃣ 映射规则列表")

filter_col1, filter_col2 = st.columns(2)
with filter_col1:
    selected_level = st.multiselect(
        "🔍 按自动化等级过滤",
        options=["HIGH", "MEDIUM", "MANUAL"],
        default=["HIGH", "MEDIUM", "MANUAL"],
    )
with filter_col2:
    search = st.text_input("🔍 搜索占位符 / 描述", "")

filtered = [m for m in mappings if m.get("automation_level") in selected_level]
if search:
    filtered = [
        m for m in filtered
        if search in m.get("template_placeholder", "")
        or search in m.get("v4_text_preview", "")
    ]

st.caption(f"📋 显示 {len(filtered)} / {total} 个映射")

# === 表格 + 展开详情 ===
for i, m in enumerate(filtered, 1):
    placeholder = m.get("template_placeholder", "")
    level = m.get("automation_level", "MANUAL")
    mode = m.get("generation_mode", "extract")
    slots = m.get("source_slots", [])
    preview = m.get("v4_text_preview", "")[:80]
    fallback = m.get("fallback_text", "") or ""
    notes = m.get("notes", "")

    level_color = {"HIGH": "🟢", "MEDIUM": "🟡", "MANUAL": "🔴"}[level]
    mode_icon = {"extract": "📥", "grounded_category": "🎯", "fallback": "🔄"}[mode]

    with st.expander(
        f"{level_color} **{placeholder}** · {mode_icon} {mode} · {preview}...",
        expanded=False,
    ):
        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.markdown(f"**等级**: `{level}`")
            st.markdown(f"**模式**: `{mode}`")
            st.markdown(f"**润色**: {'✅ 是' if m.get('polish_required') else '❌ 否'}")
        with info_col2:
            st.markdown(f"**槽位数**: `{len(slots)}`")
            st.markdown(f"**V4 段落号**: `{m.get('v4_index', '?')}`")
            st.markdown(f"**说明**: {notes}")

        st.markdown("**V4 范文预览**:")
        st.caption(m.get("v4_text_preview", "—")[:300])

        if slots:
            st.markdown(f"**数据源槽位** ({len(slots)} 个):")
            for s in slots:
                st.code(s, language="text")

        if fallback:
            st.markdown("**Fallback 文本**（当数据缺失时使用）:")
            st.info(fallback)
        else:
            st.caption("📌 无 fallback（必须有数据源）")

        # 可编辑模式
        with st.expander("✏️ 高级：编辑 Fallback", expanded=False):
            new_fallback = st.text_area(
                "Fallback 文本",
                value=fallback,
                key=f"fb_{placeholder}",
                height=100,
            )
            if st.button(f"💾 保存 Fallback", key=f"save_fb_{placeholder}"):
                # 仅在内存中更新（避免修改源文件）
                m["fallback_text"] = new_fallback
                st.success("✅ Fallback 已更新（仅本次会话）")

st.divider()

# === 保存到 PipelineState + 下一步 ===
st.subheader("3️⃣ 进入下一步")

col1, col2 = st.columns([3, 1])
with col1:
    st.info(
        f"✅ 数据已就绪：{len(state.raw_data)} 个字段 + "
        f"{total} 个映射规则"
    )
with col2:
    if st.button(
        "➡️ 进入 Step 3: 🤖 生成驾驶舱",
        type="primary",
        use_container_width=True,
    ):
        state_mgr.update_field(
            mappings=mappings,
            current_step=3,
        )
        st.success("✅ 已进入 Step 3")
        st.info("👈 请点击左侧菜单进入「🤖 生成驾驶舱」")

# === 侧边栏 ===
with st.sidebar:
    st.header("🧩 映射驾驶舱")
    st.caption("Step 2/7")
    st.metric("已加载数据", f"{len(state.raw_data)} 字段")
    st.metric("映射规则", total)

    by_lvl_text = " | ".join(f"{k}: {v}" for k, v in by_level.items())
    st.caption(f"**等级分布**: {by_lvl_text}")
    st.divider()
    st.caption("""
    **提示**:
    - HIGH 等级完全自动
    - MEDIUM 等级需要 LLM
    - MANUAL 等级需人工
    """)
