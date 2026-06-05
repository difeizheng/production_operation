"""Excel 单元格映射表 - 综合分析表 → 文档字段

本模块定义了综合分析报表.xlsx中"综合分析表"sheet的单元格到文档字段的映射。

列映射（综合分析表）：
    C = 水电, D = 新能源, E = 风电, F = 光伏, G = 火电, H = 储能, I = 合计

行映射（综合分析表）：
    国内数据：
        Row 4-7:   本周数据（电量、电量占比、电价、电费）
        Row 8-11:  去年本周数据
        Row 12-15: 上周数据
        Row 16-26: 同比分析
        Row 27-37: 环比分析
    国际数据：
        Row 39-74: 国际数据（结构同国内）
    报告表1：
        Row 76-86: 已转换单位的报告数据（亿千瓦时/亿元）

数据来源：周例会营销发言材料（数据模板）0602.docx 中的标注
    如 [综合分析表I4/10000] 表示 I4 单元格的值除以 10000
"""

from typing import Dict, Tuple, Optional, Any


# 类型别名
CellRef = Tuple[str, int]  # (列字母, 行号)

# ============================================================================
# 核心映射表：字段名 → (列, 行)
# ============================================================================
CELL_MAP: Dict[str, CellRef] = {
    # ==========================================================================
    # 国内全口径数据分析（Row 4-37）
    # ==========================================================================

    # --- 本周数据 (Rows 4-7) ---
    "dom.electricity.total":        ("I", 4),    # 合计电量（万千瓦时）
    "dom.electricity.hydro":        ("C", 4),    # 水电电量
    "dom.electricity.new_energy":   ("D", 4),    # 新能源电量
    "dom.electricity.wind":         ("E", 4),    # 风电电量
    "dom.electricity.solar":        ("F", 4),    # 光伏电量
    "dom.electricity.thermal":      ("G", 4),    # 火电电量
    "dom.electricity.storage":      ("H", 4),    # 储能电量

    "dom.share.total":              ("I", 5),    # 合计电量占比
    "dom.share.hydro":              ("C", 5),    # 水电占比
    "dom.share.new_energy":         ("D", 5),    # 新能源占比
    "dom.share.wind":               ("E", 5),    # 风电占比
    "dom.share.solar":              ("F", 5),    # 光伏占比
    "dom.share.thermal":            ("G", 5),    # 火电占比

    "dom.price.total":              ("I", 6),    # 合计电价（元/千瓦时）
    "dom.price.hydro":              ("C", 6),
    "dom.price.new_energy":         ("D", 6),
    "dom.price.wind":               ("E", 6),
    "dom.price.solar":              ("F", 6),
    "dom.price.thermal":            ("G", 6),

    "dom.revenue.total":            ("I", 7),    # 合计电费（万元）
    "dom.revenue.hydro":            ("C", 7),
    "dom.revenue.new_energy":       ("D", 7),
    "dom.revenue.wind":             ("E", 7),
    "dom.revenue.solar":            ("F", 7),
    "dom.revenue.thermal":          ("G", 7),

    # --- 去年本周数据 (Rows 8-11) ---
    "dom.prev_year_electricity.total":  ("I", 8),
    "dom.prev_year_electricity.hydro":  ("C", 8),
    "dom.prev_year_electricity.new_energy": ("D", 8),
    "dom.prev_year_electricity.wind":   ("E", 8),
    "dom.prev_year_electricity.solar":  ("F", 8),
    "dom.prev_year_electricity.thermal": ("G", 8),

    "dom.prev_year_share.hydro":    ("C", 9),
    "dom.prev_year_share.new_energy": ("D", 9),

    "dom.prev_year_price.total":    ("I", 10),
    "dom.prev_year_price.hydro":    ("C", 10),
    "dom.prev_year_price.new_energy": ("D", 10),

    "dom.prev_year_revenue.total":  ("I", 11),

    # --- 上周数据 (Rows 12-15) ---
    "dom.last_week_electricity.total":  ("I", 12),
    "dom.last_week_electricity.hydro":  ("C", 12),
    "dom.last_week_electricity.new_energy": ("D", 12),
    "dom.last_week_electricity.wind":   ("E", 12),
    "dom.last_week_electricity.solar":  ("F", 12),
    "dom.last_week_electricity.thermal": ("G", 12),

    "dom.last_week_share.hydro":    ("C", 13),
    "dom.last_week_share.new_energy": ("D", 13),

    "dom.last_week_price.total":    ("I", 14),
    "dom.last_week_price.hydro":    ("C", 14),
    "dom.last_week_price.new_energy": ("D", 14),

    "dom.last_week_revenue.total":  ("I", 15),

    # --- 同比分析 (Rows 16-26) ---
    "dom.yoy.electricity.total":        ("I", 17),  # 电量同比变化率
    "dom.yoy.electricity.hydro":        ("C", 17),
    "dom.yoy.electricity.new_energy":   ("D", 17),
    "dom.yoy.electricity.wind":         ("E", 17),
    "dom.yoy.electricity.solar":        ("F", 17),
    "dom.yoy.electricity.thermal":      ("G", 17),

    "dom.yoy.revenue_change.total":      ("I", 19),  # 电费同比变化额（万元，绝对值）
    "dom.yoy.revenue_change.hydro":      ("C", 19),
    "dom.yoy.revenue_change.new_energy": ("D", 19),

    "dom.yoy.price_change.total":       ("I", 21),  # 电价变化（元/千瓦时）
    "dom.yoy.price_change.hydro":       ("C", 21),
    "dom.yoy.price_change.new_energy":  ("D", 21),
    "dom.yoy.price_change.wind":        ("E", 21),
    "dom.yoy.price_change.solar":       ("F", 21),
    "dom.yoy.price_change.thermal":     ("G", 21),

    "dom.yoy.share_change.hydro":       ("C", 22),  # 电量占比变化
    "dom.yoy.share_change.new_energy":  ("D", 22),
    "dom.yoy.share_change.wind":        ("E", 22),
    "dom.yoy.share_change.solar":       ("F", 22),
    "dom.yoy.share_change.thermal":     ("G", 22),

    "dom.yoy.price_impact.total":       ("I", 23),  # 电价变化影响电价
    "dom.yoy.price_impact.hydro":       ("C", 23),
    "dom.yoy.price_impact.new_energy":  ("D", 23),

    "dom.yoy.share_impact.total":       ("I", 24),  # 电量占比变化影响电价
    "dom.yoy.share_impact.hydro":       ("C", 24),
    "dom.yoy.share_impact.new_energy":  ("D", 24),

    "dom.yoy.cross_impact.total":       ("I", 25),  # 交叉影响

    "dom.yoy.combined_impact.hydro":        ("C", 26),  # 量价合计影响
    "dom.yoy.combined_impact.new_energy":   ("D", 26),
    "dom.yoy.combined_impact.wind":         ("E", 26),
    "dom.yoy.combined_impact.solar":        ("F", 26),
    "dom.yoy.combined_impact.thermal":      ("G", 26),

    # --- 环比分析 (Rows 27-37) ---
    "dom.wow.electricity.total":        ("I", 28),  # 电量环比变化率
    "dom.wow.electricity.hydro":        ("C", 28),
    "dom.wow.electricity.new_energy":   ("D", 28),
    "dom.wow.electricity.wind":         ("E", 28),
    "dom.wow.electricity.solar":        ("F", 28),
    "dom.wow.electricity.thermal":      ("G", 28),

    "dom.wow.revenue_change.total":      ("I", 30),  # 电费环比变化额（万元，绝对值）
    "dom.wow.revenue_change.hydro":      ("C", 30),
    "dom.wow.revenue_change.new_energy": ("D", 30),

    "dom.wow.price_change.total":       ("I", 32),  # 电价环比变化
    "dom.wow.price_change.hydro":       ("C", 32),
    "dom.wow.price_change.new_energy":  ("D", 32),
    "dom.wow.price_change.wind":        ("E", 32),
    "dom.wow.price_change.solar":       ("F", 32),
    "dom.wow.price_change.thermal":     ("G", 32),

    "dom.wow.share_change.hydro":       ("C", 33),  # 电量占比环比变化
    "dom.wow.share_change.new_energy":  ("D", 33),
    "dom.wow.share_change.wind":        ("E", 33),
    "dom.wow.share_change.solar":       ("F", 33),
    "dom.wow.share_change.thermal":     ("G", 33),

    "dom.wow.price_impact.total":       ("I", 34),
    "dom.wow.price_impact.hydro":       ("C", 34),
    "dom.wow.price_impact.new_energy":  ("D", 34),

    "dom.wow.share_impact.total":       ("I", 35),
    "dom.wow.share_impact.hydro":       ("C", 35),
    "dom.wow.share_impact.new_energy":  ("D", 35),

    "dom.wow.cross_impact.total":       ("I", 36),

    "dom.wow.combined_impact.hydro":        ("C", 37),
    "dom.wow.combined_impact.new_energy":   ("D", 37),
    "dom.wow.combined_impact.wind":         ("E", 37),
    "dom.wow.combined_impact.solar":        ("F", 37),
    "dom.wow.combined_impact.thermal":      ("G", 37),

    # ==========================================================================
    # 国际数据分析（Row 39-74）
    # ==========================================================================
    "intl.electricity.total":        ("I", 41),
    "intl.electricity.hydro":        ("C", 41),
    "intl.electricity.new_energy":   ("D", 41),
    "intl.electricity.wind":         ("E", 41),
    "intl.electricity.solar":        ("F", 41),

    "intl.price.total":              ("I", 43),
    "intl.revenue.total":            ("I", 44),

    "intl.prev_year_electricity.total": ("I", 45),
    "intl.prev_year_price.total":       ("I", 47),

    "intl.last_week_electricity.total": ("I", 49),
    "intl.last_week_price.total":       ("I", 51),

    "intl.yoy.electricity.total":       ("I", 54),
    "intl.yoy.price_change.total":      ("I", 58),
    "intl.yoy.price_impact.total":      ("I", 60),
    "intl.yoy.share_impact.total":      ("I", 61),

    "intl.wow.electricity.total":       ("I", 65),
    "intl.wow.price_change.total":      ("I", 69),
    "intl.wow.price_impact.total":      ("I", 71),
    "intl.wow.share_impact.total":      ("I", 72),

    # ==========================================================================
    # 报告表1（Row 76-86，已转换单位：亿千瓦时、亿元）
    # ==========================================================================
    # 国内上网电量
    "report.electricity.total":      ("I", 78),
    "report.electricity.hydro":      ("C", 78),
    "report.electricity.new_energy": ("D", 78),
    "report.electricity.wind":       ("E", 78),
    "report.electricity.solar":      ("F", 78),
    "report.electricity.thermal":    ("G", 78),

    # 同比
    "report.yoy_electricity.total":  ("I", 79),
    "report.yoy_electricity.hydro":  ("C", 79),
    "report.yoy_electricity.new_energy": ("D", 79),
    "report.yoy_electricity.wind":   ("E", 79),
    "report.yoy_electricity.solar":  ("F", 79),
    "report.yoy_electricity.thermal": ("G", 79),

    # 环比
    "report.wow_electricity.total":  ("I", 80),
    "report.wow_electricity.hydro":  ("C", 80),
    "report.wow_electricity.new_energy": ("D", 80),
    "report.wow_electricity.wind":   ("E", 80),
    "report.wow_electricity.solar":  ("F", 80),
    "report.wow_electricity.thermal": ("G", 80),

    # 国内上网电价
    "report.price.total":            ("I", 81),
    "report.price.hydro":            ("C", 81),
    "report.price.new_energy":       ("D", 81),
    "report.price.wind":             ("E", 81),
    "report.price.solar":            ("F", 81),
    "report.price.thermal":          ("G", 81),

    # 电价同比
    "report.yoy_price.total":        ("I", 82),
    "report.yoy_price.hydro":        ("C", 82),
    "report.yoy_price.new_energy":   ("D", 82),
    "report.yoy_price.wind":         ("E", 82),
    "report.yoy_price.solar":        ("F", 82),
    "report.yoy_price.thermal":      ("G", 82),

    # 电价环比
    "report.wow_price.total":        ("I", 83),
    "report.wow_price.hydro":        ("C", 83),
    "report.wow_price.new_energy":   ("D", 83),
    "report.wow_price.wind":         ("E", 83),
    "report.wow_price.solar":        ("F", 83),
    "report.wow_price.thermal":      ("G", 83),

    # 国内发电收入
    "report.revenue.total":          ("I", 84),
    "report.revenue.hydro":          ("C", 84),
    "report.revenue.new_energy":     ("D", 84),
    "report.revenue.wind":           ("E", 84),
    "report.revenue.solar":          ("F", 84),
    "report.revenue.thermal":        ("G", 84),

    # 收入同比
    "report.yoy_revenue.total":      ("I", 85),
    "report.yoy_revenue.hydro":      ("C", 85),
    "report.yoy_revenue.new_energy": ("D", 85),
    "report.yoy_revenue.wind":       ("E", 85),
    "report.yoy_revenue.solar":      ("F", 85),
    "report.yoy_revenue.thermal":    ("G", 85),

    # 收入环比
    "report.wow_revenue.total":      ("I", 86),
    "report.wow_revenue.hydro":      ("C", 86),
    "report.wow_revenue.new_energy": ("D", 86),
    "report.wow_revenue.wind":       ("E", 86),
    "report.wow_revenue.solar":      ("F", 86),
    "report.wow_revenue.thermal":    ("G", 86),
}

