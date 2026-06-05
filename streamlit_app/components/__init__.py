"""
Streamlit 复用组件包
====================

包含:
- kpi_card: KPI 卡片（单卡/网格/行布局）
- chart_renderer: 图表渲染（bar/pie/line）
- table_renderer: 表格渲染
- story_panel: 业务故事/总结/异常/洞察
- analyzer_panel: 通用 AnalysisResult 渲染器（核心）
"""

__version__ = "2.0.0-phase5"

from .kpi_card import kpi_card, kpi_grid, kpi_row
from .chart_renderer import render_chart, render_charts, render_simple_bar
from .table_renderer import render_table, render_tables, render_simple_dict_table
from .story_panel import render_story, render_summary, render_anomalies, render_insights
from .analyzer_panel import render_analyzer_result

__all__ = [
    # KPI
    "kpi_card",
    "kpi_grid",
    "kpi_row",
    # 图表
    "render_chart",
    "render_charts",
    "render_simple_bar",
    # 表格
    "render_table",
    "render_tables",
    "render_simple_dict_table",
    # 故事
    "render_story",
    "render_summary",
    "render_anomalies",
    "render_insights",
    # 通用渲染
    "render_analyzer_result",
]
