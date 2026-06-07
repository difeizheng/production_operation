"""End-to-End test: 真实 Excel → Word 报告

测试覆盖：
    1. run_analysis_pipeline 全流程
    2. 生成的 Word 文档包含原因文本
    3. reason_stats 正确反映覆盖率
    4. 端到端回归（防止引入回归）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 测试用真实文件
ANALYSIS_FILE = PROJECT_ROOT / "files" / "2026年第21周周数据综合分析报表.xlsx"
SUMMARY_FILE = PROJECT_ROOT / "files" / "2026年第21周周数据汇总表.xlsx"


@pytest.fixture
def skip_if_no_files() -> bool:
    return not (ANALYSIS_FILE.exists() and SUMMARY_FILE.exists())


# ============================================================================
# 端到端测试
# ============================================================================

class TestEndToEndPipeline:
    """端到端流程测试。"""

    def test_run_analysis_pipeline_with_reasons(
        self, tmp_path, skip_if_no_files: bool  # type: ignore[no-untyped-def]
    ) -> None:
        """完整流程 + reason 解析 + Word 生成。"""
        if skip_if_no_files:
            pytest.skip("测试文件不存在")

        from scripts.run_pipeline import run_analysis_pipeline

        results = run_analysis_pipeline(
            analysis_path=str(ANALYSIS_FILE),
            year=2026,
            week=21,
            summary_path=str(SUMMARY_FILE),
            output_dir=str(tmp_path),
            quiet=True,
        )

        # 基本成功
        assert results["status"] == "success"
        assert "collect" in results["steps"]
        assert "store" in results["steps"]
        assert "generate" in results["steps"]
        assert "resolve_reasons" in results["steps"]

        # 文件生成
        assert "report" in results["files"]
        report_path = Path(results["files"]["report"])
        assert report_path.exists()
        assert report_path.stat().st_size > 0

        # 原因统计
        stats = results["reason_stats"]
        assert stats["total"] > 0
        assert stats["automation_rate"] >= 0.5  # 至少 50% 自动化

    def test_generated_word_contains_reason_text(
        self, tmp_path, skip_if_no_files: bool  # type: ignore[no-untyped-def]
    ) -> None:
        """生成的 Word 文档应包含从 Excel 提取的原因文本。"""
        if skip_if_no_files:
            pytest.skip("测试文件不存在")

        from scripts.run_pipeline import run_analysis_pipeline
        from docx import Document

        results = run_analysis_pipeline(
            analysis_path=str(ANALYSIS_FILE),
            year=2026,
            week=21,
            summary_path=str(SUMMARY_FILE),
            output_dir=str(tmp_path),
            quiet=True,
        )

        doc = Document(results["files"]["report"])
        all_text = "\n".join(p.text for p in doc.paragraphs)

        # 这些关键词应来自 Excel 提取的原因文本（H29, H53, H101 等）
        expected_keywords = [
            "梯级电站综合考虑来水形势",  # H29 的原文（"全口径电量同比增加..."）
            "电量结构变化",                # H29/H53 出现多次
        ]
        for kw in expected_keywords:
            assert kw in all_text, f"Word 文档应包含原因文本关键词: {kw}"

    def test_reason_stats_reasonable(
        self, tmp_path, skip_if_no_files: bool  # type: ignore[no-untyped-def]
    ) -> None:
        """原因统计应合理。"""
        if skip_if_no_files:
            pytest.skip("测试文件不存在")

        from scripts.run_pipeline import run_analysis_pipeline

        results = run_analysis_pipeline(
            analysis_path=str(ANALYSIS_FILE),
            year=2026,
            week=21,
            summary_path=str(SUMMARY_FILE),
            output_dir=str(tmp_path),
            quiet=True,
        )

        stats = results["reason_stats"]

        # 至少有 HIGH 自动化段落
        assert stats["by_level"].get("HIGH", 0) >= 1, \
            f"应至少有 1 个 HIGH 自动化，实际: {stats['by_level']}"

        # MANUAL 段落不超过总数
        total = stats["total"]
        manual = stats["by_level"].get("MANUAL", 0)
        assert manual <= total

    def test_legacy_pipeline_still_works(
        self, tmp_path, skip_if_no_files: bool  # type: ignore[no-untyped-def]
    ) -> None:
        """旧模式（无 summary）仍能跑（向后兼容）。"""
        if skip_if_no_files:
            pytest.skip("测试文件不存在")

        from scripts.run_pipeline import run_analysis_pipeline

        results = run_analysis_pipeline(
            analysis_path=str(ANALYSIS_FILE),
            year=2026,
            week=21,
            summary_path=None,  # 旧模式
            output_dir=str(tmp_path),
            quiet=True,
        )

        assert results["status"] == "success"
        # 无 summary 时不应有 resolve_reasons 步骤
        assert "resolve_reasons" not in results["steps"]
        # 报告仍生成
        assert "report" in results["files"]
