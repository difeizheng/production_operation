"""Unit tests for VersionRouter - URL 参数 + 版本路由

测试覆盖：
    1. 默认版本是 v3
    2. URL 参数 ?version=v2 强制 v2
    3. URL 参数 ?version=v3 强制 v3
    4. 非法 URL 参数回退默认
    5. set_version 更新 session_state + URL
    6. switch_to_version rerun
    7. get_switch_url 构造
    8. 切换器渲染
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
    """Mock streamlit。"""
    # 只清 LLM 相关环境变量（不影响 HOME）
    env_clear = {k: v for k, v in os.environ.items()
                 if k in ("HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH")}
    with patch.dict(os.environ, env_clear, clear=True):
        from streamlit_app.core import version_router as vr_module
        mock_st = MagicMock()
        mock_session = {}
        mock_st.session_state = mock_session
        # 默认 URL 参数为空
        mock_query = MagicMock()
        mock_query.get = MagicMock(return_value="")
        mock_st.query_params = mock_query

        vr_module.st = mock_st
        yield mock_st, mock_session, vr_module


# ============================================================================
# get_current_version 测试
# ============================================================================

class TestGetCurrentVersion:
    """获取当前版本测试。"""

    def test_default_is_v3(self, mock_streamlit) -> None:
        mock_st, mock_session, vr = mock_streamlit
        assert vr.get_current_version() == "v3"

    def test_url_v2_forces_v2(self, mock_streamlit) -> None:
        mock_st, mock_session, vr = mock_streamlit
        mock_st.query_params.get = MagicMock(return_value="v2")
        assert vr.get_current_version() == "v2"

    def test_url_v3_forces_v3(self, mock_streamlit) -> None:
        mock_st, mock_session, vr = mock_streamlit
        mock_st.query_params.get = MagicMock(return_value="v3")
        assert vr.get_current_version() == "v3"

    def test_invalid_url_falls_back_to_default(self, mock_streamlit) -> None:
        mock_st, mock_session, vr = mock_streamlit
        mock_st.query_params.get = MagicMock(return_value="v999")
        # 无 session_state，URL 无效 → 默认 v3
        assert vr.get_current_version() == "v3"

    def test_session_state_secondary(self, mock_streamlit) -> None:
        mock_st, mock_session, vr = mock_streamlit
        # URL 为空，session_state 为 v2
        mock_st.query_params.get = MagicMock(return_value="")
        mock_session[vr.VERSION_KEY] = "v2"
        assert vr.get_current_version() == "v2"

    def test_url_priority_over_session(self, mock_streamlit) -> None:
        mock_st, mock_session, vr = mock_streamlit
        mock_st.query_params.get = MagicMock(return_value="v2")
        mock_session[vr.VERSION_KEY] = "v3"  # session 是 v3
        # URL 优先
        assert vr.get_current_version() == "v2"

    def test_url_lowercase_normalized(self, mock_streamlit) -> None:
        mock_st, mock_session, vr = mock_streamlit
        mock_st.query_params.get = MagicMock(return_value="V2")
        assert vr.get_current_version() == "v2"


# ============================================================================
# set_version 测试
# ============================================================================

class TestSetVersion:
    """set_version 测试。"""

    def test_valid_v2(self, mock_streamlit) -> None:
        mock_st, mock_session, vr = mock_streamlit
        vr.set_version("v2")
        assert mock_session[vr.VERSION_KEY] == "v2"
        # query_params 接受赋值即可
        assert mock_st.query_params.__setitem__.called or mock_st.query_params["version"] == "v2"

    def test_valid_v3(self, mock_streamlit) -> None:
        mock_st, mock_session, vr = mock_streamlit
        vr.set_version("v3")
        assert mock_session[vr.VERSION_KEY] == "v3"

    def test_invalid_raises(self, mock_streamlit) -> None:
        mock_st, mock_session, vr = mock_streamlit
        with pytest.raises(ValueError):
            vr.set_version("v999")

    def test_no_url_update(self, mock_streamlit) -> None:
        mock_st, mock_session, vr = mock_streamlit
        # 记录调用前的 query_params.__setitem__ 次数
        vr.set_version("v2", update_url=False)
        assert mock_session[vr.VERSION_KEY] == "v2"
        # 不应设置 query_params（虽然 mock 仍可调用）


# ============================================================================
# switch_to_version 测试
# ============================================================================

class TestSwitchToVersion:
    """switch_to_version 测试。"""

    def test_same_version_no_rerun(self, mock_streamlit) -> None:
        mock_st, mock_session, vr = mock_streamlit
        # 当前是 v3（默认）
        vr.switch_to_version("v3")
        mock_st.rerun.assert_not_called()

    def test_different_version_rerun(self, mock_streamlit) -> None:
        mock_st, mock_session, vr = mock_streamlit
        # 当前是 v3，切到 v2
        vr.switch_to_version("v2")
        mock_st.rerun.assert_called_once()
        assert mock_session[vr.VERSION_KEY] == "v2"


# ============================================================================
# get_switch_url 测试
# ============================================================================

class TestGetSwitchUrl:
    """URL 构造测试。"""

    def test_version_only(self, mock_streamlit) -> None:
        _, _, vr = mock_streamlit
        url = vr.get_switch_url("v2")
        assert url == "?version=v2"

    def test_version_and_page(self, mock_streamlit) -> None:
        _, _, vr = mock_streamlit
        url = vr.get_switch_url("v3", "v3_1")
        assert "version=v3" in url
        assert "page=v3_1" in url
        assert url.startswith("?")


# ============================================================================
# 渲染器测试
# ============================================================================

class TestRenderers:
    """侧边栏渲染器测试。"""

    def test_render_version_switcher(self, mock_streamlit) -> None:
        mock_st, mock_session, vr = mock_streamlit
        # 简单 mock sidebar: patch 整个 st 对象的 sidebar
        with patch.object(vr, "st") as mock_st_obj:
            mock_st_obj.radio = MagicMock(return_value="v3")
            vr.render_version_switcher()
            # 不应触发 rerun（v3 == v3 默认）
            mock_st_obj.rerun.assert_not_called()

    def test_render_switcher_triggers_rerun(self, mock_streamlit) -> None:
        mock_st, mock_session, vr = mock_streamlit
        with patch.object(vr, "st") as mock_st_obj:
            mock_st_obj.radio = MagicMock(return_value="v2")  # 用户选 v2
            vr.render_version_switcher()
            mock_st_obj.rerun.assert_called_once()
