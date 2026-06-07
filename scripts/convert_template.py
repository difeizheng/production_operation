"""模板转换脚本 - 准备 report_template.docx（用于 docxtpl）

功能：
    1. 检测源文件格式（.doc vs .docx）
    2. 优先用 LibreOffice 命令行转换
    3. 失败回退：用 python-docx 直接读取（如果源是 docx）
    4. 缓存到 data/templates/report_template.docx

使用：
    PYTHONPATH=. python scripts/convert_template.py \\
        --source files/详版_第22周例会营销发言材料_V3清洁版.docx \\
        --output data/templates/report_template.docx
"""
from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)


# ============================================================================
# 格式检测
# ============================================================================

def detect_format(file_path: Path) -> str:
    """检测文件实际格式。"""
    with open(file_path, "rb") as f:
        head = f.read(8)
    if head[:4] == b"PK\x03\x04":
        return "docx"
    elif head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "doc"
    else:
        return "unknown"


# ============================================================================
# 转换策略
# ============================================================================

def try_libreoffice_convert(source: Path, output_dir: Path) -> Optional[Path]:
    """尝试用 LibreOffice 转换。"""
    for cmd in ["libreoffice", "soffice"]:
        try:
            result = subprocess.run(
                [cmd, "--headless", "--convert-to", "docx",
                 "--outdir", str(output_dir), str(source)],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                converted = output_dir / f"{source.stem}.docx"
                if converted.exists():
                    logger.info("✅ LibreOffice 转换成功: %s", converted)
                    return converted
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            logger.warning("LibreOffice 转换超时")
        except Exception as e:
            logger.warning("LibreOffice 失败: %s", e)
    return None


def try_python_docx_read(source: Path, target: Path) -> bool:
    """回退方案：如果是 docx 直接复制。"""
    try:
        from docx import Document
        # 验证能读取
        doc = Document(str(source))
        logger.info("源文件可被 python-docx 读取（%d 段落）", len(doc.paragraphs))
        # 直接复制（python-docx 读取再保存会改变格式）
        shutil.copy2(str(source), str(target))
        logger.info("✅ 已复制到: %s", target)
        return True
    except Exception as e:
        logger.error("python-docx 读取失败: %s", e)
        return False


# ============================================================================
# 主流程
# ============================================================================

def convert_template(
    source: Path,
    output: Path,
    prefer: str = "auto",
) -> bool:
    """转换模板。

    Args:
        source: 源文件路径
        output: 输出路径
        prefer: "auto" / "libreoffice" / "python-docx"

    Returns:
        True = 成功
    """
    if not source.exists():
        logger.error("源文件不存在: %s", source)
        return False

    fmt = detect_format(source)
    logger.info("源文件格式: %s (%s)", fmt, source.name)

    output.parent.mkdir(parents=True, exist_ok=True)

    # 如果源就是 docx，直接复制
    if fmt == "docx":
        logger.info("源文件已是 docx 格式，直接复制")
        return try_python_docx_read(source, output)

    # 源是 doc，尝试 LibreOffice
    if prefer in ("auto", "libreoffice"):
        result = try_libreoffice_convert(source, output.parent)
        if result is not None:
            # 重命名
            if result != output:
                shutil.move(str(result), str(output))
            return True
        if prefer == "libreoffice":
            return False  # 强制 LibreOffice 但失败

    # LibreOffice 失败 → 报错
    logger.error(
        "源文件是 .doc 格式但 LibreOffice 未安装。\n"
        "解决方案：\n"
        "  1. 安装 LibreOffice: https://www.libreoffice.org/\n"
        "  2. 或在 Word 中打开 .doc → 另存为 .docx"
    )
    return False


def main() -> int:
    # Windows 控制台 UTF-8（仅运行时）
    if sys.platform == "win32":
        import io
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(description="V3/V4 模板 → docx 转换")
    parser.add_argument(
        "--source",
        default="files/详版_第22周例会营销发言材料_V3清洁版 - 副本.docx",
        help="源文件路径",
    )
    parser.add_argument(
        "--output",
        default="data/templates/report_template.docx",
        help="输出文件路径",
    )
    parser.add_argument(
        "--prefer",
        choices=["auto", "libreoffice", "python-docx"],
        default="auto",
        help="转换策略",
    )
    args = parser.parse_args()

    source = PROJECT_ROOT / args.source
    output = PROJECT_ROOT / args.output

    success = convert_template(source, output, prefer=args.prefer)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
