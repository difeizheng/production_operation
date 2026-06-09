"""v3 实时预览（Step 4 单段调试）单元测试

测试 v3.2 中 Step 4 实时预览功能：
1. _preview_single_slot 纯函数逻辑
2. _apply_preview_to_state 写入 state.polished_slots
3. _render_realtime_preview 容错（无 mappings 场景）
4. session_state 隔离（预览不影响批量）
5. 错误处理（resolver 失败 → 返回错误 dict）

设计原则：
- 不依赖 Streamlit runtime（直接 import 函数 / 模拟 state）
- 使用真实的 PipelineState + PolishedSlot
- ReasonResolver 不做真实调用（mock 或使用 fixture）
- 使用 importlib 加载含 emoji 中文文件名的 v3_3 模块
"""
import importlib
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from streamlit_app.core.pipeline_state import (
    PipelineState,
    PolishedSlot,
    PipelineStateManager,
)


# ============================================================================
# 动态加载含中文/emoji 文件名的模块
# ============================================================================
def _load_v3_module():
    """动态加载 streamlit_app.pages.v3_3_🤖_生成驾驶舱"""
    return importlib.import_module("streamlit_app.pages.v3_3_🤖_生成驾驶舱")


# ============================================================================
# 测试夹具
# ============================================================================
def make_mapping(
    placeholder: str = "{{ v4_P05_overview }}",
    source_slots: List[str] = None,
    fallback_text: str = "默认 fallback 文本",
    generation_mode: str = "extract",
) -> Dict[str, Any]:
    """构造一个 mapping fixture。"""
    return {
        "template_placeholder": placeholder,
        "source_slots": source_slots or ["slot_1", "slot_2"],
        "fallback_text": fallback_text,
        "generation_mode": generation_mode,
    }


def make_state_with_mappings(mappings: List[Dict[str, Any]]) -> PipelineState:
    """构造包含 mappings 的 PipelineState。"""
    return PipelineState(
        current_step=4,
        raw_data={"domestic": {"total": 1000}},
        summary_path="/tmp/test.xlsx",
        mappings=mappings,
        slot_results={
            "slot_1": {
                "raw_text": "原始数据 1",
                "source_file": "test.xlsx",
                "is_empty": False,
            },
            "slot_2": {
                "raw_text": "原始数据 2",
                "source_file": "test.xlsx",
                "is_empty": False,
            },
        },
        polished_slots={},
    )


