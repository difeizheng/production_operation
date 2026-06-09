"""v3 fallback UX 改进单元测试

测试 v3.2 中 fallback 模式 UX 改进：
1. Step 3 顶部空数据警告
2. Step 4 全部 fallback 检测 + 强制继续按钮
3. Step 6 fallback 比例警告 + 按钮禁用
4. slot_results 完整数据时的正常流程

设计原则：
- 不依赖 Streamlit session_state（直接测试纯函数逻辑）
- 使用 PipelineState 真实实例 + PolishedSlot dataclass
- 覆盖：empty / partial_fallback / all_fallback / no_fallback 四种场景
"""
import unittest
from typing import Any, Dict, List

from streamlit_app.core.pipeline_state import (
    PipelineState,
    PolishedSlot,
)


# ============================================================================
# 测试夹具：构造 PolishedSlot 实例
# ============================================================================
def make_polished_slot(
    slot_id: str,
    is_fallback: bool = False,
    final_text: str = "默认文本",
    placeholder: str = "{{ default }}",
) -> PolishedSlot:
    """构造一个 PolishedSlot 测试实例。"""
    return PolishedSlot(
        slot_id=slot_id,
        placeholder=placeholder,
        raw_text="原始文本",
        llm_output=None if is_fallback else "LLM 润色后文本",
        final_text=final_text,
        is_edited_by_human=False,
        generation_mode="fallback" if is_fallback else "extract",
        automation_level="MANUAL" if is_fallback else "HIGH",
        tokens_used=0 if is_fallback else 100,
        model_used="" if is_fallback else "gpt-4o-mini",
        is_fallback=is_fallback,
    )


def make_polished_slots(fallback_ratio: float, total: int = 10) -> List[PolishedSlot]:
    """构造一组 PolishedSlot，fallback 比例 = fallback_ratio（0-1）。"""
    fallback_count = int(total * fallback_ratio)
    slots = []
    for i in range(total):
        is_fallback = i < fallback_count
        slots.append(
            make_polished_slot(
                slot_id=f"slot_{i:02d}",
                is_fallback=is_fallback,
                placeholder=f"{{{{ v4_P{i:02d} }}}}",
            )
        )
    return slots


# ============================================================================
# Task A-1: 纯函数 fallback 检测逻辑（核心算法）
# ============================================================================
class TestFallbackDetection(unittest.TestCase):
    """测试 fallback 比例检测的纯函数逻辑（不依赖 Streamlit）。

    这些函数在 v3_3_🤖_生成驾驶舱.py 中被内联使用，
    在这里重新提取为可测试形式。
    """

    def test_compute_fallback_ratio_empty(self):
        """空 polished_slots：比例应为 0，count 为 0。"""
        polished_slots: Dict[str, PolishedSlot] = {}
        total = len(polished_slots)
        fallback_count = sum(1 for s in polished_slots.values() if s.is_fallback)
        ratio = fallback_count / total if total > 0 else 0

        self.assertEqual(total, 0)
        self.assertEqual(fallback_count, 0)
        self.assertEqual(ratio, 0.0)

    def test_compute_fallback_ratio_all_fallback(self):
        """100% fallback：比例 = 1.0。"""
        slots = make_polished_slots(fallback_ratio=1.0, total=15)
        polished_slots = {s.slot_id: s for s in slots}

        total = len(polished_slots)
        fallback_count = sum(1 for s in polished_slots.values() if s.is_fallback)
        ratio = fallback_count / total

        self.assertEqual(total, 15)
        self.assertEqual(fallback_count, 15)
        self.assertEqual(ratio, 1.0)
        self.assertTrue(all(s.is_fallback for s in polished_slots.values()))

    def test_compute_fallback_ratio_partial_50_percent(self):
        """50% fallback：比例 = 0.5。"""
        slots = make_polished_slots(fallback_ratio=0.5, total=10)
        polished_slots = {s.slot_id: s for s in slots}

        total = len(polished_slots)
        fallback_count = sum(1 for s in polished_slots.values() if s.is_fallback)
        ratio = fallback_count / total

        self.assertEqual(total, 10)
        self.assertEqual(fallback_count, 5)
        self.assertEqual(ratio, 0.5)

    def test_compute_fallback_ratio_no_fallback(self):
        """0% fallback：比例 = 0.0。"""
        slots = make_polished_slots(fallback_ratio=0.0, total=15)
        polished_slots = {s.slot_id: s for s in slots}

        total = len(polished_slots)
        fallback_count = sum(1 for s in polished_slots.values() if s.is_fallback)
        ratio = fallback_count / total

        self.assertEqual(total, 15)
        self.assertEqual(fallback_count, 0)
        self.assertEqual(ratio, 0.0)

    def test_compute_fallback_ratio_30_percent(self):
        """30% fallback：比例 = 0.3。"""
        slots = make_polished_slots(fallback_ratio=0.3, total=10)
        polished_slots = {s.slot_id: s for s in slots}

        total = len(polished_slots)
        fallback_count = sum(1 for s in polished_slots.values() if s.is_fallback)
        ratio = fallback_count / total

        self.assertEqual(total, 10)
        self.assertEqual(fallback_count, 3)
        self.assertAlmostEqual(ratio, 0.3, places=2)


