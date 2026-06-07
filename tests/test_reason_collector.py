"""Unit tests for ReasonCollector - Step 1 PoC

测试覆盖：
    1. 槽位定义完整性（所有 slot_id 唯一）
    2. 文件不存在时的优雅降级
    3. 空文本标记
    4. 单槽位采集
    5. 数据类不可变性（frozen）
    6. 文本规范化（None / 占位符处理）
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.collector.reason_collector import (
    ALL_REASON_SLOTS,
    DOMESTIC_REASON_SLOTS,
    INTERNATIONAL_REASON_SLOTS,
    CARBON_REASON_SLOTS,
    ReasonCollector,
    ReasonResult,
    ReasonSlot,
    collect_all_reasons,
    find_slot_by_id,
)

# 测试用 fixture 路径
TEST_FILE = PROJECT_ROOT / "files" / "2026年第21周周数据汇总表.xlsx"


# ============================================================================
# 槽位定义测试
# ============================================================================

class TestReasonSlotDefinition:
    """槽位定义的完整性测试。"""

    def test_all_slots_have_unique_ids(self) -> None:
        """所有槽位 ID 必须唯一。"""
        ids = [s.slot_id for s in ALL_REASON_SLOTS]
        assert len(ids) == len(set(ids)), f"重复 ID: {[i for i in ids if ids.count(i) > 1]}"

    def test_all_slots_have_valid_sheet_name(self) -> None:
        """所有 sheet_name 必须是非空字符串。"""
        for slot in ALL_REASON_SLOTS:
            assert isinstance(slot.sheet_name, str)
            assert slot.sheet_name.strip(), f"空 sheet: {slot.slot_id}"

    def test_all_slots_have_positive_row_col(self) -> None:
        """行/列号必须 > 0。"""
        for slot in ALL_REASON_SLOTS:
            assert slot.row >= 1, f"行号无效: {slot.slot_id} = {slot.row}"
            assert slot.col >= 1, f"列号无效: {slot.slot_id} = {slot.col}"

    def test_domestic_slots_use_h_column(self) -> None:
        """国内段原因应在 H 列（col=8）。"""
        for slot in DOMESTIC_REASON_SLOTS:
            assert slot.col == 8, f"国内段槽位应使用 H 列: {slot.slot_id} col={slot.col}"

    def test_categories_are_valid(self) -> None:
        """category 必须是预定义值。"""
        valid_categories = {
            "domestic_yoy", "domestic_wow",
            "intl_yoy", "intl_wow",
            "spot", "carbon",
        }
        for slot in ALL_REASON_SLOTS:
            assert slot.category in valid_categories, \
                f"未分类: {slot.slot_id} = {slot.category}"


# ============================================================================
# 数据类测试
# ============================================================================

class TestReasonSlotFrozen:
    """ReasonSlot 必须不可变（frozen=True）。"""

    def test_slot_is_immutable(self) -> None:
        slot = ReasonSlot("test", "sheet", 1, 8, "desc", "domestic_yoy")
        with pytest.raises(Exception):  # FrozenInstanceError
            slot.slot_id = "changed"  # type: ignore[misc]

    def test_result_is_immutable(self) -> None:
        slot = ReasonSlot("test", "sheet", 1, 8, "desc", "domestic_yoy")
        result = ReasonResult(slot, "text", "file.xlsx", False)
        with pytest.raises(Exception):
            result.raw_text = "changed"  # type: ignore[misc]


# ============================================================================
# 采集器测试
# ============================================================================

class TestReasonCollectorBasics:
    """ReasonCollector 基础功能测试。"""

    def test_file_not_found(self) -> None:
        """文件不存在时返回空结果 + 错误。"""
        collector = ReasonCollector()
        results, errors = collector.collect("/nonexistent/file.xlsx")
        assert results == {}
        assert len(errors) == 1
        assert errors[0]["level"] == "ERROR"

    def test_collect_returns_all_slots(self, skip_if_no_file: bool) -> None:  # type: ignore[no-untyped-def]
        """成功采集时返回所有槽位的结果。"""
        if skip_if_no_file:
            pytest.skip("测试文件不存在")
        collector = ReasonCollector()
        results, errors = collector.collect(str(TEST_FILE))
        assert len(results) == len(ALL_REASON_SLOTS)

    def test_collect_marks_empty_text(self, skip_if_no_file: bool) -> None:  # type: ignore[no-untyped-def]
        """空文本应标记 is_empty=True。"""
        if skip_if_no_file:
            pytest.skip("测试文件不存在")
        collector = ReasonCollector()
        results, _ = collector.collect(str(TEST_FILE))

        # 至少应有一些非空（真实 Excel 中会有内容）
        non_empty = [r for r in results.values() if not r.is_empty]
        assert len(non_empty) > 0, "应该至少有一些非空原因"

        # 测试占位符
        for r in results.values():
            if r.raw_text in ("", "-", "—", "/", "N/A"):
                assert r.is_empty is True


class TestReasonCollectorSingle:
    """单槽位采集测试。"""

    def test_collect_one_known_slot(self, skip_if_no_file: bool) -> None:  # type: ignore[no-untyped-def]
        """采集已知槽位。"""
        if skip_if_no_file:
            pytest.skip("测试文件不存在")
        collector = ReasonCollector()
        result = collector.collect_one(str(TEST_FILE), "dom.elec.yoy.changjiang")
        assert result is not None
        assert result.slot.slot_id == "dom.elec.yoy.changjiang"
        assert result.source_file.endswith(".xlsx")

    def test_collect_one_unknown_slot(self) -> None:
        """采集未知槽位返回 None。"""
        collector = ReasonCollector()
        result = collector.collect_one(str(TEST_FILE), "nonexistent.slot.id")
        assert result is None


# ============================================================================
# 便利函数测试
# ============================================================================

class TestConvenienceFunctions:
    """便利函数测试。"""

    def test_find_slot_by_id_found(self) -> None:
        slot = find_slot_by_id("dom.elec.yoy.changjiang")
        assert slot is not None
        assert slot.slot_id == "dom.elec.yoy.changjiang"

    def test_find_slot_by_id_not_found(self) -> None:
        slot = find_slot_by_id("nonexistent")
        assert slot is None

    def test_collect_all_reasons_filters_empty(self, skip_if_no_file: bool) -> None:  # type: ignore[no-untyped-def]
        """collect_all_reasons 应过滤空文本。"""
        if skip_if_no_file:
            pytest.skip("测试文件不存在")
        all_reasons = collect_all_reasons(str(TEST_FILE))
        # 所有返回的文本都不应为空
        for sid, text in all_reasons.items():
            assert text and text.strip(), f"槽位 {sid} 文本为空"


# ============================================================================
# 文本规范化测试
# ============================================================================

class TestNormalizeText:
    """文本规范化逻辑测试。"""

    def test_none_returns_empty(self) -> None:
        assert ReasonCollector._normalize_text(None) == ""

    def test_dash_returns_empty(self) -> None:
        assert ReasonCollector._normalize_text("-") == ""
        assert ReasonCollector._normalize_text("—") == ""
        assert ReasonCollector._normalize_text("/") == ""
        assert ReasonCollector._normalize_text("N/A") == ""

    def test_normal_text_preserved(self) -> None:
        text = "1、全集团电量同比增加..."
        assert ReasonCollector._normalize_text(text) == text

    def test_strips_whitespace(self) -> None:
        assert ReasonCollector._normalize_text("  hello  ") == "hello"


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def skip_if_no_file() -> bool:
    """如果测试文件不存在则跳过。"""
    return not TEST_FILE.exists()