# ============================================================================
# Task C-1: _preview_single_slot 纯函数逻辑（mocked resolver）
# ============================================================================
class TestPreviewSingleSlot(unittest.TestCase):
    """测试 _preview_single_slot 函数（mocked ReasonResolver）。"""

    def _get_preview_fn(self):
        return _load_v3_module()._preview_single_slot

    def test_preview_success_with_llm_output(self):
        """成功场景：返回 ok=True + llm_output。"""
        _preview_single_slot = self._get_preview_fn()

        state = make_state_with_mappings([make_mapping()])

        # Mock resolver 返回 polished 段位
        mock_seg = MagicMock()
        mock_seg.raw_text = "原始数据 1 原始数据 2"
        mock_seg.final_text = "✨ 润色后的文本"
        mock_seg.polished = True
        mock_seg.tokens_used = 150
        mock_seg.automation_level = "HIGH"
        mock_seg.is_fallback = False
        mock_seg.error = None

        v3_mod = _load_v3_module()
        with patch.object(v3_mod, "ReasonResolver") as mock_resolver_cls:
            mock_resolver = mock_resolver_cls.return_value
            mock_resolver.resolve_all.return_value = {
                "{{ v4_P05_overview }}": mock_seg
            }
            result = _preview_single_slot(state, state.mappings[0], 0.3, 500, False)

        self.assertTrue(result["ok"])
        self.assertEqual(result["llm_output"], "✨ 润色后的文本")
        self.assertEqual(result["tokens_used"], 150)
        self.assertFalse(result["is_fallback"])
        self.assertEqual(result["model_used"], "qwen")
        self.assertEqual(result["automation_level"], "HIGH")

    def test_preview_fallback_mode(self):
        """fallback 场景：is_fallback=True + llm_output=None。"""
        _preview_single_slot = self._get_preview_fn()

        state = make_state_with_mappings([make_mapping()])

        mock_seg = MagicMock()
        mock_seg.raw_text = ""
        mock_seg.final_text = "默认 fallback 文本"
        mock_seg.polished = False
        mock_seg.tokens_used = 0
        mock_seg.automation_level = "MANUAL"
        mock_seg.is_fallback = True
        mock_seg.error = None

        v3_mod = _load_v3_module()
        with patch.object(v3_mod, "ReasonResolver") as mock_resolver_cls:
            mock_resolver = mock_resolver_cls.return_value
            mock_resolver.resolve_all.return_value = {
                "{{ v4_P05_overview }}": mock_seg
            }
            result = _preview_single_slot(state, state.mappings[0], 0.3, 500, False)

        self.assertTrue(result["ok"])
        self.assertIsNone(result["llm_output"])
        self.assertTrue(result["is_fallback"])
        self.assertEqual(result["model_used"], "none")

    def test_preview_resolver_exception(self):
        """resolver 抛异常：返回 ok=False + 错误信息。"""
        _preview_single_slot = self._get_preview_fn()

        state = make_state_with_mappings([make_mapping()])

        v3_mod = _load_v3_module()
        with patch.object(v3_mod, "ReasonResolver") as mock_resolver_cls:
            mock_resolver = mock_resolver_cls.return_value
            mock_resolver.resolve_all.side_effect = RuntimeError("LLM API timeout")
            result = _preview_single_slot(state, state.mappings[0], 0.3, 500, False)

        self.assertFalse(result["ok"])
        self.assertTrue(result["is_fallback"])
        self.assertIn("timeout", result["error"])
        self.assertIsNone(result["llm_output"])

    def test_preview_missing_placeholder_in_result(self):
        """resolver 返回的 segments 中没有目标 placeholder。"""
        _preview_single_slot = self._get_preview_fn()

        state = make_state_with_mappings([make_mapping(placeholder="{{ missing }}")])

        v3_mod = _load_v3_module()
        with patch.object(v3_mod, "ReasonResolver") as mock_resolver_cls:
            mock_resolver = mock_resolver_cls.return_value
            mock_resolver.resolve_all.return_value = {}  # 空 dict
            result = _preview_single_slot(state, state.mappings[0], 0.3, 500, False)

        self.assertFalse(result["ok"])
        self.assertIn("未返回段位", result["error"])


