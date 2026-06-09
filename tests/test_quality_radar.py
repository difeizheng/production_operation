"""Unit tests for quality_radar - 4 维雷达图构建

测试覆盖：
    1. build_radar_figure（空/非空/聚合/颜色）
    2. render_quality_radar（mock streamlit 验证 plotly 调用）
    3. score_table 组件
    4. quality_summary 组件
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
def mixed_metrics():
    """混合分值的 QualityMetrics。"""
    from streamlit_app.core import QualityMetrics
    return {
        "slot_perfect": QualityMetrics(
            slot_id="slot_perfect",
            numbers_consistency=True, length_reasonable=True,
            no_forbidden_words=True, professionalism=20,
            original_deviation=0.95, overall_score=100,
        ),
        "slot_warn": QualityMetrics(
            slot_id="slot_warn",
            numbers_consistency=True, length_reasonable=True,
            no_forbidden_words=False, professionalism=10,
            original_deviation=0.7, overall_score=70,
            warnings=["含禁词: 预计将"],
        ),
        "slot_bad": QualityMetrics(
            slot_id="slot_bad",
            numbers_consistency=False, length_reasonable=True,
            no_forbidden_words=True, professionalism=0,
            original_deviation=0.3, overall_score=40,
            warnings=["数字与原文不一致", "行业术语稀疏(命中1/30)"],
        ),
    }


# ============================================================================
# TestBuildRadarFigure
# ============================================================================

class TestBuildRadarFigure:
    """build_radar_figure 单元测试。"""

    def test_empty_metrics_returns_none(self) -> None:
        from streamlit_app.components.quality_radar import build_radar_figure
        assert build_radar_figure({}) is None

    def test_builds_figure_with_metrics(self, mixed_metrics) -> None:
        from streamlit_app.components.quality_radar import build_radar_figure
        fig = build_radar_figure(mixed_metrics)
        assert fig is not None
        # Plotly Figure 应有 1 个 Scatterpolar trace
        assert len(fig.data) == 1
        trace = fig.data[0]
        # 闭合多边形：4 维 + 1 闭合点 = 5
        assert len(trace.r) == 5
        assert len(trace.theta) == 5

    def test_categories_order_is_fixed(self, mixed_metrics) -> None:
        from streamlit_app.components.quality_radar import (
            build_radar_figure, RADAR_CATEGORIES,
        )
        fig = build_radar_figure(mixed_metrics)
        # 前 4 个分类必须匹配固定顺序
        actual_categories = list(fig.data[0].theta)[:4]
        assert actual_categories == list(RADAR_CATEGORIES)

    def test_color_mapping_for_verdict(self, mixed_metrics) -> None:
        """3 档颜色：绿(>=80)/黄(60-79)/红(<60)。"""
        from streamlit_app.components.quality_radar import build_radar_figure
        # mixed: 100+70+40 = 210/3 = 70（黄）
        fig = build_radar_figure(mixed_metrics)
        line_color = fig.data[0].line.color
        assert "191" in line_color or "191," in line_color  # 黄

        # 全 PASS → 绿
        from streamlit_app.core import QualityMetrics
        all_pass = {f"s{i}": QualityMetrics(slot_id=f"s{i}", overall_score=95) for i in range(3)}
        fig_green = build_radar_figure(all_pass)
        assert "46" in fig_green.data[0].line.color  # 绿

        # 全 BLOCK → 红
        all_block = {f"s{i}": QualityMetrics(slot_id=f"s{i}", overall_score=30) for i in range(3)}
        fig_red = build_radar_figure(all_block)
        assert "220" in fig_red.data[0].line.color  # 红


# ============================================================================
# TestRenderRadar（mock streamlit）
# ============================================================================

class TestRenderRadar:
    """render_quality_radar 渲染测试。"""

    def test_render_empty_metrics(self) -> None:
        """空 metrics → info 提示。"""
        with patch("streamlit.info") as mock_info:
            from streamlit_app.components.quality_radar import render_quality_radar
            render_quality_radar({})
            mock_info.assert_called_once()

    def test_render_with_metrics(self, mixed_metrics) -> None:
        """非空 metrics → plotly_chart 调用。"""
        with patch("streamlit.plotly_chart") as mock_plotly:
            from streamlit_app.components.quality_radar import render_quality_radar
            render_quality_radar(mixed_metrics)
            mock_plotly.assert_called_once()

    def test_render_key_propagation(self, mixed_metrics) -> None:
        """key 参数透传到 plotly_chart。"""
        with patch("streamlit.plotly_chart") as mock_plotly:
            from streamlit_app.components.quality_radar import render_quality_radar
            render_quality_radar(mixed_metrics, key="custom_key")
            call_kwargs = mock_plotly.call_args.kwargs
            assert call_kwargs.get("key") == "custom_key"


# ============================================================================
# TestQualityScoreTable
# ============================================================================

class TestQualityScoreTable:
    """段位详情表测试。"""

    def test_build_dataframe_empty(self) -> None:
        from streamlit_app.components.quality_score_table import (
            build_score_dataframe,
        )
        assert build_score_dataframe({}) is None

    def test_build_dataframe_with_metrics(self, mixed_metrics) -> None:
        from streamlit_app.components.quality_score_table import (
            build_score_dataframe,
        )
        df = build_score_dataframe(mixed_metrics)
        assert df is not None
        assert len(df) == 3
        # 按总分升序排列
        assert df.iloc[0]["总分"] == 40
        assert df.iloc[-1]["总分"] == 100
        # 列名
        assert "占位符" in df.columns
        assert "总分" in df.columns


# ============================================================================
# TestQualitySummary
# ============================================================================

class TestQualitySummary:
    """质量汇总卡片测试。"""

    def test_render_uses_st_metric(self) -> None:
        """应调用 4 次 st.metric。"""
        with patch("streamlit.metric") as mock_metric:
            from streamlit_app.components.quality_summary import (
                render_quality_summary,
            )
            render_quality_summary(
                avg=82.4, pass_rate=0.78, min_score=45, count=18,
                verdict="warn", key="test",
            )
            assert mock_metric.call_count == 4

    def test_render_uses_st_warning_for_warn(self) -> None:
        """warn verdict → st.warning。"""
        with patch("streamlit.warning") as mock_warn:
            from streamlit_app.components.quality_summary import (
                render_quality_summary,
            )
            render_quality_summary(
                avg=70, pass_rate=0.5, min_score=50, count=10,
                verdict="warn", key="test",
            )
            mock_warn.assert_called()

    def test_render_uses_st_error_for_block(self) -> None:
        """block verdict → st.error。"""
        with patch("streamlit.error") as mock_error:
            from streamlit_app.components.quality_summary import (
                render_quality_summary,
            )
            render_quality_summary(
                avg=50, pass_rate=0.0, min_score=30, count=10,
                verdict="block", key="test",
            )
            mock_error.assert_called()
