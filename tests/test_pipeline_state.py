"""Unit tests for PipelineState - 状态管理

测试覆盖：
    1. PolishedSlot / QualityMetrics / PipelineState 数据类
    2. PipelineStateManager 初始化和 session_state 持久化
    3. 不可变更新（update_field）
    4. 人工编辑记录（record_human_edit）
    5. 快照保存/加载
    6. 统计计算（get_stats）
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
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
    with patch.dict(os.environ, {}, clear=True):
        from streamlit_app.core import pipeline_state as ps_module
        mock_st = MagicMock()
        mock_session = {}
        mock_st.session_state = mock_session
        ps_module.st = mock_st
        yield mock_st, mock_session, ps_module


@pytest.fixture
def sample_polished_slot():
    """示例 PolishedSlot。"""
    from streamlit_app.core import PolishedSlot
    return PolishedSlot(
        slot_id="dom.elec.yoy.changjiang",
        placeholder="{{ v4_P6_dom_elec_yoy_wow }}",
        raw_text="全集团电量同比增加",
        llm_output="全集团上网电量同比增加 3.2%",
        final_text="全集团上网电量同比增加 3.2%",
        is_edited_by_human=False,
        generation_mode="extract",
        automation_level="HIGH",
        tokens_used=124,
        model_used="qwen3.5-plus",
    )


# ============================================================================
# 数据类测试
# ============================================================================

class TestPolishedSlot:
    """PolishedSlot 测试。"""

    def test_creation(self) -> None:
        from streamlit_app.core import PolishedSlot
        slot = PolishedSlot(
            slot_id="test",
            placeholder="{{ x }}",
            raw_text="raw",
            llm_output="polished",
            final_text="final",
        )
        assert slot.slot_id == "test"
        assert slot.placeholder == "{{ x }}"
        assert slot.is_edited_by_human is False
        assert slot.tokens_used == 0

    def test_immutable(self, sample_polished_slot) -> None:
        """frozen=True 应该禁止修改。"""
        with pytest.raises(Exception):  # FrozenInstanceError
            sample_polished_slot.slot_id = "new_id"  # type: ignore

    def test_to_dict(self, sample_polished_slot) -> None:
        d = sample_polished_slot.to_dict()
        assert d["slot_id"] == "dom.elec.yoy.changjiang"
        assert d["tokens_used"] == 124
        assert d["model_used"] == "qwen3.5-plus"

    def test_from_dict(self) -> None:
        from streamlit_app.core import PolishedSlot
        data = {
            "slot_id": "test",
            "placeholder": "{{ p }}",
            "raw_text": "raw",
            "llm_output": "polished",
            "final_text": "final",
            "is_edited_by_human": True,
            "generation_mode": "extract",
            "automation_level": "MEDIUM",
            "tokens_used": 50,
            "model_used": "test-model",
            "is_fallback": False,
            "error": None,
            "timestamp": "2026-06-07T10:00:00",
        }
        slot = PolishedSlot.from_dict(data)
        assert slot.is_edited_by_human is True
        assert slot.tokens_used == 50


class TestQualityMetrics:
    """QualityMetrics 测试。"""

    def test_default_score(self) -> None:
        from streamlit_app.core import QualityMetrics
        m = QualityMetrics(slot_id="test")
        assert m.overall_score == 100
        assert m.numbers_consistency is True
        assert m.warnings == []

    def test_to_dict(self) -> None:
        from streamlit_app.core import QualityMetrics
        m = QualityMetrics(
            slot_id="test",
            numbers_consistency=False,
            overall_score=60,
            warnings=["数字不一致"],
        )
        d = m.to_dict()
        assert d["overall_score"] == 60
        assert "数字不一致" in d["warnings"]


# ============================================================================
# PipelineStateManager 测试
# ============================================================================

class TestPipelineStateManager:
    """PipelineStateManager 测试。"""

    def test_init_creates_empty_state(self, mock_streamlit) -> None:
        mock_st, mock_session, ps_module = mock_streamlit
        mgr = ps_module.PipelineStateManager()
        state = mgr.get()
        assert state.current_step == 1
        assert state.raw_data is None
        assert state.polished_slots == {}

    def test_update_field(self, mock_streamlit) -> None:
        mock_st, mock_session, ps_module = mock_streamlit
        mgr = ps_module.PipelineStateManager()
        mgr.update_field(current_step=3, excel_path="test.xlsx")
        state = mgr.get()
        assert state.current_step == 3
        assert state.excel_path == "test.xlsx"

    def test_update_preserves_other_fields(self, mock_streamlit) -> None:
        mock_st, mock_session, ps_module = mock_streamlit
        mgr = ps_module.PipelineStateManager()
        mgr.update_field(current_step=2)
        mgr.update_field(excel_path="test.xlsx")
        state = mgr.get()
        assert state.current_step == 2
        assert state.excel_path == "test.xlsx"

    def test_update_changes_timestamp(self, mock_streamlit) -> None:
        mock_st, mock_session, ps_module = mock_streamlit
        mgr = ps_module.PipelineStateManager()
        first = mgr.get()
        first_ts = first.updated_at
        import time
        time.sleep(0.01)
        mgr.update_field(current_step=2)
        second = mgr.get()
        assert second.updated_at != first_ts

    def test_reset(self, mock_streamlit) -> None:
        mock_st, mock_session, ps_module = mock_streamlit
        mgr = ps_module.PipelineStateManager()
        mgr.update_field(current_step=5, excel_path="x")
        mgr.reset()
        state = mgr.get()
        assert state.current_step == 1
        assert state.excel_path is None

    def test_upsert_polished_slot(self, mock_streamlit, sample_polished_slot) -> None:
        mock_st, mock_session, ps_module = mock_streamlit
        mgr = ps_module.PipelineStateManager()
        mgr.upsert_polished_slot(sample_polished_slot)
        state = mgr.get()
        assert sample_polished_slot.slot_id in state.polished_slots
        assert state.polished_slots[sample_polished_slot.slot_id].tokens_used == 124

    def test_record_human_edit(self, mock_streamlit, sample_polished_slot) -> None:
        mock_st, mock_session, ps_module = mock_streamlit
        mgr = ps_module.PipelineStateManager()
        mgr.upsert_polished_slot(sample_polished_slot)
        new_text = "管理员编辑后的文本"
        mgr.record_human_edit(sample_polished_slot.slot_id, new_text)
        state = mgr.get()
        # human_edits 应有记录
        assert state.human_edits[sample_polished_slot.slot_id] == new_text
        # polished_slot 的 final_text 应更新
        slot = state.polished_slots[sample_polished_slot.slot_id]
        assert slot.final_text == new_text
        assert slot.is_edited_by_human is True

    def test_record_human_edit_unknown_slot(self, mock_streamlit) -> None:
        """编辑不存在的段位时，human_edits 仍记录但 polished_slots 不变。"""
        mock_st, mock_session, ps_module = mock_streamlit
        mgr = ps_module.PipelineStateManager()
        mgr.record_human_edit("unknown.slot", "text")
        state = mgr.get()
        assert state.human_edits.get("unknown.slot") == "text"


class TestPipelineStateStats:
    """get_stats 测试。"""

    def test_empty_stats(self, mock_streamlit) -> None:
        mock_st, mock_session, ps_module = mock_streamlit
        mgr = ps_module.PipelineStateManager()
        stats = mgr.get_stats()
        assert stats["total_slots"] == 0
        assert stats["automation_rate"] == 0.0

    def test_stats_with_slots(self, mock_streamlit) -> None:
        mock_st, mock_session, ps_module = mock_streamlit
        from streamlit_app.core import PolishedSlot
        mgr = ps_module.PipelineStateManager()
        mgr.upsert_polished_slot(PolishedSlot(
            slot_id="s1", placeholder="{{ p1 }}", raw_text="r1",
            llm_output="p1", final_text="p1",
            generation_mode="extract", automation_level="HIGH",
            tokens_used=100, model_used="qwen",
        ))
        mgr.upsert_polished_slot(PolishedSlot(
            slot_id="s2", placeholder="{{ p2 }}", raw_text="r2",
            llm_output=None, final_text="r2",
            generation_mode="fallback", automation_level="MANUAL",
            is_fallback=True,
        ))
        stats = mgr.get_stats()
        assert stats["total_slots"] == 2
        assert stats["polished_count"] == 1
        assert stats["fallback_count"] == 1
        assert stats["by_level"]["HIGH"] == 1
        assert stats["by_level"]["MANUAL"] == 1
        assert stats["total_tokens"] == 100
        assert stats["automation_rate"] == 0.5  # 1 HIGH / 2 total


class TestSnapshot:
    """快照测试。"""

    def test_save_and_load_snapshot(self, mock_streamlit, tmp_path) -> None:
        mock_st, mock_session, ps_module = mock_streamlit
        # 重定向 SNAPSHOT_DIR 到 tmp_path
        ps_module.PipelineStateManager.SNAPSHOT_DIR = tmp_path

        mgr = ps_module.PipelineStateManager()
        mgr.update_field(current_step=3, excel_path="/tmp/test.xlsx")

        # 保存
        snapshot_path = mgr.save_snapshot(name="test")
        assert snapshot_path.exists()
        content = json.loads(snapshot_path.read_text(encoding="utf-8"))
        assert content["current_step"] == 3
        assert content["excel_path"] == "/tmp/test.xlsx"

        # 重置
        mgr.reset()
        assert mgr.get().current_step == 1

        # 加载
        mgr.load_snapshot(snapshot_path)
        state = mgr.get()
        assert state.current_step == 3
        assert state.excel_path == "/tmp/test.xlsx"