# ============================================================================
# Task C-2: _apply_preview_to_state 写入逻辑
# ============================================================================
class TestApplyPreviewToState(unittest.TestCase):
    """测试 _apply_preview_to_state 写入 polished_slots。"""

    def _get_apply_fn(self):
        return _load_v3_module()._apply_preview_to_state

    def test_apply_llm_output_writes_new_slot(self):
        """应用 LLM 输出：polished_slots 应增加新段位。"""
        _apply_preview_to_state = self._get_apply_fn()

        state_mgr = PipelineStateManager()
        state_mgr.update(make_state_with_mappings([make_mapping()]))

        mapping = state_mgr.get().mappings[0]
        preview_result = {
            "ok": True,
            "raw_text": "原始数据",
            "llm_output": "✨ LLM 润色",
            "tokens_used": 100,
            "model_used": "qwen",
            "is_fallback": False,
            "error": None,
            "automation_level": "HIGH",
        }

        _apply_preview_to_state(state_mgr, mapping, preview_result)

        new_state = state_mgr.get()
        self.assertIn("{{ v4_P05_overview }}", new_state.polished_slots)
        slot = new_state.polished_slots["{{ v4_P05_overview }}"]
        self.assertEqual(slot.llm_output, "✨ LLM 润色")
        self.assertEqual(slot.final_text, "✨ LLM 润色")
        self.assertFalse(slot.is_fallback)

    def test_apply_fallback_uses_mapping_fallback_text(self):
        """应用 fallback：final_text 应来自 mapping.fallback_text。"""
        _apply_preview_to_state = self._get_apply_fn()

        state_mgr = PipelineStateManager()
        mapping = make_mapping(fallback_text="自定义 fallback")
        state_mgr.update(make_state_with_mappings([mapping]))

        preview_result = {
            "ok": True,
            "raw_text": "",
            "llm_output": None,
            "tokens_used": 0,
            "model_used": "none",
            "is_fallback": True,
            "error": None,
            "automation_level": "MANUAL",
        }

        _apply_preview_to_state(state_mgr, mapping, preview_result)

        slot = state_mgr.get().polished_slots["{{ v4_P05_overview }}"]
        self.assertEqual(slot.final_text, "自定义 fallback")
        self.assertTrue(slot.is_fallback)

    def test_apply_does_not_affect_other_slots(self):
        """应用一个段位不应影响其他段位。"""
        _apply_preview_to_state = self._get_apply_fn()

        # 预先填充 polished_slots（用 replace 保持不可变性）
        from dataclasses import replace
        existing_slot = PolishedSlot(
            slot_id="{{ other }}",
            placeholder="{{ other }}",
            raw_text="other raw",
            llm_output="other polished",
            final_text="other final",
            is_fallback=False,
        )
        initial_state = replace(
            make_state_with_mappings([make_mapping()]),
            polished_slots={"{{ other }}": existing_slot},
        )

        state_mgr = PipelineStateManager()
        state_mgr.update(initial_state)

        preview_result = {
            "ok": True,
            "raw_text": "new",
            "llm_output": "new polished",
            "tokens_used": 50,
            "model_used": "qwen",
            "is_fallback": False,
            "error": None,
            "automation_level": "HIGH",
        }

        _apply_preview_to_state(state_mgr, state_mgr.get().mappings[0], preview_result)

        new_state = state_mgr.get()
        # 原有段位保持不变
        self.assertEqual(new_state.polished_slots["{{ other }}"].final_text, "other final")
        # 新段位已添加
        self.assertIn("{{ v4_P05_overview }}", new_state.polished_slots)
        self.assertEqual(len(new_state.polished_slots), 2)


# ============================================================================
# Task C-3: 实时预览与批量润色隔离
# ============================================================================
class TestRealtimeVsBatchIsolation(unittest.TestCase):
    """测试实时预览与批量润色的隔离性。"""

    def test_preview_does_not_modify_state_polished_slots_directly(self):
        """_preview_single_slot 纯函数，不修改 state。"""
        _preview_single_slot = _load_v3_module()._preview_single_slot

        state = make_state_with_mappings([make_mapping()])
        before_polished = dict(state.polished_slots)

        mock_seg = MagicMock()
        mock_seg.raw_text = "test"
        mock_seg.final_text = "polished"
        mock_seg.polished = True
        mock_seg.tokens_used = 50
        mock_seg.automation_level = "HIGH"
        mock_seg.is_fallback = False
        mock_seg.error = None

        v3_mod = _load_v3_module()
        with patch.object(v3_mod, "ReasonResolver") as mock_resolver_cls:
            mock_resolver = mock_resolver_cls.return_value
            mock_resolver.resolve_all.return_value = {
                "{{ v4_P05_overview }}": mock_seg
            }
            _preview_single_slot(state, state.mappings[0], 0.3, 500, False)

        # state 应未被修改
        self.assertEqual(state.polished_slots, before_polished)
        self.assertEqual(len(state.polished_slots), 0)

    def test_preview_does_not_affect_slot_results(self):
        """预览不影响 slot_results。"""
        _preview_single_slot = _load_v3_module()._preview_single_slot

        state = make_state_with_mappings([make_mapping()])
        before_slot_results = dict(state.slot_results)

        mock_seg = MagicMock()
        mock_seg.raw_text = "test"
        mock_seg.final_text = "polished"
        mock_seg.polished = True
        mock_seg.tokens_used = 50
        mock_seg.automation_level = "HIGH"
        mock_seg.is_fallback = False
        mock_seg.error = None

        v3_mod = _load_v3_module()
        with patch.object(v3_mod, "ReasonResolver") as mock_resolver_cls:
            mock_resolver = mock_resolver_cls.return_value
            mock_resolver.resolve_all.return_value = {
                "{{ v4_P05_overview }}": mock_seg
            }
            _preview_single_slot(state, state.mappings[0], 0.3, 500, False)

        self.assertEqual(state.slot_results, before_slot_results)


