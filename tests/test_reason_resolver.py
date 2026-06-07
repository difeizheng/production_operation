"""Unit tests for ReasonResolver - Step 4

测试覆盖：
    1. 映射加载（默认路径 + 自定义路径）
    2. 解析为 {placeholder: text} 字典
    3. Fallback 处理（无源文件/槽位为空）
    4. LLM 润色集成
    5. 统计信息
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.collector.reason_collector import (
    ALL_REASON_SLOTS,
    ReasonCollector,
    ReasonResult,
    ReasonSlot,
)
from src.generator.reason_polisher import PolishResult, ReasonPolisher
from src.generator.reason_resolver import (
    DEFAULT_REASON_MAP_PATH,
    ReasonResolver,
    ResolvedSegment,
    load_reason_map,
    quick_resolve,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_reason_map() -> dict:
    """测试用 reason_map。"""
    return {
        "version": "test-1.0",
        "total_mappings": 3,
        "mappings": [
            {
                "v4_index": 1,
                "template_placeholder": "{{ v4_P1 }}",
                "source_slots": ["dom.elec.yoy.changjiang"],
                "automation_level": "HIGH",
                "polish_required": True,
                "fallback_text": "[Fallback P1]",
            },
            {
                "v4_index": 2,
                "template_placeholder": "{{ v4_P2 }}",
                "source_slots": [],
                "automation_level": "MANUAL",
                "polish_required": False,
                "fallback_text": "[Fallback P2]",
            },
            {
                "v4_index": 3,
                "template_placeholder": "{{ v4_P3 }}",
                # 使用真实存在的槽位但 mock_collector 返回空结果 → 触发 fallback
                "source_slots": ["dom.elec.wow.thermal"],
                "automation_level": "HIGH",
                "polish_required": False,
                "fallback_text": "[Fallback P3]",
            },
        ],
    }


@pytest.fixture
def mock_collector() -> ReasonCollector:
    """Mock ReasonCollector（注入预定义结果，不读真实文件）。"""
    collector = ReasonCollector.__new__(ReasonCollector)
    collector._slots = ALL_REASON_SLOTS
    collector._errors = []

    # 自定义 collect：返回预设结果
    def fake_collect(file_path, year=None, week=None):
        results = {
            "dom.elec.yoy.changjiang": ReasonResult(
                slot=ReasonSlot(
                    "dom.elec.yoy.changjiang", "国内数据填报表", 29, 8,
                    "测试", "domestic_yoy",
                ),
                raw_text="1、全集团电量同比增加",
                source_file="test.xlsx",
                is_empty=False,
            ),
            # dom.elec.wow.thermal 故意不放 → 测试 fallback
        }
        return results, []

    import types
    collector.collect = types.MethodType(fake_collect, collector)
    return collector


@pytest.fixture
def mock_polisher() -> ReasonPolisher:
    """Mock ReasonPolisher（不调真实 LLM，但 is_available=True）。"""
    polisher = ReasonPolisher.__new__(ReasonPolisher)
    polisher._api_key = "test-key"
    polisher._model = "mock-model"
    polisher._max_length = 250
    polisher._validate = True
    polisher._client = MagicMock()  # 假装有客户端

    def fake_polish(raw_text, context=None, max_length=None):
        return PolishResult(
            raw_text=raw_text,
            polished_text=f"[POLISHED] {raw_text}",
            is_fallback=False,
            model_used="mock-model",
            tokens_used=100,
            validation_passed=True,
        )

    polisher.polish = fake_polish  # type: ignore[method-assign]
    return polisher


# ============================================================================
# 初始化测试
# ============================================================================

class TestReasonResolverInit:
    """ReasonResolver 初始化测试。"""

    def test_init_with_dict(self, sample_reason_map: dict) -> None:
        """传入字典初始化。"""
        resolver = ReasonResolver(reason_map=sample_reason_map)
        assert len(resolver.mappings) == 3

    def test_init_with_path(self, sample_reason_map: dict, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """从文件路径加载。"""
        map_path = tmp_path / "map.json"
        import json
        with open(map_path, "w", encoding="utf-8") as f:
            json.dump(sample_reason_map, f)

        resolver = ReasonResolver(reason_map_path=map_path)
        assert len(resolver.mappings) == 3

    def test_init_default_path(self) -> None:
        """默认路径加载。"""
        resolver = ReasonResolver()
        # 默认路径存在
        assert DEFAULT_REASON_MAP_PATH.exists()
        assert len(resolver.mappings) > 0


# ============================================================================
# 解析测试
# ============================================================================

class TestReasonResolverResolve:
    """解析逻辑测试。"""

    def test_resolve_with_data(
        self, sample_reason_map: dict, mock_collector: MagicMock, mock_polisher: MagicMock,
    ) -> None:
        """有数据时正常解析。"""
        resolver = ReasonResolver(
            reason_map=sample_reason_map,
            collector=mock_collector,
            polisher=mock_polisher,
        )
        segments = resolver.resolve_all(summary_file="test.xlsx")

        assert "{{ v4_P1 }}" in segments
        seg = segments["{{ v4_P1 }}"]
        assert "POLISHED" in seg.final_text  # 经过 LLM
        assert seg.polished is True
        assert seg.is_fallback is False
        assert seg.tokens_used == 100

    def test_resolve_manual_uses_fallback(
        self, sample_reason_map: dict, mock_collector: MagicMock, mock_polisher: MagicMock,
    ) -> None:
        """MANUAL 段落使用 fallback。"""
        resolver = ReasonResolver(
            reason_map=sample_reason_map,
            collector=mock_collector,
            polisher=mock_polisher,
        )
        segments = resolver.resolve_all(summary_file="test.xlsx")

        seg = segments["{{ v4_P2 }}"]
        assert seg.is_fallback is True
        assert seg.final_text == "[Fallback P2]"

    def test_resolve_missing_slot_uses_fallback(
        self, sample_reason_map: dict, mock_collector: MagicMock, mock_polisher: MagicMock,
    ) -> None:
        """槽位不存在时使用 fallback。"""
        resolver = ReasonResolver(
            reason_map=sample_reason_map,
            collector=mock_collector,
            polisher=mock_polisher,
        )
        segments = resolver.resolve_all(summary_file="test.xlsx")

        seg = segments["{{ v4_P3 }}"]
        assert seg.is_fallback is True
        assert seg.final_text == "[Fallback P3]"

    def test_resolve_no_file(
        self, sample_reason_map: dict, mock_polisher: MagicMock,
    ) -> None:
        """无文件时全部 fallback。"""
        resolver = ReasonResolver(
            reason_map=sample_reason_map,
            polisher=mock_polisher,
        )
        segments = resolver.resolve_all(summary_file=None)

        for seg in segments.values():
            assert seg.is_fallback is True


class TestReasonResolverTextDict:
    """resolve_to_text_dict 测试。"""

    def test_returns_simple_dict(
        self, sample_reason_map: dict, mock_collector: MagicMock, mock_polisher: MagicMock,
    ) -> None:
        """返回 {placeholder: text} 字典。"""
        resolver = ReasonResolver(
            reason_map=sample_reason_map,
            collector=mock_collector,
            polisher=mock_polisher,
        )
        text_dict = resolver.resolve_to_text_dict(summary_file="test.xlsx")

        assert isinstance(text_dict, dict)
        assert "{{ v4_P1 }}" in text_dict
        assert "POLISHED" in text_dict["{{ v4_P1 }}"]


# ============================================================================
# 统计测试
# ============================================================================

class TestReasonResolverStats:
    """统计信息测试。"""

    def test_stats_with_data(
        self, sample_reason_map: dict, mock_collector: MagicMock, mock_polisher: MagicMock,
    ) -> None:
        """统计正确。"""
        resolver = ReasonResolver(
            reason_map=sample_reason_map,
            collector=mock_collector,
            polisher=mock_polisher,
        )
        segments = resolver.resolve_all(summary_file="test.xlsx")
        stats = resolver.get_stats(segments)

        assert stats["total"] == 3
        assert stats["polished_count"] == 1  # 只有 P1 走 LLM
        assert stats["fallback_count"] == 2  # P2 + P3
        assert stats["total_tokens"] == 100
        assert "HIGH" in stats["by_level"]
        assert "MANUAL" in stats["by_level"]


# ============================================================================
# 便利函数测试
# ============================================================================

class TestConvenienceFunctions:
    """便利函数测试。"""

    def test_load_reason_map_default(self) -> None:
        m = load_reason_map()
        assert "mappings" in m
        assert len(m["mappings"]) > 0

    def test_load_reason_map_custom(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        import json
        path = tmp_path / "test_map.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"mappings": []}, f)
        m = load_reason_map(path)
        assert m["mappings"] == []
