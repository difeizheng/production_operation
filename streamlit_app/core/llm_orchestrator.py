"""LLM 编排器 - 调参包装与重试逻辑

设计原则：
    1. 包装现有 call_llm() 保持兼容
    2. 支持可调参数：temperature/max_tokens/model_name
    3. 自动重试：指数退避（1s → 2s → 4s）
    4. Token 统计：每次调用累计到 orchestrator 实例
    5. Few-shot 支持：从 corrections 库拉历史编辑作为示例

使用：
    orchestrator = LLMOrchestrator()
    result = orchestrator.polish(raw_text, slot_id="dom.elec.yoy.changjiang")
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.utils.llm_factory import call_llm, LLMResponse
from src.generator.reason_polisher import PolishResult
from src.generator.grounded_generator import GroundedResult, build_category_data_block
from streamlit_app.core.corrections_store import CorrectionsStore, get_corrections_store

logger = logging.getLogger(__name__)


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class LLMCallParams:
    """LLM 调用参数。"""
    temperature: float = 0.3
    max_tokens: int = 500
    model_name: Optional[str] = None
    custom_system_prompt: Optional[str] = None
    custom_user_prompt: Optional[str] = None
    use_few_shot: bool = False  # 从 corrections 库注入示例

    def to_dict(self) -> Dict[str, Any]:
        return {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "model_name": self.model_name,
            "use_few_shot": self.use_few_shot,
            "has_custom_system": self.custom_system_prompt is not None,
            "has_custom_user": self.custom_user_prompt is not None,
        }


@dataclass
class OrchestratorStats:
    """编排器统计。"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    retried_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_latency_ms: int = 0

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_calls == 0:
            return 0.0
        return self.total_latency_ms / self.successful_calls

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "retried_calls": self.retried_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
        }


# ============================================================================
# 提示词模板
# ============================================================================

DEFAULT_SYSTEM_PROMPT = """你是能源行业（电力营销）资深周报撰写专家。

【核心原则】
- 所有数字必须**严格保留**（来自原始文本）
- 不得编造任何数据、电站名称、流域名称
- 保持正式、专业的语言风格
- 输出严格 JSON 格式

【JSON 结构】
{
  "polished_text": "改写后的完整段落",
  "key_numbers": ["80.3", "59.05", ...]
}
"""

DEFAULT_USER_PROMPT = """请将以下原始文本改写为更专业、更精炼的周报段落：

【原始文本】
{raw_text}

【要求】
1. 保留所有数字
2. 100-300 字
3. 保持信息完整性
4. 严格 JSON 输出
"""


def build_few_shot_block(corrections: List[Any], max_examples: int = 3) -> str:
    """构建 few-shot 示例块。"""
    if not corrections:
        return ""
    examples = corrections[-max_examples:]
    lines = ["【历史编辑示例（学习风格）】"]
    for i, c in enumerate(examples, 1):
        lines.append(f"\n示例 {i}:")
        lines.append(f"原文：{c.original_raw[:200]}")
        lines.append(f"改写：{c.human_edited[:200]}")
    return "\n".join(lines)


# ============================================================================
# 核心类
# ============================================================================

