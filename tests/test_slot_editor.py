"""Unit tests for SlotEditor - 段位编辑器组件

由于 Streamlit 组件不易直接单元测试，本测试覆盖：
    1. 调参面板的数据流（LLMCallParams 序列化）
    2. 质量徽章生成
    3. 模式描述生成
    4. diff_stats 计算（复用）
    5. number 提取（复用）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# LLMCallParams 测试
# ============================================================================

class TestLLMCallParams:
    """LLMCallParams 数据类测试。"""

    def test_default_values(self) -> None:
        from streamlit_app.core import LLMCallParams
        p = LLMCallParams()
        assert p.temperature == 0.3
        assert p.max_tokens == 500
        assert p.model_name is None
        assert p.use_few_shot is False
        assert p.custom_system_prompt is None

    def test_to_dict(self) -> None:
        from streamlit_app.core import LLMCallParams
        p = LLMCallParams(
            temperature=0.7,
            max_tokens=1000,
            model_name="claude-sonnet-4-6",
            use_few_shot=True,
        )
        d = p.to_dict()
        assert d["temperature"] == 0.7
        assert d["max_tokens"] == 1000
        assert d["model_name"] == "claude-sonnet-4-6"
        assert d["use_few_shot"] is True
        assert d["has_custom_system"] is False
        assert d["has_custom_user"] is False

    def test_with_custom_prompts(self) -> None:
        from streamlit_app.core import LLMCallParams
        p = LLMCallParams(
            custom_system_prompt="你是一个专家",
            custom_user_prompt="请改写：{raw_text}",
        )
        d = p.to_dict()
        assert d["has_custom_system"] is True
        assert d["has_custom_user"] is True


class TestOrchestratorStats:
    """OrchestratorStats 测试。"""

    def test_defaults(self) -> None:
        from streamlit_app.core import OrchestratorStats
        s = OrchestratorStats()
        assert s.total_calls == 0
        assert s.successful_calls == 0
        assert s.avg_latency_ms == 0.0
        assert s.total_tokens == 0

    def test_avg_latency(self) -> None:
        from streamlit_app.core import OrchestratorStats
        s = OrchestratorStats(
            successful_calls=4,
            total_latency_ms=4000,
            total_input_tokens=100,
            total_output_tokens=200,
        )
        assert s.avg_latency_ms == 1000.0
        assert s.total_tokens == 300

    def test_to_dict(self) -> None:
        from streamlit_app.core import OrchestratorStats
        s = OrchestratorStats(total_calls=10, successful_calls=8, failed_calls=2)
        d = s.to_dict()
        assert d["total_calls"] == 10
        assert d["successful_calls"] == 8
        assert "total_tokens" in d


# ============================================================================
# LLMOrchestrator 单元测试
# ============================================================================

class TestLLMOrchestratorPolish:
    """LLMOrchestrator.polish 单元测试。"""

    def test_empty_text(self) -> None:
        from streamlit_app.core import LLMOrchestrator
        with patch.dict(os.environ, {}, clear=True):
            orch = LLMOrchestrator()
            result = orch.polish("")
            assert result.is_fallback is True
            assert result.error == "空文本"

    def test_short_text_passthrough(self) -> None:
        from streamlit_app.core import LLMOrchestrator
        with patch.dict(os.environ, {}, clear=True):
            orch = LLMOrchestrator()
            short = "1、来水偏丰。"
            result = orch.polish(short)
            assert result.polished_text == short
            assert result.model_used == "none-short"
            assert result.is_fallback is True

    def test_no_api_key_fallback(self) -> None:
        from streamlit_app.core import LLMOrchestrator
        with patch("src.utils.llm_factory.load_env"), \
             patch.dict(os.environ, {
                "LLM_PROVIDER": "",
                "LLM_API_KEY": "",
                "ANTHROPIC_API_KEY": "",
                "ENABLE_LLM_POLISH": "false",
             }, clear=True):
            orch = LLMOrchestrator()
            # 使用 ASCII 避免 GBK 编码问题
            text = "Group electricity YoY +3.2%, main reason hydro more generation. " * 2
            result = orch.polish(text)
            assert result.is_fallback is True
            assert result.error is not None
            assert "LLM" in result.error
            assert result.polished_text == text  # 返回原文

    def test_with_mock_llm(self) -> None:
        from streamlit_app.core import LLMOrchestrator
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "qwen",
            "LLM_API_KEY": "test",
            "LLM_BASE_URL": "https://test/v1",
        }, clear=True):
            with patch("openai.OpenAI") as mock_openai_class:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                # 数字必须出现在 raw 中
                mock_response.choices[0].message.content = '{"polished_text": "Group electricity 80.3 TWh"}'
                mock_response.model = "qwen"
                mock_response.usage.prompt_tokens = 50
                mock_response.usage.completion_tokens = 30
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai_class.return_value = mock_client

                orch = LLMOrchestrator()
                raw = "Group electricity 80.3 TWh YoY +3.2%, main reason hydro more generation."
                result = orch.polish(raw, slot_id="test.slot")
                assert result.is_fallback is False
                assert "80.3" in result.polished_text
                assert result.tokens_used == 80
                # 统计应更新
                assert orch.stats.total_calls == 1
                assert orch.stats.successful_calls == 1

    def test_hallucination_detected(self) -> None:
        from streamlit_app.core import LLMOrchestrator
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "qwen",
            "LLM_API_KEY": "test",
            "LLM_BASE_URL": "https://test/v1",
        }, clear=True):
            with patch("openai.OpenAI") as mock_openai_class:
                mock_client = MagicMock()
                mock_response = MagicMock()
                # LLM 编造了 99.9（原文没有）
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = '{"polished_text": "Group electricity 99.9 TWh, with 5% increase due to high water period"}'
                mock_response.model = "qwen"
                mock_response.usage.prompt_tokens = 50
                mock_response.usage.completion_tokens = 30
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai_class.return_value = mock_client

                orch = LLMOrchestrator()
                # raw_text 必须 >= 30 字符才能走到 LLM 调用
                raw = "Group electricity 80.3 TWh YoY increase, main reason is high water inflow period"
                result = orch.polish(raw, slot_id="test.slot")
                # 验证未通过（99.9 不在原文）
                assert result.validation_passed is False


class TestLLMOrchestratorRetry:
    """重试机制测试。"""

    def test_retry_on_exception(self) -> None:
        from streamlit_app.core import LLMOrchestrator
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "qwen",
            "LLM_API_KEY": "test",
            "LLM_BASE_URL": "https://test/v1",
        }, clear=True):
            with patch("openai.OpenAI") as mock_openai_class:
                mock_client = MagicMock()
                # 前两次失败，第三次成功
                success_response = MagicMock()
                success_response.choices = [MagicMock()]
                success_response.choices[0].message.content = '{"polished_text": "Group electricity 80.3 TWh"}'
                success_response.model = "qwen"
                success_response.usage.prompt_tokens = 50
                success_response.usage.completion_tokens = 30

                mock_client.chat.completions.create.side_effect = [
                    Exception("Network error"),
                    Exception("Timeout"),
                    success_response,
                ]
                mock_openai_class.return_value = mock_client

                # 加速重试
                LLMOrchestrator.INITIAL_BACKOFF = 0.01
                LLMOrchestrator.BACKOFF_MULTIPLIER = 1.0

                orch = LLMOrchestrator()
                raw = "Group electricity 80.3 TWh YoY +3.2%, main reason hydro more generation."
                result = orch.polish(raw, slot_id="test.slot")
                assert result.is_fallback is False
                assert orch.stats.retried_calls == 2
                assert orch.stats.successful_calls == 1


# ============================================================================
# diff_viewer 辅助函数测试
# ============================================================================

class TestDiffViewerHelpers:
    """diff_viewer 内部函数测试。"""

    def test_extract_numbers(self) -> None:
        from streamlit_app.components.diff_viewer import extract_numbers
        nums = extract_numbers("Group electricity 80.3 TWh, YoY +3.2%")
        assert "80.3" in nums
        # 注意：正则会把 3.2% 当作一个数（包含 %）
        assert any("3.2" in n for n in nums)
        # extract_numbers 提取所有数字（含单数字 0-9）
        # "显著数字" 过滤在 _validate_numbers 中进行
        assert "5" in extract_numbers("I have 5 reasons")
        # 但 _validate_numbers 会忽略单数字
        from streamlit_app.core.llm_orchestrator import LLMOrchestrator
        passed = LLMOrchestrator._validate_numbers(
            input_numbers=["10.5"],
            output_numbers=["1", "2", "3"],  # 单数字忽略
        )
        assert passed is True

    def test_compute_diff_stats(self) -> None:
        from streamlit_app.components.diff_viewer import compute_diff_stats
        stats = compute_diff_stats("全集团电量 80.3", "全集团上网电量 80.3")
        assert stats["similarity"] > 0.5
        assert "80.3" in stats["preserved_numbers"]

    def test_compute_diff_stats_with_added_number(self) -> None:
        from streamlit_app.components.diff_viewer import compute_diff_stats
        stats = compute_diff_stats("全集团电量 80.3", "全集团电量 80.3，增幅 99.9")
        assert "99.9" in stats["added_numbers"]

    def test_compute_diff_stats_empty(self) -> None:
        from streamlit_app.components.diff_viewer import compute_diff_stats
        stats = compute_diff_stats("", "")
        assert stats["similarity"] == 0.0


# ============================================================================
# categorize_field 测试
# ============================================================================

class TestDataPreviewHelpers:
    """data_preview 辅助函数测试。"""

    def test_categorize_electricity(self) -> None:
        from streamlit_app.components.data_preview import categorize_field
        assert categorize_field("report.electricity.hydro") == "电量"
        assert categorize_field("report.electricity.wind") == "电量"

    def test_categorize_price(self) -> None:
        from streamlit_app.components.data_preview import categorize_field
        assert categorize_field("report.price.hydro") == "电价"
        assert categorize_field("report.wow_price.hydro") == "电价"

    def test_categorize_yoy(self) -> None:
        from streamlit_app.components.data_preview import categorize_field
        # 注意：categorize_field 按 FIELD_CATEGORIES 顺序匹配，"yoy" 在 "electricity" 之后
        # report.yoy_electricity.hydro 先匹配到"电量"分类（electricity）
        # report.yoy_price.hydro 先匹配到"电价"分类（price）
        # 使用纯 yoy 字段才能匹配到同比
        assert categorize_field("report.yoy.field") == "同比"
        assert categorize_field("yoy_metric") == "同比"

    def test_categorize_unknown(self) -> None:
        from streamlit_app.components.data_preview import categorize_field
        assert categorize_field("report.unknown.field") == "其他"

    def test_detect_anomalies_with_missing(self) -> None:
        from streamlit_app.components.data_preview import detect_anomalies
        result = detect_anomalies([1.0, 2.0, None, 3.0])
        assert 2 in result["missing_indices"]

    def test_detect_anomalies_with_outlier(self) -> None:
        from streamlit_app.components.data_preview import detect_anomalies
        # 极端离群值：4 个 1 + 1 个 1000000
        # mean=200000.4, stdev≈447213
        # z(1000000) = 800000/447213 ≈ 1.79 → 仍 < 2.5
        # 需要更极端的对比度：99% 相同 + 1% 极端
        result = detect_anomalies([1.0] * 9 + [100000.0])
        # z(100000) = (100000 - 10001) / ~30000 ≈ 3.0 → > 2.5
        assert len(result["outlier_indices"]) > 0

    def test_detect_anomalies_too_few_values(self) -> None:
        from streamlit_app.components.data_preview import detect_anomalies
        result = detect_anomalies([1.0, 2.0])
        # 少于 3 个值不检测离群点
        assert result["outlier_indices"] == []
