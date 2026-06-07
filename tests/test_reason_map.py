"""Step 3 回归测试 - 验证 reason_map.json 端到端

测试覆盖：
    1. JSON 文件结构完整性
    2. 所有 source_slots 在 ALL_REASON_SLOTS 中存在
    3. 每个 HIGH 自动化段落可成功提取数据
    4. automation_level 分布合理
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.collector.reason_collector import (
    ALL_REASON_SLOTS,
    ReasonCollector,
)


REASON_MAP_PATH = PROJECT_ROOT / "data" / "dictionaries" / "reason_map.json"
SUMMARY_FILE = PROJECT_ROOT / "files" / "2026年第21周周数据汇总表.xlsx"


# ============================================================================
# JSON 结构测试
# ============================================================================

class TestReasonMapStructure:
    """reason_map.json 结构测试。"""

    def test_file_exists(self) -> None:
        """reason_map.json 必须存在。"""
        assert REASON_MAP_PATH.exists(), f"文件不存在: {REASON_MAP_PATH}"

    def test_json_valid(self) -> None:
        """JSON 必须能解析。"""
        with open(REASON_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "mappings" in data
        assert "version" in data
        assert "total_mappings" in data

    def test_mappings_have_required_fields(self) -> None:
        """每条 mapping 必须有必需字段。"""
        with open(REASON_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for m in data["mappings"]:
            assert "v4_index" in m
            assert "template_placeholder" in m
            assert "source_slots" in m
            assert "automation_level" in m
            assert "polish_required" in m

    def test_automation_level_valid(self) -> None:
        """automation_level 必须是有效值。"""
        valid_levels = {"HIGH", "MEDIUM", "LOW", "MANUAL"}
        with open(REASON_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for m in data["mappings"]:
            assert m["automation_level"] in valid_levels, \
                f"P{m['v4_index']}: 非法 level '{m['automation_level']}'"

    def test_placeholder_unique(self) -> None:
        """占位符必须唯一。"""
        with open(REASON_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        placeholders = [m["template_placeholder"] for m in data["mappings"]]
        assert len(placeholders) == len(set(placeholders)), \
            f"重复占位符: {[p for p in placeholders if placeholders.count(p) > 1]}"


# ============================================================================
# 槽位引用测试
# ============================================================================

class TestSlotReferences:
    """所有引用的槽位必须存在。"""

    def test_all_source_slots_exist(self) -> None:
        """所有 source_slots 必须在 ALL_REASON_SLOTS 中。"""
        with open(REASON_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        valid_slot_ids = {s.slot_id for s in ALL_REASON_SLOTS}

        for m in data["mappings"]:
            for slot_id in m["source_slots"]:
                assert slot_id in valid_slot_ids, \
                    f"P{m['v4_index']}: 引用了不存在的槽位 '{slot_id}'"


# ============================================================================
# 提取验证测试
# ============================================================================

class TestExtractionCoverage:
    """实测每个 HIGH 自动化段落能否取到数据。"""

    def test_high_auto_can_extract(self, skip_if_no_files: bool) -> None:  # type: ignore[no-untyped-def]
        """HIGH 自动化的段落必须能取到非空数据。"""
        if skip_if_no_files:
            pytest.skip("测试文件不存在")

        collector = ReasonCollector()
        results, _ = collector.collect(str(SUMMARY_FILE))

        with open(REASON_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        high_pass = 0
        high_fail = 0
        for m in data["mappings"]:
            if m["automation_level"] != "HIGH":
                continue
            if not m["source_slots"]:
                continue

            any_non_empty = any(
                slot_id in results and not results[slot_id].is_empty
                for slot_id in m["source_slots"]
            )

            if any_non_empty:
                high_pass += 1
            else:
                high_fail += 1
                pytest.fail(
                    f"P{m['v4_index']} 标记为 HIGH 但所有 source_slots 都为空: {m['source_slots']}"
                )

        # 至少应有 1 个 HIGH 段落
        assert high_pass > 0, "至少应有 1 个 HIGH 段落能取到数据"

    def test_manual_segments_have_fallback(self) -> None:
        """MANUAL 段落必须有 fallback_text。"""
        with open(REASON_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for m in data["mappings"]:
            if m["automation_level"] == "MANUAL":
                assert m.get("fallback_text"), \
                    f"P{m['v4_index']} 标记为 MANUAL 但无 fallback_text"


# ============================================================================
# 覆盖率统计测试
# ============================================================================

class TestCoverageStats:
    """覆盖率统计测试。"""

    def test_automation_rate_reasonable(self) -> None:
        """自动化覆盖率应在 50% 以上。"""
        with open(REASON_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        total = len(data["mappings"])
        auto = sum(
            1 for m in data["mappings"]
            if m["automation_level"] in ("HIGH", "MEDIUM")
        )

        rate = auto / total if total > 0 else 0
        assert rate >= 0.5, f"自动化覆盖率 {rate:.0%} 低于 50%"

    def test_no_over_automation(self) -> None:
        """100% 自动化是允许的（Step 8 后所有 MANUAL 都已自动化）。"""
        with open(REASON_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 现在所有段落都是 HIGH/MEDIUM，100% 自动化是允许的
        # 但应至少有 1 个 fallback_text 字段（用于 graceful degradation）
        has_fallback = any(
            m.get("fallback_text") for m in data["mappings"]
        )
        assert has_fallback, "应至少保留 1 个 fallback_text 字段"


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def skip_if_no_files() -> bool:
    """如果测试文件不存在则跳过。"""
    return not (REASON_MAP_PATH.exists() and SUMMARY_FILE.exists())
