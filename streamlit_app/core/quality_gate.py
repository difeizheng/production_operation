"""质量门禁规则 - 4 档判定 + 与 fallback 组合

设计原则：
    1. 门禁规则独立于 UI（纯函数）
    2. 与 fallback 比例组合（取更严格者）
    3. frozen dataclass + Enum 防止误修改
    4. 阈值可配置（GateConfig）

使用：
    from streamlit_app.core.quality_gate import evaluate
    result = evaluate(state)
    if not result.can_generate:
        st.error(f"门禁阻断: {result.reasons[0]}")
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from streamlit_app.core.pipeline_state import PipelineState

logger = logging.getLogger(__name__)


# ============================================================================
# 数据类
# ============================================================================

@dataclass(frozen=True)
class GateConfig:
    """门禁配置（4 档阈值 + fallback 联动阈值）。"""
    pass_threshold: int = 80
    warn_threshold: int = 60
    block_threshold: int = 40
    fallback_warn_ratio: float = 0.5
    fallback_block_ratio: float = 1.0


class GateVerdict(str, Enum):
    """4 档判定结果（继承 str 以便 JSON 序列化）。"""
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"
    CRITICAL = "critical"


@dataclass(frozen=True)
class GateResult:
    """门禁评估结果。

    Attributes:
        verdict: 4 档判定
        avg_score: 平均质量分
        fallback_ratio: fallback 段位比例
        reasons: 触发该档位的原因列表
        can_generate: 是否允许生成 Word（CRITICAL/BLOCK 必为 False，PASS/WARN 为 True）
    """
    verdict: GateVerdict
    avg_score: float
    fallback_ratio: float
    reasons: List[str]
    can_generate: bool


# ============================================================================
# 核心逻辑
# ============================================================================

def combine_with_fallback(
    quality_avg: float,
    fallback_ratio: float,
    config: Optional[GateConfig] = None,
) -> GateVerdict:
    """组合质量分 + fallback 比例 → 4 档判定（取更严格者）。

    真值表（4×4 = 16 格）：

    | quality \\ fallback | 0%      | 1-50%   | 51-99%  | 100%   |
    |---------------------|---------|---------|---------|--------|
    | >=80                | PASS    | WARN    | WARN    | WARN   |
    | 60-79               | WARN    | WARN    | BLOCK   | BLOCK  |
    | 40-59               | BLOCK   | BLOCK   | BLOCK   | CRITICAL|
    | <40                 | BLOCK   | BLOCK   | CRITICAL| CRITICAL|
    """
    cfg = config or GateConfig()

    # 按质量分初判
    if quality_avg >= cfg.pass_threshold:
        base = GateVerdict.PASS
    elif quality_avg >= cfg.warn_threshold:
        base = GateVerdict.WARN
    else:
        base = GateVerdict.BLOCK  # < 60（包含 < 40 的严重段）

    # 按 fallback 比例升级
    if fallback_ratio >= cfg.fallback_block_ratio:
        fb = GateVerdict.BLOCK  # 100% fallback
    elif fallback_ratio > cfg.fallback_warn_ratio:
        fb = GateVerdict.BLOCK  # > 50% fallback
    elif fallback_ratio > 0:
        fb = GateVerdict.WARN
    else:
        fb = GateVerdict.PASS

    # CRITICAL 特殊规则：双维度同时最差
    # (quality < 40 AND fallback > 50%) OR (fallback 100% AND quality < 60)
    is_critical = (
        (quality_avg < cfg.block_threshold and fallback_ratio > cfg.fallback_warn_ratio)
        or (fallback_ratio >= cfg.fallback_block_ratio and quality_avg < cfg.warn_threshold)
    )
    if is_critical:
        return GateVerdict.CRITICAL

    # 取更严格者
    severity_order = [
        GateVerdict.PASS, GateVerdict.WARN, GateVerdict.BLOCK, GateVerdict.CRITICAL,
    ]
    base_idx = severity_order.index(base)
    fb_idx = severity_order.index(fb)
    return severity_order[max(base_idx, fb_idx)]


def evaluate(
    state: PipelineState,
    config: Optional[GateConfig] = None,
) -> GateResult:
    """从 PipelineState 计算门禁结果。

    Args:
        state: 当前 pipeline 状态（含 quality_metrics 和 polished_slots）
        config: 门禁配置（默认 80/60/40）

    Returns:
        GateResult（verdict + can_generate + reasons）
    """
    cfg = config or GateConfig()
    slots = state.polished_slots
    metrics = state.quality_metrics

    # 1. 计算 avg_score
    if metrics:
        scores = [m.overall_score for m in metrics.values()]
        avg_score = sum(scores) / len(scores)
    else:
        avg_score = 0.0

    # 2. 计算 fallback_ratio
    total = len(slots)
    fallback_count = sum(1 for s in slots.values() if s.is_fallback)
    fallback_ratio = fallback_count / total if total > 0 else 0.0

    # 3. 空状态特殊处理
    if total == 0:
        return GateResult(
            verdict=GateVerdict.CRITICAL,
            avg_score=0.0,
            fallback_ratio=0.0,
            reasons=["尚未生成任何段位（请先完成 Step 4 润色）"],
            can_generate=False,
        )

    # 4. 组合判定
    verdict = combine_with_fallback(avg_score, fallback_ratio, cfg)

    # 5. 构造 reasons（人类可读）
    reasons: List[str] = []
    if verdict == GateVerdict.PASS:
        reasons.append(f"质量良好（平均 {avg_score:.1f} 分）")
    elif verdict == GateVerdict.WARN:
        if avg_score < cfg.pass_threshold:
            reasons.append(
                f"质量警告：平均 {avg_score:.1f} 分（阈值 {cfg.pass_threshold}）"
            )
        if 0 < fallback_ratio <= 1.0:
            reasons.append(
                f"Fallback 段位 {fallback_count}/{total}（{fallback_ratio:.0%}）"
            )
    elif verdict == GateVerdict.BLOCK:
        if avg_score < cfg.warn_threshold:
            reasons.append(
                f"质量阻断：平均 {avg_score:.1f} 分（< {cfg.warn_threshold}）"
            )
        if fallback_ratio >= 0.5:
            reasons.append(
                f"Fallback 段位过多：{fallback_count}/{total}（{fallback_ratio:.0%}）"
            )
    else:  # CRITICAL
        if avg_score < cfg.block_threshold:
            reasons.append(
                f"质量严重：平均 {avg_score:.1f} 分（< {cfg.block_threshold}）"
            )
        if fallback_ratio >= 1.0:
            reasons.append(
                f"全部 {total} 段都是 fallback 模式"
            )

    # 6. can_generate：BLOCK 和 CRITICAL 都禁用（需强制继续）
    if verdict in (GateVerdict.BLOCK, GateVerdict.CRITICAL):
        can_generate = False
    else:
        can_generate = True

    return GateResult(
        verdict=verdict,
        avg_score=round(avg_score, 1),
        fallback_ratio=round(fallback_ratio, 3),
        reasons=reasons,
        can_generate=can_generate,
    )


def should_block_button(result: GateResult) -> bool:
    """便捷判断：是否应禁用「生成 Word」按钮。

    BLOCK 或 CRITICAL → True（禁用）
    PASS / WARN → False（允许）
    """
    return result.verdict in (GateVerdict.BLOCK, GateVerdict.CRITICAL)
