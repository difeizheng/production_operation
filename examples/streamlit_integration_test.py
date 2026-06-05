"""
Streamlit 集成测试
====================

测试 4 Analyzer 与 Streamlit 组件的集成：
- 数据加载
- 4 Analyzer 执行
- AnalysisResult 渲染

运行方式:
    PYTHONPATH=. python examples/streamlit_integration_test.py
"""

import json
import sys
from pathlib import Path

# 添加项目根到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_data_loading():
    """测试 1: 数据加载"""
    print("=" * 60)
    print("测试 1: 数据加载")
    print("=" * 60)

    from streamlit_app.utils.data_loader import load_default_data, get_report_meta

    data = load_default_data.__wrapped__()  # bypass cache
    meta = get_report_meta(data)

    print(f"  ✅ 报告: {meta.get('report_id')}")
    print(f"  ✅ 周期: {meta.get('year')} 年 {meta.get('week')} 周")
    print(f"  ✅ 字段数: {len(data)} 个顶层字段")
    print(f"  ✅ 包含字段: {list(data.keys())}")
    print()


def test_4_analyzers():
    """测试 2: 4 Analyzer 执行"""
    print("=" * 60)
    print("测试 2: 4 Analyzer 执行")
    print("=" * 60)

    from streamlit_app.utils.data_loader import load_default_data
    from src.analyzer import (
        DomesticAnalyzer, InternationalAnalyzer,
        MarketTradingAnalyzer, EnvironmentalAnalyzer,
    )

    data = load_default_data.__wrapped__()
    analyzers = {
        "domestic": DomesticAnalyzer,
        "international": InternationalAnalyzer,
        "market_trading": MarketTradingAnalyzer,
        "environmental": EnvironmentalAnalyzer,
    }

    results = {}
    for key, cls in analyzers.items():
        result = cls(data).analyze()
        results[key] = result
        print(f"  ✅ {key}: {result.dimension} - {len(result.kpis)} KPIs, {len(result.anomalies)} 异常")

    print(f"\n  📊 总计: 4 Analyzer 全部就绪")
    return results


def test_components_import():
    """测试 3: 组件导入"""
    print("=" * 60)
    print("测试 3: Streamlit 组件导入")
    print("=" * 60)

    from streamlit_app.components import (
        kpi_card, kpi_grid, kpi_row,
        render_chart, render_charts, render_simple_bar,
        render_table, render_tables, render_simple_dict_table,
        render_story, render_summary, render_anomalies, render_insights,
        render_analyzer_result,
    )

    components = [
        "kpi_card", "kpi_grid", "kpi_row",
        "render_chart", "render_charts", "render_simple_bar",
        "render_table", "render_tables", "render_simple_dict_table",
        "render_story", "render_summary", "render_anomalies", "render_insights",
        "render_analyzer_result",
    ]

    for c in components:
        print(f"  ✅ {c}")

    print(f"\n  📊 总计: {len(components)} 个组件全部可导入")
    print()


def test_analysis_result_structure():
    """测试 4: AnalysisResult 结构"""
    print("=" * 60)
    print("测试 4: AnalysisResult 结构")
    print("=" * 60)

    from streamlit_app.utils.data_loader import load_default_data
    from src.analyzer import (
        DomesticAnalyzer, InternationalAnalyzer,
        MarketTradingAnalyzer, EnvironmentalAnalyzer,
    )

    data = load_default_data.__wrapped__()

    for name, cls in [
        ("国内", DomesticAnalyzer),
        ("国际", InternationalAnalyzer),
        ("市场化", MarketTradingAnalyzer),
        ("碳资产", EnvironmentalAnalyzer),
    ]:
        result = cls(data).analyze()
        print(f"\n  【{name}】")
        print(f"    dimension: {result.dimension}")
        print(f"    section_ids: {result.section_ids}")
        print(f"    kpis: {len(result.kpis)} 个")
        print(f"    tables: {len(result.tables)} 个")
        print(f"    charts: {len(result.charts)} 个")
        print(f"    insights: {len(result.insights)} 个")
        print(f"    anomalies: {len(result.anomalies)} 个")
        print(f"    story: {len(result.story)} 字符")
        print(f"    summary: {len(result.summary)} 字符")


def test_report_generation():
    """测试 5: 报告生成"""
    print()
    print("=" * 60)
    print("测试 5: 报告生成")
    print("=" * 60)

    from streamlit_app.utils.data_loader import load_default_data, get_report_meta
    from src.analyzer import (
        DomesticAnalyzer, InternationalAnalyzer,
        MarketTradingAnalyzer, EnvironmentalAnalyzer,
    )

    data = load_default_data.__wrapped__()
    meta = get_report_meta(data)

    results = {
        "domestic": DomesticAnalyzer(data).analyze(),
        "international": InternationalAnalyzer(data).analyze(),
        "market_trading": MarketTradingAnalyzer(data).analyze(),
        "environmental": EnvironmentalAnalyzer(data).analyze(),
    }

    # 简单的报告生成
    report = f"""# 周报分析报告 - {meta.get('year')} 年 {meta.get('week')} 周

> **报告 ID**: `{meta.get('report_id')}`

## 4 维度概览

| 维度 | 关键指标 | 异常 |
|------|---------|------|
"""
    for key, result in results.items():
        first_kpi = list(result.kpis.items())[0] if result.kpis else ("—", "—")
        report += f"| {result.dimension} | {first_kpi[0]}: {first_kpi[1]} | {len(result.anomalies)} |\n"

    print(f"  ✅ 报告长度: {len(report)} 字符")
    print(f"  ✅ 报告预览（前 200 字符）:")
    print("  " + report[:200].replace("\n", "\n  "))
    print()


if __name__ == "__main__":
    print("\n🚀 Streamlit 集成测试")
    print("=" * 60)

    test_data_loading()
    test_4_analyzers()
    test_components_import()
    test_analysis_result_structure()
    test_report_generation()

    print("=" * 60)
    print("✅ 全部集成测试通过")
    print("=" * 60)
    print()
    print("🚀 现在可以运行:")
    print("    PYTHONPATH=. streamlit run streamlit_app/app.py")
    print()
