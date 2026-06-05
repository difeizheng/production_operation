"""数据采集脚本入口"""

import argparse
import sys
from pathlib import Path

from src.collector.excel_collector import ExcelCollector
from src.validator.schema_validator import SchemaValidator
from src.validator.data_cleaner import DataCleaner
from src.storage.json_store import JSONStore


def main():
    parser = argparse.ArgumentParser(description="Excel 数据采集")

    parser.add_argument("--input", "-i", required=True, help="Excel 文件路径")
    parser.add_argument("--output", "-o", required=True, help="JSON 输出路径")
    parser.add_argument("--year", "-y", type=int, help="年份")
    parser.add_argument("--week", "-w", type=int, help="周数")
    parser.add_argument("--sheets", "-s", nargs="+", help="Sheet 名称列表")
    parser.add_argument("--validate", "-v", action="store_true", help="校验数据")
    parser.add_argument("--clean", "-c", action="store_true", help="清洗数据")
    parser.add_argument("--quiet", "-q", action="store_true", help="静默模式")

    args = parser.parse_args()

    # 检查输入文件
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误: 文件不存在 - {input_path}")
        sys.exit(1)

    # 初始化组件
    collector = ExcelCollector()
    validator = SchemaValidator()
    cleaner = DataCleaner()
    store = JSONStore()

    # 1. 采集数据
    if not args.quiet:
        print(f"采集数据: {input_path.name}")

    data, errors = collector.collect(
        str(input_path),
        sheets=args.sheets,
        year=args.year,
        week=args.week
    )

    # 输出采集错误
    if not args.quiet:
        for err in errors:
            level = err.get("level", "INFO")
            msg = err.get("message", "")
            if level == "ERROR":
                print(f"  [ERROR] {msg}")
            elif level == "WARN":
                print(f"  [WARN] {msg}")

    # 2. 校验数据
    if args.validate:
        if not args.quiet:
            print("校验数据...")

        validation_result = validator.full_validate(data)

        if not args.quiet:
            print(f"  状态: {validation_result['status']}")
            print(f"  错误: {validation_result['error_count']}")
            print(f"  警告: {validation_result['warn_count']}")

        data["validation_report"] = validation_result

    # 3. 清洗数据
    if args.clean:
        if not args.quiet:
            print("清洗数据...")

        data, clean_reports = cleaner.clean_full_data(data)

        if not args.quiet:
            print(f"  清洗记录: {len(clean_reports)}")
            for report in clean_reports[:5]:  # 显示前 5 条
                print(f"    {report['org']}.{report['energy_type']}.{report['metric']}")

    # 4. 保存数据
    if not args.quiet:
        print(f"保存数据: {args.output}")

    output_file = collector.save_json(data, args.output)

    # 输出摘要
    if not args.quiet:
        print("\n摘要:")
        print(f"  组织数量: {len(data.get('organizations', {}))}")
        print(f"  覆盖率: {data.get('validation_report', {}).get('coverage', 0)}%")
        print(f"  输出文件: {output_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())