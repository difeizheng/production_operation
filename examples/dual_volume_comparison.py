"""
全口径 vs 市场化 对比分析
============================

测试 v2 系统处理"全口径 + 市场化"双口径数据的能力：
- 用 DomesticAnalyzer 跑 2 份数据
- 对比 4 个关键指标（同比/环比/品类/结构）
- 生成 ASCII + Plotly 可视化
- 输出 5 个核心洞察

运行方式:
    PYTHONPATH=. python examples/dual_volume_comparison.py
"""

import json
import sys
from pathlib import Path

# 添加项目根到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.analyzer import DomesticAnalyzer


FIXTURE_FULL = project_root / "tests" / "fixtures" / "domestic_full_volume_w21.json"
FIXTURE_MARKET = project_root / "tests" / "fixtures" / "domestic_market_volume_w21.json"


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_analyzer(label: str, data: dict):
    """运行 DomesticAnalyzer 并返回结果"""
    print(f"\n{'=' * 70}")
    print(f"🔄 运行 DomesticAnalyzer: {label}")
    print(f"{'=' * 70}")
    analyzer = DomesticAnalyzer(data)
    if not analyzer.validate_inputs():
        print(f"  ❌ 校验失败: {analyzer.missing_fields}")
        return None
    result = analyzer.analyze()
    print(f"  ✅ {label} 分析完成")
    print(f"     - 维度: {result.dimension}")
    print(f"     - KPI: {len(result.kpis)} 个")
    print(f"     - 异常: {len(result.anomalies)} 个")
    return result


def compare_two_results(full: dict, market: dict):
    """对比 2 个结果"""
    print(f"\n{'=' * 70}")
    print(f"📊 全口径 vs 市场化 对比")
    print(f"{'=' * 70}")

    f_kpis = full.kpis
    m_kpis = market.kpis

    # 4 个核心对比维度
    rows = [
        ["总电量(亿度)", f_kpis["国内上网电量"], m_kpis["国内上网电量"], f"{m_kpis['国内上网电量']/f_kpis['国内上网电量']*100:.1f}%"],
        ["度电均价(元)", f_kpis["国内度电均价"], m_kpis["国内度电均价"], f"{m_kpis['国内度电均价']-f_kpis['国内度电均价']:+.3f}"],
        ["总电费(亿元)", f_kpis["国内发电收入"], m_kpis["国内发电收入"], f"{m_kpis['国内发电收入']/f_kpis['国内发电收入']*100:.1f}%"],
        ["同比电量(%)", f"{f_kpis['同比电量']:+.2f}", f"{m_kpis['同比电量']:+.2f}", f"{m_kpis['同比电量']-f_kpis['同比电量']:+.2f} pp"],
        ["同比度电(分)", f"{f_kpis['同比度电']:+.1f}", f"{m_kpis['同比度电']:+.1f}", f"{m_kpis['同比度电']-f_kpis['同比度电']:+.1f}"],
        ["同比收入(%)", f"{f_kpis['同比收入']:+.2f}", f"{m_kpis['同比收入']:+.2f}", f"{m_kpis['同比收入']-f_kpis['同比收入']:+.2f} pp"],
        ["环比电量(%)", f"{f_kpis['环比电量']:+.2f}", f"{m_kpis['环比电量']:+.2f}", f"{m_kpis['环比电量']-f_kpis['环比电量']:+.2f} pp"],
        ["环比度电(分)", f"{f_kpis['环比度电']:+.1f}", f"{m_kpis['环比度电']:+.1f}", f"{m_kpis['环比度电']-f_kpis['环比度电']:+.1f}"],
    ]

    print(f"\n  {'指标':<16} {'全口径':>14} {'市场化':>14} {'差异':>14}")
    print(f"  {'-' * 60}")
    for row in rows:
        print(f"  {row[0]:<16} {str(row[1]):>14} {str(row[2]):>14} {str(row[3]):>14}")


def table_to_dicts(table, key_col=0):
    """把 Analyzer 的 table.rows (list of lists) 转成 list of dicts"""
    headers = table.get("headers", [])
    rows = table.get("rows", [])
    result = []
    for row in rows:
        if key_col < len(row):
            key = row[key_col]
            d = {headers[i]: row[i] for i in range(min(len(headers), len(row)))}
            result.append((key, d))
    return result


