"""Unit tests for convert_template.py - Step 9"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.convert_template import convert_template, detect_format


# ============================================================================
# 格式检测测试
# ============================================================================

class TestDetectFormat:
    """格式检测测试。"""

    def test_docx_format(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """docx 格式（ZIP 头）。"""
        f = tmp_path / "test.docx"
        f.write_bytes(b"PK\x03\x04" + b"\x00" * 100)
        assert detect_format(f) == "docx"

    def test_doc_format(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """旧 .doc 格式（OLE2 头）。"""
        f = tmp_path / "test.doc"
        f.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
        assert detect_format(f) == "doc"

    def test_unknown_format(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """未知格式。"""
        f = tmp_path / "test.xyz"
        f.write_bytes(b"UNKNOWNFORMAT")
        assert detect_format(f) == "unknown"


# ============================================================================
# 转换测试
# ============================================================================

class TestConvertTemplate:
    """convert_template 测试。"""

    def test_convert_existing_docx(self) -> None:
        """V3 是 docx 格式，直接复制。"""
        source = PROJECT_ROOT / "files" / "详版_第22周例会营销发言材料_V3清洁版 - 副本.docx"
        if not source.exists():
            pytest.skip("V3 文件不存在")

        target = PROJECT_ROOT / "data" / "templates" / "test_report.docx"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()

        success = convert_template(source, target)
        assert success is True
        assert target.exists()
        assert target.stat().st_size > 0

    def test_nonexistent_source(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """不存在的源文件返回 False。"""
        source = tmp_path / "nonexistent.docx"
        target = tmp_path / "output.docx"
        success = convert_template(source, target)
        assert success is False


# ============================================================================
# 模板验证测试
# ============================================================================

class TestTemplateReadability:
    """模板可读性测试。"""

    def test_template_readable_by_docx(self) -> None:
        """模板可被 python-docx 读取。"""
        from docx import Document
        template = PROJECT_ROOT / "data" / "templates" / "report_template.docx"
        if not template.exists():
            pytest.skip("模板不存在，请先运行 convert_template.py")

        doc = Document(str(template))
        assert len(doc.paragraphs) > 0
