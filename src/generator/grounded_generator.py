"""数据基础的原因生成器 - 用 LLM 把结构化数据转化为"原因叙述"文本

设计原则：
    1. 数据是事实，文本是表达：所有数字必须来自数据
    2. 防幻觉：所有输出数字必须出现在输入数据中
    3. 品类级：水电/风电/光伏/火电 各品类的电价变化原因
    4. 上下文感知：参考 V4 真实范文风格

使用场景：
    - V4 段落 P13-P16（4 个品类级环比原因）
    - 任何需要从数据生成自然语言解释的场景
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.utils.llm_factory import call_llm, is_configured

logger = logging.getLogger(__name__)


# ============================================================================
# 数据类
# ============================================================================

@dataclass(frozen=True)
class GroundedResult:
    """数据基础生成结果。"""
    text: str
    is_fallback: bool       # True = 没生成（数据不足或 LLM 不可用）
    model_used: str
    tokens_used: int
    numbers_in_output: List[str] = field(default_factory=list)
    numbers_in_input: List[str] = field(default_factory=list)
    validation_passed: bool = False
    error: Optional[str] = None


# ============================================================================
# Prompt 模板
# ============================================================================

GROUNDED_SYSTEM_PROMPT = """你是能源行业（电力营销）资深周报撰写专家。

【核心原则】
- 所有数字必须**严格基于**用户提供的"数据"部分
- 不得编造任何数据、电站名称、流域名称
- 如数据不足以解释，可以写"具体原因待人工补充"
- 保持正式、专业的语言风格

【输出格式】
- 段落开头必须点明品类（如"水电"、"风电"）
- 数字保留原始精度（如"下降0.4分"而非"下降约0.4分"）
- 100-200 字
- 严格 JSON 输出

【JSON 结构】
{
  "text": "完整段落文本",
  "key_facts": ["使用到的关键事实 1", "事实 2", ...]
}
"""

GROUNDED_CATEGORY_PROMPT = """请根据以下"数据"撰写"【{category_name}】电价环比变化的原因"段落。

【数据】（所有数字必须来自这里，**不得修改或编造**）
{data_block}

【参考范文】（学习风格，**不要复制其数字**）
【水电电价环比下降的原因】（水电电价环比下降每千瓦时0.4分，主要原因是电价较高的金下梯级电站电量在大水电中占比下降10个百分点，抽蓄电站电量在水电中占比下降0.2个百分点。）

【要求】
1. 段落开头点明品类
2. 用"主要原因"或"主因"等措辞
3. 数字保留原始精度
4. 解释"为什么"变化（不只是"变化了多少"）
5. 100-200 字

