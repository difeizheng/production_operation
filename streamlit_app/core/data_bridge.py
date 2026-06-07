"""v2/v3 数据桥 - 让两个版本共享数据。

v2 用 st.session_state["bundle"] = {"data": ..., "results": ..., "source": ...}
v3 用 pipeline_state.get().raw_data + 4 个 analyzer results

桥接策略：
    - v3 上传数据后 → 同步到 v2 的 bundle
    - v2 加载数据后 → 同步到 v3 的 pipeline_state
    - 任何一方变化 → 触发同步

去重逻辑：
    - 用 last_synced_data_id 记录上次同步的数据指纹
    - 指纹未变 → 跳过同步（避免循环）
    - 指纹变化 → 执行同步

注意：safe_set_page_config 已移到 streamlit_app.core.safe_page_config（独立模块）
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, Optional

import streamlit as st

logger = logging.getLogger(__name__)


# === 同步状态 Key ===
BUNDLE_KEY = "bundle"
SYNC_FINGERPRINT_KEY = "_data_bridge_fingerprint"


# ============================================================================
# 工具函数
# ============================================================================

def _compute_fingerprint(data: Any) -> str:
    """计算数据指纹（用于去重）。"""
    if data is None:
        return "empty"
    try:
        raw = str(data).encode("utf-8")
        return hashlib.md5(raw).hexdigest()[:16]
    except Exception as e:
        logger.warning("指纹计算失败: %s", e)
        return "error"


def _should_sync(new_fingerprint: str) -> bool:
    """判断是否需要同步（指纹变化才同步）。"""
    old = st.session_state.get(SYNC_FINGERPRINT_KEY)
    if old == new_fingerprint:
        return False
    return True


def _mark_synced(fingerprint: str) -> None:
    """记录已同步的指纹。"""
    st.session_state[SYNC_FINGERPRINT_KEY] = fingerprint


# ============================================================================
# v3 → v2 同步
# ============================================================================

def sync_v3_to_v2(force: bool = False) -> bool:
    """v3 上传 Excel 后，同步到 v2 的 bundle。

    Args:
        force: 强制同步（忽略指纹检查）

    Returns:
        True 表示已同步，False 表示跳过
    """
    try:
        from streamlit_app.core import get_state_manager
        from streamlit_app.utils.data_loader import run_all_analyzers
    except ImportError as e:
        logger.error("导入失败: %s", e)
        return False

    state = get_state_manager().get()
    if not state.raw_data:
        return False

    fingerprint = _compute_fingerprint(state.raw_data)
    if not force and not _should_sync(fingerprint):
        return False

    with st.spinner("🔄 同步 v3 → v2 ..."):
        try:
            results = run_all_analyzers(state.raw_data)
        except Exception as e:
            logger.error("Analyzer 执行失败: %s", e)
            results = {}

    st.session_state[BUNDLE_KEY] = {
        "data": state.raw_data,
        "results": results,
        "source": "v3_uploaded",
    }
    _mark_synced(fingerprint)
    logger.info("v3 → v2 同步完成: %d 字段", len(state.raw_data))
    return True


# ============================================================================
# v2 → v3 同步
# ============================================================================

def sync_v2_to_v3(force: bool = False) -> bool:
    """v2 上传 JSON 后，同步到 v3 的 pipeline_state。

    Args:
        force: 强制同步（忽略指纹检查）

    Returns:
        True 表示已同步，False 表示跳过
    """
    try:
        from streamlit_app.core import get_state_manager
    except ImportError as e:
        logger.error("导入失败: %s", e)
        return False

    bundle = st.session_state.get(BUNDLE_KEY)
    if not bundle or not bundle.get("data"):
        return False

    fingerprint = _compute_fingerprint(bundle["data"])
    if not force and not _should_sync(fingerprint):
        return False

    mgr = get_state_manager()
    mgr.update_field(raw_data=bundle["data"])
    _mark_synced(fingerprint)
    logger.info("v2 → v3 同步完成: %d 字段", len(bundle["data"]))
    return True


# ============================================================================
# 双向自动同步
# ============================================================================

def auto_sync() -> None:
    """自动检测哪边有新数据，同步到另一边。

    策略：
        - 如果 v3 有数据但 v2 bundle 的 data 不一致 → sync_v3_to_v2
        - 如果 v2 有数据但 v3 state 的 raw_data 不一致 → sync_v2_to_v3
    """
    try:
        from streamlit_app.core import get_state_manager
    except ImportError:
        return

    state = get_state_manager().get()
    bundle = st.session_state.get(BUNDLE_KEY)

    # 比较指纹
    v3_data = state.raw_data
    v2_data = bundle.get("data") if bundle else None

    v3_fp = _compute_fingerprint(v3_data)
    v2_fp = _compute_fingerprint(v2_data)

    if v3_fp == v2_fp:
        # 一致，无需同步
        return

    # 决定方向：哪边"更新"（v3 优先）
    if v3_data is not None and v3_fp != st.session_state.get(SYNC_FINGERPRINT_KEY):
        sync_v3_to_v2()
    elif v2_data is not None:
        sync_v2_to_v3()


# ============================================================================
# 入口函数（给 v2 页面调用）
# ============================================================================

def ensure_bundle() -> Dict[str, Any]:
    """保证 bundle 存在（v2 页面调用入口）。

    Returns:
        bundle 字典 {"data": ..., "results": ..., "source": ...}
    """
    if BUNDLE_KEY not in st.session_state or not st.session_state[BUNDLE_KEY].get("data"):
        # 尝试从 v3 状态恢复
        sync_v3_to_v2()

    if BUNDLE_KEY not in st.session_state or not st.session_state[BUNDLE_KEY].get("data"):
        # 都没有就用演示数据
        try:
            from streamlit_app.utils.data_loader import load_data_and_analyze
            bundle = load_data_and_analyze(use_default=True)
        except Exception as e:
            logger.error("演示数据加载失败: %s", e)
            bundle = {"data": None, "results": {}, "source": "none"}
        st.session_state[BUNDLE_KEY] = bundle

    return st.session_state[BUNDLE_KEY]


# ============================================================================
# 工具函数（v3 页面调用）
# ============================================================================

def get_shared_data() -> Optional[Dict[str, Any]]:
    """获取共享数据（优先 v2 bundle，其次 v3 state）。"""
    bundle = st.session_state.get(BUNDLE_KEY)
    if bundle and bundle.get("data"):
        return bundle["data"]

    try:
        from streamlit_app.core import get_state_manager
        state = get_state_manager().get()
        if state.raw_data:
            return state.raw_data
    except ImportError:
        pass

    return None


def clear_all() -> None:
    """清空 v2/v3 共享数据。"""
    if BUNDLE_KEY in st.session_state:
        del st.session_state[BUNDLE_KEY]
    if SYNC_FINGERPRINT_KEY in st.session_state:
        del st.session_state[SYNC_FINGERPRINT_KEY]

    try:
        from streamlit_app.core import get_state_manager
        mgr = get_state_manager()
        mgr.update_field(raw_data=None)
    except ImportError:
        pass

    logger.info("v2/v3 共享数据已清空")


def get_sync_status() -> Dict[str, Any]:
    """获取同步状态（用于调试 / 审计）。"""
    bundle = st.session_state.get(BUNDLE_KEY)
    v3_data = None
    try:
        from streamlit_app.core import get_state_manager
        v3_data = get_state_manager().get().raw_data
    except ImportError:
        pass

    return {
        "v2_has_bundle": bool(bundle and bundle.get("data")),
        "v3_has_data": v3_data is not None,
        "fingerprint": st.session_state.get(SYNC_FINGERPRINT_KEY, "none"),
        "v2_data_keys": list(bundle["data"].keys())[:5] if bundle and bundle.get("data") else [],
        "v2_source": bundle.get("source", "none") if bundle else "none",
    }
