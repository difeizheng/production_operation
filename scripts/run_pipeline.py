"""完整流程脚本 - 从综合分析报表到 Word 报告

支持两种模式：
    1. 新模式（推荐）：--analysis-input 综合分析报表.xlsx
    2. 旧模式（兼容）：--input 汇总表.xlsx
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


def run_analysis_pipeline(
    analysis_path: str,
    year: int,
    week: int,
    summary_path: Optional[str] = None,
    output_dir: str = "archive",
    quiet: bool = False,
) -> Dict[str, Any]:
    """使用综合分析报表运行完整流程。

    Args:
        analysis_path: 综合分析报表.xlsx 路径
        year: 年份
        week: 周数
        summary_path: 汇总表.xlsx 路径（可选，补充现货+原因数据）
        output_dir: 输出目录
        quiet: 是否静默

    Returns:
        结果字典
    """
    from src.collector.analysis_collector import AnalysisCollector
    from src.generator.report_generator import ReportGenerator

    results: Dict[str, Any] = {
        "status": "success",
        "steps": [],
        "files": {},
        "errors": [],
    }

    # 1. 数据采集（综合分析表）
    if not quiet:
        print(f"\n[Step 1] 从综合分析报表采集数据: {Path(analysis_path).name}")

    collector = AnalysisCollector()
    data, errors = collector.collect(analysis_path, year=year, week=week)

    results["steps"].append("collect")
    results["errors"].extend(errors)

    if not quiet:
        meta = data.get("meta", {})
        validation = data.get("validation_report", {})
        print(f"  字段数: {validation.get('field_count', 0)}")
        print(f"  覆盖率: {validation.get('coverage', 0)}%")
        if errors:
            error_count = len([e for e in errors if e["level"] == "ERROR"])
            print(f"  错误: {error_count}")

    # 1b. 补充数据采集（汇总表）
    if summary_path:
        if not quiet:
            print(f"\n[Step 1b] 从汇总表采集补充数据: {Path(summary_path).name}")

        from src.collector.summary_collector import SummaryCollector

        summary_collector = SummaryCollector()
        supplement, supp_errors = summary_collector.collect(
            summary_path, year=year, week=week
        )

        results["steps"].append("collect_supplement")
        results["errors"].extend(supp_errors)

        if supplement:
            # 合并补充数据到主数据
            if "spot_prices" in supplement:
                data["spot_prices"] = supplement["spot_prices"]
            if "reasons" in supplement:
                data["reasons"] = supplement["reasons"]

        if not quiet:
            spot_count = len(data.get("spot_prices", {}).get("regions", []))
            has_reasons = bool(data.get("reasons", {}).get("yoy_summary"))
            print(f"  现货地区: {spot_count}/10")
            print(f"  原因文本: {'有' if has_reasons else '无'}")
            if supp_errors:
                print(f"  补充错误: {len(supp_errors)}")

    # 2. 数据存储
    if not quiet:
        print(f"\n[Step 2] 数据存储")

    from src.storage.json_store import JSONStore

    store = JSONStore()
    json_path = store.save(data, year, week)

    results["steps"].append("store")
    results["files"]["json"] = json_path

    if not quiet:
        print(f"  JSON: {json_path}")

    # 2b. 原因文本解析（新功能 - Step 4-6 整合 + Step 8 数据驱动）
    reason_text = None
    if summary_path:
        if not quiet:
            print(f"\n[Step 2b] 原因文本解析（Excel → 占位符字典）")

        from src.generator.reason_resolver import ReasonResolver

        # 传入 data 用于 grounded_category 模式（4 个品类级原因）
        resolver = ReasonResolver(data=data)
        reason_text = resolver.resolve_all(summary_file=summary_path, data=data)
        stats = resolver.get_stats(reason_text)

        results["steps"].append("resolve_reasons")
        results["reason_stats"] = {
            "total": stats["total"],
            "by_level": stats["by_level"],
            "polished_count": stats["polished_count"],
            "fallback_count": stats["fallback_count"],
            "automation_rate": stats["automation_rate"],
        }

        if not quiet:
            print(f"  解析段落: {stats['total']}")
            print(f"  自动化覆盖: {stats['automation_rate']:.0%}")
            print(f"  润色数: {stats['polished_count']} / Fallback: {stats['fallback_count']}")
            print(f"  按等级: {stats['by_level']}")

    # 3. 报告生成
    if not quiet:
        print(f"\n[Step 3] 报告生成")

    generator = ReportGenerator(output_dir=output_dir)
    report_path = generator.generate_report(
        data, year=year, week=week, reason_text=reason_text,
    )

    results["steps"].append("generate")
    results["files"]["report"] = report_path

    if not quiet:
        print(f"  Word: {report_path}")

    # 完成
    if not quiet:
        print(f"\n[完成] 流程结束")
        print(f"  输出文件: {len(results['files'])} 个")
        print(f"  总错误: {len(results['errors'])}")

    return results


def run_legacy_pipeline(
    excel_path: str,
    year: int,
    week: int,
    output_dir: str = "archive",
    quiet: bool = False,
) -> Dict[str, Any]:
    """使用旧模式（汇总表）运行流程（兼容）。"""
    from src.collector.excel_collector import ExcelCollector
    from src.validator.schema_validator import SchemaValidator
    from src.validator.data_cleaner import DataCleaner
    from src.storage.json_store import JSONStore
    from src.generator.report_generator import ReportGenerator

    results: Dict[str, Any] = {
        "status": "success",
        "steps": [],
        "files": {},
        "errors": [],
    }

    if not quiet:
        print(f"\n[Step 1] 数据采集（旧模式）: {Path(excel_path).name}")

    collector = ExcelCollector()
    data, errors = collector.collect(excel_path, year=year, week=week)

    results["steps"].append("collect")
    results["errors"].extend(errors)

    if not quiet:
        org_count = len(data.get("organizations", {}))
        coverage = data.get("validation_report", {}).get("coverage", 0)
        print(f"  组织数量: {org_count}, 覆盖率: {coverage}%")

    # 存储
    store = JSONStore()
    json_path = store.save(data, year, week)
    results["steps"].append("store")
    results["files"]["json"] = json_path

    # 生成
    generator = ReportGenerator(output_dir=output_dir)
    report_path = generator.generate_report(data, year=year, week=week)
    results["steps"].append("generate")
    results["files"]["report"] = report_path

    if not quiet:
        print(f"\n[完成] JSON: {json_path}")
        print(f"  Word: {report_path}")

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="周报生成流程: Excel → JSON → Word"
    )

    # 输入源（二选一）
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--analysis-input", "-a",
        help="综合分析报表.xlsx 路径（推荐）"
    )
    input_group.add_argument(
        "--input", "-i",
        help="汇总表.xlsx 路径（旧模式）"
    )

    # 补充数据源（可选）
    parser.add_argument(
        "--summary-input", "-s",
        help="汇总表.xlsx 路径（补充现货+原因数据，需配合 --analysis-input 使用）"
    )

    parser.add_argument("--year", "-y", type=int, required=True, help="年份")
    parser.add_argument("--week", "-w", type=int, required=True, help="周数")
    parser.add_argument("--output-dir", "-o", default="archive", help="输出目录")
    parser.add_argument("--quiet", "-q", action="store_true", help="静默模式")

    args = parser.parse_args()

    # 检查输入文件
    input_path = Path(args.analysis_input or args.input)
    if not input_path.exists():
        print(f"错误: 文件不存在 - {input_path}")
        return 1

    # 运行流程
    if args.analysis_input:
        results = run_analysis_pipeline(
            analysis_path=str(input_path),
            year=args.year,
            week=args.week,
            summary_path=args.summary_input,
            output_dir=args.output_dir,
            quiet=args.quiet,
        )
    else:
        results = run_legacy_pipeline(
            excel_path=str(input_path),
            year=args.year,
            week=args.week,
            output_dir=args.output_dir,
            quiet=args.quiet,
        )

    return 0 if results["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