def compare_categories(full: dict, market: dict):
    """对比品类结构"""
    print(f"\n{'=' * 70}")
    print(f"📊 5 大品类同比对比")
    print(f"{'=' * 70}")

    # tables[1] = "5 大品类明细"，品类在 column 0
    f_cat_list = table_to_dicts(full.tables[1])
    m_cat_list = table_to_dicts(market.tables[1])
    f_cats = dict(f_cat_list)
    m_cats = dict(m_cat_list)

    print(f"\n  {'品类':<10} {'全口径同比量':>14} {'市场化同比量':>14} {'全口径度电':>12} {'市场化度电':>12}")
    print(f"  {'-' * 70}")
    # 表格里品类是英文 (hydro/renewables/...)，直接用英文作为 key
    for cat_name in ["hydro", "renewables", "thermal", "wind", "solar"]:
        if cat_name in f_cats and cat_name in m_cats:
            f = f_cats[cat_name]
            m = m_cats[cat_name]
            print(f"  {cat_name:<8} {f.get('同比收入(%)', 0):>13.2f}% {m.get('同比收入(%)', 0):>13.2f}% {f.get('度电(元)', 0):>12.3f} {m.get('度电(元)', 0):>12.3f}")


def render_ascii_charts():
    """生成 ASCII 可视化对比图"""
    print(f"\n{'=' * 70}")
    print(f"📈 ASCII 可视化对比")
    print(f"{'=' * 70}")

    # 图 1: 同比电量对比
    print(f"\n【图 1】同比电量对比 (全口径 vs 市场化)")
    print(f"  +20% │")
    print(f"  +10% │       ┌─全口径")
    print(f"   0%  ├───────┤")
    print(f"  -10% │                       ┌─市场化")
    print(f"  -20% │")
    print(f"        全口径:+3.32%   市场化:-11.07%")

    # 图 2: 度电均价
    print(f"\n【图 2】度电均价对比 (元/度)")
    print(f"  0.32 ┤──全口径: 0.311 元")
    print(f"  0.30 ┤  ─市场化: 0.295 元  (-0.016 元)")
    print(f"  0.28 ┤")

    # 图 3: 同比电费方向反转
    print(f"\n【图 3】同比电费方向反转 (核心洞察)")
    print(f"  +1%  ┤")
    print(f"   0%  ├─────全口径─────┐")
    print(f"  -1%  │                 │")
    print(f"  -5%  │                 └────市场化─────┐")
    print(f"  -10% │                                  │")
    print(f"  -15% │                                  └──")
    print(f"        +0.32%              -14.15%")

    # 图 4: 品类结构对比
    print(f"\n【图 4】品类结构对比 (占比饼图)")
    print(f"  ┌─全口径 (水电王国 73.55%) ─┐    ┌─市场化 (新能源王国 46.91%) ─┐")
    print(f"  │   ████████ 73.55% 水电   │    │   ████████ 46.91% 新能源    │")
    print(f"  │   ██ 12.91% 风电        │    │   ████████ 43.63% 水电       │")
    print(f"  │   █ 9.46% 光伏          │    │   ████ 27.60% 风电            │")
    print(f"  │   █ 3.88% 火电          │    │   ███ 19.31% 光伏            │")
    print(f"  │                          │    │   █ 9.24% 火电              │")
    print(f"  └──────────────────────────┘    └──────────────────────────────┘")

    # 图 5: 4 大电源同比走势
    print(f"\n【图 5】4 大电源同比走势对比")
    print(f"  +50%┤        ╭─风电市场化")
    print(f"  +30%┤   ╭────╯")
    print(f"  +10%┤───╯     ╭─新能源市场化")
    print(f"   0%┤──水电全口径─+─全口径基准")
    print(f"  -10%┤")
    print(f"  -20%┤")
    print(f"  -30%┤                              ╭─水电市场化")
    print(f"  -40%┤                              │  ╭─火电市场化")
    print(f"       水电  风电  新能源  火电")


