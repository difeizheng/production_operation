"""v3 渲染方法回归测试。

覆盖 ReportGeneratorV2 的 .render() 方法（v3.0 新增）和
__init__ 对 str 路径的兼容性（修复 "'str' has no .exists()" bug）。

历史 bug：
    - v3_3 页面调 ReportGeneratorV2(template_path=str(path))
      但 __init__ 不会把 str 转 Path，导致 .exists() 失败
    - v3_3 调 .render(output_path, text_dict, data)
      但类里只有 .generate_report()，没有 .render()
"""
from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


TEMPLATE_PATH = (
    PROJECT_ROOT / "data" / "templates" / "report_template_jinja.docx"
)


def _extract_all_docx_text(docx_path: Path) -> str:
    """从 docx 提取所有文本（包括表格、嵌套段落），用 XML 全文搜。

    原因：doc.paragraphs 不递归遍历表格，而 v4 占位符经常在表格 cell 里。
    """
    with zipfile.ZipFile(str(docx_path), "r") as z:
        with z.open("word/document.xml") as f:
            return f.read().decode("utf-8")


# ============================================================
# __init__ str/Path 兼容性
# ============================================================


class TestInitAcceptsBothStrAndPath:
    """构造函数必须兼容 str 和 Path 输入（修复 v3.3 bug）。"""

    def test_str_path_does_not_raise_exists_error(self):
        """str 输入不应触发 "'str' has no attribute 'exists'" 错误。"""
        from src.generator.report_generator_v2 import ReportGeneratorV2
        # 这是 v3.3 实际使用的方式：template_path=str(...)
        gen = ReportGeneratorV2(template_path=str(TEMPLATE_PATH))
        # 关键：template_path 必须是 Path 实例（不是 str）
        assert isinstance(gen.template_path, Path)
        assert gen.template_path.exists()

    def test_path_path_still_works(self):
        """Path 输入继续工作（向后兼容）。"""
        from src.generator.report_generator_v2 import ReportGeneratorV2
        gen = ReportGeneratorV2(template_path=TEMPLATE_PATH)
        assert isinstance(gen.template_path, Path)
        assert gen.template_path.exists()

    def test_default_template_works(self):
        """不传参时使用 DEFAULT_TEMPLATE。"""
        from src.generator.report_generator_v2 import ReportGeneratorV2, DEFAULT_TEMPLATE
        gen = ReportGeneratorV2()
        assert gen.template_path == DEFAULT_TEMPLATE


# ============================================================
# render 方法（v3.3 调用的入口）
# ============================================================


class TestRenderMethod:
    """v3.3 页面调用的 .render() 方法。"""

    @pytest.fixture
    def generator(self):
        from src.generator.report_generator_v2 import ReportGeneratorV2
        return ReportGeneratorV2(template_path=str(TEMPLATE_PATH))

    @pytest.fixture
    def sample_text_dict(self):
        return {
            "{{ v4_P5_overview }}": "上周，集团公司合计上网电量 89.1 亿千瓦时...",
            "{{ v4_P6_dom_elec_yoy_wow }}": "国内 80.3 亿千瓦时、同比提高 3.2%...",
            "{{ v4_P11_dom_price_yoy }}": "水电电价同比下降每千瓦时 0.1 分...",
        }

    @pytest.fixture
    def sample_data(self):
        return {
            "report_period": {
                "year": 2026,
                "week": 21,
                "start_date": "2026-05-16",
                "end_date": "2026-05-22",
            },
            "group_total": {
                "domestic_ongrid_volume_yi_kwh": 80.3,
                "international_ongrid_volume_yi_kwh": 8.8,
            },
        }

    def test_render_creates_docx_file(self, generator, sample_text_dict, sample_data):
        """render() 必须生成 .docx 文件。"""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "test_output.docx"
            result = generator.render(
                output_path=str(output),
                text_dict=sample_text_dict,
                data=sample_data,
            )
            assert Path(result).exists()
            assert Path(result).suffix == ".docx"
            assert Path(result).stat().st_size > 1000  # 不是空文件

    def test_render_creates_parent_dirs(self, generator, sample_text_dict, sample_data):
        """render() 必须自动创建不存在的父目录（fix 路径经常嵌套深）。"""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "deep" / "nested" / "dir" / "report.docx"
            assert not output.parent.exists()
            result = generator.render(
                output_path=str(output),
                text_dict=sample_text_dict,
                data=sample_data,
            )
            assert Path(result).exists()

    def test_render_strips_braces_from_placeholders(
        self, generator, sample_text_dict, sample_data
    ):
        """text_dict 里的 '{{ xxx }}' 必须能匹配模板里的占位符（去花括号）。"""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "test.docx"
            generator.render(
                output_path=str(output),
                text_dict=sample_text_dict,
                data=sample_data,
            )
            # 用 zipfile 读全文（v4 占位符经常在表格 cell 里）
            xml_text = _extract_all_docx_text(output)
            # text_dict 里的内容应该出现在最终 docx 里
            assert "89.1" in xml_text, "text_dict 内容未注入模板（89.1 缺失）"
            assert "亿千瓦时" in xml_text, "单位文本未注入模板"
            # 模板里的 {{ v4_P5_overview }} 占位符应该被替换
            assert "{{ v4_P5_overview }}" not in xml_text, "占位符未被替换"
            assert "v4_P5_overview }}" not in xml_text, "占位符残留"

    def test_render_handles_missing_placeholders_gracefully(
        self, generator, sample_data
    ):
        """text_dict 为空时，模板里所有占位符用"（待补充）"兜底，不应报错。"""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "test.docx"
            # 不应抛异常
            result = generator.render(
                output_path=str(output),
                text_dict={},  # 空字典
                data=sample_data,
            )
            assert Path(result).exists()

    def test_render_uses_report_period_fallback(self, generator, sample_text_dict):
        """数据无 report_period 时回退到 meta（向后兼容 v2 数据格式）。"""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "test.docx"
            v2_data = {
                "meta": {"year": 2026, "week": 21},
                # 注意：没有 report_period
            }
            # 不应抛异常
            result = generator.render(
                output_path=str(output),
                text_dict=sample_text_dict,
                data=v2_data,
            )
            assert Path(result).exists()

    def test_render_returns_str_path(self, generator, sample_text_dict, sample_data):
        """返回值必须是字符串路径（v3.3 期望）。"""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "test.docx"
            result = generator.render(
                output_path=str(output),
                text_dict=sample_text_dict,
                data=sample_data,
            )
            assert isinstance(result, str)
            assert result == str(output)


