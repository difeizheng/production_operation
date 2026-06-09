"""原因文本润色器 - 使用 LLM 把 Excel 里的原始叙述改写为专业周报语言

核心思想（per 用户洞察）：
    - Excel 里的原因文本（如"1、全集团电量同比增加，主要原因为乌东德..."）已经"基本可用"
    - 不需要 LLM 从零生成，LLM 的工作是**编辑/润色**
    - 任务：让叙述更**专业、平行、有逻辑**

设计原则：
    1. 优雅降级：API key 不存在时返回原文本（标记 fallback=True）
    2. 防幻觉验证：润色后所有数字必须出现在原文
    3. 结构化输出：JSON 格式便于程序化处理
    4. 风格可控：prompt 内置 few-shot 示例

成本控制：
    - 默认使用 claude-haiku-4-5（90% Sonnet 能力，3x 成本节省）
    - 每次调用 ~200 token 输出，周报 30 段 ≈ 6000 token
    - 周成本 < 1 元 RMB
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.utils.llm_factory import (
    LLMConfig,
    call_llm,
    create_client,
    load_config,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 数据类
# ============================================================================

@dataclass(frozen=True)
class PolishResult:
    """单次润色结果。"""
    raw_text: str
    polished_text: str
    is_fallback: bool       # True = 没调用 LLM（API 未配置或失败）
    model_used: str          # 实际使用的模型，如 "claude-haiku-4-5" 或 "none"
    tokens_used: int         # 消耗 token（fallback 时为 0）
    validation_passed: bool  # 防幻觉验证是否通过
    error: Optional[str] = None  # 错误信息（如有）


# ============================================================================
# Prompt 模板
# ============================================================================

POLISH_SYSTEM_PROMPT = """你是电力行业（能源营销）资深周报撰写专家，擅长把口语化的工作总结改写为正式、专业、有逻辑的周报段落。

【改写要求】
1. **语言风格**：正式、专业、客观；使用行业术语（"上网电价""同比""环比""市场化交易""现货均价"等）
2. **结构**：保持原文的"一是…二是…三是…"或"1、2、3"结构；如原文已有结构则保留
3. **平行性**：并列原因使用相同句式（如"主因一是…，二是…，三是…"）
4. **数字处理**：原文所有数字必须**原样保留**；不要编造新数字
5. **禁止**：第一人称（我们/我）、推测性措辞（"预计将""据预测"）、结尾套话
6. **长度**：150-250 字；如原文 < 80 字，控制在 80-150 字

【严禁】
- 改写原文中的任何数字
- 添加原文未出现的新事实
- 删除原文的并列结构
- 颠倒原文中明显的因果关系

【输出格式】（严格 JSON）
{
  "polished_text": "改写后的段落",
  "key_numbers_used": ["原文出现的所有数字"],
  "key_entities_used": ["公司/电站/流域/省份名称"]
}
"""

POLISH_USER_TEMPLATE = """【原始叙述】（来自 Excel 表格，保留所有事实）
{raw_text}

【上下文数据】（仅供你参考格式，不要添加到输出中）
{context_hint}

