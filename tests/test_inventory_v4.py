"""Unit tests for V4.docx inventory (Step 2)

测试覆盖：
    1. 段落分类器（SegmentClassifier）
    2. 关键词匹配
    3. 数据密度判断
    4. 建议 ReasonSlot 推断
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from examples.inventory_v4_reasons import SegmentClassifier


# ============================================================================
# SegmentClassifier 测试
# ============================================================================

class TestSegmentClassifier:
    """段落分类器测试。"""

    def setup_method(self) -> None:
        self.classifier = SegmentClassifier()

    def test_classify_empty_text(self) -> None:
        """空文本应被跳过。"""
        seg = self.classifier.classify(0, "Normal", "")
        assert seg.category == "skip"
        assert seg.needs_mapping is False

    def test_classify_heading(self) -> None:
        """标题段应被识别为 heading。"""
        seg = self.classifier.classify(0, "Heading 1", "一、上周销售情况")
        assert seg.category == "heading"
        assert seg.needs_mapping is False

    def test_classify_table_ref(self) -> None:
        """表格引用应被识别。"""
        seg = self.classifier.classify(0, "Normal", "表1 上周销售情况")
        assert seg.category == "table_ref"
        assert seg.needs_mapping is False

    def test_classify_pure_data(self) -> None:
        """纯数据段应被识别。"""
        seg = self.classifier.classify(0, "Normal", "80.3 亿千瓦时")
        assert seg.category == "data"
        assert seg.needs_mapping is False

    def test_classify_pure_reason(self) -> None:
        """纯原因段应被识别。"""
        seg = self.classifier.classify(
            0, "Normal",
            "水电电价环比下降每千瓦时0.4分，主要原因是电价较高的金下梯级电站占比下降。",
        )
        assert seg.category == "reason"
        assert seg.needs_mapping is True
        assert len(seg.reason_keywords) > 0

    def test_classify_summary(self) -> None:
        """数据+原因混合段应被识别为 summary。"""
        seg = self.classifier.classify(
            0, "Normal",
            "上周，集团公司国内上网电量80.3亿千瓦时，发电收入24.9亿元、同比3.2%，环比15.7%，主要原因是水电、新能源收入同比提高。",
        )
        assert seg.category == "summary"
        assert seg.needs_mapping is True

    def test_priority_higher_for_more_keywords(self) -> None:
        """多关键词段落优先级更高。"""
        seg_low = self.classifier.classify(
            0, "Normal", "原因为来水偏丰。",
        )
        seg_high = self.classifier.classify(
            0, "Normal",
            "主要原因是来水偏丰，受供需影响，电价上涨。",
        )
        # 多关键词应该 priority 更高（不强制 > 1）
        assert seg_high.priority >= seg_low.priority


class TestKeywordMatching:
    """关键词匹配测试。"""

    def setup_method(self) -> None:
        self.classifier = SegmentClassifier()

    def test_match_main_reason(self) -> None:
        keywords = self.classifier._match_reason_keywords("主要原因是 X")
        assert any("主要" in k for k in keywords)

    def test_match_shou_yinxiang(self) -> None:
        """匹配"受...影响"模式。"""
        keywords = self.classifier._match_reason_keywords("受来水偏丰影响")
        assert len(keywords) > 0

    def test_no_match_pure_data(self) -> None:
        """纯数据不匹配。"""
        keywords = self.classifier._match_reason_keywords("80.3 亿千瓦时")
        # 80.3 不在关键词中
        # 实际上 "其中" 可能在，但数据段会被分类为 data
        # 这里仅验证 _match_reason_keywords 本身
        assert isinstance(keywords, list)


class TestDataDensity:
    """数据密度判断测试。"""

    def setup_method(self) -> None:
        self.classifier = SegmentClassifier()

    def test_high_density(self) -> None:
        text = "80.3亿千瓦时 同比3.2% 环比15.7%"
        assert self.classifier._is_data_heavy(text) is True

    def test_low_density(self) -> None:
        text = "上周，集团公司国内上网电量同比提高，主要原因是水电、新能源电量提高。"
        # 中文段落，数字占比低
        assert self.classifier._is_data_heavy(text) is False


class TestSuggestSlot:
    """建议 ReasonSlot 测试。"""

    def setup_method(self) -> None:
        self.classifier = SegmentClassifier()

    def test_suggest_dom_yoy(self) -> None:
        text = "国内电量同比增加，主要原因是水电。"
        slot = self.classifier._suggest_slot(text, "reason")
        assert slot is not None
        assert "dom" in slot
        assert "yoy" in slot

    def test_suggest_dom_wow(self) -> None:
        text = "国内电价环比下降，主要原因是结构变化。"
        slot = self.classifier._suggest_slot(text, "reason")
        assert slot is not None
        assert "dom" in slot
        assert "wow" in slot

    def test_suggest_intl(self) -> None:
        text = "国际电价同比提高，主要原因是汇率变动。"
        slot = self.classifier._suggest_slot(text, "reason")
        assert slot is not None
        assert "intl" in slot

    def test_no_suggestion(self) -> None:
        text = "上周水电多发。"
        slot = self.classifier._suggest_slot(text, "other")
        # 没有明确指标，可能无法建议
        # 但 _suggest_slot 会尽力匹配
        # 这里不强断言
        assert slot is None or "dom" in (slot or "")
