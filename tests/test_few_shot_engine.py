"""Few-shot 自动注入引擎测试"""
import pytest
from streamlit_app.core.few_shot_engine import (
    FewShotExample,
    BUILTIN_EXAMPLES,
    extract_slot_features,
    _extract_text_tags,
    compute_example_similarity,
    select_few_shot_examples,
    format_few_shot_examples,
    inject_few_shot_into_system,
)
from streamlit_app.core.pipeline_state import PolishedSlot


class TestFewShotExample:
    """FewShotExample 数据类测试"""

    def test_create_example(self):
        """测试创建示例"""
        example = FewShotExample(
            example_id="test_001",
            category="domestic",
            generation_mode="extract",
            raw_text="原始文本",
            polished_text="润色后文本",
            tags=("电量", "电价"),
            quality_score=90,
        )
        assert example.example_id == "test_001"
        assert example.category == "domestic"
        assert example.quality_score == 90

    def test_example_immutable(self):
        """测试示例不可变"""
        example = FewShotExample(
            example_id="test_001",
            category="domestic",
            generation_mode="extract",
            raw_text="原始",
            polished_text="润色",
            tags=(),
        )
        with pytest.raises(AttributeError):
            example.category = "international"


class TestBuiltinExamples:
    """内置示例库测试"""

    def test_builtin_examples_exist(self):
        """测试内置示例存在"""
        assert len(BUILTIN_EXAMPLES) > 0
        assert "domestic" in BUILTIN_EXAMPLES
        assert "general" in BUILTIN_EXAMPLES

    def test_all_categories_have_examples(self):
        """测试所有类别都有示例"""
        expected_categories = {"domestic", "international", "market", "environmental", "general"}
        actual_categories = set(BUILTIN_EXAMPLES.keys())
        assert expected_categories.issubset(actual_categories)

    def test_examples_have_required_fields(self):
        """测试示例包含必需字段"""
        for category, examples in BUILTIN_EXAMPLES.items():
            for example in examples:
                assert example.example_id
                assert example.category == category
                assert example.raw_text
                assert example.polished_text
                assert example.quality_score > 0


class TestExtractSlotFeatures:
    """extract_slot_features 函数测试"""

    def test_domestic_slot(self):
        """测试国内段位特征提取"""
        slot = PolishedSlot(
            slot_id="dom.elec.yoy",
            placeholder="{{domestic_electricity}}",
            raw_text="电量同比增加",
            llm_output=None,
            final_text="",
        )
        features = extract_slot_features(slot)
        assert features["category"] == "domestic"

    def test_international_slot(self):
        """测试国际段位特征提取"""
        slot = PolishedSlot(
            slot_id="intl.pakistan.price",
            placeholder="{{pakistan_price}}",
            raw_text="巴基斯坦电价上涨",
            llm_output=None,
            final_text="",
        )
        features = extract_slot_features(slot)
        assert features["category"] == "international"

    def test_market_slot(self):
        """测试市场化段位特征提取"""
        slot = PolishedSlot(
            slot_id="market.trading.volume",
            placeholder="{{market_volume}}",
            raw_text="市场化交易电量",
            llm_output=None,
            final_text="",
        )
        features = extract_slot_features(slot)
        assert features["category"] == "market"

    def test_environmental_slot(self):
        """测试环境资产段位特征提取"""
        slot = PolishedSlot(
            slot_id="env.green_cert",
            placeholder="{{green_cert}}",
            raw_text="绿证交易收入",
            llm_output=None,
            final_text="",
        )
        features = extract_slot_features(slot)
        assert features["category"] == "environmental"

    def test_general_slot(self):
        """测试通用段位特征提取"""
        slot = PolishedSlot(
            slot_id="unknown.slot",
            placeholder="{{unknown}}",
            raw_text="未知内容",
            llm_output=None,
            final_text="",
        )
        features = extract_slot_features(slot)
        assert features["category"] == "general"

    def test_generation_mode_extracted(self):
        """测试生成模式提取"""
        slot = PolishedSlot(
            slot_id="test",
            placeholder="{{test}}",
            raw_text="",
            llm_output=None,
            final_text="",
            generation_mode="grounded_category",
        )
        features = extract_slot_features(slot)
        assert features["generation_mode"] == "grounded_category"


class TestExtractTextTags:
    """_extract_text_tags 函数测试"""

    def test_empty_text(self):
        """测试空文本"""
        tags = _extract_text_tags("")
        assert tags == ()

    def test_single_keyword(self):
        """测试单个关键词"""
        tags = _extract_text_tags("电量同比增加")
        assert "电量" in tags
        assert "同比" in tags

    def test_multiple_keywords(self):
        """测试多个关键词"""
        tags = _extract_text_tags("电量电价同比环比")
        assert "电量" in tags
        assert "电价" in tags
        assert "同比" in tags
        assert "环比" in tags

    def test_top_k_limit(self):
        """测试 top_k 限制"""
        text = "电量电价同比环比市场化现货长协来水偏丰"
        tags = _extract_text_tags(text, top_k=3)
        assert len(tags) <= 3


