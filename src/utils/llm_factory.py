"""LLM 客户端工厂 - 支持多家 LLM 提供商（Anthropic/Qwen/OpenAI/DeepSeek）

设计原则：
    1. 配置驱动：通过环境变量切换 LLM，无需改代码
    2. 接口统一：所有 provider 都返回 (client, model_name) 元组
    3. 优雅降级：未配置任何 key 时返回 None，调用方走 fallback
    4. .env 友好：自动加载 .env 文件

支持矩阵：
    ┌──────────┬──────────────────────────────┬────────────────────────┐
    │ Provider │ base_url                     │ 默认 model             │
    ├──────────┼──────────────────────────────┼────────────────────────┤
    │ anthropic│ (Anthropic SDK 内置)         │ claude-haiku-4-5       │
    │ qwen     │ dashscope OpenAI 兼容        │ qwen-turbo             │
    │ openai   │ api.openai.com/v1            │ gpt-4o-mini            │
    │ deepseek │ api.deepseek.com/v1          │ deepseek-chat          │
    └──────────┴──────────────────────────────┴────────────────────────┘
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# 数据类
# ============================================================================

@dataclass(frozen=True)
class LLMConfig:
    """LLM 配置。"""
    provider: str             # anthropic / qwen / openai / deepseek
    api_key: str
    base_url: Optional[str]
    model_name: str
    max_tokens: int = 500

    @property
    def is_valid(self) -> bool:
        return bool(self.api_key and self.model_name)


# ============================================================================
# .env 加载
# ============================================================================

def load_env(env_path: Optional[Path] = None) -> None:
    """加载 .env 文件。

    Args:
        env_path: 自定义 .env 路径（默认项目根目录下的 .env）
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        logger.warning("python-dotenv 未安装，跳过 .env 加载")
        return

    if env_path is None:
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"

    if env_path.exists():
        load_dotenv(env_path)
        logger.debug("已加载 .env: %s", env_path)
    else:
        # 尝试从当前工作目录
        cwd_env = Path.cwd() / ".env"
        if cwd_env.exists():
            load_dotenv(cwd_env)
            logger.debug("已加载 .env: %s", cwd_env)


# ============================================================================
# 配置加载
# ============================================================================

def load_config() -> Optional[LLMConfig]:
    """从环境变量加载 LLM 配置。

    Returns:
        LLMConfig 或 None（未配置时）
    """
    load_env()

    provider = os.environ.get("LLM_PROVIDER", "").lower()
    if not provider:
        return None

    # 提取公共配置
    max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "500"))
    enable_polish = os.environ.get("ENABLE_LLM_POLISH", "true").lower() in ("true", "1", "yes")
    if not enable_polish:
        logger.info("ENABLE_LLM_POLISH=false，跳过 LLM 加载")
        return None

    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            logger.warning("LLM_PROVIDER=anthropic 但 ANTHROPIC_API_KEY 未设置")
            return None
        return LLMConfig(
            provider=provider,
            api_key=api_key,
            base_url=None,
            model_name=os.environ.get("LLM_MODEL_NAME", "claude-haiku-4-5"),
            max_tokens=max_tokens,
        )

    elif provider in ("qwen", "openai", "deepseek"):
        api_key = os.environ.get("LLM_API_KEY", "")
        if not api_key:
            logger.warning("LLM_PROVIDER=%s 但 LLM_API_KEY 未设置", provider)
            return None

        # 各 provider 默认 base_url
        default_urls = {
            "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "openai": "https://api.openai.com/v1",
            "deepseek": "https://api.deepseek.com/v1",
        }
        default_models = {
            "qwen": "qwen-turbo",
            "openai": "gpt-4o-mini",
            "deepseek": "deepseek-chat",
        }
        return LLMConfig(
            provider=provider,
            api_key=api_key,
            base_url=os.environ.get("LLM_BASE_URL", default_urls[provider]),
            model_name=os.environ.get("LLM_MODEL_NAME", default_models[provider]),
            max_tokens=max_tokens,
        )

    else:
        logger.error("未知的 LLM_PROVIDER: %s", provider)
        return None


# ============================================================================
# 客户端工厂
# ============================================================================

def create_client() -> Tuple[Optional[Any], Optional[LLMConfig]]:
    """创建 LLM 客户端。

    Returns:
        (client, config) 元组；未配置时返回 (None, None)
    """
    config = load_config()
    if config is None or not config.is_valid:
        return None, None

    if config.provider == "anthropic":
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=config.api_key)
            logger.info("✅ Anthropic 客户端创建成功 (model=%s)", config.model_name)
            return client, config
        except Exception as e:
            logger.error("Anthropic 客户端创建失败: %s", e)
            return None, None

    else:  # qwen / openai / deepseek - 都用 OpenAI 兼容 SDK
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
            )
            logger.info(
                "✅ %s 客户端创建成功 (model=%s, base_url=%s)",
                config.provider, config.model_name, config.base_url,
            )
            return client, config
        except Exception as e:
            logger.error("%s 客户端创建失败: %s", config.provider, e)
            return None, None


# ============================================================================
# 统一调用接口
# ============================================================================

@dataclass(frozen=True)
class LLMResponse:
    """LLM 统一响应。"""
    content: str          # 文本内容
    model: str
    input_tokens: int
    output_tokens: int
    provider: str


def call_llm(
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 500,
    temperature: float = 0.3,
) -> Optional[LLMResponse]:
    """统一的 LLM 调用接口（不依赖特定 SDK）。

    Args:
        prompt: 用户 prompt
        system: 系统 prompt
        max_tokens: 最大输出 token
        temperature: 温度参数

    Returns:
        LLMResponse 或 None（失败时）
    """
    client, config = create_client()
    if client is None or config is None:
        return None

    try:
        if config.provider == "anthropic":
            response = client.messages.create(
                model=config.model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system or "",
                messages=[{"role": "user", "content": prompt}],
            )
            return LLMResponse(
                content=response.content[0].text,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                provider="anthropic",
            )
        else:  # OpenAI 兼容
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(
                model=config.model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                provider=config.provider,
            )
    except Exception as e:
        logger.error("LLM 调用失败 (%s): %s", config.provider, e)
        return None


# ============================================================================
# 便利函数
# ============================================================================

def is_configured() -> bool:
    """检查 LLM 是否已配置。"""
    return load_config() is not None


def get_provider() -> Optional[str]:
    """获取当前配置的 provider（无配置时返回 None）。"""
    load_env()
    return os.environ.get("LLM_PROVIDER", "").lower() or None
