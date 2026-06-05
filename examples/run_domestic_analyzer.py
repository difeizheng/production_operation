"""
DomesticAnalyzer 使用示例
=========================

展示如何在国内段分析中使用 DomesticAnalyzer。

运行方式:
    PYTHONPATH=. python examples/run_domestic_analyzer.py
"""

import json
import sys
from pathlib import Path

# 添加项目根到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.analyzer import DomesticAnalyzer


def main():
    """主函数：演示 DomesticAnalyzer 的使用"""
    print("=" * 70)
    print("DomesticAnalyzer 使用示例")
    print("=" * 70)

    # 1. 加载样本数据
    fixture_path = project_root / "tests" / "fixtures" / "domestic_sample.json"
    print(f"\n[1] 加载样本数据: {fixture_path}")
    with open(fixture_path, encoding="utf-8") as f:
        sample_data = json.load(f)
    print(f"    报告: {sample_data['report_id']}")
    print(f"    周期: {sample_data['report_period']['year']}年第{sample_data['report_period']['week']}周")

    # 2. 创建 Analyzer
    print("\n[2] 创建 DomesticAnalyzer")
    analyzer = DomesticAnalyzer(sample_data)

    # 3. 输入校验
    print("\n[3] 输入校验")
    is_valid = analyzer.validate_inputs()
    print(f"    校验结果: {'✅ 通过' if is_valid else '❌ 失败'}")
    if not is_valid:
        print(f"    缺失字段: {analyzer.missing_fields}")
        return

    # 4. 执行分析
    print("\n[4] 执行分析")
    result = analyzer.analyze()

    # 5. 输出 KPI
    print("\n[5] 关键 KPI")
    print("-" * 70)
    for key, value in result.kpis.items():
        print(f"  {key:20s}: {value}")

    # 6. 输出同比/环比分析
    print("\n[6] 同比/环比分析")
    print("-" * 70)
    print(f"  同比: {result.yoy_data['summary']}")
    print(f"  环比: {result.mom_data['summary']}")

    # 7. 输出异常
    print(f"\n[7] 异常检测 (共 {len(result.anomalies)} 个)")
    print("-" * 70)
    for a in result.anomalies:
        level_emoji = {"critical": "🔴", "warning": "🟠", "info": "🟡"}.get(a["level"], "⚪")
        print(f"  {level_emoji} [{a['level'].upper():8s}] {a['message']}")

    # 8. 输出表格
    print(f"\n[8] 表格数据 (共 {len(result.tables)} 个)")
    print("-" * 70)
    for t in result.tables:
        print(f"\n  📊 {t['title']}")
        print(f"  表头: {' | '.join(t['headers'])}")
        for row in t['rows'][:3]:
            print(f"  {' | '.join(str(c) for c in row)}")
        if len(t['rows']) > 3:
            print(f"  ... 还有 {len(t['rows']) - 3} 行")

    # 9. 输出图表
    print(f"\n[9] 图表数据 (共 {len(result.charts)} 个)")
    print("-" * 70)
    for c in result.charts:
        print(f"  📈 {c['title']} ({c['type']})")

    # 10. 输出洞察
    print(f"\n[10] 关键洞察 (共 {len(result.insights)} 条)")
    print("-" * 70)
    for i, insight in enumerate(result.insights, 1):
        print(f"  {i}. {insight}")

    # 11. 输出总结
    print("\n[11] 一句话总结")
    print("-" * 70)
    print(f"  {result.summary}")

    # 12. 输出故事
    print("\n[12] 完整业务故事")
    print("-" * 70)
    print(result.story)

    # 13. 转换为字典（用于 JSON 序列化）
    print("\n[13] 序列化为字典")
    print("-" * 70)
    result_dict = {
        "dimension": result.dimension,
        "section_ids": result.section_ids,
        "summary": result.summary,
        "kpis": result.kpis,
        "yoy_pattern": result.yoy_data.get("pattern"),
        "mom_strength": result.mom_data.get("strength"),
        "anomalies_count": len(result.anomalies),
        "tables_count": len(result.tables),
        "charts_count": len(result.charts),
        "insights_count": len(result.insights),
        "computed_at": result.computed_at,
    }
    print(f"  {json.dumps(result_dict, ensure_ascii=False, indent=2)}")

    # 14. 演示自定义配置
    print("\n[14] 演示自定义配置（严格阈值）")
    print("-" * 70)
    strict_config = {
        "thresholds": {
            "yoy_price_fen_warning": 0.5,  # 严格到 0.5 分
        }
    }
    strict_analyzer = DomesticAnalyzer(sample_data, strict_config)
    strict_result = strict_analyzer.analyze()
    print(f"  严格阈值下检测到 {len(strict_result.anomalies)} 个异常")
    for a in strict_result.anomalies[:3]:
        print(f"    - [{a['level']}] {a['message'][:80]}")

    print("\n" + "=" * 70)
    print("✅ 示例运行完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