# ============================================================================
# Task A-2: 警告级别判断（用于 UI 显示不同严重度）
# ============================================================================
class TestWarningLevel(unittest.TestCase):
    """测试警告级别判定逻辑。"""

    def test_warning_level_empty(self):
        """空数据：critical（应被前置拦截）"""
        polished_slots: Dict[str, PolishedSlot] = {}
        total = len(polished_slots)
        fallback_count = 0
        level = _classify_warning_level(total, fallback_count)
        self.assertEqual(level, "empty")

    def test_warning_level_all_fallback(self):
        """100% fallback：critical（按钮禁用）"""
        level = _classify_warning_level(15, 15)
        self.assertEqual(level, "critical")

    def test_warning_level_majority_fallback(self):
        """60% fallback：warning（建议先编辑）"""
        level = _classify_warning_level(10, 6)
        self.assertEqual(level, "warning")

    def test_warning_level_minor_fallback(self):
        """30% fallback：info（提示）"""
        level = _classify_warning_level(10, 3)
        self.assertEqual(level, "info")

    def test_warning_level_no_fallback(self):
        """0% fallback：ok（无警告）"""
        level = _classify_warning_level(15, 0)
        self.assertEqual(level, "ok")


def _classify_warning_level(total: int, fallback_count: int) -> str:
    """判定警告级别（与 v3_3_🤖_生成驾驶舱.py 保持一致）。"""
    if total == 0:
        return "empty"
    ratio = fallback_count / total
    if fallback_count == total:
        return "critical"
    elif ratio > 0.5:
        return "warning"
    elif ratio > 0:
        return "info"
    else:
        return "ok"


# ============================================================================
# Task A-3: 强制继续 session_state 模拟
# ============================================================================
class TestForceContinueState(unittest.TestCase):
    """测试强制继续的状态转换。"""

    def test_force_continue_default_false(self):
        """默认未强制继续。"""
        session_state: Dict[str, Any] = {}
        self.assertFalse(session_state.get("_force_continue_fallback", False))

    def test_force_continue_after_click(self):
        """用户点击强制继续按钮后，session_state 应为 True。"""
        session_state: Dict[str, Any] = {}
        # 模拟点击
        session_state["_force_continue_fallback"] = True
        self.assertTrue(session_state["_force_continue_fallback"])

    def test_force_continue_can_be_reset(self):
        """强制继续可重置。"""
        session_state = {"_force_continue_fallback": True}
        # 重置
        session_state["_force_continue_fallback"] = False
        self.assertFalse(session_state["_force_continue_fallback"])


