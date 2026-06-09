"""编辑历史对比组件测试"""
import pytest
from streamlit_app.components.edit_history import (
    DiffResult,
    compute_similarity,
    compute_diff,
    compute_edit_chain,
)
from streamlit_app.core.pipeline_state import PolishedSlot


class TestComputeSimilarity:
    """compute_similarity 函数测试"""

    def test_identical_strings(self):
        """测试相同字符串"""
        sim = compute_similarity("abc", "abc")
        assert sim == 1.0

    def test_completely_different(self):
        """测试完全不同字符串"""
        sim = compute_similarity("abc", "xyz")
        assert sim < 0.5

    def test_empty_strings(self):
        """测试空字符串"""
        sim = compute_similarity("", "")
        assert sim == 1.0

    def test_one_empty(self):
        """测试一个为空"""
        sim = compute_similarity("abc", "")
        assert sim == 0.0

    def test_partial_similarity(self):
        """测试部分相似"""
        sim = compute_similarity("abcdef", "abcxyz")
        assert 0.3 < sim < 0.7


class TestComputeDiff:
    """compute_diff 函数测试"""

    def test_identical_text(self):
        """测试相同文本"""
        diff = compute_diff("abc\n123", "abc\n123")
        assert diff.similarity == 1.0
        assert diff.added_chars == 0
        assert diff.removed_chars == 0

    def test_added_lines(self):
        """测试新增行"""
        old = "line1\nline2"
        new = "line1\nline2\nline3"
        diff = compute_diff(old, new)
        assert diff.added_chars > 0
        # diff 算法可能重新计算上下文，所以 removed_chars 可能 > 0
        assert diff.similarity < 1.0

    def test_removed_lines(self):
        """测试删除行"""
        old = "line1\nline2\nline3"
        new = "line1\nline2"
        diff = compute_diff(old, new)
        # diff 算法可能重新计算上下文，所以 added_chars 可能 > 0
        assert diff.removed_chars > 0
        assert diff.similarity < 1.0

    def test_modified_lines(self):
        """测试修改行"""
        old = "line1\nline2"
        new = "line1\nmodified"
        diff = compute_diff(old, new)
        assert diff.added_chars > 0
        assert diff.removed_chars > 0
        assert diff.similarity < 1.0

    def test_diff_lines_format(self):
        """测试 diff 行格式"""
        old = "abc"
        new = "xyz"
        diff = compute_diff(old, new)
        assert len(diff.diff_lines) > 0
        # diff 行应该包含 + 或 - 前缀
        has_changes = any(
            line.startswith("+") or line.startswith("-")
            for line in diff.diff_lines
        )
        assert has_changes


class TestComputeEditChain:
    """compute_edit_chain 函数测试"""

    def test_empty_slot(self):
        """测试空槽位"""
        slot = PolishedSlot(
            slot_id="slot1",
            placeholder="{{test}}",
            raw_text="",
            llm_output=None,
            final_text="",
        )
        chain = compute_edit_chain(slot)
        assert chain == []

    def test_raw_to_llm(self):
        """测试 raw → llm"""
        slot = PolishedSlot(
            slot_id="slot1",
            placeholder="{{test}}",
            raw_text="原始文本",
            llm_output="LLM 输出",
            final_text="LLM 输出",
        )
        chain = compute_edit_chain(slot)
        assert len(chain) == 1
        assert chain[0][0] == "raw → llm"

    def test_raw_llm_final(self):
        """测试 raw → llm → final"""
        slot = PolishedSlot(
            slot_id="slot1",
            placeholder="{{test}}",
            raw_text="原始文本",
            llm_output="LLM 输出",
            final_text="人工编辑后",
        )
        chain = compute_edit_chain(slot)
        assert len(chain) == 2
        assert chain[0][0] == "raw → llm"
        assert chain[1][0] == "llm → final"

    def test_raw_to_final_no_llm(self):
        """测试 raw → final（无 LLM）"""
        slot = PolishedSlot(
            slot_id="slot1",
            placeholder="{{test}}",
            raw_text="原始文本",
            llm_output=None,
            final_text="人工编辑后",
        )
        chain = compute_edit_chain(slot)
        assert len(chain) == 1
        assert chain[0][0] == "raw → final"

    def test_no_changes(self):
        """测试无变化（final == llm）"""
        slot = PolishedSlot(
            slot_id="slot1",
            placeholder="{{test}}",
            raw_text="原始文本",
            llm_output="LLM 输出",
            final_text="LLM 输出",  # 与 llm_output 相同
        )
        chain = compute_edit_chain(slot)
        # 应该只有 raw → llm，没有 llm → final
        assert len(chain) == 1
        assert chain[0][0] == "raw → llm"


class TestDiffResult:
    """DiffResult 数据类测试"""

    def test_create_diff_result(self):
        """测试创建 DiffResult"""
        diff = DiffResult(
            old_text="old",
            new_text="new",
            similarity=0.5,
            added_chars=3,
            removed_chars=3,
            diff_lines=["-old", "+new"],
        )
        assert diff.old_text == "old"
        assert diff.new_text == "new"
        assert diff.similarity == 0.5
        assert diff.added_chars == 3
        assert diff.removed_chars == 3

    def test_diff_result_immutable(self):
        """测试 DiffResult 不可变"""
        diff = DiffResult(
            old_text="old",
            new_text="new",
            similarity=0.5,
            added_chars=3,
            removed_chars=3,
            diff_lines=[],
        )
        with pytest.raises(AttributeError):
            diff.similarity = 1.0
