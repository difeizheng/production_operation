"""
Streamlit 复用组件包
====================

包含:
- kpi_card: KPI 卡片（单卡/网格/行布局）
- chart_renderer: 图表渲染（bar/pie/line）
- table_renderer: 表格渲染
- story_panel: 业务故事/总结/异常/洞察
- analyzer_panel: 通用 AnalysisResult 渲染器（核心）
- comparison_view: 双口径对比视图（v2.1 新增，v2.2 支持国内/国际）
- unit_view: 按公司拆分视图（v2.3 新增）
- market_view: 市场化维度视图（v2.4 新增）

v3.0 新增（人机协同驾驶舱）:
- stepper: 7 步导航
- data_preview: Excel 数据预览
- diff_viewer: 原文/润色对比
- slot_editor: 段位编辑器（核心）

v3.1 新增（v2/v3 路由）:
- version_badge: 视觉徽章 + 跨版本跳转
"""

__version__ = "3.1.0-phase1"

from .kpi_card import kpi_card, kpi_grid, kpi_row
from .chart_renderer import render_chart, render_charts, render_simple_bar
from .table_renderer import render_table, render_tables, render_simple_dict_table
from .story_panel import render_story, render_summary, render_anomalies, render_insights
from .analyzer_panel import render_analyzer_result
from .comparison_view import (
    render_dual_comparison,
    load_plotly_specs,
    KPI_MAPS,
    DOMESTIC_KPI_MAP,
    INTERNATIONAL_KPI_MAP,
)
from .unit_view import render_by_company
from .market_view import (
    render_market_summary_cards,
    render_market_rate_ranking,
    render_price_diff_scatter,
    render_org_quadrant_distribution,
    render_category_bucket_pie,
)

# v3.0 新增
from .stepper import (
    PIPELINE_STEPS,
    render_pipeline_stepper,
    render_stepper,
)
from .data_preview import (
    categorize_field,
    detect_anomalies,
    render_excel_preview,
    render_kpi_overview,
)
from .diff_viewer import (
    compute_diff_stats,
    extract_numbers,
    highlight_numbers,
    render_diff,
    render_diff_inline,
    render_diff_summary,
)
from .slot_editor import (
    render_params_panel,
    render_slot_editor,
)
# v3.1 新增
from .version_badge import (
    render_cross_version_link,
    render_home_hero,
    render_switch_button,
    render_v3_title_gradient,
    render_version_badge,
)

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
    # 对比视图
    "render_dual_comparison",
    "load_plotly_specs",
    "KPI_MAPS",
    "DOMESTIC_KPI_MAP",
    "INTERNATIONAL_KPI_MAP",
    # 按公司视图（v2.3）
    "render_by_company",
    # 市场化视图（v2.4）
    "render_market_summary_cards",
    "render_market_rate_ranking",
    "render_price_diff_scatter",
    "render_org_quadrant_distribution",
    "render_category_bucket_pie",
    # v3.0 新增
    "PIPELINE_STEPS",
    "render_pipeline_stepper",
    "render_stepper",
    "categorize_field",
    "detect_anomalies",
    "render_excel_preview",
    "render_kpi_overview",
    "compute_diff_stats",
    "extract_numbers",
    "highlight_numbers",
    "render_diff",
    "render_diff_inline",
    "render_diff_summary",
    "render_params_panel",
    "render_slot_editor",
    # v3.1 新增
    "render_cross_version_link",
    "render_home_hero",
    "render_switch_button",
    "render_v3_title_gradient",
    "render_version_badge",
]
