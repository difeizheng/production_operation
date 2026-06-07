"""Unit tests for DataBridge - v2/v3 数据共享层

测试覆盖：
    1. 指纹计算 + 去重
    2. v3 → v2 同步
    3. v2 → v3 同步
    4. ensure_bundle 入口（4 种场景）
    5. auto_sync 自动方向判断
    6. clear_all 清空
    7. get_sync_status 状态查询
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_streamlit():
    """Mock streamlit session_state。"""
    # 只清 LLM 相关环境变量（不影响 HOME）
    env_clear = {k: v for k, v in os.environ.items()
                 if k in ("HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH")}
    with patch.dict(os.environ, env_clear, clear=True):
        from streamlit_app.core import data_bridge as db_module
        mock_st = MagicMock()
        mock_session = {}
        mock_st.session_state = mock_session
        mock_st.spinner = MagicMock()
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock()
        db_module.st = mock_st
        yield mock_st, mock_session, db_module


@pytest.fixture
def sample_data():
    """示例数据。"""
    return {
        "report.electricity.hydro": 59.05,
        "report.electricity.wind": 18.5,
        "meta": {"year": 2026, "week": 21},
    }


# ============================================================================
# 指纹计算测试
# ============================================================================

class TestFingerprint:
    """指纹计算测试。"""

    def test_compute_fingerprint_deterministic(self, mock_streamlit) -> None:
        _, _, db = mock_streamlit
        fp1 = db._compute_fingerprint({"a": 1, "b": 2})
        fp2 = db._compute_fingerprint({"a": 1, "b": 2})
        assert fp1 == fp2

    def test_compute_fingerprint_different_data(self, mock_streamlit) -> None:
        _, _, db = mock_streamlit
        fp1 = db._compute_fingerprint({"a": 1})
        fp2 = db._compute_fingerprint({"a": 2})
        assert fp1 != fp2

    def test_compute_fingerprint_none(self, mock_streamlit) -> None:
        _, _, db = mock_streamlit
        assert db._compute_fingerprint(None) == "empty"

    def test_should_sync_first_time(self, mock_streamlit) -> None:
        _, mock_session, db = mock_streamlit
        assert db._should_sync("new_fp") is True
        assert "new_fp" not in mock_session

    def test_should_sync_skip_same(self, mock_streamlit) -> None:
        _, mock_session, db = mock_streamlit
        mock_session[db.SYNC_FINGERPRINT_KEY] = "same"
        assert db._should_sync("same") is False

    def test_mark_synced(self, mock_streamlit) -> None:
        _, mock_session, db = mock_streamlit
        db._mark_synced("abc123")
        assert mock_session[db.SYNC_FINGERPRINT_KEY] == "abc123"


# ============================================================================
# ensure_bundle 测试
# ============================================================================

class TestEnsureBundle:
    """ensure_bundle 入口测试。"""

    def test_existing_bundle_returned(self, mock_streamlit) -> None:
        mock_st, mock_session, db = mock_streamlit
        # 预设 bundle
        mock_session["bundle"] = {
            "data": {"a": 1},
            "results": {"domestic": "x"},
            "source": "default",
        }
        result = db.ensure_bundle()
        assert result["data"] == {"a": 1}
        assert result["source"] == "default"

    def test_no_bundle_loads_default(self, mock_streamlit) -> None:
        mock_st, mock_session, db = mock_streamlit
        with patch("streamlit_app.utils.data_loader.load_data_and_analyze") as mock_load, \
             patch("streamlit_app.core.get_state_manager") as mock_mgr_fn:
            mock_mgr_fn.return_value.get.return_value.raw_data = None
            mock_load.return_value = {
                "data": {"a": 1},
                "results": {"domestic": "x"},
                "source": "default",
            }
            result = db.ensure_bundle()
            mock_load.assert_called_once_with(use_default=True)
            assert mock_session["bundle"]["data"] == {"a": 1}

    def test_no_data_falls_back_to_default(self, mock_streamlit) -> None:
        mock_st, mock_session, db = mock_streamlit
        # bundle 存在但 data 为 None
        mock_session["bundle"] = {"data": None, "results": {}, "source": "none"}
        with patch("streamlit_app.utils.data_loader.load_data_and_analyze") as mock_load, \
             patch("streamlit_app.core.get_state_manager") as mock_mgr_fn:
            mock_mgr_fn.return_value.get.return_value.raw_data = None
            mock_load.return_value = {
                "data": {"a": 1},
                "results": {},
                "source": "default",
            }
            result = db.ensure_bundle()
            mock_load.assert_called_once()


# ============================================================================
# sync_v3_to_v2 测试
# ============================================================================

class TestSyncV3ToV2:
    """v3 → v2 同步测试。"""

    def test_no_v3_data_skips(self, mock_streamlit, sample_data) -> None:
        mock_st, mock_session, db = mock_streamlit
        with patch("streamlit_app.core.get_state_manager") as mock_mgr_fn:
            mock_mgr_fn.return_value.get.return_value.raw_data = None
            result = db.sync_v3_to_v2()
            assert result is False
            assert "bundle" not in mock_session

    def test_with_v3_data_creates_bundle(self, mock_streamlit, sample_data) -> None:
        mock_st, mock_session, db = mock_streamlit
        with patch("streamlit_app.core.get_state_manager") as mock_mgr_fn, \
             patch("streamlit_app.utils.data_loader.run_all_analyzers") as mock_run:
            mock_mgr_fn.return_value.get.return_value.raw_data = sample_data
            mock_run.return_value = {"domestic": "analyzer_result"}

            result = db.sync_v3_to_v2()
            assert result is True
            assert mock_session["bundle"]["data"] == sample_data
            assert mock_session["bundle"]["source"] == "v3_uploaded"
            assert "domestic" in mock_session["bundle"]["results"]

    def test_skip_duplicate_sync(self, mock_streamlit, sample_data) -> None:
        mock_st, mock_session, db = mock_streamlit
        # 预设已同步指纹
        fp = db._compute_fingerprint(sample_data)
        mock_session[db.SYNC_FINGERPRINT_KEY] = fp

        with patch("streamlit_app.core.get_state_manager") as mock_mgr_fn:
            mock_mgr_fn.return_value.get.return_value.raw_data = sample_data

            result = db.sync_v3_to_v2()
            assert result is False
            assert "bundle" not in mock_session

    def test_force_sync_ignores_fingerprint(self, mock_streamlit, sample_data) -> None:
        mock_st, mock_session, db = mock_streamlit
        fp = db._compute_fingerprint(sample_data)
        mock_session[db.SYNC_FINGERPRINT_KEY] = fp

        with patch("streamlit_app.core.get_state_manager") as mock_mgr_fn, \
             patch("streamlit_app.utils.data_loader.run_all_analyzers") as mock_run:
            mock_mgr_fn.return_value.get.return_value.raw_data = sample_data
            mock_run.return_value = {}

            result = db.sync_v3_to_v2(force=True)
            assert result is True


# ============================================================================
# sync_v2_to_v3 测试
# ============================================================================

class TestSyncV2ToV3:
    """v2 → v3 同步测试。"""

    def test_no_bundle_skips(self, mock_streamlit) -> None:
        mock_st, mock_session, db = mock_streamlit
        result = db.sync_v2_to_v3()
        assert result is False

    def test_with_bundle_updates_state(self, mock_streamlit, sample_data) -> None:
        mock_st, mock_session, db = mock_streamlit
        mock_session["bundle"] = {"data": sample_data, "results": {}, "source": "default"}
        with patch("streamlit_app.core.get_state_manager") as mock_mgr_fn:
            mock_mgr = mock_mgr_fn.return_value
            result = db.sync_v2_to_v3()
            assert result is True
            mock_mgr.update_field.assert_called_once_with(raw_data=sample_data)


# ============================================================================
# auto_sync 测试
# ============================================================================

class TestAutoSync:
    """auto_sync 自动方向判断测试。"""

    def test_consistent_data_no_sync(self, mock_streamlit, sample_data) -> None:
        mock_st, mock_session, db = mock_streamlit
        # v2 和 v3 数据一致
        mock_session["bundle"] = {"data": sample_data, "results": {}, "source": "default"}
        fp = db._compute_fingerprint(sample_data)
        mock_session[db.SYNC_FINGERPRINT_KEY] = fp

        with patch("streamlit_app.core.get_state_manager") as mock_mgr_fn:
            mock_mgr_fn.return_value.get.return_value.raw_data = sample_data
            # auto_sync 应检测到一致，不调用同步
            db.auto_sync()
            # 无 update_field 调用
            mock_mgr_fn.return_value.update_field.assert_not_called()

    def test_v3_newer_syncs_to_v2(self, mock_streamlit, sample_data) -> None:
        mock_st, mock_session, db = mock_streamlit
        # v3 有数据，v2 没有
        with patch("streamlit_app.core.get_state_manager") as mock_mgr_fn, \
             patch("streamlit_app.utils.data_loader.run_all_analyzers") as mock_run:
            mock_mgr_fn.return_value.get.return_value.raw_data = sample_data
            mock_run.return_value = {}

            db.auto_sync()
            # v3 → v2 应创建 bundle
            assert "bundle" in mock_session

    def test_v2_newer_syncs_to_v3(self, mock_streamlit, sample_data) -> None:
        mock_st, mock_session, db = mock_streamlit
        # v2 有数据，v3 没有
        mock_session["bundle"] = {"data": sample_data, "results": {}, "source": "default"}
        with patch("streamlit_app.core.get_state_manager") as mock_mgr_fn:
            mock_mgr_fn.return_value.get.return_value.raw_data = None

            db.auto_sync()
            # v2 → v3 应更新 state
            mock_mgr_fn.return_value.update_field.assert_called()


# ============================================================================
# clear_all + get_sync_status 测试
# ============================================================================

class TestClearAndStatus:
    """清空 + 状态查询测试。"""

    def test_clear_all(self, mock_streamlit) -> None:
        mock_st, mock_session, db = mock_streamlit
        mock_session["bundle"] = {"data": {"a": 1}, "results": {}, "source": "default"}
        mock_session[db.SYNC_FINGERPRINT_KEY] = "abc"

        with patch("streamlit_app.core.get_state_manager") as mock_mgr_fn:
            mock_mgr = mock_mgr_fn.return_value

            db.clear_all()
            assert "bundle" not in mock_session
            assert db.SYNC_FINGERPRINT_KEY not in mock_session
            mock_mgr.update_field.assert_called_once_with(raw_data=None)

    def test_get_sync_status_v2_only(self, mock_streamlit, sample_data) -> None:
        mock_st, mock_session, db = mock_streamlit
        mock_session["bundle"] = {"data": sample_data, "results": {}, "source": "default"}
        with patch("streamlit_app.core.get_state_manager") as mock_mgr_fn:
            mock_mgr_fn.return_value.get.return_value.raw_data = None

            status = db.get_sync_status()
            assert status["v2_has_bundle"] is True
            assert status["v3_has_data"] is False
            assert status["v2_source"] == "default"

    def test_get_shared_data_v2_first(self, mock_streamlit, sample_data) -> None:
        mock_st, mock_session, db = mock_streamlit
        mock_session["bundle"] = {"data": sample_data, "results": {}, "source": "default"}
        result = db.get_shared_data()
        assert result == sample_data

    def test_get_shared_data_fallback_v3(self, mock_streamlit, sample_data) -> None:
        mock_st, mock_session, db = mock_streamlit
        # v2 没有
        with patch("streamlit_app.core.get_state_manager") as mock_mgr_fn:
            mock_mgr_fn.return_value.get.return_value.raw_data = sample_data
            result = db.get_shared_data()
            assert result == sample_data


# ============================================================================
# safe_set_page_config 测试
# ============================================================================

class TestSafeSetPageConfig:
    """safe_set_page_config 测试 - 避免 set_page_config 重复调用报错。"""

    def test_normal_call_passes_through(self, mock_streamlit) -> None:
        mock_st, _, db = mock_streamlit
        mock_st.set_page_config = MagicMock()
        db.safe_set_page_config(page_title="测试", page_icon="📊", layout="wide")
        mock_st.set_page_config.assert_called_once_with(
            page_title="测试", page_icon="📊", layout="wide"
        )

    def test_already_called_silently_ignored(self, mock_streamlit) -> None:
        """当 set_page_config 抛错时（app.py 已调用过），safe 版本静默忽略。"""
        mock_st, _, db = mock_streamlit

        def raise_error(**kwargs):
            from streamlit.errors import StreamlitSetPageConfigMustBeFirstCommandError
            raise StreamlitSetPageConfigMustBeFirstCommandError()

        mock_st.set_page_config = MagicMock(side_effect=raise_error)
        # 不应抛错
        db.safe_set_page_config(page_title="test")

    def test_other_exceptions_still_propagate(self, mock_streamlit) -> None:
        """非 set_page_config 错误应正常抛出。"""
        mock_st, _, db = mock_streamlit
        mock_st.set_page_config = MagicMock(side_effect=ValueError("其他错误"))
        with __import__("pytest").raises(ValueError):
            db.safe_set_page_config(page_title="test")