# ============================================================
# _build_context_v3 单元测试
# ============================================================


class TestBuildContextV3:
    """上下文构建函数的单元测试。"""

    def test_text_dict_injects_stripped_keys(self):
        """text_dict 的 key 必须去花括号后才能匹配 Jinja2 占位符。"""
        from src.generator.report_generator_v2 import ReportGeneratorV2
        gen = ReportGeneratorV2(template_path=str(TEMPLATE_PATH))

        text_dict = {
            "{{ v4_P5_overview }}": "测试 P5",
            "{{ v4_P6_dom_elec_yoy_wow }}": "测试 P6",
        }
        ctx = gen._build_context_v3(
            data={"report_period": {"year": 2026, "week": 21}},
            text_dict=text_dict,
        )
        # 去花括号后的 key 存在
        assert ctx["v4_P5_overview"] == "测试 P5"
        assert ctx["v4_P6_dom_elec_yoy_wow"] == "测试 P6"
        # 原带花括号的 key 不存在
        assert "{{ v4_P5_overview }}" not in ctx

    def test_missing_v4_keys_get_default(self):
        """所有 v4_P* 占位符必须至少有"（待补充）"兜底。"""
        from src.generator.report_generator_v2 import ReportGeneratorV2
        gen = ReportGeneratorV2(template_path=str(TEMPLATE_PATH))

        ctx = gen._build_context_v3(data={}, text_dict={})
        # 检查所有 15 个 v4 段位都有兜底
        for n in [5, 6, 11, 12, 13, 14, 15, 16, 18, 20, 21, 23, 24, 25, 27]:
            key = f"v4_P{n}_" if n < 10 else f"v4_P{n}_"
            matching = [k for k in ctx.keys() if k.startswith(f"v4_P{n}_")]
            assert matching, f"v4_P{n}_* 至少应有一个兜底 key"
            for k in matching:
                assert ctx[k] == "（待补充）", f"{k} 应有兜底值"

    def test_period_extraction_prefers_report_period(self):
        """优先用 report_period，回退到 meta。"""
        from src.generator.report_generator_v2 import ReportGeneratorV2
        gen = ReportGeneratorV2(template_path=str(TEMPLATE_PATH))

        # 同时给 start_date 和 end_date（date_range 需要两者都有）
        ctx = gen._build_context_v3(
            data={
                "report_period": {
                    "year": 2026,
                    "week": 21,
                    "start_date": "2026-05-16",
                    "end_date": "2026-05-22",
                },
            },
            text_dict={},
        )
        assert ctx["year"] == 2026
        assert ctx["week"] == 21
        assert "2026-05-16" in ctx["date_range"]
        assert "2026-05-22" in ctx["date_range"]

    def test_period_falls_back_to_meta(self):
        """无 report_period 时回退到 meta（v2 数据格式兼容）。"""
        from src.generator.report_generator_v2 import ReportGeneratorV2
        gen = ReportGeneratorV2(template_path=str(TEMPLATE_PATH))

        ctx = gen._build_context_v3(
            data={
                "meta": {
                    "year": 2025,
                    "week": 50,
                    "start_date": "2025-12-08",
                    "end_date": "2025-12-14",
                },
            },
            text_dict={},
        )
        assert ctx["year"] == 2025
        assert ctx["week"] == 50
        assert "2025-12-08" in ctx["date_range"]
