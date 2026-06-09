"""Unit tests for quality_metrics - 4 重检测 + 段位评分

测试覆盖：
    1. 行业术语加载（缓存/降级）
    2. 4 重检测算子（数字/长度/禁词/专业度）
    3. QualityMetrics 计算（段位级 + 批量 + 聚合）
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def clear_industry_cache() -> None:
    """每个测试前后清除 lru_cache，避免污染。"""
    from streamlit_app.core.quality_metrics import clear_industry_terms_cache
    clear_industry_terms_cache()
    yield
    clear_industry_terms_cache()


@pytest.fixture
def perfect_slot():
    """满分 PolishedSlot（数字保留+长度合理+无禁词+专业）。"""
    from streamlit_app.core import PolishedSlot
    # 25 字原文 → 36 字改写 = 1.44x（合规）
    raw = "全集团上网电量同比增加 3.3%，主要受水电增发拉动。"
    polished = "本周全集团上网电量同比增加 3.3%，受水电增发拉动，主因来水偏丰影响。"
    return PolishedSlot(
        slot_id="test.perfect",
        placeholder="{{ v4_test }}",
        raw_text=raw,
        llm_output=polished,
        final_text=polished,
        tokens_used=100,
    )


@pytest.fixture
def bad_slot():
    """低分 PolishedSlot（数字不一致+过长+含禁词+口语化）。"""
    from streamlit_app.core import PolishedSlot
    return PolishedSlot(
        slot_id="test.bad",
        placeholder="{{ v4_bad }}",
        raw_text="电量涨",
        llm_output=(
            "我们觉得可能将有望其实其实其实其实"
            "123.456 789.012 345.678 901.234 567.890 111.222 333.444"
            "555.666 777.888 999.000 222.333 444.555 666.777 888.999"
        ),
        final_text=(
            "我们觉得可能将有望其实其实其实其实"
            "123.456 789.012 345.678 901.234 567.890 111.222 333.444"
            "555.666 777.888 999.000 222.333 444.555 666.777 888.999"
        ),
    )


# ============================================================================
# TestLoadIndustryTerms
# ============================================================================

class TestLoadIndustryTerms:
    """行业术语加载测试。"""

    def test_load_from_real_dictionaries(self) -> None:
        """从真实词典加载（metrics/energy_types/organizations）。"""
        from streamlit_app.core.quality_metrics import load_industry_terms
        result = load_industry_terms()
        assert result.fallback is False
        assert len(result.terms) > 10
        # 至少应该包含核心术语
        assert any("电量" in t for t in result.terms)
        assert any("水电" in t for t in result.terms)
        # 至少加载 2 个文件
        assert len(result.source_files) >= 2

    def test_cache_hits(self) -> None:
        """第二次调用应返回同一对象（lru_cache）。"""
        from streamlit_app.core.quality_metrics import load_industry_terms
        a = load_industry_terms()
        b = load_industry_terms()
        assert a is b

    def test_fallback_when_dir_missing(self, tmp_path: Path) -> None:
        """词典目录不存在时降级为 FALLBACK_TERMS。"""
        from streamlit_app.core import quality_metrics as qm
        # 重定向 PROJECT_ROOT 到 tmp_path
        fake_root = tmp_path / "fake_project"
        fake_root.mkdir()
        with patch.object(qm, "Path") as mock_path_cls:
            mock_path_cls.return_value.resolve.return_value.parent.parent.parent.__truediv__ = lambda *args: fake_root  # type: ignore
            # 上面那行太复杂，直接 mock load 函数对路径的依赖
            # 简化方式：mock Path(__file__).resolve().parent.parent.parent
            with patch.object(
                Path, "resolve",
                return_value=tmp_path / "fake_quality_metrics.py"
            ):
                from streamlit_app.core.quality_metrics import (
                    clear_industry_terms_cache, load_industry_terms,
                )
                clear_industry_terms_cache()
                result = load_industry_terms()
                # 词典目录不存在时应降级
                assert result.fallback is True
                assert len(result.terms) == len(qm.FALLBACK_TERMS)


# ============================================================================
# TestValidateNumbers
# ============================================================================

class TestValidateNumbers:
    """数字保留检测测试。"""

    def test_pass_identical_numbers(self) -> None:
        """数字完全保留。"""
        from streamlit_app.core.quality_metrics import validate_numbers
        assert validate_numbers(
            "本周电量 89.08 亿千瓦时", "本周上网电量达 89.08 亿千瓦时"
        ) is True

    def test_fail_new_number(self) -> None:
        """出现新数字。"""
        from streamlit_app.core.quality_metrics import validate_numbers
        assert validate_numbers(
            "本周电量 89.08", "本周电量 89.08，同比 100.5 亿"
        ) is False

    def test_pass_with_tolerance(self) -> None:
        """容差 ±0.011 范围内视为通过。"""
        from streamlit_app.core.quality_metrics import validate_numbers
        assert validate_numbers(
            "上周电价 0.45 元/度", "上周电价 0.459 元/度"
        ) is True


# ============================================================================
# TestCheckLength
# ============================================================================

class TestCheckLength:
    """长度检测测试。"""

    def test_pass_normal_ratio(self) -> None:
        """长度比例在 [0.5, 1.8] 内。"""
        from streamlit_app.core.quality_metrics import check_length
        # 22 字原文 → 30 字改写 ≈ 1.36x（合规）
        raw = "全集团上网电量同比增加 3.3%，主要受水电增发拉动"
        polished = "本周全集团上网电量同比增加 3.3%，受水电增发拉动，影响显著。"
        ok, ratio = check_length(raw, polished)
        assert ok is True
        assert 0.5 <= ratio <= 1.8

    def test_fail_too_long(self) -> None:
        """polished 超过 raw 1.8 倍。"""
        from streamlit_app.core.quality_metrics import check_length
        ok, ratio = check_length("短", "a" * 100)
        assert ok is False
        assert ratio > 1.8


# ============================================================================
# TestCheckForbidden
# ============================================================================

class TestCheckForbidden:
    """禁词扫描测试。"""

    def test_clean_text(self) -> None:
        """无禁词。"""
        from streamlit_app.core.quality_metrics import check_forbidden
        ok, matched = check_forbidden("本周电量同比增加 3.3%")
        assert ok is True
        assert matched == []

    def test_forbidden_word_detected(self) -> None:
        """含禁词。"""
        from streamlit_app.core.quality_metrics import check_forbidden
        ok, matched = check_forbidden("本周电量预计将增长，主因来水偏丰。")
        assert ok is False
        assert "预计将" in matched


# ============================================================================
# TestProfessionalism
# ============================================================================

class TestProfessionalism:
    """专业度检测测试。"""

    def test_full_score(self) -> None:
        """专业段落满分 20。"""
        from streamlit_app.core.quality_metrics import compute_professionalism
        text = (
            "本周全集团上网电量同比增加 3.3%，"
            "受水电增发拉动，主因来水偏丰影响。"
            "一是水电增发 5%；二是新能源稳中有升。"
        )
        score, warnings = compute_professionalism(text)
        assert score == 20
        assert warnings == []

    def test_deduct_for_missing_terms(self) -> None:
        """缺术语扣 10 分。"""
        from streamlit_app.core.quality_metrics import compute_professionalism
        score, warnings = compute_professionalism("今天天气真好，我爱学习。")
        # 无术语 + 无结构 + 长度过短 + 含口语
        assert score < 20
        assert any("术语" in w for w in warnings)

    def test_deduct_for_colloquial(self) -> None:
        """口语化扣分。"""
        from streamlit_app.core.quality_metrics import compute_professionalism
        text = (
            "本周全集团上网电量同比增加 3.3%，"
            "受水电增发拉动，主因来水偏丰影响。"
            "我们觉得这其实蛮重要的"
        )
        score, warnings = compute_professionalism(text)
        assert any("口语" in w for w in warnings)

    def test_zero_for_empty(self) -> None:
        """空文本 0 分。"""
        from streamlit_app.core.quality_metrics import compute_professionalism
        score, warnings = compute_professionalism("")
        assert score == 0
        assert "空文本" in warnings


# ============================================================================
# TestComputeSlotMetrics
# ============================================================================

class TestComputeSlotMetrics:
    """段位质量计算测试。"""

    def test_perfect_slot_scores_high(self, perfect_slot) -> None:
        """完美段位总分应 ≥ 80。"""
        from streamlit_app.core.quality_metrics import compute_slot_metrics
        m = compute_slot_metrics(perfect_slot)
        assert m.overall_score >= 80
        assert m.slot_id == perfect_slot.slot_id
        assert m.numbers_consistency is True
        assert m.length_reasonable is True
        assert m.no_forbidden_words is True
        assert m.professionalism == 20

    def test_failed_slot_with_warnings(self, bad_slot) -> None:
        """低分段位 warnings 应包含多个问题。"""
        from streamlit_app.core.quality_metrics import compute_slot_metrics
        m = compute_slot_metrics(bad_slot)
        assert m.overall_score < 60
        assert len(m.warnings) >= 2
        # 至少一个 warning 应涉及数字或禁词
        assert any(
            "数字" in w or "禁词" in w or "口语" in w
            for w in m.warnings
        )


# ============================================================================
# TestAggregateOverall
# ============================================================================

class TestAggregateOverall:
    """聚合统计测试。"""

    def test_aggregate_perfect_and_bad(self, perfect_slot, bad_slot) -> None:
        from streamlit_app.core.quality_metrics import (
            compute_slot_metrics, aggregate_overall,
        )
        metrics = {
            perfect_slot.slot_id: compute_slot_metrics(perfect_slot),
            bad_slot.slot_id: compute_slot_metrics(bad_slot),
        }
        result = aggregate_overall(metrics)
        assert result["count"] == 2
        assert 0 < result["avg_score"] < 100
        assert result["min_score"] < result["max_score"]
        assert 0.0 <= result["pass_rate"] <= 1.0
