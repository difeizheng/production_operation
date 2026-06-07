"""Unit tests for ReasonPolisher - Step 1 PoC

测试覆盖：
    1. 优雅降级（API key 不存在时返回原文）
    2. 空文本处理
    3. 短文本直通
    4. 防幻觉验证（数字、推测措辞、长度）
    5. 批量润色
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.generator.reason_polisher import (
    PolishResult,
    ReasonPolisher,
    polish_reason,
)


# ============================================================================
# 初始化测试
# ============================================================================

class TestReasonPolisherInit:
    """初始化测试。"""

    def test_init_without_api_key_is_fallback(self) -> None:
        """没有 API key 时 is_available=False。"""
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {
                "LLM_PROVIDER": "", "LLM_API_KEY": "", "ANTHROPIC_API_KEY": "",
                "ENABLE_LLM_POLISH": "false",
            }, clear=True):
            polisher = ReasonPolisher()
            assert polisher.is_available is False

    def test_init_with_api_key_loads_client(self) -> None:
        """有 API key 时尝试加载客户端（通过工厂）。"""
        # 使用 LLM 工厂路径（Qwen 模拟）
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "qwen",
            "LLM_API_KEY": "test-qwen-key",
            "LLM_BASE_URL": "https://test.url/v1",
            "LLM_MODEL_NAME": "qwen-test",
        }):
            with patch("openai.OpenAI") as mock_openai:
                mock_openai.return_value = MagicMock()
                polisher = ReasonPolisher()
                # 通过 .env 工厂初始化，验证 provider 和 model
                assert polisher.provider == "qwen"
                assert polisher.model_name == "qwen-test"

    def test_init_explicit_api_key(self) -> None:
        """显式传入 API key 走 Anthropic 路径。"""
        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_anthropic.return_value = MagicMock()
            polisher = ReasonPolisher(api_key="explicit-key")
            assert polisher.provider == "anthropic"


# ============================================================================
# Fallback 行为测试
# ============================================================================

class TestFallbackBehavior:
    """无 LLM 时的回退行为。"""

    def test_empty_text_returns_empty(self) -> None:
        """空文本返回空 polish。"""
        with patch.dict(os.environ, {}, clear=True):
            polisher = ReasonPolisher()
            result = polisher.polish("")
            assert result.polished_text == ""
            assert result.is_fallback is True
            assert result.error == "空文本"

    def test_whitespace_text_returns_empty(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            polisher = ReasonPolisher()
            result = polisher.polish("   \n  ")
            assert result.polished_text == ""

    def test_short_text_returns_as_is(self) -> None:
        """< 30 字符的短文本不调 LLM，直接返回。"""
        with patch.dict(os.environ, {}, clear=True):
            polisher = ReasonPolisher()
            short = "1、来水偏丰。"
            result = polisher.polish(short)
            assert result.polished_text == short
            assert result.is_fallback is True
            assert result.model_used == "none-short"

    def test_no_api_key_fallback(self) -> None:
        """无 API key 时直接返回原文。"""
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {
                "LLM_PROVIDER": "", "LLM_API_KEY": "", "ANTHROPIC_API_KEY": "",
                "ENABLE_LLM_POLISH": "false",
            }, clear=True):
            polisher = ReasonPolisher()
            text = "1、全集团电量同比增加，主要原因为乌东德电站及白鹤滩电站来水偏丰。"
            result = polisher.polish(text)
            assert result.polished_text == text
            assert result.is_fallback is True
            assert result.error == "LLM 不可用"


# ============================================================================
# 防幻觉验证测试
# ============================================================================

class TestValidation:
    """防幻觉验证逻辑测试。"""

    def test_validate_number_preservation_pass(self) -> None:
        """数字保留时通过。"""
        with patch.dict(os.environ, {}, clear=True):
            polisher = ReasonPolisher()
            raw = "1、全集团电量 80.3 亿千瓦时，同比 +3.3%。"
            polished = "1、全集团上网电量 80.3 亿千瓦时，同比增加 3.3%。"
            assert polisher._validate_output(raw, polished) is True

    def test_validate_number_addition_fails(self) -> None:
        """数字被添加时失败。"""
        with patch.dict(os.environ, {}, clear=True):
            polisher = ReasonPolisher()
            raw = "1、全集团电量增加。"
            polished = "1、全集团电量增加 15%。"  # 凭空添加 15
            assert polisher._validate_output(raw, polished) is False

    def test_validate_forbidden_words_fails(self) -> None:
        """发现推测措辞时失败。"""
        with patch.dict(os.environ, {}, clear=True):
            polisher = ReasonPolisher()
            raw = "1、来水偏丰，水电多发。"
            polished = "1、来水偏丰，水电多发，预计下周将继续增长。"  # 推测
            assert polisher._validate_output(raw, polished) is False

    def test_validate_length_too_long_fails(self) -> None:
        """输出过长时失败。"""
        with patch.dict(os.environ, {}, clear=True):
            polisher = ReasonPolisher()
            raw = "1、来水偏丰。"
            polished = "1、来水偏丰。" + "其他内容" * 20  # 远超 1.8 倍
            assert polisher._validate_output(raw, polished) is False


# ============================================================================
# 批量测试
# ============================================================================

class TestBatchPolish:
    """批量润色测试。"""

    def test_batch_returns_dict(self) -> None:
        """批量返回字典。"""
        with patch.dict(os.environ, {}, clear=True):
            polisher = ReasonPolisher()
            batch = {
                "slot1": "1、全集团电量同比增加。",
                "slot2": "1、全集团电价环比降低。",
            }
            results = polisher.polish_batch(batch)
            assert isinstance(results, dict)
            assert "slot1" in results
            assert "slot2" in results
            assert all(isinstance(r, PolishResult) for r in results.values())


# ============================================================================
# JSON 解析测试
# ============================================================================

class TestJsonExtraction:
    """从 LLM 输出中提取 JSON 的健壮性测试。"""

    def test_extract_from_valid_json(self) -> None:
        text = '{"polished_text": "改写后的文本", "key_numbers": ["80.3"]}'
        result = ReasonPolisher._extract_polished_from_text(text)
        assert result == "改写后的文本"

    def test_extract_from_plain_text(self) -> None:
        text = "这是普通文本，没有 JSON 结构"
        result = ReasonPolisher._extract_polished_from_text(text)
        assert result == text


# ============================================================================
# 便利函数测试
# ============================================================================

class TestConvenienceFunction:
    """polish_reason 便利函数测试。"""

    def test_returns_string(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            text = "1、全集团电量同比增加。短文"
            result = polish_reason(text)
            assert isinstance(result, str)