请改写上方"原始叙述"为周报专业段落。记住：
- 所有数字必须保留且不得修改
- 所有实体名（公司/电站/流域/省份）必须保留
- 改写只针对语言风格、结构、句式
"""


FEW_SHOT_EXAMPLES: List[Dict[str, str]] = [
    {
        "raw": "1、全集团电量同比增加，主要原因为乌东德电站及白鹤滩电站来水偏丰。2、全集团电价同比降低，主要原因为电源结构变化，广东省2026年度合约电价同比降低。",
        "polished": "1、全集团上网电量同比增加，主要受乌东德、白鹤滩电站来水偏丰拉动，水电发电能力同比提升；2、全集团上网电价同比下降，主要受电源结构变化及广东省2026年度合约电价同比下行影响。",
    },
    {
        "raw": "1、全集团电量环比增加，主要原因为乌东德电站及白鹤滩电站来水偏丰，集团外送电计划增加。2、全集团电价环比降低，主要原因是电源结构变化。",
        "polished": "1、全集团上网电量环比增加，主因乌东德、白鹤滩流域来水偏丰叠加集团外送电计划释放；2、全集团上网电价环比下降，主因电源结构变化导致均价较低的水电、清洁能源占比提升。",
    },
]


# ============================================================================
# 核心类
# ============================================================================

class ReasonPolisher:
    """原因文本润色器。

    用法：
        polisher = ReasonPolisher()
        result = polisher.polish("1、全集团电量...")
        print(result.polished_text)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-haiku-4-5",
        max_length: int = 250,
        validate: bool = True,
    ) -> None:
        """初始化润色器。

        优先使用 LLM 工厂（从 .env 读取配置），回退到 api_key 参数。

        Args:
            api_key: 显式传入 API key（覆盖 .env）
            model: 使用的模型（覆盖 .env）
            max_length: 输出最大字符数
            validate: 是否启用防幻觉验证
        """
        self._max_length = max_length
        self._validate = validate
        self._client: Optional[Any] = None
        self._config: Optional[LLMConfig] = None

        # 优先用 .env 工厂
        if api_key is None:
            self._client, self._config = create_client()
            if self._client is not None:
                logger.info("✅ ReasonPolisher 使用 LLM 工厂 (provider=%s, model=%s)",
                            self._config.provider, self._config.model_name)
                return
            else:
                logger.info("LLM 未配置（无 .env 或 API key），启用 fallback 模式")
                return

        # 回退到显式 api_key + Anthropic
        self._api_key = api_key
        self._model = model
        try:
            from anthropic import Anthropic
            self._client = Anthropic(api_key=api_key)
            logger.info("✅ ReasonPolisher 初始化成功（Anthropic 显式 key，模型: %s）", model)
        except ImportError:
            logger.warning("anthropic 库未安装，回退到原文模式")
        except Exception as e:
            logger.warning("Anthropic 客户端初始化失败: %s", e)
            self._client = None

    @property
    def is_available(self) -> bool:
        """LLM 是否可用。"""
        return self._client is not None

    @property
    def provider(self) -> Optional[str]:
        """当前 LLM provider（如已配置）。"""
        if self._config:
            return self._config.provider
        return "anthropic" if self._client else None

    @property
    def model_name(self) -> Optional[str]:
        """当前模型名称。"""
        if self._config:
            return self._config.model_name
        return getattr(self, "_model", None)

    def polish(
        self,
        raw_text: str,
        context: Optional[Dict[str, Any]] = None,
        max_length: Optional[int] = None,
        slot: Optional[Any] = None,
    ) -> PolishResult:
        """润色单段文本。

        Args:
            raw_text: 原始叙述（来自 Excel）
            context: 上下文数据（可选，仅用于参考格式）
            max_length: 覆盖默认的最大长度
            slot: PolishedSlot 实例（可选，用于智能 few-shot 选择）

        Returns:
            PolishResult
        """
        max_len = max_length or self._max_length
        context = context or {}

        # 1. 输入校验
        if not raw_text or not raw_text.strip():
            return PolishResult(
                raw_text=raw_text,
                polished_text="",
                is_fallback=True,
                model_used="none",
                tokens_used=0,
                validation_passed=True,
                error="空文本",
            )

        # 2. 短文本直接返回（不值得调用 LLM）
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

        # 3. LLM 不可用 → fallback
        if not self.is_available:
            return PolishResult(
                raw_text=raw_text,
                polished_text=raw_text,
                is_fallback=True,
                model_used="none",
                tokens_used=0,
                validation_passed=True,
                error="LLM 不可用",
            )

        # 4. 调用 LLM
        try:
            polished, tokens = self._call_llm(raw_text, context, max_len, slot=slot)
        except Exception as e:
            logger.error("LLM 调用失败: %s", e)
            return PolishResult(
                raw_text=raw_text,
                polished_text=raw_text,
                is_fallback=True,
                model_used=self.model_name or "unknown",
                tokens_used=0,
                validation_passed=False,
                error=str(e),
            )

        # 5. 防幻觉验证
        validation_passed = True
        if self._validate:
            validation_passed = self._validate_output(raw_text, polished)
            if not validation_passed:
                logger.warning(
                    "润色输出未通过验证（可能 LLM 改动了数字/事实），回退到原文"
                )
                polished = raw_text

        return PolishResult(
            raw_text=raw_text,
            polished_text=polished,
            is_fallback=False,
            model_used=self.model_name or "unknown",
            tokens_used=tokens,
            validation_passed=validation_passed,
            error=None,
        )

    def polish_batch(
        self,
        raw_texts: Dict[str, str],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, PolishResult]:
        """批量润色。

        Args:
            raw_texts: {slot_id: raw_text} 字典
            context: 共享上下文

        Returns:
            {slot_id: PolishResult} 字典
        """
        return {
            slot_id: self.polish(text, context=context)
            for slot_id, text in raw_texts.items()
        }

    # ========================================================================
    # 内部方法
    # ========================================================================

    def _call_llm(
        self,
        raw_text: str,
        context: Dict[str, Any],
        max_length: int,
        slot: Optional[Any] = None,
    ) -> Tuple[str, int]:
        """调用 LLM（通过统一工厂，支持 Anthropic/Qwen/OpenAI/DeepSeek）。

        Args:
            raw_text: 原始文本
            context: 上下文数据
            max_length: 最大长度
            slot: PolishedSlot 实例（可选，用于智能 few-shot 选择）
        """
        assert self._client is not None

        # 构建上下文提示（不强制 LLM 用，仅作参考）
        context_hint = ""
        if context:
            context_hint = json.dumps(context, ensure_ascii=False, indent=1)[:500]

        user_prompt = POLISH_USER_TEMPLATE.format(
            raw_text=raw_text,
            context_hint=context_hint or "（无）",
        )

        # Phase 3: 智能 few-shot 注入（如果提供了 slot）
        if slot is not None:
            try:
                from streamlit_app.core.few_shot_engine import inject_few_shot_into_system
                system_with_examples = inject_few_shot_into_system(
                    POLISH_SYSTEM_PROMPT, slot, top_k=2
                )
                logger.debug("Smart few-shot injected for slot %s", getattr(slot, 'slot_id', '?'))
            except ImportError:
                logger.warning("few_shot_engine not available, falling back to hardcoded examples")
                system_with_examples = self._build_fallback_few_shot()
        else:
            # 降级：使用硬编码示例
            system_with_examples = self._build_fallback_few_shot()

        # 使用统一接口（支持所有 provider）
        response = call_llm(
            prompt=user_prompt,
            system=system_with_examples,
            max_tokens=max_length * 2,  # 中文 1 字 ≈ 2 token
            temperature=0.3,
        )

        if response is None:
            raise RuntimeError("LLM 调用失败")

        content_text = response.content
        tokens = response.input_tokens + response.output_tokens

        # 解析 JSON 输出
        try:
            data = json.loads(content_text)
            polished = data.get("polished_text", content_text)
        except json.JSONDecodeError:
            # 兜底：尝试从文本中提取
            polished = self._extract_polished_from_text(content_text)

        return polished, tokens

    def _build_fallback_few_shot(self) -> str:
        """构建降级 few-shot（硬编码示例）。

        当 few_shot_engine 不可用或未提供 slot 时使用。
        """
        few_shot_text = "\n\n".join(
            f"【示例 {i+1}】\n原始：{ex['raw']}\n改写：{ex['polished']}"
            for i, ex in enumerate(FEW_SHOT_EXAMPLES)
        )
        return POLISH_SYSTEM_PROMPT + "\n\n【改写示例】\n" + few_shot_text

    @staticmethod
    def _extract_polished_from_text(text: str) -> str:
        """从非 JSON 输出中提取 polished_text。"""
        # 尝试找 "polished_text" 字段
        match = re.search(r'"polished_text"\s*:\s*"([^"]+)"', text)
        if match:
            return match.group(1)
        # 兜底：返回原文清理后版本
        return text.strip()

    def _validate_output(self, raw: str, polished: str) -> bool:
        """验证润色输出（防幻觉）。

        规则：
        1. polished 中的所有数字必须出现在 raw 中
        2. polished 中不能出现明显的"推测"措辞
        3. polished 长度不能比 raw 长太多（避免 LLM 注水）
        """
        # 1. 数字验证
        raw_numbers = set(re.findall(r"\d+\.?\d*", raw))
        polished_numbers = set(re.findall(r"\d+\.?\d*", polished))

        # 忽略 0/1 这种通用数字
        ignore = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}
        raw_significant = raw_numbers - ignore
        polished_significant = polished_numbers - ignore

        if polished_significant - raw_significant:
            logger.debug(
                "数字不一致 - raw: %s, polished: %s, 新增: %s",
                raw_significant, polished_significant,
                polished_significant - raw_significant,
            )
            return False

        # 2. 推测措辞检查
        forbidden = ["预计将", "据预测", "有望", "可能会", "或将", "可能将"]
        for word in forbidden:
            if word in polished:
                logger.debug("发现禁止措辞: %s", word)
                return False

        # 3. 长度检查（polished 不应超过 raw 1.8 倍）
        if len(polished) > len(raw) * 1.8:
            logger.debug("polished 过长 (raw=%d, polished=%d)", len(raw), len(polished))
            return False

        return True


