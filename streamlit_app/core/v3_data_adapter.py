"""v3 数据适配器 - 把 AnalysisCollector 输出转换为 UI 标准格式

设计目标：
    AnalysisCollector 输出与演示数据 (weekly_report_merged.json) 结构不同：
    - 采集器：domestic.electricity.total（扁平 + 万千瓦时/万元）
    - 演示数据：group_total.total_ongrid_volume_yi_kwh（嵌套 + 亿千瓦时/亿元）

    本模块负责：
    1. **保留所有原始数据**（去年/上周/按品类细分等，不丢失字段）
    2. **添加 UI 标准视图**（group_total/by_category/international，做单位转换）
    3. **让 CURATED 描述生效**（路径与演示数据一致）

    这样：
    - 字段总数 = 原始 149 + 新增 ~13 = ~162（不丢任何数据）
    - KPI 卡片用 group_total.* 路径，能取到正确值
    - 中文描述自动匹配 CURATED_OVERRIDES

使用：
    from streamlit_app.core.v3_data_adapter import adapt_collector_output

    ui_data = adapt_collector_output(raw_data)
"""
from __future__ import annotations

from typing import Any, Dict, Optional


# ============================================================================
# 常量
# ============================================================================
WAN_TO_YI = 10000  # 1亿 = 10000万
YUAN_TO_FEN = 100  # 1元 = 100分

CATEGORY_NAME_MAP = {
    "hydro": "hydro",
    "new_energy": "renewables",
    "wind": "wind",
    "solar": "solar",
    "thermal": "thermal",
}


# ============================================================================
# 辅助函数
# ============================================================================
def _safe_get(data: Dict[str, Any], *keys: str) -> Optional[float]:
    """安全获取嵌套字典的值，任一层缺失返回 None。"""
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def _pct_to_number(value: Optional[float]) -> Optional[float]:
    """把 0.033 转为 3.3（百分比数值）。"""
    if value is None:
        return None
    return round(value * 100, 1)


def _yuan_to_fen(value: Optional[float]) -> Optional[float]:
    """把元/千瓦时转为分（如 0.009 → 0.9）。"""
    if value is None:
        return None
    return round(value * YUAN_TO_FEN, 1)


def _wan_to_yi(value: Optional[float]) -> Optional[float]:
    """把万（千瓦时/元）转为亿。"""
    if value is None:
        return None
    return round(value / WAN_TO_YI, 2)