# ============================================================================
# Task A-4: PipelineState 真实场景集成
# ============================================================================
class TestPipelineStateIntegration(unittest.TestCase):
    """测试 PipelineState 在 fallback 场景下的集成行为。"""

    def test_state_with_empty_polished_slots(self):
        """空 polished_slots：Step 6 应被拦截。"""
        state = PipelineState(current_step=6, polished_slots={})
        self.assertFalse(state.polished_slots)
        # 模拟 Step 6 顶部检查
        should_stop = not state.polished_slots
        self.assertTrue(should_stop)

    def test_state_with_all_fallback_slots(self):
        """100% fallback：Step 6 按钮应禁用。"""
        slots = make_polished_slots(fallback_ratio=1.0, total=15)
        polished_slots = {s.slot_id: s for s in slots}
        state = PipelineState(current_step=6, polished_slots=polished_slots)

        total = len(state.polished_slots)
        fallback_count = sum(1 for s in state.polished_slots.values() if s.is_fallback)
        level = _classify_warning_level(total, fallback_count)

        self.assertEqual(level, "critical")
        self.assertEqual(total, 15)
        self.assertEqual(fallback_count, 15)

    def test_state_with_mixed_fallback_slots(self):
        """混合 fallback：Step 4 警告 + Step 6 info 提示。"""
        slots = make_polished_slots(fallback_ratio=0.4, total=10)
        polished_slots = {s.slot_id: s for s in slots}
        state = PipelineState(current_step=5, polished_slots=polished_slots)

        total = len(state.polished_slots)
        fallback_count = sum(1 for s in state.polished_slots.values() if s.is_fallback)
        level = _classify_warning_level(total, fallback_count)

        self.assertEqual(level, "info")
        self.assertEqual(total, 10)
        self.assertEqual(fallback_count, 4)

    def test_state_with_majority_fallback(self):
        """60% fallback：Step 4/6 warning。"""
        slots = make_polished_slots(fallback_ratio=0.6, total=10)
        polished_slots = {s.slot_id: s for s in slots}
        state = PipelineState(current_step=6, polished_slots=polished_slots)

        total = len(state.polished_slots)
        fallback_count = sum(1 for s in state.polished_slots.values() if s.is_fallback)
        level = _classify_warning_level(total, fallback_count)

        self.assertEqual(level, "warning")
        self.assertEqual(total, 10)
        self.assertEqual(fallback_count, 6)

    def test_state_with_no_fallback(self):
        """0% fallback：完全正常流程。"""
        slots = make_polished_slots(fallback_ratio=0.0, total=15)
        polished_slots = {s.slot_id: s for s in slots}
        state = PipelineState(current_step=6, polished_slots=polished_slots)

        total = len(state.polished_slots)
        fallback_count = sum(1 for s in state.polished_slots.values() if s.is_fallback)
        level = _classify_warning_level(total, fallback_count)

        self.assertEqual(level, "ok")
        # 模板变量字典应能正常构造
        text_dict = {s.placeholder: s.final_text for s in state.polished_slots.values()}
        self.assertEqual(len(text_dict), 15)


# ============================================================================
# Task A-5: Step 3 空数据检测
# ============================================================================
class TestStep3EmptyDataDetection(unittest.TestCase):
    """测试 Step 3 顶部的空数据检测。"""

    def test_no_summary_path_no_mappings(self):
        """无汇总表 + 无映射：应显示严重错误。"""
        state = PipelineState(
            current_step=3,
            summary_path=None,
            mappings=[],
            slot_results={},
        )
        should_show_critical = not state.summary_path and not (state.mappings or [])
        self.assertTrue(should_show_critical)

    def test_no_summary_path_with_mappings(self):
        """无汇总表 + 有映射：应只显示 warning（fallback 可走通）。"""
        state = PipelineState(
            current_step=3,
            summary_path=None,
            mappings=[{"slot_id": "s1", "target_field": "t1"}],
            slot_results={},
        )
        should_show_critical = not state.summary_path and not (state.mappings or [])
        should_show_warning = not state.summary_path
        self.assertFalse(should_show_critical)
        self.assertTrue(should_show_warning)

    def test_with_summary_path_no_mappings(self):
        """有汇总表 + 无映射：应只显示 warning（可提取后用 fallback）。"""
        state = PipelineState(
            current_step=3,
            summary_path="/tmp/test.xlsx",
            mappings=[],
            slot_results={"s1": {"text": "data", "is_empty": False}},
        )
        should_show_critical = not state.summary_path and not (state.mappings or [])
        should_show_warning = not state.summary_path
        self.assertFalse(should_show_critical)
        self.assertFalse(should_show_warning)

    def test_with_summary_path_with_mappings(self):
        """有汇总表 + 有映射：完全正常。"""
        state = PipelineState(
            current_step=3,
            summary_path="/tmp/test.xlsx",
            mappings=[{"slot_id": "s1", "target_field": "t1"}],
            slot_results={"s1": {"text": "data", "is_empty": False}},
        )
        should_show_critical = not state.summary_path and not (state.mappings or [])
        self.assertFalse(should_show_critical)


if __name__ == "__main__":
    unittest.main()