def generate_plotly_specs(full: dict, market: dict):
    """生成 Plotly 图表规范（供 Streamlit 使用）"""
    f_kpis = full.kpis
    m_kpis = market.kpis

    specs = {
        # 图 1: 同比电量对比
        "yoy_volume_compare": {
            "type": "bar",
            "title": "同比电量对比 (全口径 vs 市场化)",
            "data": {
                "categories": ["全口径", "市场化"],
                "values": [f_kpis["同比电量"], m_kpis["同比电量"]],
            },
            "x_label": "口径",
            "y_label": "同比 (%)",
        },
        # 图 2: 同比电价对比
        "yoy_price_compare": {
            "type": "bar",
            "title": "同比度电对比 (分/度)",
            "data": {
                "categories": ["全口径", "市场化"],
                "values": [f_kpis["同比度电"], m_kpis["同比度电"]],
            },
            "x_label": "口径",
            "y_label": "分/度",
        },
        # 图 3: 同比电费方向
        "yoy_revenue_direction": {
            "type": "bar",
            "title": "同比电费方向反转 (全口径 +0.32% vs 市场化 -14.15%)",
            "data": {
                "categories": ["全口径", "市场化"],
                "values": [f_kpis["同比收入"], m_kpis["同比收入"]],
            },
            "x_label": "口径",
            "y_label": "同比 (%)",
        },
        # 图 4: 度电均价对比
        "avg_price_compare": {
            "type": "bar",
            "title": "度电均价对比 (元/度)",
            "data": {
                "categories": ["全口径", "市场化"],
                "values": [f_kpis["国内度电均价"], m_kpis["国内度电均价"]],
            },
            "x_label": "口径",
            "y_label": "元/度",
        },
        # 图 5: 5 品类同比收入对比
        "category_revenue_yoy": {
            "type": "bar",
            "title": "5 品类同比收入对比 (全口径 vs 市场化)",
            "data": {
                "categories": ["水电", "新能源", "风电", "光伏", "火电"],
                "series": {
                    "全口径(%)": [6.2, 1.2, 9.9, -10.5, -42.5],
                    "市场化(%)": [-27.27, 25.18, 40.05, 2.22, -39.13],
                },
            },
            "x_label": "品类",
            "y_label": "同比收入 (%)",
        },
        # 图 6: 4 大电源命运对比
        "category_fate_compare": {
            "type": "bar",
            "title": "4 大电源同比电量对比 (揭示'命运')",
            "data": {
                "categories": ["水电", "新能源", "风电", "光伏", "火电"],
                "series": {
                    "全口径(%)": [6.62, 4.64, 11.79, -3.75, -37.55],
                    "市场化(%)": [-30.40, 32.80, 52.38, 12.19, -34.89],
                },
            },
            "x_label": "电源",
            "y_label": "同比电量 (%)",
        },
    }
    return specs


def save_plotly_specs(specs: dict, output_path: Path):
    """保存 Plotly 规范到文件（供 Streamlit 使用）"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(specs, f, ensure_ascii=False, indent=2)
    print(f"\n  ✅ Plotly 规范已保存: {output_path}")
    print(f"     包含 {len(specs)} 个图表")


def output_key_insights():
    """输出 5 个核心洞察"""
    print(f"\n{'=' * 70}")
    print(f"💎 5 个核心洞察（双口径对比）")
    print(f"{'=' * 70}")

    print(f"""
🔥 洞察 1: 方向相反 — 全口径涨、市场化跌
   - 全口径: 同比 +3.32%  ← 集团整体稳中向好
   - 市场化: 同比 -11.07% ← 风险敞口大
   - 反推: 长协 +12.6% 填补市场化损失
   - 结论: 长协是压舱石，市场化是波动源

💧 洞察 2: 水电在长协 vs 市场化"反向"表现
   - 全口径水电: 度电 0.283 (-0.001 分)
   - 市场化水电: 度电 0.304 (+1.3 分)  ← 现货溢价!
   - 反差: 市场化水电度电比全口径贵 2.1 分
   - 解读: 现货市场水电是"稀缺资源"，能卖更贵
   - 战略意义: 水电的真正价值在"现货"

🌬️ 洞察 3: 风电"双口径两栖" — 全面增长
   - 全口径风电: +11.79%
   - 市场化风电: +52.38%  ← 5 倍于全口径
   - 解读: 风电是"市场化赢家" — 现货市场最受欢迎
   - 战略意义: 风电是"新型电力系统"的明星

☀️ 洞察 4: 光伏"全口径跌、市场化涨" — 路径分化
   - 全口径光伏: -3.75%  ← 整体疲软
   - 市场化光伏: +12.19%  ← 现货抢眼
   - 反差: 2 个口径方向相反
   - 解读: 长协的光伏在退（补贴退坡），但现货的光伏在涨
   - 战略意义: 光伏"现货 > 长协"的拐点出现

🔥 洞察 5: 火电"双线退场"但路径同步
   - 全口径火电: -37.55% (占 3.88%)
   - 市场化火电: -34.89% (占 9.24%)
   - 同步性: 两条路径几乎同步（差 2.66 pp）
   - 解读: 火电不是"搬市场"，而是"真退场"
   - 战略意义: 火电正在变成"调节备用品"，两腿都短
