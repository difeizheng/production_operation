"""审计时间线组件测试"""
import pytest
from datetime import datetime
from streamlit_app.components.audit_timeline import (
    TimelineEvent,
    extract_timeline_events,
    group_events_by_stage,
    compute_stage_stats,
)
from streamlit_app.core.pipeline_state import PolishedSlot


class TestTimelineEvent:
    """TimelineEvent 数据类测试"""

    def test_create_event(self):
        """测试创建事件"""
        event = TimelineEvent(
            stage="extract",
            slot_id="test_slot",
            timestamp="2026-06-09T10:00:00",
            status="success",
            detail="提取完成",
            metadata={"source": "excel"},
        )
        assert event.stage == "extract"
        assert event.slot_id == "test_slot"
        assert event.status == "success"

    def test_event_immutable(self):
        """测试事件不可变"""
        event = TimelineEvent(
            stage="polish",
            slot_id="slot1",
            timestamp="2026-06-09T10:00:00",
            status="success",
            detail="润色完成",
            metadata={},
        )
        with pytest.raises(AttributeError):
            event.stage = "edit"


class TestExtractTimelineEvents:
    """extract_timeline_events 函数测试"""

    def test_empty_slots(self):
        """测试空槽位"""
        events = extract_timeline_events({})
        assert events == []

    def test_extract_stage(self):
        """测试提取阶段事件"""
        slot = PolishedSlot(
            slot_id="slot1",
            placeholder="{{test}}",
            raw_text="原始文本",
            llm_output=None,
            final_text="原始文本",
            timestamp="2026-06-09T10:00:00",
        )
        events = extract_timeline_events({"slot1": slot})
        assert len(events) == 1
        assert events[0].stage == "extract"
        assert events[0].status == "success"

    def test_polish_stage_success(self):
        """测试润色阶段（成功）"""
        slot = PolishedSlot(
            slot_id="slot1",
            placeholder="{{test}}",
            raw_text="原始文本",
            llm_output="润色后文本",
            final_text="润色后文本",
            tokens_used=100,
            model_used="claude-haiku-4-5",
            timestamp="2026-06-09T10:00:00",
        )
        events = extract_timeline_events({"slot1": slot})
        # 应该有 extract + polish 两个事件
        assert len(events) == 2
        polish_event = next(e for e in events if e.stage == "polish")
        assert polish_event.status == "success"
        assert polish_event.metadata["tokens_used"] == 100

    def test_polish_stage_fallback(self):
        """测试润色阶段（fallback）"""
        slot = PolishedSlot(
            slot_id="slot1",
            placeholder="{{test}}",
            raw_text="原始文本",
            llm_output=None,
            final_text="原始文本",
            is_fallback=True,
            error="LLM 不可用",
            timestamp="2026-06-09T10:00:00",
        )
        events = extract_timeline_events({"slot1": slot})
        polish_event = next(e for e in events if e.stage == "polish")
        assert polish_event.status == "fallback"

    def test_edit_stage(self):
        """测试编辑阶段"""
        slot = PolishedSlot(
            slot_id="slot1",
            placeholder="{{test}}",
            raw_text="原始文本",
            llm_output="LLM 输出",
            final_text="人工编辑后",
            is_edited_by_human=True,
            timestamp="2026-06-09T10:00:00",
        )
        events = extract_timeline_events({"slot1": slot})
        edit_event = next((e for e in events if e.stage == "edit"), None)
        assert edit_event is not None
        assert edit_event.status == "success"

    def test_render_stage(self):
        """测试渲染阶段"""
        slot = PolishedSlot(
            slot_id="slot1",
            placeholder="{{test}}",
            raw_text="原始文本",
            llm_output="LLM 输出",
            final_text="最终文本",
            timestamp="2026-06-09T10:00:00",
        )
        audit_log = {
            "rendered_at": "2026-06-09T11:00:00",
            "docx_path": "/path/to/report.docx",
        }
        events = extract_timeline_events({"slot1": slot}, audit_log)
        render_event = next((e for e in events if e.stage == "render"), None)
        assert render_event is not None
        assert render_event.slot_id == "__global__"

    def test_events_sorted_by_time(self):
        """测试事件按时间排序"""
        slot1 = PolishedSlot(
            slot_id="slot1",
            placeholder="{{test1}}",
            raw_text="文本1",
            llm_output="输出1",
            final_text="最终1",
            timestamp="2026-06-09T10:00:00",
        )
        slot2 = PolishedSlot(
            slot_id="slot2",
            placeholder="{{test2}}",
            raw_text="文本2",
            llm_output="输出2",
            final_text="最终2",
            timestamp="2026-06-09T09:00:00",  # 更早
        )
        events = extract_timeline_events({"slot1": slot1, "slot2": slot2})
        # 验证时间戳递增
        timestamps = [e.timestamp for e in events]
        assert timestamps == sorted(timestamps)


class TestGroupEventsByStage:
    """group_events_by_stage 函数测试"""

    def test_empty_events(self):
        """测试空事件列表"""
        grouped = group_events_by_stage([])
        assert grouped == {}

    def test_group_single_stage(self):
        """测试单阶段分组"""
        events = [
            TimelineEvent("extract", "slot1", "2026-06-09T10:00:00", "success", "", {}),
            TimelineEvent("extract", "slot2", "2026-06-09T10:01:00", "success", "", {}),
        ]
        grouped = group_events_by_stage(events)
        assert "extract" in grouped
        assert len(grouped["extract"]) == 2

    def test_group_multiple_stages(self):
        """测试多阶段分组"""
        events = [
            TimelineEvent("extract", "slot1", "2026-06-09T10:00:00", "success", "", {}),
            TimelineEvent("polish", "slot1", "2026-06-09T10:01:00", "success", "", {}),
            TimelineEvent("edit", "slot1", "2026-06-09T10:02:00", "success", "", {}),
        ]
        grouped = group_events_by_stage(events)
        assert len(grouped) == 3
        assert "extract" in grouped
        assert "polish" in grouped
        assert "edit" in grouped


class TestComputeStageStats:
    """compute_stage_stats 函数测试"""

    def test_empty_events(self):
        """测试空事件列表"""
        stats = compute_stage_stats([])
        assert stats == {}

    def test_stats_calculation(self):
        """测试统计计算"""
        events = [
            TimelineEvent("polish", "slot1", "2026-06-09T10:00:00", "success", "", {"tokens_used": 100}),
            TimelineEvent("polish", "slot2", "2026-06-09T10:01:00", "fallback", "", {"tokens_used": 0}),
            TimelineEvent("polish", "slot3", "2026-06-09T10:02:00", "success", "", {"tokens_used": 150}),
        ]
        stats = compute_stage_stats(events)
        assert "polish" in stats
        polish_stats = stats["polish"]
        assert polish_stats["count"] == 3
        assert polish_stats["success_count"] == 2
        assert polish_stats["fallback_count"] == 1
        assert polish_stats["total_tokens"] == 250