# ============================================================================
# 报告表1的行映射（用于批量读取）
# ============================================================================
REPORT_TABLE_1_ROWS: Dict[str, int] = {
    "国内上网电量": 78,
    "同比": 79,
    "环比": 80,
    "国内上网电价": 81,
    "同比_电价": 82,
    "环比_电价": 83,
    "国内发电收入": 84,
    "同比_收入": 85,
    "环比_收入": 86,
}

# 报告表1的列映射
REPORT_TABLE_1_COLS: Dict[str, str] = {
    "水电": "C",
    "新能源": "D",
    "风电": "E",
    "光伏": "F",
    "火电": "G",
    "合计": "I",
}

# ============================================================================
# 辅助函数
# ============================================================================


def get_cell(field_name: str) -> Optional[CellRef]:
    """获取字段名对应的单元格引用。

    Args:
        field_name: 点分字段名，如 "dom.electricity.total"

    Returns:
        (列字母, 行号) 或 None
    """
    return CELL_MAP.get(field_name)


def get_value(field_name: str, data: Dict[str, Any]) -> Optional[float]:
    """从已采集的数据字典中获取字段值。

    Args:
        field_name: 点分字段名
        data: 由 AnalysisCollector.collect() 返回的数据

    Returns:
        数值或 None
    """
    return data.get(field_name)


def col_letter_to_idx(col_letter: str) -> int:
    """将列字母转换为列号（A=1, B=2, ..., Z=26, AA=27）。

    Args:
        col_letter: 列字母

    Returns:
        列号（1-based）
    """
    result = 0
    for ch in col_letter.upper():
        result = result * 26 + (ord(ch) - ord("A") + 1)
    return result


def idx_to_col_letter(idx: int) -> str:
    """将列号转换为列字母（1=A, 2=B, ..., 26=Z, 27=AA）。

    Args:
        idx: 列号（1-based）

    Returns:
        列字母
    """
    result = ""
    while idx > 0:
        idx, remainder = divmod(idx - 1, 26)
        result = chr(65 + remainder) + result
    return result


def cell_coordinate(col_letter: str, row: int) -> str:
    """生成 Excel 单元格坐标字符串。

    Args:
        col_letter: 列字母
        row: 行号

    Returns:
        如 "I4"
    """
    return f"{col_letter}{row}"