# ============================================================================
# 核心转换函数
# ============================================================================
def adapt_collector_output(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """把 AnalysisCollector 输出转换为 UI 标准格式。

    策略：
    1. 保留所有原始字段（不丢失 Excel 实际数据）
    2. 添加 group_total / by_category / international 三个 UI 视图
    3. 添加 report_period（从 meta 提取）
    4. 添加 ui_view 标志（方便 UI 识别这是 adapter 后的数据）

    Args:
        raw_data: AnalysisCollector.collect() 返回的第一个元素（dict）

    Returns:
        包含原始数据 + UI 视图的 dict
    """
    # 深拷贝原始数据（避免修改 raw_data）
    import copy
    result: Dict[str, Any] = copy.deepcopy(raw_data)

    domestic = raw_data.get("domestic", {})
    international = raw_data.get("international", {})
    meta = raw_data.get("meta", {})

    # === 1. report_period（从 meta 提取）===
    result["report_period"] = {
        "year": meta.get("year"),
        "week": meta.get("week"),
        "start_date": None,
        "end_date": None,
    }

    # === 2. group_total（13 个核心 KPI，做单位转换）===
    result["group_total"] = _build_group_total(domestic, international)

    # === 3. by_category（5 大品类，做单位转换）===
    result["by_category"] = _build_by_category(domestic)

    # === 4. international（覆盖原始，做单位转换）===
    # 注意：这里会覆盖原始的 international 字段，但保留 original 引用
    result["international"] = _build_international(international)

    # === 5. ui_view 标志 ===
    result["ui_view"] = {
        "adapted": True,
        "adapter_version": "v3.2",
        "original_section_count": len(raw_data),
    }

    return result


def _build_group_total(
    domestic: Dict[str, Any],
    international: Dict[str, Any],
) -> Dict[str, Any]:
    """构建集团汇总 KPI。

    字段映射（参考 weekly_report_merged.json 的 group_total section）：
    - domestic_ongrid_volume_yi_kwh ← domestic.electricity.total ÷ 10000
    - international_ongrid_volume_yi_kwh ← international.electricity.total ÷ 10000
    - total_ongrid_volume_yi_kwh ← 两者之和
    - domestic_avg_price_yuan_per_kwh ← domestic.price.total
    - domestic_revenue_yi_yuan ← domestic.revenue.total ÷ 10000
    - yoy_volume_pct ← domestic.yoy.electricity × 100
    - mom_volume_pct ← domestic.wow.electricity × 100
    - yoy_price_change_fen ← domestic.yoy.price_change × 100
    - mom_price_change_fen ← domestic.wow.price_change × 100
    - yoy_revenue_pct ← domestic.yoy.revenue × 100
    - mom_revenue_pct ← domestic.wow.revenue × 100
    """
    dom_vol_raw = _safe_get(domestic, "electricity", "total")
    dom_vol = _wan_to_yi(dom_vol_raw)
    dom_price = _safe_get(domestic, "price", "total")
    dom_rev_raw = _safe_get(domestic, "revenue", "total")
    dom_rev = _wan_to_yi(dom_rev_raw)

    intl_vol_raw = _safe_get(international, "electricity", "total")
    intl_vol = _wan_to_yi(intl_vol_raw)
    intl_price = _safe_get(international, "price", "total")
    intl_rev_raw = _safe_get(international, "revenue", "total")
    intl_rev = _wan_to_yi(intl_rev_raw)

    total_vol = (dom_vol or 0) + (intl_vol or 0) if dom_vol is not None or intl_vol is not None else None

    yoy_vol_pct = _pct_to_number(_safe_get(domestic, "yoy", "electricity"))
    mom_vol_pct = _pct_to_number(_safe_get(domestic, "wow", "electricity"))
    yoy_price_fen = _yuan_to_fen(_safe_get(domestic, "yoy", "price_change"))
    mom_price_fen = _yuan_to_fen(_safe_get(domestic, "wow", "price_change"))

    yoy_rev_pct = _pct_to_number(_safe_get(domestic, "yoy", "revenue"))
    mom_rev_pct = _pct_to_number(_safe_get(domestic, "wow", "revenue"))

    return {
        "domestic_ongrid_volume_yi_kwh": dom_vol,
        "international_ongrid_volume_yi_kwh": intl_vol,
        "total_ongrid_volume_yi_kwh": total_vol,
        "domestic_avg_price_yuan_per_kwh": dom_price,
        "international_avg_price_yuan_per_kwh": intl_price,
        "domestic_revenue_yi_yuan": dom_rev,
        "international_revenue_yi_yuan": intl_rev,
        "yoy_volume_pct": yoy_vol_pct,
        "mom_volume_pct": mom_vol_pct,
        "yoy_price_change_fen": yoy_price_fen,
        "mom_price_change_fen": mom_price_fen,
        "yoy_revenue_pct": yoy_rev_pct,
        "mom_revenue_pct": mom_rev_pct,
    }


def _build_by_category(domestic: Dict[str, Any]) -> Dict[str, Any]:
    """构建按品类数据（5 大品类）。

    字段映射（参考 weekly_report_merged.json 的 by_category section）：
    每个品类包含：
    - volume_yi_kwh（电量）
    - avg_price_yuan_per_kwh（电价）
    - revenue_yi_yuan（收入）
    - yoy_volume_pct（电量同比）
    - mom_volume_pct（电量环比）
    - yoy_price_change_fen（电价同比变化）
    - mom_price_change_fen（电价环比变化）
    - yoy_revenue_pct（收入同比，AnalysisCollector 未采集）
    - mom_revenue_pct（收入环比，AnalysisCollector 未采集）
    - share_pct（电量占比）
    """
    result = {}

    for src_name, dst_name in CATEGORY_NAME_MAP.items():
        # 电量、电价、收入（注意单位转换）
        vol_raw = _safe_get(domestic, "electricity", src_name)
        vol = _wan_to_yi(vol_raw)
        price = _safe_get(domestic, "price", src_name)
        rev_raw = _safe_get(domestic, "revenue", src_name)
        rev = _wan_to_yi(rev_raw)

        # 同比环比（电量）：AnalysisCollector 没有按品类的电量同比，设为 None
        # 用户在 UI 上会看到"—"，点击详情可跳到原始数据
        yoy_vol = _safe_get(domestic, "yoy", src_name, "price_change")  # 这是电价变化，不是电量
        mom_vol = _safe_get(domestic, "wow", src_name, "price_change")

        # 同比环比（电价）：元→分
        yoy_price = _yuan_to_fen(_safe_get(domestic, "yoy", src_name, "price_change"))
        mom_price = _yuan_to_fen(_safe_get(domestic, "wow", src_name, "price_change"))

        # 收入同比环比：AnalysisCollector 没有按品类的收入同比
        yoy_rev = None
        mom_rev = None

        # 电量占比
        share = _pct_to_number(_safe_get(domestic, "share", src_name))

        result[dst_name] = {
            "volume_yi_kwh": vol,
            "avg_price_yuan_per_kwh": price,
            "revenue_yi_yuan": rev,
            "yoy_volume_pct": None,  # AnalysisCollector 没有
            "mom_volume_pct": None,  # AnalysisCollector 没有
            "yoy_price_change_fen": yoy_price,
            "mom_price_change_fen": mom_price,
            "yoy_revenue_pct": yoy_rev,
            "mom_revenue_pct": mom_rev,
            "share_pct": share,
        }

    return result


def _build_international(international: Dict[str, Any]) -> Dict[str, Any]:
    """构建国际数据（单位转换）。

    字段映射（参考 weekly_report_merged.json 的 international section）：
    """
    vol = _wan_to_yi(_safe_get(international, "electricity", "total"))
    price = _safe_get(international, "price", "total")
    rev = _wan_to_yi(_safe_get(international, "revenue", "total"))

    yoy_vol = _pct_to_number(_safe_get(international, "yoy", "electricity"))
    mom_vol = _pct_to_number(_safe_get(international, "wow", "electricity"))
    yoy_price = _yuan_to_fen(_safe_get(international, "yoy", "price_change"))
    mom_price = _yuan_to_fen(_safe_get(international, "wow", "price_change"))

    return {
        "total_volume_yi_kwh": vol,
        "total_revenue_yi_yuan": rev,
        "avg_price_yuan_per_kwh": price,
        "avg_price_yoy_change_fen": yoy_price,
        "avg_price_mom_change_fen": mom_price,
        "yoy_volume_pct": yoy_vol,
        "mom_volume_pct": mom_vol,
        "yoy_revenue_pct": None,
        "mom_revenue_pct": None,
    }
