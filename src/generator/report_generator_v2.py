"""基于 docxtpl 的报告生成器 - 替代纯 python-docx 实现

设计原则：
    1. 模板驱动：data/templates/report_template_jinja.docx 控制布局
    2. 数据驱动：所有变量通过 Jinja2 渲染
    3. 向后兼容：原 ReportGenerator 保留为 report_generator.py（旧实现）

新实现的优势：
    - 模板可由非程序员编辑（Word + Jinja2 占位符）
    - 样式（标题、表格、字体）保留
    - 占位符逻辑（条件、循环）由 Jinja2 处理
    - 代码量减少 ~40%
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from docx import Document

from src.generator.reason_resolver import (
    ReasonResolver,
    ResolvedSegment,
)
from src.generator.analysis_text import (
    generate_electricity_summary,
    generate_domestic_yoy_paragraph,
    generate_domestic_price_yoy_paragraph,
    generate_domestic_price_wow_paragraph,
    generate_revenue_summary,
    generate_spot_price_overview,
)
from src.generator.table_builder import (
    create_sales_table,
    create_spot_price_table,
)

logger = logging.getLogger(__name__)


# 默认模板路径
DEFAULT_TEMPLATE = Path(__file__).resolve().parent.parent.parent / "data" / "templates" / "report_template_jinja.docx"


class ReportGeneratorV2:
    """基于 docxtpl 的报告生成器。"""

    def __init__(
        self,
        output_dir: str = "archive",
        template_path: Optional[Path] = None,
    ) -> None:
        """初始化。

        Args:
            output_dir: 输出目录
            template_path: 自定义模板路径
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.template_path = template_path or DEFAULT_TEMPLATE

        if not self.template_path.exists():
            raise FileNotFoundError(
                f"模板不存在: {self.template_path}\n"
                f"请先运行: python scripts/prepare_template.py"
            )

        logger.info("使用模板: %s", self.template_path)

    def generate_report(
        self,
        data: Dict[str, Any],
        output_filename: Optional[str] = None,
        year: Optional[int] = None,
        week: Optional[int] = None,
        reason_text: Optional[Dict[str, ResolvedSegment]] = None,
    ) -> str:
        """生成 Word 报告。

        Args:
            data: AnalysisCollector 输出
            output_filename: 输出文件名
            year, week: 年周
            reason_text: 原因文本字典

        Returns:
            输出文件路径
        """
        from docxtpl import DocxTemplate

        meta = data.get("meta", {})
        year = year or meta.get("year", datetime.now().year)
        week = week or meta.get("week", 1)

        if output_filename is None:
            output_filename = f"{year}年第{week}周周例会营销发言材料.docx"

        output_path = self.output_dir / str(year) / f"week{week}"
        output_path.mkdir(parents=True, exist_ok=True)
        output_file = output_path / output_filename

        # 1. 准备 Jinja2 上下文
        context = self._build_context(data, year, week, reason_text)

        # 2. 渲染模板
        tpl = DocxTemplate(str(self.template_path))
        tpl.render(context)

        # 3. 文档后处理：插入表格（docxtpl 不支持复杂表格的 Jinja2 控制）
        self._post_process(tpl, data)

        # 4. 保存
        tpl.save(str(output_file))
        logger.info("✅ 报告已生成: %s", output_file)
        return str(output_file)

    def _build_context(
        self,
        data: Dict[str, Any],
        year: int,
        week: int,
        reason_text: Optional[Dict[str, ResolvedSegment]],
    ) -> Dict[str, Any]:
        """构建 Jinja2 渲染上下文。"""
        from scripts.prepare_table_templates import build_sales_rows, build_spot_rows

        meta = data.get("meta", {})
        start_date = meta.get("start_date", "")
        end_date = meta.get("end_date", "")

        # 基础上下文
        context: Dict[str, Any] = {
            "title": "市场营销部汇报材料",
            "year": year,
            "week": week,
            "date_range": f"（{start_date}-{end_date}）" if start_date and end_date else "",
            "dom_overview": "",
        }

        # 销售表 + 现货表数据
        context.update(build_sales_rows(data))
        context.update(build_spot_rows(data))

        # 原因文本
        if reason_text:
            for ph, seg in reason_text.items():
                key = ph.replace("{{", "").replace("}}", "").strip()
                context[key] = seg.final_text
        else:
            # 回退到 analysis_text
            context["v4_P6_dom_elec_yoy_wow"] = generate_domestic_yoy_paragraph(data)
            context["v4_P11_dom_price_yoy"] = generate_domestic_price_yoy_paragraph(data)
            context["v4_P12_dom_price_wow"] = generate_domestic_price_wow_paragraph(data)
            context["v4_P18_dom_revenue"] = generate_revenue_summary(data)

        # 兜底所有占位符
        default_keys = [
            "v4_P6_dom_elec_yoy_wow",
            "v4_P11_dom_price_yoy",
            "v4_P12_dom_price_wow",
            "v4_P13_hydro_price_wow",
            "v4_P14_wind_price_wow",
            "v4_P15_solar_price_wow",
            "v4_P16_thermal_price_wow",
            "v4_P18_dom_revenue",
            "v4_P20_intl_price_yoy",
            "v4_P21_intl_price_wow",
            "v4_P23_market_hydro",
            "v4_P24_market_new_energy",
            "v4_P25_market_thermal",
            "v4_P27_green_cert",
        ]
        for k in default_keys:
            if k not in context:
                context[k] = "（待补充）"

        return context

    def _post_process(self, tpl: Any, data: Dict[str, Any]) -> None:
        """后处理：插入表格、图片等。

        注意：docxtpl 的 DocxTemplate 不直接暴露 docx 对象。
        复杂表格应作为 docxtpl 子模板（subdoc），不在此处处理。
        此方法为占位实现，后续可扩展。
        """
        # 当前不做后处理（占位）
        # 实际生产中应在模板中预定义表格位置，或用 subdoc 模式
        pass


# ============================================================================
# 便利函数
# ============================================================================

def generate_report_v2(
    data: Dict[str, Any],
    summary_file: Optional[str] = None,
    output_dir: str = "archive",
    year: Optional[int] = None,
    week: Optional[int] = None,
) -> str:
    """便利函数：自动解析原因 + 生成报告。

    Args:
        data: AnalysisCollector 输出
        summary_file: 汇总表路径（可选，用于解析原因）
        output_dir: 输出目录
        year, week: 年周

    Returns:
        输出文件路径
    """
    # 1. 解析原因
    reason_text = None
    if summary_file:
        resolver = ReasonResolver(data=data)
        reason_text = resolver.resolve_all(summary_file=summary_file, data=data)

    # 2. 生成报告
    generator = ReportGeneratorV2(output_dir=output_dir)
    return generator.generate_report(
        data=data, year=year, week=week, reason_text=reason_text,
    )
