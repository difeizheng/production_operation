"""Unit tests for GroundedReasonGenerator - Step 8

测试覆盖：
    1. 数据块构建
    2. 数字验证（防幻觉）
    3. Markdown 提取
    4. LLM 不可用时的 fallback
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.generator.grounded_generator import (
    CATEGORY_KEYS,
    GroundedReasonGenerator,
    GroundedResult,
    build_category_data_block,
    generate_category_text,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_data() -> dict:
    """模拟 AnalysisCollector 的输出。"""
    return {
        "report.electricity.hydro": 59.045,
        "report.electricity.wind": 10.363,
        "report.electricity.solar": 7.594,
        "report.electricity.thermal": 3.118,
        "report.wow_electricity.hydro": 0.192,
        "report.wow_electricity.wind": 0.284,
        "report.wow_electricity.solar": -0.066,
        "report.wow_electricity.thermal": -0.101,
        "report.yoy_electricity.hydro": 0.066,
        "report.yoy_electricity.wind": 0.118,
        "report.yoy_electricity.solar": -0.038,
        "report.yoy_electricity.thermal": -0.376,
        "report.price.hydro": 0.283,
        "report.price.wind": 0.412,
        "report.price.solar": 0.340,
        "report.price.thermal": 0.420,
        "report.wow_price.hydro": -0.0044,  # -0.44 分
        "report.wow_price.wind": 0.0172,    # +1.72 分
        "report.wow_price.solar": 0.0111,   # +1.11 分
        "report.wow_price.thermal": 0.0342, # +3.42 分
        "report.yoy_price.hydro": -0.0011,
        "report.yoy_price.wind": -0.0070,
        "report.yoy_price.solar": -0.0257,
        "report.yoy_price.thermal": -0.0364,
    }


# ============================================================================
# 数据块构建测试
# ============================================================================

class TestBuildCategoryDataBlock:
    """build_category_data_block 测试。"""

    def test_hydro_block(self, sample_data: dict) -> None:
        """构建水电数据块。"""
        block = build_category_data_block(sample_data, "hydro")
        assert "水电" in block
        assert "本周电量" in block
        assert "59.05" in block  # 59.045 → 59.05
        assert "0.283" in block  # 电价 0.283（保留 3 位小数）
        assert "-0.44" in block  # 电价环比 -0.44 分

    def test_wind_block(self, sample_data: dict) -> None:
        """构建风电数据块。"""
        block = build_category_data_block(sample_data, "wind")
        assert "风电" in block
        assert "1.72" in block  # 电价环比 +1.72 分

    def test_unknown_category_uses_key(self, sample_data: dict) -> None:
        """未知品类用 key 代替。"""
        block = build_category_data_block(sample_data, "unknown_cat")
        assert "unknown_cat" in block

    def test_missing_data_field(self) -> None:
        """缺失数据字段时显示"无数据"。"""
        block = build_category_data_block({}, "hydro")
        assert "（无数据）" in block


# ============================================================================
# 数字验证测试
# ============================================================================

class TestValidateNumbers:
    """防幻觉验证测试。"""

    def test_all_numbers_preserved(self) -> None:
        """所有数字都在输入中时通过。"""
        gen = GroundedReasonGenerator(use_llm=False)
        passed = gen._validate_numbers(
            input_numbers=["10.5", "0.44", "59.04"],
            output_numbers=["10.5", "0.44"],
        )
        assert passed is True

    def test_new_number_in_output_fails(self) -> None:
        """输出有输入未有的数字时失败。"""
        gen = GroundedReasonGenerator(use_llm=False)
        passed = gen._validate_numbers(
            input_numbers=["10.5"],
            output_numbers=["10.5", "99.9"],  # 99.9 不在输入
        )
        assert passed is False

    def test_tolerance_for_rounding(self) -> None:
        """容忍 ±0.01 误差。"""
        gen = GroundedReasonGenerator(use_llm=False)
        passed = gen._validate_numbers(
            input_numbers=["0.44"],
            output_numbers=["0.45"],  # 0.01 误差
        )
        assert passed is True

    def test_empty_output_passes(self) -> None:
        """空输出算通过。"""
        gen = GroundedReasonGenerator(use_llm=False)
        passed = gen._validate_numbers(input_numbers=["10.5"], output_numbers=[])
        assert passed is True

    def test_single_digit_ignored(self) -> None:
        """单数字（0-9）不算关键数字。"""
        gen = GroundedReasonGenerator(use_llm=False)
        passed = gen._validate_numbers(
            input_numbers=["10.5"],
            output_numbers=["1", "2", "3"],  # 单数字忽略
        )
        assert passed is True


# ============================================================================
# Markdown 提取测试
# ============================================================================

class TestExtractFromMarkdown:
    """_extract_from_markdown 测试。"""

    def test_extract_json_text(self) -> None:
        text = '{"text": "水电电价环比下降", "key_facts": ["A"]}'
        assert GroundedReasonGenerator._extract_from_markdown(text) == "水电电价环比下降"

    def test_plain_text(self) -> None:
        text = "普通文本"
        assert GroundedReasonGenerator._extract_from_markdown(text) == "普通文本"


# ============================================================================
# 生成器测试
# ============================================================================

class TestGroundedGenerator:
    """GroundedReasonGenerator 端到端测试。"""

    def test_without_llm_returns_datablock(self, sample_data: dict) -> None:
        """无 LLM 时返回数据块。"""
        gen = GroundedReasonGenerator(use_llm=False)
        result = gen.generate_category_reason(sample_data, "hydro")
        assert result.is_fallback is True
        assert "水电" in result.text

    def test_with_llm_no_config(self, sample_data: dict) -> None:
        """LLM 未配置时返回数据块。"""
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(__import__("os").environ, {
                "LLM_PROVIDER": "", "LLM_API_KEY": "", "ANTHROPIC_API_KEY": "",
                "ENABLE_LLM_POLISH": "false",
             }, clear=True):
            gen = GroundedReasonGenerator(use_llm=True)
            result = gen.generate_category_reason(sample_data, "hydro")
            assert result.is_fallback is True
            assert "水电" in result.text

    def test_with_mock_llm(self, sample_data: dict) -> None:
        """Mock LLM 调用。"""
        with patch.dict(__import__("os").environ, {
            "LLM_PROVIDER": "qwen",
            "LLM_API_KEY": "test",
            "LLM_BASE_URL": "https://test/v1",
            "LLM_MODEL_NAME": "qwen-test",
        }, clear=True):
            with patch("src.generator.grounded_generator.call_llm") as mock_call:
                # 使用数据中实际存在的数字（59.05, 19.2, -0.44）
                mock_response = MagicMock()
                mock_response.content = '{"text": "水电电价环比下降-0.44分，电量59.05亿千瓦时，环比增长19.2%。", "key_facts": ["A"]}'
                mock_response.model = "qwen-test"
                mock_response.input_tokens = 100
                mock_response.output_tokens = 50
                mock_call.return_value = mock_response

                gen = GroundedReasonGenerator(use_llm=True)
                result = gen.generate_category_reason(sample_data, "hydro")

                # 所有数字都在输入中，验证通过
                assert result.is_fallback is False
                assert "水电电价" in result.text
                assert result.tokens_used == 150

    def test_hallucination_detected(self, sample_data: dict) -> None:
        """检测到幻觉时回退。"""
        with patch.dict(__import__("os").environ, {
            "LLM_PROVIDER": "qwen",
            "LLM_API_KEY": "test",
            "LLM_BASE_URL": "https://test/v1",
        }, clear=True):
            with patch("src.generator.grounded_generator.call_llm") as mock_call:
                # LLM 编造了 999.99 这个数据
                mock_response = MagicMock()
                mock_response.content = '{"text": "水电电价下降 999.99 分。"}'
                mock_response.model = "qwen"
                mock_response.input_tokens = 100
                mock_response.output_tokens = 50
                mock_call.return_value = mock_response

                gen = GroundedReasonGenerator(use_llm=True)
                result = gen.generate_category_reason(sample_data, "hydro")

                # 验证失败，应该回退到数据块
                assert result.validation_passed is False


# ============================================================================
# 便利函数测试
# ============================================================================

class TestConvenienceFunction:
    """generate_category_text 测试。"""

    def test_returns_string(self, sample_data: dict) -> None:
        with patch.dict(__import__("os").environ, {}, clear=True):
            text = generate_category_text(sample_data, "hydro", use_llm=False)
            assert isinstance(text, str)
            assert "水电" in text
