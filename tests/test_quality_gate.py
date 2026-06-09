"""Unit tests for quality_gate - 4 档门禁 + fallback 组合

测试覆盖：
    1. 真值表（4×4 = 16 格组合的核心 6 格）
    2. evaluate() 对 PipelineState 的完整评估
    3. can_generate 标志正确性
    4. 边界情况（空 state / 全 fallback）
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def make_state():
    """构造 PipelineState mock。"""
    def _make(
        metrics_scores: list[int] | None = None,
        fallback_flags: list[bool] | None = None,
    ):
        from streamlit_app.core import PolishedSlot, QualityMetrics

        # 构造 slots
        slots = {}
        n = len(metrics_scores or fallback_flags or [])
        for i in range(n):
            slots[f"slot_{i}"] = PolishedSlot(
                slot_id=f"slot_{i}",
                placeholder=f"{{{{ v4_p{i} }}}}",
                raw_text="raw",
                llm_output="out",
                final_text="out",
                is_fallback=(fallback_flags[i] if fallback_flags else False),
            )
        # 构造 metrics
        metrics = {}
        for i, score in enumerate(metrics_scores or []):
            metrics[f"slot_{i}"] = QualityMetrics(
                slot_id=f"slot_{i}",
                overall_score=score,
            )

        mock_state = MagicMock()
        mock_state.polished_slots = slots
        mock_state.quality_metrics = metrics
        return mock_state
    return _make


# ============================================================================
# TestCombineWithFallback（真值表核心 6 格）
# ============================================================================

class TestCombineWithFallback:
    """真值表测试：覆盖核心 6 个组合。"""

    def test_pass_when_quality_high_and_no_fallback(self) -> None:
        from streamlit_app.core.quality_gate import (
            combine_with_fallback, GateVerdict,
        )
        assert combine_with_fallback(85.0, 0.0) == GateVerdict.PASS

    def test_warn_when_quality_high_but_some_fallback(self) -> None:
        from streamlit_app.core.quality_gate import (
            combine_with_fallback, GateVerdict,
        )
        # 质量 85 + fallback 30% → WARN
        assert combine_with_fallback(85.0, 0.3) == GateVerdict.WARN

    def test_block_when_fallback_100_with_pass_quality(self) -> None:
        from streamlit_app.core.quality_gate import (
            combine_with_fallback, GateVerdict,
        )
        # 质量 85 + 100% fallback → BLOCK（fallback 拉低）
        assert combine_with_fallback(85.0, 1.0) == GateVerdict.BLOCK

    def test_block_when_quality_50_no_fallback(self) -> None:
        from streamlit_app.core.quality_gate import (
            combine_with_fallback, GateVerdict,
        )
        # 质量 50 + 0% fallback → BLOCK
        assert combine_with_fallback(50.0, 0.0) == GateVerdict.BLOCK

    def test_critical_when_quality_30_with_full_fallback(self) -> None:
        from streamlit_app.core.quality_gate import (
            combine_with_fallback, GateVerdict,
        )
        # 质量 30 + 100% fallback → CRITICAL
        assert combine_with_fallback(30.0, 1.0) == GateVerdict.CRITICAL

    def test_warn_when_quality_70_with_minor_fallback(self) -> None:
        from streamlit_app.core.quality_gate import (
            combine_with_fallback, GateVerdict,
        )
        # 质量 70 + 10% fallback → WARN
        assert combine_with_fallback(70.0, 0.1) == GateVerdict.WARN


# ============================================================================
# TestEvaluate
# ============================================================================

class TestEvaluate:
    """evaluate() 端到端测试。"""

    def test_empty_state_returns_critical(self, make_state) -> None:
        """空 state → CRITICAL。"""
        from streamlit_app.core.quality_gate import evaluate, GateVerdict
        state = make_state(metrics_scores=[], fallback_flags=[])
        result = evaluate(state)
        assert result.verdict == GateVerdict.CRITICAL
        assert result.can_generate is False
        assert "尚未生成" in result.reasons[0]

    def test_full_state_returns_correct_verdict(self, make_state) -> None:
        """满 state + 高分 → PASS。"""
        from streamlit_app.core.quality_gate import evaluate, GateVerdict
        state = make_state(
            metrics_scores=[85, 90, 88, 92, 87],
            fallback_flags=[False, False, False, False, False],
        )
        result = evaluate(state)
        assert result.verdict == GateVerdict.PASS
        assert result.can_generate is True
        assert result.avg_score == pytest.approx(88.4, abs=0.5)

    def test_can_generate_false_for_block(self, make_state) -> None:
        """BLOCK 时 can_generate=False。"""
        from streamlit_app.core.quality_gate import evaluate
        state = make_state(
            metrics_scores=[50, 55, 45],
            fallback_flags=[False, False, False],
        )
        result = evaluate(state)
        assert result.verdict.value == "block"
        assert result.can_generate is False


# ============================================================================
# TestConfig
# ============================================================================

class TestConfig:
    """GateConfig 测试。"""

    def test_default_thresholds(self) -> None:
        from streamlit_app.core.quality_gate import GateConfig
        cfg = GateConfig()
        assert cfg.pass_threshold == 80
        assert cfg.warn_threshold == 60
        assert cfg.block_threshold == 40

    def test_custom_thresholds(self) -> None:
        from streamlit_app.core.quality_gate import (
            combine_with_fallback, GateConfig, GateVerdict,
        )
        cfg = GateConfig(pass_threshold=90, warn_threshold=70, block_threshold=50)
        # 85 分在默认下 PASS，但自定义 90 → WARN
        assert combine_with_fallback(85.0, 0.0, cfg) == GateVerdict.WARN


# ============================================================================
# TestShouldBlockButton
# ============================================================================

class TestShouldBlockButton:
    """should_block_button 便捷判断测试。"""

    def test_block_verdict_blocks(self) -> None:
        from streamlit_app.core.quality_gate import (
            should_block_button, GateVerdict, GateResult,
        )
        result = GateResult(
            verdict=GateVerdict.BLOCK,
            avg_score=50.0,
            fallback_ratio=0.0,
            reasons=["x"],
            can_generate=False,
        )
        assert should_block_button(result) is True

    def test_warn_verdict_does_not_block(self) -> None:
        from streamlit_app.core.quality_gate import (
            should_block_button, GateVerdict, GateResult,
        )
        result = GateResult(
            verdict=GateVerdict.WARN,
            avg_score=70.0,
            fallback_ratio=0.0,
            reasons=["x"],
            can_generate=True,
        )
        assert should_block_button(result) is False
