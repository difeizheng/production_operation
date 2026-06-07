"""Unit tests for LLM Factory - Step 7

测试覆盖：
    1. .env 加载
    2. 各 provider 配置加载（anthropic/qwen/openai/deepseek）
    3. 客户端创建
    4. 统一 call_llm 接口
    5. 优雅降级
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.llm_factory import (
    LLMConfig,
    LLMResponse,
    call_llm,
    create_client,
    get_provider,
    is_configured,
    load_config,
    load_env,
)


# ============================================================================
# 配置加载测试
# ============================================================================

class TestLoadConfig:
    """LLMConfig 加载测试。"""

    def test_no_config_returns_none(self) -> None:
        """无任何环境变量时返回 None。"""
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {}, clear=True):
            assert load_config() is None

    def test_qwen_config(self) -> None:
        """Qwen 配置。"""
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {
                "LLM_PROVIDER": "qwen",
                "LLM_API_KEY": "test-key",
                "LLM_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "LLM_MODEL_NAME": "qwen-turbo",
            }, clear=True):
            config = load_config()
            assert config is not None
            assert config.provider == "qwen"
            assert config.api_key == "test-key"
            assert "dashscope" in config.base_url
            assert config.model_name == "qwen-turbo"

    def test_anthropic_config(self) -> None:
        """Anthropic 配置。"""
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {
                "LLM_PROVIDER": "anthropic",
                "ANTHROPIC_API_KEY": "test-ant-key",
                "LLM_MODEL_NAME": "claude-test",
            }, clear=True):
            config = load_config()
            assert config is not None
            assert config.provider == "anthropic"
            assert config.api_key == "test-ant-key"
            assert config.base_url is None  # Anthropic 不需要

    def test_disabled_returns_none(self) -> None:
        """ENABLE_LLM_POLISH=false 时返回 None。"""
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {
                "LLM_PROVIDER": "qwen",
                "LLM_API_KEY": "test-key",
                "ENABLE_LLM_POLISH": "false",
            }, clear=True):
            assert load_config() is None

    def test_unknown_provider_returns_none(self) -> None:
        """未知 provider 返回 None。"""
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {
                "LLM_PROVIDER": "unknown-llm",
                "LLM_API_KEY": "test-key",
            }, clear=True):
            assert load_config() is None

    def test_missing_api_key_returns_none(self) -> None:
        """Qwen 配但无 API key 返回 None。"""
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {
                "LLM_PROVIDER": "qwen",
                # 故意不设 LLM_API_KEY
            }, clear=True):
            assert load_config() is None


# ============================================================================
# 客户端创建测试
# ============================================================================

class TestCreateClient:
    """create_client 测试。"""

    def test_qwen_creates_openai_client(self) -> None:
        """Qwen 创建 OpenAI 兼容客户端。"""
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {
                "LLM_PROVIDER": "qwen",
                "LLM_API_KEY": "test-key",
                "LLM_BASE_URL": "https://test.url/v1",
                "LLM_MODEL_NAME": "qwen-turbo",
            }, clear=True):
            with patch("openai.OpenAI") as mock_openai:
                mock_openai.return_value = MagicMock()
                client, config = create_client()
                assert client is not None
                assert config.provider == "qwen"

    def test_anthropic_creates_anthropic_client(self) -> None:
        """Anthropic 创建 Anthropic 客户端。"""
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {
                "LLM_PROVIDER": "anthropic",
                "ANTHROPIC_API_KEY": "test-key",
            }, clear=True):
            with patch("anthropic.Anthropic") as mock_anthropic:
                mock_anthropic.return_value = MagicMock()
                client, config = create_client()
                assert client is not None
                assert config.provider == "anthropic"

    def test_no_config_returns_none_tuple(self) -> None:
        """无配置返回 (None, None)。"""
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {}, clear=True):
            client, config = create_client()
            assert client is None
            assert config is None


# ============================================================================
# call_llm 测试
# ============================================================================

class TestCallLLM:
    """统一调用接口测试。"""

    def test_call_qwen(self) -> None:
        """调用 Qwen。"""
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {
                "LLM_PROVIDER": "qwen",
                "LLM_API_KEY": "test-key",
                "LLM_BASE_URL": "https://test.url/v1",
                "LLM_MODEL_NAME": "qwen-turbo",
            }, clear=True):
            with patch("openai.OpenAI") as mock_openai_class:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "Qwen 回复"
                mock_response.model = "qwen-turbo"
                mock_response.usage.prompt_tokens = 10
                mock_response.usage.completion_tokens = 20
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai_class.return_value = mock_client

                response = call_llm("测试 prompt", system="你是助手")
                assert response is not None
                assert response.content == "Qwen 回复"
                assert response.provider == "qwen"
                assert response.input_tokens == 10
                assert response.output_tokens == 20

    def test_call_no_config(self) -> None:
        """无配置返回 None。"""
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {}, clear=True):
            response = call_llm("测试")
            assert response is None


# ============================================================================
# 便利函数测试
# ============================================================================

class TestConvenienceFunctions:
    """便利函数测试。"""

    def test_is_configured_false(self) -> None:
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {
                "LLM_PROVIDER": "", "LLM_API_KEY": "", "ANTHROPIC_API_KEY": "",
                "ENABLE_LLM_POLISH": "false",
            }, clear=True):
            assert is_configured() is False

    def test_is_configured_true(self) -> None:
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {
                "LLM_PROVIDER": "qwen",
                "LLM_API_KEY": "test",
            }, clear=True):
            assert is_configured() is True

    def test_get_provider(self) -> None:
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {
                "LLM_PROVIDER": "qwen", "LLM_API_KEY": "", "ANTHROPIC_API_KEY": "",
            }, clear=True):
            assert get_provider() == "qwen"

    def test_get_provider_none(self) -> None:
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {
                "LLM_PROVIDER": "", "LLM_API_KEY": "", "ANTHROPIC_API_KEY": "",
            }, clear=True):
            assert get_provider() is None