class TestComputeExampleSimilarity:
    """compute_example_similarity 函数测试"""

    def test_perfect_match(self):
        """测试完美匹配"""
        features = {
            "category": "domestic",
            "generation_mode": "extract",
            "tags": ("电量", "电价"),
        }
        example = FewShotExample(
            example_id="test",
            category="domestic",
            generation_mode="extract",
            raw_text="电量电价",
            polished_text="润色后",
            tags=("电量", "电价"),
        )
        sim = compute_example_similarity(features, example)
        assert sim >= 0.8  # 类别 0.5 + 模式 0.3 + 标签 0.2

    def test_category_match_only(self):
        """测试仅类别匹配"""
        features = {
            "category": "domestic",
            "generation_mode": "fallback",
            "tags": (),
        }
        example = FewShotExample(
            example_id="test",
            category="domestic",
            generation_mode="extract",
            raw_text="文本",
            polished_text="润色",
            tags=(),
        )
        sim = compute_example_similarity(features, example)
        assert 0.4 <= sim <= 0.6  # 仅类别匹配 0.5

    def test_no_match(self):
        """测试无匹配"""
        features = {
            "category": "domestic",
            "generation_mode": "extract",
            "tags": (),
        }
        example = FewShotExample(
            example_id="test",
            category="international",
            generation_mode="fallback",
            raw_text="文本",
            polished_text="润色",
            tags=(),
        )
        sim = compute_example_similarity(features, example)
        assert sim < 0.3


class TestSelectFewShotExamples:
    """select_few_shot_examples 函数测试"""

    def test_select_for_domestic_slot(self):
        """测试为国内段位选择示例"""
        slot = PolishedSlot(
            slot_id="dom.elec.yoy",
            placeholder="{{domestic}}",
            raw_text="电量同比增加",
            llm_output=None,
            final_text="",
        )
        examples = select_few_shot_examples(slot, top_k=2)
        assert len(examples) > 0
        # 应该优先选择 domestic 类别的示例
        assert any(ex.category == "domestic" for ex in examples)

    def test_select_for_international_slot(self):
        """测试为国际段位选择示例"""
        slot = PolishedSlot(
            slot_id="intl.pakistan",
            placeholder="{{pakistan}}",
            raw_text="巴基斯坦电价",
            llm_output=None,
            final_text="",
        )
        examples = select_few_shot_examples(slot, top_k=2)
        assert len(examples) > 0

    def test_fallback_to_general(self):
        """测试降级到通用示例"""
        slot = PolishedSlot(
            slot_id="unknown.slot",
            placeholder="{{unknown}}",
            raw_text="完全无关的内容 XYZ123",
            llm_output=None,
            final_text="",
        )
        examples = select_few_shot_examples(slot, top_k=2, min_similarity=0.9)
        # 应该降级到 general
        assert len(examples) > 0

    def test_top_k_respected(self):
        """测试 top_k 参数生效"""
        slot = PolishedSlot(
            slot_id="dom.test",
            placeholder="{{test}}",
            raw_text="电量",
            llm_output=None,
            final_text="",
        )
        examples = select_few_shot_examples(slot, top_k=1)
        assert len(examples) == 1


class TestFormatFewShotExamples:
    """format_few_shot_examples 函数测试"""

    def test_format_empty_list(self):
        """测试空列表"""
        result = format_few_shot_examples([])
        assert result == ""

    def test_format_single_example(self):
        """测试单个示例"""
        example = FewShotExample(
            example_id="test",
            category="domestic",
            generation_mode="extract",
            raw_text="原始文本",
            polished_text="润色后文本",
            tags=(),
            quality_score=90,
        )
        result = format_few_shot_examples([example])
        assert "【改写示例】" in result
        assert "原始：原始文本" in result
        assert "改写：润色后文本" in result
        assert "domestic" in result
        assert "90分" in result

    def test_format_multiple_examples(self):
        """测试多个示例"""
        examples = [
            FewShotExample("ex1", "domestic", "extract", "原始1", "润色1", (), 90),
            FewShotExample("ex2", "market", "extract", "原始2", "润色2", (), 85),
        ]
        result = format_few_shot_examples(examples)
        assert "【示例 1】" in result
        assert "【示例 2】" in result


class TestInjectFewShotIntoSystem:
    """inject_few_shot_into_system 函数测试"""

    def test_inject_with_slot(self):
        """测试带 slot 注入"""
        base_system = "你是周报润色专家。"
        slot = PolishedSlot(
            slot_id="dom.test",
            placeholder="{{test}}",
            raw_text="电量同比增加",
            llm_output=None,
            final_text="",
        )
        result = inject_few_shot_into_system(base_system, slot, top_k=2)
        assert base_system in result
        assert "【改写示例】" in result

    def test_inject_without_slot(self):
        """测试无 slot 降级"""
        base_system = "你是周报润色专家。"
        result = inject_few_shot_into_system(base_system, None, top_k=2)
        # 应该返回原始 system（无 few-shot）
        assert result == base_system
