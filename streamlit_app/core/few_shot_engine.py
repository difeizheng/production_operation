"""Few-shot 自动注入引擎 - 根据段位特征智能选择最佳示例

设计原则：
    1. 从段位元数据（generation_mode, automation_level, category）提取特征
    2. 示例库按特征分类，匹配最相似的 2-3 个示例
    3. 降级策略：无匹配时回退到通用示例
    4. 纯函数设计，方便单测

使用：
    from streamlit_app.core.few_shot_engine import select_few_shot_examples
    examples = select_few_shot_examples(slot)
    # 注入到 ReasonPolisher._call_llm()
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# 数据类
# ============================================================================

@dataclass(frozen=True)
class FewShotExample:
    """单个 few-shot 示例。

    Attributes:
        example_id: 示例 ID
        category: 类别（domestic/international/market/environmental/general）
        generation_mode: 生成模式（extract/grounded_category/fallback）
        raw_text: 原始文本
        polished_text: 润色后文本
        tags: 标签列表（用于匹配）
        quality_score: 质量分（0-100，用于排序）
    """
    example_id: str
    category: str
    generation_mode: str
    raw_text: str
    polished_text: str
    tags: Tuple[str, ...]
    quality_score: int = 100


# ============================================================================
# 示例库（内置 + 可扩展）
# ============================================================================

# 内置示例库（按类别分类）
BUILTIN_EXAMPLES: Dict[str, List[FewShotExample]] = {
    "domestic": [
        FewShotExample(
            example_id="dom_001",
            category="domestic",
            generation_mode="extract",
            raw_text="1、全集团电量同比增加，主要原因为乌东德电站及白鹤滩电站来水偏丰。2、全集团电价同比降低，主要原因为电源结构变化，广东省2026年度合约电价同比降低。",
            polished_text="1、全集团上网电量同比增加，主要受乌东德、白鹤滩电站来水偏丰拉动，水电发电能力同比提升；2、全集团上网电价同比下降，主要受电源结构变化及广东省2026年度合约电价同比下行影响。",
            tags=("电量", "电价", "同比", "来水偏丰", "电源结构"),
            quality_score=95,
        ),
        FewShotExample(
            example_id="dom_002",
            category="domestic",
            generation_mode="extract",
            raw_text="1、全集团电量环比增加，主要原因为乌东德电站及白鹤滩电站来水偏丰，集团外送电计划增加。2、全集团电价环比降低，主要原因是电源结构变化。",
            polished_text="1、全集团上网电量环比增加，主因乌东德、白鹤滩流域来水偏丰叠加集团外送电计划释放；2、全集团上网电价环比下降，主因电源结构变化导致均价较低的水电、清洁能源占比提升。",
            tags=("电量", "电价", "环比", "来水偏丰", "外送电"),
            quality_score=92,
        ),
    ],
    "international": [
        FewShotExample(
            example_id="intl_001",
            category="international",
            generation_mode="extract",
            raw_text="1、巴基斯坦项目电价同比上涨5%，主因当地电力市场需求增长。2、巴西项目电价环比下降3%，受汇率波动影响。",
            polished_text="1、巴基斯坦项目上网电价同比上涨5%，主因当地电力市场需求持续增长叠加供需缺口扩大；2、巴西项目上网电价环比下降3%，主受雷亚尔汇率波动及当地电力市场供需宽松影响。",
            tags=("国际", "电价", "同比", "环比", "汇率"),
            quality_score=90,
        ),
    ],
    "market": [
        FewShotExample(
            example_id="mkt_001",
            category="market",
            generation_mode="extract",
            raw_text="1、水电市场化交易电量占比35%，同比提升5个百分点。2、现货市场均价0.35元/度，高于长协均价。",
            polished_text="1、水电市场化交易电量占比达35%，同比提升5个百分点，市场化改革持续推进；2、现货市场均价0.35元/度，较长协均价溢价约8%，现货市场景气度回升。",
            tags=("市场化", "现货", "长协", "交易电量"),
            quality_score=88,
        ),
    ],
    "environmental": [
        FewShotExample(
            example_id="env_001",
            category="environmental",
            generation_mode="extract",
            raw_text="1、绿证交易收入500万元，同比增长20%。2、CCER项目备案3个，预计年减排量10万吨。",
            polished_text="1、绿证交易收入500万元，同比增长20%，环境资产价值持续兑现；2、CCER项目新增备案3个，预计年均减排量10万吨CO₂当量，碳资产储备稳步扩张。",
            tags=("绿证", "CCER", "环境资产", "碳资产"),
            quality_score=85,
        ),
    ],
    "general": [
        FewShotExample(
            example_id="gen_001",
            category="general",
            generation_mode="fallback",
            raw_text="本周整体运营平稳，无重大异常。",
            polished_text="本周集团整体运营平稳有序，各业务板块协同推进，无重大异常事项。",
            tags=("通用", "平稳", "运营"),
            quality_score=80,
        ),
    ],
}


# ============================================================================
# 特征提取
# ============================================================================

def extract_slot_features(slot: Any) -> Dict[str, Any]:
    """从段位提取特征（用于匹配示例）。

    Args:
        slot: PolishedSlot 实例

    Returns:
        {category, generation_mode, automation_level, tags}
    """
    # 1. 类别推断（从 slot_id 或 placeholder）
    slot_id = getattr(slot, "slot_id", "") or ""
    placeholder = getattr(slot, "placeholder", "") or ""
    combined = f"{slot_id} {placeholder}".lower()

    if any(kw in combined for kw in ("dom", "domestic", "国内", "电量", "电价")):
        category = "domestic"
    elif any(kw in combined for kw in ("intl", "international", "国际", "海外", "巴基斯坦", "巴西")):
        category = "international"
    elif any(kw in combined for kw in ("market", "市场化", "现货", "长协")):
        category = "market"
    elif any(kw in combined for kw in ("env", "environmental", "绿证", "ccer", "碳")):
        category = "environmental"
    else:
        category = "general"

    # 2. 生成模式
    generation_mode = getattr(slot, "generation_mode", "extract") or "extract"

    # 3. 自动化等级
    automation_level = getattr(slot, "automation_level", "MANUAL") or "MANUAL"

    # 4. 文本标签（从 raw_text 提取关键词）
    raw_text = getattr(slot, "raw_text", "") or ""
    tags = _extract_text_tags(raw_text)

    return {
        "category": category,
        "generation_mode": generation_mode,
        "automation_level": automation_level,
        "tags": tags,
    }


def _extract_text_tags(text: str, top_k: int = 5) -> Tuple[str, ...]:
    """从文本提取关键词标签（简单规则）。

    策略：匹配行业术语词典中的关键词。
    """
    if not text:
        return ()

    # 行业关键词（可扩展）
    KEYWORDS = (
        "电量", "电价", "电费", "同比", "环比", "市场化", "现货", "长协",
        "来水", "偏丰", "偏枯", "电源结构", "水电", "火电", "风电", "光伏",
        "绿证", "CCER", "碳", "减排", "利用小时", "发电量", "上网",
        "合约", "交易", "均价", "外送", "国际", "海外",
    )

    matched = [kw for kw in KEYWORDS if kw in text]
    return tuple(matched[:top_k])


# ============================================================================
# 示例匹配
# ============================================================================

def compute_example_similarity(
    slot_features: Dict[str, Any],
    example: FewShotExample,
) -> float:
    """计算段位特征与示例的相似度（0-1）。

    权重：
        - category 匹配: 0.5
        - generation_mode 匹配: 0.3
        - 标签重叠: 0.2
    """
    score = 0.0

    # 1. 类别匹配（0.5）
    if slot_features["category"] == example.category:
        score += 0.5
    elif slot_features["category"] == "general" or example.category == "general":
        score += 0.2  # 部分匹配

    # 2. 生成模式匹配（0.3）
    if slot_features["generation_mode"] == example.generation_mode:
        score += 0.3

    # 3. 标签重叠（0.2）
    slot_tags = set(slot_features.get("tags", ()))
    example_tags = set(example.tags)
    if slot_tags and example_tags:
        overlap = len(slot_tags & example_tags) / max(len(slot_tags), len(example_tags))
        score += 0.2 * overlap

    return score


def select_few_shot_examples(
    slot: Any,
    top_k: int = 2,
    min_similarity: float = 0.3,
) -> List[FewShotExample]:
    """为段位选择最佳 few-shot 示例。

    Args:
        slot: PolishedSlot 实例
        top_k: 返回的示例数量
        min_similarity: 最低相似度阈值

    Returns:
        排序后的示例列表（相似度降序）
    """
    # 1. 提取特征
    features = extract_slot_features(slot)
    logger.debug("Slot features: %s", features)

    # 2. 遍历所有示例，计算相似度
    all_examples: List[Tuple[float, FewShotExample]] = []
    for category_examples in BUILTIN_EXAMPLES.values():
        for example in category_examples:
            sim = compute_example_similarity(features, example)
            if sim >= min_similarity:
                all_examples.append((sim, example))

    # 3. 排序（相似度降序 → 质量分降序）
    all_examples.sort(key=lambda x: (x[0], x[1].quality_score), reverse=True)

    # 4. 返回 top_k
    selected = [ex for _, ex in all_examples[:top_k]]

    # 5. 降级：无匹配时返回通用示例
    if not selected:
        logger.warning("No few-shot examples matched for slot, using fallback")
        selected = BUILTIN_EXAMPLES.get("general", [])[:top_k]

    logger.info(
        "Selected %d few-shot examples for slot %s (category=%s)",
        len(selected), getattr(slot, "slot_id", "?"), features["category"],
    )
    return selected


# ============================================================================
# Prompt 构建
# ============================================================================

def format_few_shot_examples(examples: List[FewShotExample]) -> str:
    """将示例列表格式化为 prompt 文本。

    Returns:
        格式化后的 few-shot 文本（可直接注入 system prompt）
    """
    if not examples:
        return ""

    lines = ["【改写示例】"]
    for i, ex in enumerate(examples, 1):
        lines.append(f"\n【示例 {i}】（类别: {ex.category}, 质量: {ex.quality_score}分）")
        lines.append(f"原始：{ex.raw_text}")
        lines.append(f"改写：{ex.polished_text}")

    return "\n".join(lines)


def inject_few_shot_into_system(
    base_system: str,
    slot: Any,
    top_k: int = 2,
) -> str:
    """将智能选择的 few-shot 示例注入 system prompt。

    Args:
        base_system: 基础 system prompt（不含示例）
        slot: PolishedSlot 实例（如果为 None，则返回原始 base_system）
        top_k: 示例数量

    Returns:
        注入示例后的完整 system prompt
    """
    # 如果 slot 为 None，直接返回原始 system（不注入 few-shot）
    if slot is None:
        return base_system

    examples = select_few_shot_examples(slot, top_k=top_k)
    few_shot_text = format_few_shot_examples(examples)

    if not few_shot_text:
        return base_system

    return base_system + "\n\n" + few_shot_text