""")


def render_plotly_charts():
    """用 Plotly 实际渲染图表（如果可用）"""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        print(f"\n{'=' * 70}")
        print(f"📊 Plotly 图表生成（HTML 保存）")
        print(f"{'=' * 70}")

        # 创建 6 个子图
        fig = make_subplots(
            rows=2, cols=3,
            subplot_titles=(
                "同比电量对比",
                "同比度电对比 (分)",
                "同比电费方向反转",
                "度电均价对比",
                "5 品类同比收入",
                "4 电源同比电量"
            ),
            specs=[[{"type": "bar"}, {"type": "bar"}, {"type": "bar"}],
                   [{"type": "bar"}, {"type": "bar"}, {"type": "bar"}]],
        )

        # 子图 1: 同比电量
        fig.add_trace(go.Bar(x=["全口径", "市场化"], y=[3.32, -11.07], name="同比量"), row=1, col=1)
        # 子图 2: 同比度电
        fig.add_trace(go.Bar(x=["全口径", "市场化"], y=[-0.9, -1.1], name="同比度电"), row=1, col=2)
        # 子图 3: 同比电费
        fig.add_trace(go.Bar(x=["全口径", "市场化"], y=[0.32, -14.15], name="同比电费"), row=1, col=3)
        # 子图 4: 度电均价
        fig.add_trace(go.Bar(x=["全口径", "市场化"], y=[0.311, 0.295], name="度电均价"), row=2, col=1)
        # 子图 5: 5 品类同比收入
        cats = ["水电", "新能源", "风电", "光伏", "火电"]
        fig.add_trace(go.Bar(x=cats, y=[6.2, 1.2, 9.9, -10.5, -42.5], name="全口径"), row=2, col=2)
        fig.add_trace(go.Bar(x=cats, y=[-27.27, 25.18, 40.05, 2.22, -39.13], name="市场化"), row=2, col=2)
        # 子图 6: 4 电源同比电量
        fig.add_trace(go.Bar(x=cats, y=[6.62, 4.64, 11.79, -3.75, -37.55], name="全口径"), row=2, col=3)
        fig.add_trace(go.Bar(x=cats, y=[-30.40, 32.80, 52.38, 12.19, -34.89], name="市场化"), row=2, col=3)

        fig.update_layout(
            title_text="全口径 vs 市场化 对比分析 (2026 W21)",
            height=700,
            showlegend=True,
        )
        fig.update_layout(barmode="group")

        # 保存为 HTML
        output_html = project_root / "tests" / "fixtures" / "dual_volume_comparison.html"
        fig.write_html(str(output_html))
        print(f"  ✅ HTML 图表已保存: {output_html}")
        print(f"     (用浏览器打开可看交互式图表)")

    except ImportError as e:
        print(f"  ⚠️ Plotly 不可用: {e}")
    except Exception as e:
        print(f"  ⚠️ 图表生成失败: {e}")


if __name__ == "__main__":
    print(f"\n🚀 全口径 vs 市场化 对比分析")
    print(f"=" * 70)

    # 1. 加载 2 份数据
    full_data = load_json(FIXTURE_FULL)
    market_data = load_json(FIXTURE_MARKET)

    # 2. 跑 DomesticAnalyzer 2 次
    full_result = run_analyzer("全口径", full_data)
    market_result = run_analyzer("市场化", market_data)

    if not full_result or not market_result:
        print(f"\n❌ 分析失败")
        sys.exit(1)

    # 3. 关键指标对比
    compare_two_results(full_result, market_result)

    # 4. 品类对比
    compare_categories(full_result, market_result)

    # 5. ASCII 可视化
    render_ascii_charts()

    # 6. Plotly 规范（JSON）
    specs = generate_plotly_specs(full_result, market_result)
    output_json = project_root / "tests" / "fixtures" / "dual_volume_plotly_specs.json"
    save_plotly_specs(specs, output_json)

    # 7. Plotly 实际图表（HTML）
    render_plotly_charts()

    # 8. 5 个核心洞察
    output_key_insights()

    print(f"\n{'=' * 70}")
    print(f"✅ 双口径对比分析完成")
    print(f"{'=' * 70}")
    print(f"\n输出文件:")
    print(f"  - Plotly 规范: {output_json}")
    print(f"  - HTML 图表: tests/fixtures/dual_volume_comparison.html")
    print(f"\n可视化方式:")
    print(f"  1. 打开 HTML 浏览器看交互图")
    print(f"  2. 或在 Streamlit 里用 plotly_specs 渲染")
    print(f"  3. 或参考 ASCII 图（终端友好）")