# ============================================================================
# 便利函数
# ============================================================================

def polish_reason(raw_text: str, **kwargs: Any) -> str:
    """便利函数：润色单个文本并返回字符串。

    Args:
        raw_text: 原始文本
        **kwargs: 透传到 ReasonPolisher

    Returns:
        润色后的文本（fallback 时返回原文）
    """
    polisher = ReasonPolisher(**{k: v for k, v in kwargs.items() if k in {"api_key", "model", "max_length", "validate"}})
    return polisher.polish(raw_text).polished_text


# ============================================================================
# 命令行入口
# ============================================================================

def main() -> None:
    """命令行入口：演示润色效果。"""
    import argparse

    parser = argparse.ArgumentParser(description="原因文本润色器")
    parser.add_argument("--text", required=True, help="要润色的原始文本")
    parser.add_argument("--context", help="上下文 JSON 字符串")
    parser.add_argument("--show-raw", action="store_true", help="同时显示原文")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    context = None
    if args.context:
        context = json.loads(args.context)

    polisher = ReasonPolisher()
    result = polisher.polish(args.text, context=context)

    print("=" * 60)
    if args.show_raw:
        print(f"【原文】\n{result.raw_text}\n")
    print(f"【润色】\n{result.polished_text}\n")
    print("=" * 60)
    print(f"模型: {result.model_used}")
    print(f"Fallback: {'是' if result.is_fallback else '否'}")
    print(f"Tokens: {result.tokens_used}")
    print(f"验证: {'✅ 通过' if result.validation_passed else '❌ 失败'}")
    if result.error:
        print(f"错误: {result.error}")


if __name__ == "__main__":
    main()