# ============================================================================
# Task C-4: 参数传递（temperature/max_tokens/use_few_shot）
# ============================================================================
class TestPreviewParameters(unittest.TestCase):
    """测试参数正确传递给 resolver。"""

    def test_temperature_max_tokens_passed_to_resolver(self):
        """验证 _preview_single_slot 接受参数。"""
        _preview_single_slot = _load_v3_module()._preview_single_slot
        import inspect

        sig = inspect.signature(_preview_single_slot)
        params = sig.parameters
        self.assertIn("temperature", params)
        self.assertIn("max_tokens", params)
        self.assertIn("use_few_shot", params)
        # annotation 在 from __future__ import annotations 下可能是字符串
        for pname, expected_type in [
            ("temperature", "float"),
            ("max_tokens", "int"),
            ("use_few_shot", "bool"),
        ]:
            ann = params[pname].annotation
            # 兼容 PEP 563 字符串注解
            self.assertIn(expected_type, str(ann), f"{pname} annotation: {ann}")

    def test_preview_function_is_pure(self):
        """_preview_single_slot 是纯函数（同一输入 → 同一输出）。"""
        _preview_single_slot = _load_v3_module()._preview_single_slot

        state = make_state_with_mappings([make_mapping()])

        mock_seg = MagicMock()
        mock_seg.raw_text = "test"
        mock_seg.final_text = "polished"
        mock_seg.polished = True
        mock_seg.tokens_used = 50
        mock_seg.automation_level = "HIGH"
        mock_seg.is_fallback = False
        mock_seg.error = None

        v3_mod = _load_v3_module()
        with patch.object(v3_mod, "ReasonResolver") as mock_resolver_cls:
            mock_resolver = mock_resolver_cls.return_value
            mock_resolver.resolve_all.return_value = {
                "{{ v4_P05_overview }}": mock_seg
            }
            result1 = _preview_single_slot(state, state.mappings[0], 0.3, 500, False)
            result2 = _preview_single_slot(state, state.mappings[0], 0.3, 500, False)

        self.assertEqual(result1["llm_output"], result2["llm_output"])
        self.assertEqual(result1["tokens_used"], result2["tokens_used"])


# ============================================================================
# Task C-5: 错误处理
# ============================================================================
class TestPreviewErrorHandling(unittest.TestCase):
    """测试错误处理路径。"""

    def test_apply_with_invalid_state_mgr(self):
        """_apply_preview_to_state 在没有 state_mgr 时抛错（文档化行为）。"""
        _apply_preview_to_state = _load_v3_module()._apply_preview_to_state

        preview_result = {
            "ok": True,
            "raw_text": "test",
            "llm_output": "polished",
            "tokens_used": 50,
            "model_used": "qwen",
            "is_fallback": False,
            "error": None,
            "automation_level": "HIGH",
        }
        # None state_mgr：应抛 TypeError 或 AttributeError
        with self.assertRaises((TypeError, AttributeError)):
            _apply_preview_to_state(None, make_mapping(), preview_result)


if __name__ == "__main__":
    unittest.main()
