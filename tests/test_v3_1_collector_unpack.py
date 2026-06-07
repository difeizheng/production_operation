"""Unit tests for v3.1 collector tuple unpacking bug fix.

测试 AnalysisCollector / SummaryCollector 实际返回 Tuple[Dict, List]，防止再次出现
'data_dict.items()' 失败。

这些问题应在 src/collector 层修复（让 collect() 返回 Dict），
但作为回归测试，验证 collect() 当前行为。
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestAnalysisCollectorReturnType:
    """AnalysisCollector.collect() 返回类型测试。"""

    def test_collect_returns_tuple(self) -> None:
        """collect() 应返回 (data_dict, errors_list) tuple。"""
        from src.collector.analysis_collector import AnalysisCollector

        collector = AnalysisCollector()
        # 使用 fixture
        fixture = PROJECT_ROOT / "tests" / "fixtures" / "weekly_report_merged.json"
        if not fixture.exists():
            pytest.skip("fixture not found")

        result = collector.collect(str(fixture), year=2026, week=21)
        assert isinstance(result, tuple)
        assert len(result) == 2
        data, errors = result
        assert isinstance(data, dict)
        assert isinstance(errors, list)

    def test_data_dict_is_iterable(self) -> None:
        """data dict 应支持 .items() 调用。"""
        from src.collector.analysis_collector import AnalysisCollector

        collector = AnalysisCollector()
        fixture = PROJECT_ROOT / "tests" / "fixtures" / "weekly_report_merged.json"
        if not fixture.exists():
            pytest.skip("fixture not found")

        result = collector.collect(str(fixture), year=2026, week=21)
        data, errors = result
        # 这是 v3.1 报错的根因：直接用 result 而不解包 → result 是 tuple
        # tuple.items() 报错
        with pytest.raises(AttributeError):
            _ = result.items()
        # 但解包后的 data.items() 正常工作
        _ = data.items()  # 不报错


class TestSummaryCollectorReturnType:
    """SummaryCollector.collect() 返回类型测试。"""

    def test_collect_returns_tuple(self) -> None:
        """SummaryCollector.collect() 也返回 tuple。"""
        from src.collector.summary_collector import SummaryCollector

        collector = SummaryCollector()
        # 没有 fixture 用 None 测试
        result = collector.collect("nonexistent.xlsx")
        assert isinstance(result, tuple)
        assert len(result) == 2
        data, errors = result
        assert isinstance(data, dict)
        assert isinstance(errors, list)


class TestUnpackPattern:
    """解包模式测试 — 模拟 v3.1 修复后的写法。"""

    def test_unpack_analysis_result(self) -> None:
        """模拟 v3.1 collect_analysis_data 的解包逻辑。"""
        from src.collector.analysis_collector import AnalysisCollector

        collector = AnalysisCollector()
        fixture = PROJECT_ROOT / "tests" / "fixtures" / "weekly_report_merged.json"
        if not fixture.exists():
            pytest.skip("fixture not found")

        # v3.1 修复后的写法
        result = collector.collect(str(fixture), year=2026, week=21)
        assert isinstance(result, tuple)
        data, errors = result
        # 验证 data 是字典（不再报错）
        assert isinstance(data, dict)
        # data.items() 调用应正常工作（不抛 AttributeError）
        items = list(data.items())
        # items 可能是 0 个（如果 fixture 格式特殊）或多个，仅验证不抛错
        assert isinstance(items, list)

    def test_backward_compatible_with_dict(self) -> None:
        """老代码可能直接返回 dict（兼容模式）。"""
        # 模拟旧行为：直接返回 dict 而非 tuple
        old_result = {"a": 1, "b": 2}
        # v3.1 修复后的逻辑：if isinstance(result, tuple): 解包, else: 直接用
        if isinstance(old_result, tuple):
            data, errors = old_result
        else:
            data = old_result
            errors = []
        assert data == {"a": 1, "b": 2}
        assert errors == []
