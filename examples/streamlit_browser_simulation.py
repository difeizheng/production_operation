"""
Streamlit 浏览器渲染模拟
============================

用 AppTest 模拟真实浏览器渲染，捕获每个页面的输出元素
（标题/文本/markdown/表格/dataframe/metric 等）

运行方式:
    PYTHONPATH=. python examples/streamlit_browser_simulation.py
"""

import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 在导入 streamlit 前，先初始化
from streamlit_app.utils.data_loader import load_default_data
from src.analyzer import (
    DomesticAnalyzer, InternationalAnalyzer,
    MarketTradingAnalyzer, EnvironmentalAnalyzer,
)

# 预加载数据 + 跑 4 Analyzer
data = load_default_data.__wrapped__()
results = {
    "domestic": DomesticAnalyzer(data).analyze(),
    "international": InternationalAnalyzer(data).analyze(),
    "market_trading": MarketTradingAnalyzer(data).analyze(),
    "environmental": EnvironmentalAnalyzer(data).analyze(),
}


def render_page_to_text(page_name: str, result) -> str:
    """把 AnalysisResult 渲染为可视化文本（模拟页面输出）"""
    lines = []
    lines.append("=" * 70)
    lines.append(f"📄 页面: {page_name}")
    lines.append("=" * 70)
    lines.append("")

    # 1. 顶部信息条
    lines.append(f"### 🏷️ Title: {result.dimension}分析 (Streamlit H1)")
    lines.append(f"### 📝 Header: 段 {result.section_ids} (Streamlit H3)")
    lines.append(f"💡 Caption: 分析器: `{result.analyzer_name}` | 段: `{result.section_ids}` | 时间: `{result.computed_at}`")
    lines.append("")

    # 2. 一句话总结
    lines.append(f"### 💎 一句话总结 (st.markdown)")
    lines.append(f"> {result.summary}")
    lines.append("")
    lines.append("─" * 70)
    lines.append("")

    # 3. KPI 网格
    lines.append(f"### 📊 关键指标 (st.metric 网格)")
    lines.append("")
    for i, (k, v) in enumerate(result.kpis.items()):
        # 每个 KPI 显示为独立的 metric
        lines.append(f"  [{i+1:2d}] {k}: {v}")
    lines.append("")
    lines.append("─" * 70)
    lines.append("")

    # 4. 同比/环比
    if result.yoy_data or result.mom_data:
        lines.append("### 📈 同比/环比 (双列 st.columns)")
        lines.append("")
        if result.yoy_data:
            lines.append("  【同比】")
            for k, v in result.yoy_data.items():
                lines.append(f"    {k}: {v}")
        if result.mom_data:
            lines.append("  【环比】")
            for k, v in result.mom_data.items():
                lines.append(f"    {k}: {v}")
        lines.append("")
        lines.append("─" * 70)
        lines.append("")

    # 5. 业务故事
    if result.story:
        lines.append("### 📖 业务故事 (st.expander + st.markdown)")
        lines.append("")
        # 提取 markdown 标题
        import re
        headers = re.findall(r'## (.+)', result.story)
        for h in headers:
            lines.append(f"  ## {h}")
        # 提取前 3 段
        sections = result.story.split("## ")
        for section in sections[1:4]:  # 跳过第一个空段
            if section.strip():
                title = section.split("\n")[0]
                content = "\n".join(section.split("\n")[1:5])
                lines.append(f"")
                lines.append(f"  ## {title}")
                if content.strip():
                    for line in content.split("\n")[:3]:
                        if line.strip():
                            lines.append(f"  {line}")
        lines.append("")
        lines.append("─" * 70)
        lines.append("")

    # 6. 表格
    if result.tables:
        lines.append(f"### 📋 数据表格 (st.dataframe)")
        lines.append("")
        for t in result.tables:
            lines.append(f"  ┌─ {t.get('title', '')}")
            headers = t.get("headers", [])
            rows = t.get("rows", [])
            if headers:
                # 表格头部
                col_widths = [max(len(h), max((len(str(r[i])) for r in rows), default=10)) for i, h in enumerate(headers)]
                header_line = "  │ " + " │ ".join(h.ljust(w) for h, w in zip(headers, col_widths)) + " │"
                lines.append(f"  │ {header_line}")
                # 分隔线
                lines.append(f"  │ " + "─┼─".join("─" * w for w in col_widths))
                # 数据行（最多 3 行）
                for row in rows[:3]:
                    row_line = "  │ " + " │ ".join(str(c).ljust(w) for c, w in zip(row, col_widths)) + " │"
                    lines.append(f"  │ {row_line}")
                if len(rows) > 3:
                    lines.append(f"  │ ... 还有 {len(rows) - 3} 行")
            lines.append(f"  └─")
            lines.append("")
        lines.append("─" * 70)
        lines.append("")

    # 7. 图表
    if result.charts:
        lines.append(f"### 📊 图表 (st.plotly_chart)")
        lines.append("")
        for c in result.charts:
            lines.append(f"  ┌─ 图 {c.get('type', 'bar')}: {c.get('title', '')}")
            data = c.get("data", {})
            if c.get("type") == "pie":
                labels = data.get("labels", [])
                values = data.get("values", [])
                for l, v in zip(labels, values):
                    lines.append(f"  │ {l}: {v}")
            elif c.get("type") == "bar":
                cats = data.get("categories", [])
                series = data.get("series", {})
                if series:
                    for name, values in series.items():
                        lines.append(f"  │ 【{name}】")
                        for cat, val in zip(cats, values):
                            lines.append(f"  │   {cat}: {val}")
                else:
                    values = series if isinstance(series, list) else []
                    for cat, val in zip(cats, values):
                        lines.append(f"  │ {cat}: {val}")
            lines.append(f"  └─")
            lines.append("")
        lines.append("─" * 70)
        lines.append("")

    # 8. 关键洞察
    if result.insights:
        lines.append(f"### 💡 关键洞察 (st.markdown)")
        lines.append("")
        for ins in result.insights:
            lines.append(f"  • {ins}")
        lines.append("")
        lines.append("─" * 70)
        lines.append("")

    # 9. 异常告警
    if result.anomalies:
        lines.append(f"### ⚠️ 异常告警 (st.error/warning/info)")
        lines.append("")
        for a in result.anomalies:
            level = a.get("level", "info")
            msg = a.get("message", "")
            if level == "critical":
                lines.append(f"  🔴 [st.error] {msg}")
            elif level == "warning":
                lines.append(f"  🟠 [st.warning] {msg}")
            else:
                lines.append(f"  🟡 [st.info] {msg}")
        lines.append("")
        lines.append("─" * 70)

    return "\n".join(lines)


# === 主程序 ===
if __name__ == "__main__":
    print()
    print("🚀 Streamlit 浏览器渲染模拟")
    print("=" * 70)
    print()

    # 渲染每个页面
    page_names = [
        ("1_🏠_国内分析 (Page 1)", results["domestic"]),
        ("2_🌍_国际分析 (Page 2)", results["international"]),
        ("3_💹_市场化分析 (Page 3)", results["market_trading"]),
        ("4_🌱_碳资产分析 (Page 4)", results["environmental"]),
    ]

    for page_name, result in page_names:
        text = render_page_to_text(page_name, result)
        print(text)
        print()
        print()