class LLMOrchestrator:
    """LLM 调用编排器。

    包装 call_llm() 增加：
        - 可调参数（temperature/max_tokens/model）
        - 重试机制（指数退避）
        - Token 统计
        - Few-shot 示例注入
    """

    MAX_RETRIES = 3
    INITIAL_BACKOFF = 1.0
    BACKOFF_MULTIPLIER = 2.0

    def __init__(
        self,
        corrections_store: Optional[CorrectionsStore] = None,
    ) -> None:
        self.corrections = corrections_store or get_corrections_store()
        self.stats = OrchestratorStats()

    # ========================================================================
    # 主入口
    # ========================================================================

    def polish(
        self,
        raw_text: str,
        slot_id: Optional[str] = None,
        params: Optional[LLMCallParams] = None,
    ) -> PolishResult:
        """润色单段文本。

        Args:
            raw_text: 原始文本
            slot_id: 段位 ID（用于 few-shot）
            params: LLM 调用参数

        Returns:
            PolishResult
        """
        if not raw_text or not raw_text.strip():
            return PolishResult(
                raw_text=raw_text,
                polished_text="",
                is_fallback=True,
                model_used="none-empty",
                tokens_used=0,
                validation_passed=False,
                error="空文本",
            )

        if len(raw_text) < 30:
            return PolishResult(
                raw_text=raw_text,
                polished_text=raw_text,
                is_fallback=True,
                model_used="none-short",
                tokens_used=0,
                validation_passed=True,
                error=None,
            )

        params = params or LLMCallParams()

        # 构建 prompt
        system_prompt = params.custom_system_prompt or DEFAULT_SYSTEM_PROMPT
        user_prompt = params.custom_user_prompt or DEFAULT_USER_PROMPT.format(raw_text=raw_text)

        # Few-shot 注入
        if params.use_few_shot and slot_id:
            history = self.corrections.get_recent_for_slot(slot_id, n=3)
            if history:
                few_shot = build_few_shot_block(history)
                user_prompt = f"{few_shot}\n\n{user_prompt}"

        # 调用 LLM（带重试）
        response, error = self._call_with_retry(
            prompt=user_prompt,
            system=system_prompt,
            params=params,
        )

        if response is None:
            return PolishResult(
                raw_text=raw_text,
                polished_text=raw_text,
                is_fallback=True,
                model_used="error",
                tokens_used=0,
                validation_passed=False,
                error=error or "LLM 调用失败",
            )

        # 解析 JSON 输出
        polished_text = self._extract_polished_text(response.content)
        input_numbers = re.findall(r"-?\d+\.?\d*", raw_text)
        output_numbers = re.findall(r"-?\d+\.?\d*", polished_text)
        validation_passed = self._validate_numbers(input_numbers, output_numbers)

        return PolishResult(
            raw_text=raw_text,
            polished_text=polished_text,
            is_fallback=False,
            model_used=response.model,
            tokens_used=response.input_tokens + response.output_tokens,
            validation_passed=validation_passed,
            error=None if validation_passed else "数字不一致，已回退",
        )

    def generate_grounded_category(
        self,
        data: Dict[str, Any],
        category: str,
        params: Optional[LLMCallParams] = None,
        slot_id: Optional[str] = None,
    ) -> GroundedResult:
        """数据驱动的品类级原因生成（封装 GroundedReasonGenerator）。"""
        from src.generator.grounded_generator import GroundedReasonGenerator
        gen = GroundedReasonGenerator(use_llm=True)
        return gen.generate_category_reason(data=data, category=category)

    # ========================================================================
    # 内部方法
    # ========================================================================

    def _call_with_retry(
        self,
        prompt: str,
        system: str,
        params: LLMCallParams,
    ) -> Tuple[Optional[LLMResponse], Optional[str]]:
        """带指数退避的重试调用。"""
        last_error: Optional[str] = None
        backoff = self.INITIAL_BACKOFF

        for attempt in range(1, self.MAX_RETRIES + 1):
            self.stats.total_calls += 1
            start = time.time()

            try:
                response = call_llm(
                    prompt=prompt,
                    system=system,
                    max_tokens=params.max_tokens,
                    temperature=params.temperature,
                )
                latency_ms = int((time.time() - start) * 1000)
                self.stats.total_latency_ms += latency_ms

                if response is None:
                    self.stats.failed_calls += 1
                    last_error = "LLM 返回 None"
                    logger.warning("LLM 调用失败 (尝试 %d/%d): %s", attempt, self.MAX_RETRIES, last_error)
                    if attempt < self.MAX_RETRIES:
                        self.stats.retried_calls += 1
                        time.sleep(backoff)
                        backoff *= self.BACKOFF_MULTIPLIER
                    continue

                # 成功
                self.stats.successful_calls += 1
                self.stats.total_input_tokens += response.input_tokens
                self.stats.total_output_tokens += response.output_tokens
                logger.info(
                    "LLM 调用成功 (尝试 %d): tokens=%d, latency=%dms",
                    attempt, response.input_tokens + response.output_tokens, latency_ms,
                )
                return response, None

            except Exception as e:
                self.stats.failed_calls += 1
                last_error = str(e)
                logger.warning("LLM 调用异常 (尝试 %d/%d): %s", attempt, self.MAX_RETRIES, e)
                if attempt < self.MAX_RETRIES:
                    self.stats.retried_calls += 1
                    time.sleep(backoff)
                    backoff *= self.BACKOFF_MULTIPLIER

        return None, last_error or "重试耗尽"

    @staticmethod
    def _extract_polished_text(content: str) -> str:
        """从 LLM 输出中提取 polished_text 字段。"""
        # 尝试解析 JSON
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                return data.get("polished_text", content)
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 提取
        match = re.search(r'"polished_text"\s*:\s*"([^"]+)"', content)
        if match:
            return match.group(1)
        return content.strip()

    @staticmethod
    def _validate_numbers(input_numbers: List[str], output_numbers: List[str]) -> bool:
        """验证输出数字都在输入中（容忍 ±0.01 误差）。"""
        if not output_numbers:
            return True
        input_sig = {n for n in input_numbers if len(n) >= 2 or "." in n}
        output_sig = {n for n in output_numbers if len(n) >= 2 or "." in n}
        for on in output_sig:
            if on in input_sig:
                continue
            try:
                on_f = float(on)
                if any(abs(on_f - float(inum)) < 0.011 for inum in input_sig):
                    continue
            except ValueError:
                pass
            return False
        return True


# ============================================================================
# 便利函数
# ============================================================================

def get_orchestrator() -> LLMOrchestrator:
    """获取全局 LLMOrchestrator（单例）。"""
    return LLMOrchestrator()