【输出 JSON】
{{
  "text": "...",
  "key_facts": ["..."]
}}
"""


# ============================================================================
# 数据提取器
# ============================================================================

CATEGORY_KEYS = {
    "hydro": {"name": "水电", "col": "C"},
    "new_energy": {"name": "新能源", "col": "D"},
    "wind": {"name": "风电", "col": "E"},
    "solar": {"name": "光伏", "col": "F"},
    "thermal": {"name": "火电", "col": "G"},
}


def build_category_data_block(
    data: Dict[str, Any],
    category: str,
    metric: str = "price_change_wow",
) -> str:
    """从综合分析表数据构建品类数据块。

    Args:
        data: AnalysisCollector.collect() 的输出
        category: 品类 key（hydro/wind/solar/thermal）
        metric: 关注的指标（默认 price_change_wow）

    Returns:
        格式化的多行数据文本
    """
    cat_name = CATEGORY_KEYS.get(category, {}).get("name", category)

    # 从 data 字典提取相关数字
    fields = {
        "本周电量(亿千瓦时)": data.get(f"report.electricity.{category}"),
        "电量环比(%)": data.get(f"report.wow_electricity.{category}"),
        "电量同比(%)": data.get(f"report.yoy_electricity.{category}"),
        "本周电价(元/千瓦时)": data.get(f"report.price.{category}"),
        "电价环比(分)": (data.get(f"report.wow_price.{category}") or 0) * 100,
        "电价同比(分)": (data.get(f"report.yoy_price.{category}") or 0) * 100,
        "本周电费(亿元)": data.get(f"report.revenue.{category}"),
        "收入环比(%)": data.get(f"report.wow_revenue.{category}"),
        "收入同比(%)": data.get(f"report.yoy_revenue.{category}"),
    }

    lines = [f"品类: {cat_name}"]
    for label, value in fields.items():
        if value is None:
            lines.append(f"  {label}: （无数据）")
            continue
        if not isinstance(value, (int, float)):
            lines.append(f"  {label}: {value}")
            continue
        # 按字段类型格式化
        if "电量(亿千瓦时)" in label:
            lines.append(f"  {label}: {value:.2f}")
        elif "电费(亿元)" in label:
            lines.append(f"  {label}: {value:.2f}")
        elif "电价(元/千瓦时)" in label:
            lines.append(f"  {label}: {value:.3f}")
        elif "(分)" in label:
            lines.append(f"  {label}: {value:.2f}")
        elif "(%)" in label:
            # 已是比率，乘 100
            lines.append(f"  {label}: {value * 100:.1f}%")
        else:
            lines.append(f"  {label}: {value:.4f}")

    return "\n".join(lines)


# ============================================================================
# 核心类
# ============================================================================

class GroundedReasonGenerator:
    """数据基础的原因生成器。"""

    def __init__(self, use_llm: bool = True) -> None:
        """初始化。

        Args:
            use_llm: 是否使用 LLM（False 时只返回数据块本身）
        """
        self._use_llm = use_llm and is_configured()
        if use_llm and not is_configured():
            logger.info("LLM 未配置，GroundedGenerator 将返回数据块")

    @property
    def is_available(self) -> bool:
        return self._use_llm

    def generate_category_reason(
        self,
        data: Dict[str, Any],
        category: str,
        metric: str = "price_change_wow",
    ) -> GroundedResult:
        """生成品类级原因文本。

        Args:
            data: AnalysisCollector 输出
            category: 品类（hydro/wind/solar/thermal）
            metric: 指标

        Returns:
            GroundedResult
        """
        cat_name = CATEGORY_KEYS.get(category, {}).get("name", category)
        data_block = build_category_data_block(data, category, metric)
        input_numbers = re.findall(r"-?\d+\.?\d*", data_block)

        # 1. 无 LLM → 返回数据块本身
        if not self._use_llm:
            return GroundedResult(
                text=data_block,
                is_fallback=True,
                model_used="none",
                tokens_used=0,
                numbers_in_input=input_numbers,
                numbers_in_output=input_numbers,
                validation_passed=True,
                error="LLM 未配置",
            )

        # 2. 调用 LLM
        try:
            user_prompt = GROUNDED_CATEGORY_PROMPT.format(
                category_name=cat_name,
                data_block=data_block,
            )
            response = call_llm(
                prompt=user_prompt,
                system=GROUNDED_SYSTEM_PROMPT,
                max_tokens=400,
                temperature=0.3,
            )
        except Exception as e:
            logger.error("LLM 调用失败: %s", e)
            return GroundedResult(
                text="",
                is_fallback=True,
                model_used="error",
                tokens_used=0,
                numbers_in_input=input_numbers,
                validation_passed=False,
                error=str(e),
            )

        if response is None:
            return GroundedResult(
                text="",
                is_fallback=True,
                model_used="none",
                tokens_used=0,
                numbers_in_input=input_numbers,
                validation_passed=False,
                error="LLM 未返回",
            )

        # 3. 解析 JSON
        try:
            data_obj = json.loads(response.content)
            text = data_obj.get("text", "")
        except json.JSONDecodeError:
            # 尝试从 markdown 中提取
            text = self._extract_from_markdown(response.content)

        # 4. 验证：输出数字必须都在输入中
        output_numbers = re.findall(r"-?\d+\.?\d*", text)
        validation_passed = self._validate_numbers(input_numbers, output_numbers)

        if not validation_passed:
            logger.warning(
                "Grounded 生成未通过验证（数字不一致），回退到数据块\n"
                "  输入: %s\n  输出: %s",
                input_numbers, output_numbers,
            )
            text = f"【{cat_name}】数据：\n{data_block}"

        return GroundedResult(
            text=text,
            is_fallback=False,
            model_used=response.model,
            tokens_used=response.input_tokens + response.output_tokens,
            numbers_in_output=output_numbers,
            numbers_in_input=input_numbers,
            validation_passed=validation_passed,
        )

    @staticmethod
    def _validate_numbers(input_numbers: List[str], output_numbers: List[str]) -> bool:
        """验证输出数字都在输入中。

        容忍：通用数字（0,1,2,3,4,5）和小数精度差异。
        """
        if not output_numbers:
            return True  # 空文本（无数字）算通过

        # 提取"显著"数字（不是 0-9 的单个数字）
        input_significant = {n for n in input_numbers if len(n) >= 2 or "." in n}
        output_significant = {n for n in output_numbers if len(n) >= 2 or "." in n}

        # 输出数字必须是输入的子集（容忍 ±0.01 误差）
        for on in output_significant:
            if on in input_significant:
                continue
            try:
                on_f = float(on)
                if any(abs(on_f - float(inum)) < 0.011 for inum in input_significant):
                    continue
            except ValueError:
                pass
            return False

        return True

    @staticmethod
    def _extract_from_markdown(text: str) -> str:
        """从 markdown 文本中提取 text 字段。"""
        match = re.search(r'"text"\s*:\s*"([^"]+)"', text)
        if match:
            return match.group(1)
        return text.strip()


# ============================================================================
# 便利函数
# ============================================================================

def generate_category_text(
    data: Dict[str, Any],
    category: str,
    use_llm: bool = True,
) -> str:
    """便利函数：生成品类原因文本。"""
    generator = GroundedReasonGenerator(use_llm=use_llm)
    return generator.generate_category_reason(data, category).text
