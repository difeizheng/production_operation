"""原因解析器 - 把 reason_map + collector + polisher 整合为一个 {placeholder: text} 字典

设计原则：
    1. 单一职责：只负责"占位符 → 最终文本"的解析
    2. 优雅降级：任何环节失败都用 fallback_text
    3. 可缓存：同一份 Excel 一次性采集，批量解析
    4. 可观测：返回元数据（来源、是否润色、token消耗）

工作流：
    reason_map.json
        ↓ (加载映射)
    ReasonCollector.collect(summary_file)
        ↓ (提取所有 slot 文本)
    ReasonPolisher.polish(...)
        ↓ (LLM 润色)
    {placeholder: final_text}
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.collector.reason_collector import (
    ALL_REASON_SLOTS,
    ReasonCollector,
    ReasonResult,
    ReasonSlot,
)
from src.generator.reason_polisher import PolishResult, ReasonPolisher
from src.generator.grounded_generator import GroundedReasonGenerator, GroundedResult

logger = logging.getLogger(__name__)


# ============================================================================
# 默认 reason_map 路径
# ============================================================================

DEFAULT_REASON_MAP_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "dictionaries" / "reason_map.json"


# ============================================================================
# 数据类
# ============================================================================

@dataclass(frozen=True)
class ResolvedSegment:
    """单个占位符的解析结果。"""
    placeholder: str           # 占位符
    final_text: str            # 最终文本
    automation_level: str      # HIGH / MEDIUM / MANUAL
    source_slots: List[str]    # 来源槽位
    raw_text: str              # 原始文本
    polished: bool             # 是否经过 LLM 润色
    is_fallback: bool          # 是否用了 fallback
    tokens_used: int = 0       # 消耗 token
    error: Optional[str] = None


# ============================================================================
# 核心类
# ============================================================================

class ReasonResolver:
    """原因解析器：把 reason_map.json + Excel + LLM 整合为最终文本。"""

    def __init__(
        self,
        reason_map: Optional[Dict[str, Any]] = None,
        reason_map_path: Optional[Path] = None,
        collector: Optional[ReasonCollector] = None,
        polisher: Optional[ReasonPolisher] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初始化。

        Args:
            reason_map: 直接传入映射字典（优先）
            reason_map_path: 映射文件路径（reason_map 为 None 时使用）
            collector: 自定义 ReasonCollector
            polisher: 自定义 ReasonPolisher
            data: AnalysisCollector 的输出（用于 grounded_category 模式）
        """
        if reason_map is not None:
            self.reason_map = reason_map
        elif reason_map_path is not None:
            with open(reason_map_path, "r", encoding="utf-8") as f:
                self.reason_map = json.load(f)
        else:
            with open(DEFAULT_REASON_MAP_PATH, "r", encoding="utf-8") as f:
                self.reason_map = json.load(f)

        self.collector = collector or ReasonCollector()
        self.polisher = polisher or ReasonPolisher()
        self._data = data  # 用于 grounded_category 模式
        self._grounded_generator = GroundedReasonGenerator()

        logger.info(
            "ReasonResolver 初始化完成: %d 个映射, LLM %s",
            self.reason_map.get("total_mappings", 0),
            "可用" if self.polisher.is_available else "不可用（fallback 模式）",
        )

    @property
    def mappings(self) -> List[Dict[str, Any]]:
        return self.reason_map.get("mappings", [])

    def resolve_all(
        self,
        summary_file: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, ResolvedSegment]:
        """解析所有占位符。

        Args:
            summary_file: 汇总表.xlsx 路径（用于提取原因文本）
                          传 None 时只处理 fallback 段落
            data: AnalysisCollector 输出（用于 grounded_category 模式）

        Returns:
            {placeholder: ResolvedSegment} 字典
        """
        # 优先使用传入的 data，其次用 self._data
        if data is None:
            data = self._data
        # 1. 一次性提取所有需要的 slot
        slot_results: Dict[str, ReasonResult] = {}
        if summary_file:
            all_slot_ids = set()
            for m in self.mappings:
                all_slot_ids.update(m.get("source_slots", []))

            if all_slot_ids:
                # 总是使用注入的 collector（保证可测试性 + 自定义配置）
                # 如果 collector 配置的 slots 与需要的不一致，创建临时专用 collector
                active_collector = self.collector
                collector_slot_ids = set(s.slot_id for s in active_collector.slots)
                if not all_slot_ids.issubset(collector_slot_ids):
                    slots_to_collect = [
                        s for s in ALL_REASON_SLOTS if s.slot_id in all_slot_ids
                    ]
                    active_collector = ReasonCollector(slots=slots_to_collect)
                slot_results, _ = active_collector.collect(summary_file)
                logger.info("从 %s 提取了 %d 个槽位", Path(summary_file).name, len(slot_results))

        # 2. 解析每个 mapping
        results: Dict[str, ResolvedSegment] = {}
        for m in self.mappings:
            placeholder = m["template_placeholder"]
            generation_mode = m.get("generation_mode", "extract")
            segment = self._resolve_one(m, slot_results, data, generation_mode)
            results[placeholder] = segment

        return results

    def resolve_to_text_dict(
        self,
        summary_file: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """解析为简化的 {placeholder: text} 字典（直接用于模板渲染）。

        Args:
            summary_file: 汇总表.xlsx 路径
            data: AnalysisCollector 输出（用于 grounded_category 模式）

        Returns:
            {placeholder: text} 字典
        """
        segments = self.resolve_all(summary_file, data)
        return {ph: seg.final_text for ph, seg in segments.items()}

    # ========================================================================
    # 内部方法
    # ========================================================================

    def _resolve_one(
        self,
        mapping: Dict[str, Any],
        slot_results: Dict[str, ReasonResult],
        data: Optional[Dict[str, Any]] = None,
        generation_mode: str = "extract",
    ) -> ResolvedSegment:
        """解析单个 mapping。"""
        placeholder = mapping["template_placeholder"]
        source_slots = mapping.get("source_slots", [])
        automation_level = mapping.get("automation_level", "MANUAL")
        polish_required = mapping.get("polish_required", False)
        fallback_text = mapping.get("fallback_text", "")

        # === 特殊模式: grounded_category（数据驱动 LLM 生成） ===
        if generation_mode == "grounded_category":
            return self._resolve_grounded_category(
                mapping, data or self._data, fallback_text,
            )

        # === 默认模式: extract（从 slot 提取） ===
        # 1. 从 source_slots 收集原始文本
        collected_texts: List[str] = []
        for slot_id in source_slots:
            if slot_id in slot_results:
                result = slot_results[slot_id]
                if not result.is_empty and result.raw_text:
                    collected_texts.append(result.raw_text)

        raw_text = "\n\n".join(collected_texts) if collected_texts else ""
        is_fallback = not raw_text.strip()
        final_text = ""
        polished = False
        tokens_used = 0
        error: Optional[str] = None

        # 2. 决定使用 raw_text 还是 fallback
        if is_fallback:
            # 走 fallback
            final_text = fallback_text or ""  # 兜底 None → ""
            logger.debug("占位符 %s 走 fallback", placeholder)
        else:
            # 3. 可选 LLM 润色
            if polish_required and self.polisher.is_available:
                polish_result = self.polisher.polish(raw_text)
                final_text = polish_result.polished_text
                polished = not polish_result.is_fallback
                tokens_used = polish_result.tokens_used
                if not polish_result.validation_passed:
                    error = "验证未通过，已回退到原文"
            else:
                final_text = raw_text
                if polish_required and not self.polisher.is_available:
                    logger.debug(
                        "占位符 %s 需要润色但 LLM 不可用，使用原文",
                        placeholder,
                    )

        return ResolvedSegment(
            placeholder=placeholder,
            final_text=final_text,
            automation_level=automation_level,
            source_slots=source_slots,
            raw_text=raw_text,
            polished=polished,
            is_fallback=is_fallback,
            tokens_used=tokens_used,
            error=error,
        )

    def _resolve_grounded_category(
        self,
        mapping: Dict[str, Any],
        data: Optional[Dict[str, Any]],
        fallback_text: str,
    ) -> ResolvedSegment:
        """数据驱动的品类级原因生成。"""
        placeholder = mapping["template_placeholder"]
        automation_level = mapping.get("automation_level", "HIGH")
        context = mapping.get("context", {})

        # 1. 提取品类信息
        category = context.get("category", "")
        metric = context.get("metric", "price_change_wow")

        if not category or data is None:
            return ResolvedSegment(
                placeholder=placeholder,
                final_text=fallback_text or "",
                automation_level="MANUAL",
                source_slots=[],
                raw_text="",
                polished=False,
                is_fallback=True,
                tokens_used=0,
                error="缺少 category 或 data",
            )

        # 2. 调用 GroundedGenerator
        result: GroundedResult = self._grounded_generator.generate_category_reason(
            data=data, category=category, metric=metric,
        )

        if result.is_fallback or not result.validation_passed:
            return ResolvedSegment(
                placeholder=placeholder,
                final_text=fallback_text or result.text or "",
                automation_level="MANUAL",
                source_slots=[],
                raw_text=result.text or "",
                polished=False,
                is_fallback=True,
                tokens_used=result.tokens_used,
                error=result.error or "数据生成失败，使用 fallback",
            )

        return ResolvedSegment(
            placeholder=placeholder,
            final_text=result.text,
            automation_level=automation_level,
            source_slots=[],
            raw_text=result.text,
            polished=True,
            is_fallback=False,
            tokens_used=result.tokens_used,
            error=None,
        )

    def get_stats(self, segments: Dict[str, ResolvedSegment]) -> Dict[str, Any]:
        """统计解析结果。"""
        total = len(segments)
        by_level: Dict[str, int] = {}
        by_polished = 0
        by_fallback = 0
        total_tokens = 0

        for seg in segments.values():
            by_level[seg.automation_level] = by_level.get(seg.automation_level, 0) + 1
            if seg.polished:
                by_polished += 1
            if seg.is_fallback:
                by_fallback += 1
            total_tokens += seg.tokens_used

        return {
            "total": total,
            "by_level": by_level,
            "polished_count": by_polished,
            "fallback_count": by_fallback,
            "total_tokens": total_tokens,
            "automation_rate": (
                (by_level.get("HIGH", 0) + by_level.get("MEDIUM", 0)) / total
                if total > 0 else 0.0
            ),
        }


# ============================================================================
# 便利函数
# ============================================================================

def load_reason_map(path: Optional[Path] = None) -> Dict[str, Any]:
    """加载 reason_map.json。"""
    path = path or DEFAULT_REASON_MAP_PATH
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def quick_resolve(
    summary_file: str,
    reason_map_path: Optional[Path] = None,
    use_llm: bool = True,
) -> Dict[str, str]:
    """便利函数：从 Excel 快速解析为 {placeholder: text} 字典。

    Args:
        summary_file: 汇总表路径
        reason_map_path: 映射文件路径
        use_llm: 是否使用 LLM 润色

    Returns:
        {placeholder: text} 字典
    """
    polisher = ReasonPolisher() if use_llm else None
    resolver = ReasonResolver(
        reason_map_path=reason_map_path,
        polisher=polisher,
    )
    return resolver.resolve_to_text_dict(summary_file)


# ============================================================================
# CLI 入口
# ============================================================================

def main() -> None:
    """命令行入口：演示解析过程。"""
    import argparse

    parser = argparse.ArgumentParser(description="原因解析器")
    parser.add_argument("--summary", "-s", help="汇总表.xlsx 路径")
    parser.add_argument("--map", "-m", help="reason_map.json 路径")
    parser.add_argument("--placeholder", help="只显示指定占位符")
    parser.add_argument("--no-llm", action="store_true", help="禁用 LLM 润色")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    polisher = None if args.no_llm else ReasonPolisher()
    resolver = ReasonResolver(
        reason_map_path=Path(args.map) if args.map else None,
        polisher=polisher,
    )

    segments = resolver.resolve_all(args.summary)

    if args.placeholder:
        seg = segments.get(args.placeholder)
        if seg is None:
            print(f"❌ 占位符不存在: {args.placeholder}")
            return
        segments = {args.placeholder: seg}

    print("\n" + "=" * 70)
    print("解析结果")
    print("=" * 70)

    for ph, seg in segments.items():
        marker = "📝" if seg.polished else ("🔄" if seg.is_fallback else "📄")
        print(f"\n{marker} {ph}")
        print(f"  等级: {seg.automation_level}")
        print(f"  槽位: {seg.source_slots}")
        print(f"  润色: {'是' if seg.polished else '否'}, "
              f"Fallback: {'是' if seg.is_fallback else '否'}, "
              f"Tokens: {seg.tokens_used}")
        if seg.error:
            print(f"  ⚠️  {seg.error}")
        preview = seg.final_text.replace("\n", " ⏎ ")[:200]
        print(f"  文本: {preview}...")

    # 统计
    stats = resolver.get_stats(segments)
    print("\n" + "=" * 70)
    print("统计")
    print("=" * 70)
    print(f"  总数: {stats['total']}")
    print(f"  按等级: {stats['by_level']}")
    print(f"  润色数: {stats['polished_count']}")
    print(f"  Fallback 数: {stats['fallback_count']}")
    print(f"  总 Token: {stats['total_tokens']}")
    print(f"  自动化率: {stats['automation_rate']:.0%}")


if __name__ == "__main__":
    main()
