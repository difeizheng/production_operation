"""报告生成脚本入口"""

import argparse
import sys
import json
from pathlib import Path

from src.generator.report_generator import ReportGenerator
from src.generator.chart_builder import ChartBuilder
from src.generator.text_generator import TextGenerator


def main():
    parser = argparse.ArgumentParser(description="生成周报")

    parser.add_argument("--json", "-j", required=True, help="JSON 数据文件")
    parser.add_argument("--output", "-o", help="输出文件名")
    parser.add_argument("--year", "-y", type=int, help="年份")
    parser.add_argument("--week", "-w", type=int, help="周数")
    parser.add_argument("--template", "-t", default="data/templates/report_template.docx", help="模板文件")
    parser.add_argument("--charts", "-c", action="store_true", help="生成图表")
    parser.add_argument("--quiet", "-q", action="store_true", help="静默模式")

    args = parser.parse_args()

    # 检查输入文件
    json_path = Path(args.json)
    if not json_path.exists():
        print(f"错误: 文件不存在 - {json_path}")
        sys.exit(1)

    # 加载数据
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 初始化生成器
    generator = ReportGenerator(
        template_path=args.template,
        output_dir="archive"
    )

    # 生成报告
    if not args.quiet:
        print("生成报告...")

    if args.charts:
        result = generator.generate_with_charts(
            data,
            output_filename=args.output,
            year=args.year,
            week=args.week
        )
        report_path = result["report_path"]
        charts = result["charts"]

        if not args.quiet:
            print(f"  报告: {report_path}")
            print(f"  图表:")
            for name, path in charts.items():
                print(f"    - {name}: {path}")
    else:
        report_path = generator.generate_report(
            data,
            output_filename=args.output,
            year=args.year,
            week=args.week
        )

        if not args.quiet:
            print(f"  报告: {report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())