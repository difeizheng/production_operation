"""字段中文描述生成器

为 JSON 中的英文路径生成业务级中文描述，让非开发者也能看懂。

设计原则：
    1. 双层结构：CURATED_OVERRIDES（人工校对）> 智能推断（自动生成）
    2. 单位识别优先于业务含义（避免 _yi_kwh 被 _kwh 抢走，长后缀先匹配）
    3. 业务关键词列表用顺序匹配（长关键词先匹配）
    4. fallback 永远输出英文路径，保证不丢信息

使用：
    from streamlit_app.utils.field_descriptions import describe_field

    info = describe_field("by_category.hydro.volume_yi_kwh")
    # {"description_zh": "本周水电上网电量（亿千瓦时）", "unit": "亿千瓦时"}
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# 单位识别（后缀 → 中文单位）
# ============================================================
# 顺序重要：长的先匹配（避免 _yi_kwh 被 _kwh 抢走）
UNIT_SUFFIX_MAP: List[Tuple[str, str]] = [
    ("_yuan_per_kwh", "元/千瓦时"),
    ("_change_fen", "分"),
    ("_yi_kwh", "亿千瓦时"),
    ("_yi_yuan", "亿元"),
    ("_fen", "分"),
    ("_avg_price", "元/张"),  # 用于绿证
    ("_kwh", "千瓦时"),
    ("_yuan", "元"),
    ("_pct", "%"),
    ("_tons", "吨"),
    ("_count", "张"),
    ("_wan", "万"),
    ("_zhi", "只"),
]


def _extract_unit(leaf_name: str) -> str:
    """从字段名后缀推断单位。

    v3.2 增强：除了 UNIT_SUFFIX_MAP 后缀匹配，还支持 leaf_name 关键词推断
    （针对 price_change / share_impact / combined_impact 等没有标准后缀的字段）
    """
    name_lower = leaf_name.lower()

    # 1. 后缀匹配（最优先）
    for suffix, unit in UNIT_SUFFIX_MAP:
        if name_lower.endswith(suffix):
            return unit

    # 2. v3.2 关键词推断（针对 yoy/wow 分析的细分字段）
    if "price" in name_lower and "change" in name_lower:
        return "元/千瓦时"  # 电价同比/环比变化
    if "price" in name_lower and "impact" in name_lower:
        return "元/千瓦时"  # 电价影响
    if "share" in name_lower and "change" in name_lower:
        return "%"  # 占比变化
    if "share" in name_lower and "impact" in name_lower:
        return "元/千瓦时"  # 占比对电价的影响
    if "cross_impact" in name_lower or "combined_impact" in name_lower:
        return "元/千瓦时"  # 交叉影响 / 量价合计影响

    return ""


def _extract_unit_hint(path_normalized: str) -> str:
    """v3.2 新增：按路径前缀匹配单位 hint。

    用于"采集器路径"（domestic.electricity.hydro 等没有单位后缀的路径）。

    优先级（长的前缀优先匹配）：
    - domestic.electricity → 万千瓦时
    - domestic.price → 元/千瓦时
    - domestic.revenue → 万元
    - ...

    Args:
        path_normalized: 标准化后的路径（数组下标已转换）

    Returns:
        单位字符串，未匹配返回 ""
    """
    for prefix, unit in UNIT_HINT_MAP:
        if path_normalized == prefix or path_normalized.startswith(prefix + "."):
            return unit
    return ""


# ============================================================
# 子节翻译字典
# ============================================================
CATEGORY_ZH = {
    "hydro": "水电",
    "renewables": "新能源",
    "new_energy": "新能源",  # v3.2: 采集器原始命名
    "thermal": "火电",
    "wind": "风电",
    "solar": "光伏",
    "wind_offshore": "海上风电",
    "storage": "储能",
}

REGION_ZH = {
    "hubei": "湖北",
    "shandong": "山东",
    "shaanxi": "陕西",
    "jiangsu": "江苏",
    "yunnan": "云南",
    "sichuan": "四川",
    "guangdong": "广东",
    "chongqing": "重庆",
    "qinghai": "青海",
    "henan": "河南",
    "anhui": "安徽",
    "hunan": "湖南",
    "jiangxi": "江西",
}

COMPANY_ZH = {
    "three_gorges_intl": "三峡国际",
    "cyg_intl": "长江电力国际",
    "hubei_energy": "湖北能源",
    "yangtze_power": "长江电力",
    "three_gorges_energy": "三峡能源",
    "three_gorges_construction": "三峡建工",
    "three_gorges_development": "三峡发展",
    "changjiang_protection": "长江环保",
}

CURRENCY_ZH = {
    "CNY_USD": "人民币兑美元",
    "CNY_BRL": "人民币兑巴西雷亚尔",
    "CNY_EUR": "人民币兑欧元",
}

ENV_ASSET_ZH = {
    "green_cert": "绿证",
    "ccer": "CCER",
}

# v3.2 新增：AnalysisCollector 原始数据路径的 section 翻译
SECTION_ZH = {
    # 业务标准 section
    "group_total": "集团汇总",
    "by_category": "按品类",
    "by_region": "按省份",
    "by_company": "按公司",
    "by_country_category": "按国家品类",
    "international": "国际",
    "exchange_rates": "汇率",
    "market_trading": "市场化交易",
    "environmental_assets": "环境资产",
    "report_period": "报告期",
    "report_table_1": "报告表1",
    "organizations": "组织",
    "ui_view": "UI视图",
    "validation_report": "验证报告",
    # 采集器原始 section（v3.2 新增）
    "domestic": "国内",
    "international_raw": "国际（原始）",
    "electricity": "电量",
    "price": "电价",
    "revenue": "收入",
    "yoy": "同比",
    "wow": "环比",
    "share": "电量占比",
    "prev_year_electricity": "去年同期电量",
    "prev_year_price": "去年同期电价",
    "prev_year_revenue": "去年同期收入",
    "prev_year_share": "去年同期占比",
    "last_week_electricity": "上周电量",
    "last_week_price": "上周电价",
    "last_week_revenue": "上周收入",
    "last_week_share": "上周占比",
}

# v3.2 新增：单位 hint（按路径前缀匹配）
# 用于给"采集器原始路径"补充单位信息
# 路径前缀（越长越具体）→ 单位
UNIT_HINT_MAP: List[Tuple[str, str]] = [
    # 具体单位（长前缀优先）
    ("domestic.electricity", "万千瓦时"),
    ("domestic.price", "元/千瓦时"),
    ("domestic.revenue", "万元"),
    ("domestic.share", "%"),
    ("domestic.yoy.electricity", "%"),
    ("domestic.yoy.revenue", "%"),
    ("domestic.yoy.price_change", "元/千瓦时"),
    ("domestic.yoy.price_impact", "元/千瓦时"),
    ("domestic.yoy.share_impact", "元/千瓦时"),
    ("domestic.yoy.cross_impact", "元/千瓦时"),
    ("domestic.yoy.combined_impact", "元/千瓦时"),
    ("domestic.yoy.share_change", "%"),
    ("domestic.wow.electricity", "%"),
    ("domestic.wow.revenue", "%"),
    ("domestic.wow.price_change", "元/千瓦时"),
    ("domestic.wow.price_impact", "元/千瓦时"),
    ("domestic.wow.share_impact", "元/千瓦时"),
    ("domestic.wow.cross_impact", "元/千瓦时"),
    ("domestic.wow.combined_impact", "元/千瓦时"),
    ("domestic.wow.share_change", "%"),
    ("domestic.prev_year_electricity", "万千瓦时"),
    ("domestic.prev_year_price", "元/千瓦时"),
    ("domestic.prev_year_revenue", "万元"),
    ("domestic.prev_year_share", "%"),
    ("domestic.last_week_electricity", "万千瓦时"),
    ("domestic.last_week_price", "元/千瓦时"),
    ("domestic.last_week_revenue", "万元"),
    ("domestic.last_week_share", "%"),
    # 国际（注意：AnalysisCollector 国际数据原始单位也是万千瓦时/万元）
    ("international.electricity", "万千瓦时"),
    ("international.price", "元/千瓦时"),
    ("international.revenue", "万元"),
    ("international.yoy.electricity", "%"),
    ("international.yoy.price_change", "元/千瓦时"),
    ("international.wow.electricity", "%"),
    ("international.wow.price_change", "元/千瓦时"),
]


def _translate_subsection(
    section: str, parts: List[str]
) -> Tuple[str, List[str]]:
    """翻译路径中的子节名，返回 (中文名, 剩余 parts)。

    不同 section 的子节翻译策略不同：
        - by_category.X.Y → 翻译 X（水电/火电等），返回 ("水电", [Y])
        - by_country_category[0].X → 数组下标不翻译，返回 ("国家[0]", [X])
        - exchange_rates.CNY_USD.X → 翻译货币对
        - v3.2 新增：采集器路径递归翻译
          domestic.electricity.hydro → 递归处理
            ("国内", ["electricity", "hydro"])
            → ("国内·电量", ["hydro"])
            → ("国内·电量·水电", [])
    """
    if not parts:
        return "", parts

    first = parts[0]

    if section == "by_category":
        return CATEGORY_ZH.get(first, first), parts[1:]
    if section == "by_region":
        return REGION_ZH.get(first, first), parts[1:]
    if section == "by_company":
        return COMPANY_ZH.get(first, first), parts[1:]
    if section == "by_country_category":
        # 数组下标（数字），翻译为"国家[i]"
        return f"国家[{first}]", parts[1:]
    if section == "exchange_rates":
        return CURRENCY_ZH.get(first, first), parts[1:]
    if section == "market_trading":
        # 水电市场化/新能源市场化/火电市场化
        cat_zh = CATEGORY_ZH.get(first, first)
        return f"{cat_zh}市场化", parts[1:]
    if section == "environmental_assets":
        return ENV_ASSET_ZH.get(first, first), parts[1:]

    # v3.2 新增：品类在所有 section 下都翻译
    # 这样 domestic.electricity.hydro 第二次递归时能识别 "hydro" → "水电"
    if first in CATEGORY_ZH:
        return CATEGORY_ZH[first], parts[1:]

    # v3.2 新增：通用递归翻译
    # 如果 first 在 SECTION_ZH 中（采集器 section），先翻译 first，再递归处理剩余
    if first in SECTION_ZH and first != section:
        sub_zh = SECTION_ZH[first]
        # 递归处理剩余部分（用 first 作为新 section）
        inner_zh, inner_remaining = _translate_subsection(first, parts[1:])
        if inner_zh:
            return f"{sub_zh}·{inner_zh}", inner_remaining
        return sub_zh, parts[1:]

    # 未识别的 section：不翻译
    return "", parts


# ============================================================
# 叶子名业务含义（关键词 → 中文）
# ============================================================
# 顺序重要：长的先匹配
LEAF_KEYWORD_ZH: List[Tuple[str, str]] = [
    # 复合词优先
    ("weekly_issued", "本周核发量"),
    ("weekly_sold", "本周销售量"),
    ("weekly_avg_price", "本周成交均价"),
    ("domestic_ongrid_volume", "国内上网电量"),
    ("international_ongrid_volume", "国际上网电量"),
    ("domestic_revenue", "国内发电收入"),
    ("international_revenue", "国际发电收入"),
    ("domestic_avg_price", "国内度电均价"),
    ("international_avg_price", "国际度电均价"),
    ("total_ongrid_volume", "集团总上网电量"),
    ("avg_price_yoy_change", "电价同比变化"),
    ("avg_price_mom_change", "电价环比变化"),
    ("yoy_cumulative", "累计同比"),
    ("mom_cumulative", "累计环比"),
    ("cumulative_sold", "累计销售量"),
    ("cumulative_issued", "累计核发量"),
    ("ongrid_volume", "上网电量"),
    ("avg_price", "平均上网电价"),
    ("total_volume", "总上网电量"),
    ("total_revenue", "总发电收入"),
    ("yoy_volume", "电量同比"),
    ("mom_volume", "电量环比"),
    ("yoy_revenue", "收入同比"),
    ("mom_revenue", "收入环比"),
    ("yoy_price", "电价同比变化"),
    ("mom_price", "电价环比变化"),
    ("yoy_change", "同比变化"),
    ("mom_change", "环比变化"),
    ("yoy_pct", "同比"),
    ("mom_pct", "环比"),
    ("yoy", "同比"),
    ("wow", "环比"),
    ("mom", "环比"),
    # v3.2 新增：yoy/wow 归因分析字段
    ("combined_impact", "量价合计影响"),
    ("price_impact", "电价影响"),
    ("share_impact", "占比影响"),
    ("cross_impact", "交叉影响"),
    ("price_change", "电价变化"),
    ("share_change", "占比变化"),
    # 单关键词
    ("total", "合计"),
    ("volume", "上网电量"),
    ("revenue", "发电收入"),
    ("price", "电价"),
    ("share", "电量占比"),
    ("growth", "增长"),
    ("change", "变化"),
    ("current", "当前"),
    ("sold", "销售"),
    ("issued", "核发"),
    ("avg", "平均"),
    ("main_sources", "主要来源"),
    ("spot_avg_price", "现货均价"),
    ("currency_name", "币种"),
    ("name", "名称"),
    # 复合日期必须排在 date 前面（避免 start_date 被 date 抢走）
    ("start_date", "开始日期"),
    ("end_date", "结束日期"),
    ("date", "日期"),
    ("year", "年份"),
    ("week", "周次"),
    ("country", "国家"),
    ("region", "区域"),
    ("category", "品类"),
    ("count", "数量"),
]


def _extract_meaning(leaf_name: str) -> str:
    """从叶子名推断业务含义。"""
    name_lower = leaf_name.lower()
    for kw, zh in LEAF_KEYWORD_ZH:
        if kw in name_lower:
            return zh
    return ""


# ============================================================
# 重点字段人工校对（权威源，覆盖推断）
# ============================================================
# 覆盖 3 类场景：
#   1. 业务核心字段（用户最常看）
#   2. 推断会出错的复杂字段（如 by_year_weekly）
#   3. 单位容易混淆的（_avg_price 在绿证是"元/张"不是"元/千瓦时"）
CURATED_OVERRIDES: Dict[str, Dict[str, str]] = {
    # === 集团汇总（13 个核心数字）===
    "group_total.domestic_ongrid_volume_yi_kwh": {
        "description_zh": "本周国内总上网电量",
        "unit": "亿千瓦时",
    },
    "group_total.international_ongrid_volume_yi_kwh": {
        "description_zh": "本周国际总上网电量",
        "unit": "亿千瓦时",
    },
    "group_total.total_ongrid_volume_yi_kwh": {
        "description_zh": "本周集团总上网电量",
        "unit": "亿千瓦时",
    },
    "group_total.domestic_revenue_yi_yuan": {
        "description_zh": "本周国内总发电收入",
        "unit": "亿元",
    },
    "group_total.international_revenue_yi_yuan": {
        "description_zh": "本周国际总发电收入",
        "unit": "亿元",
    },
    "group_total.domestic_avg_price_yuan_per_kwh": {
        "description_zh": "本周国内度电均价",
        "unit": "元/千瓦时",
    },
    "group_total.international_avg_price_yuan_per_kwh": {
        "description_zh": "本周国际度电均价",
        "unit": "元/千瓦时",
    },
    "group_total.yoy_volume_pct": {
        "description_zh": "本周集团上网电量同比",
        "unit": "%",
    },
    "group_total.mom_volume_pct": {
        "description_zh": "本周集团上网电量环比",
        "unit": "%",
    },
    "group_total.yoy_revenue_pct": {
        "description_zh": "本周集团发电收入同比",
        "unit": "%",
    },
    "group_total.mom_revenue_pct": {
        "description_zh": "本周集团发电收入环比",
        "unit": "%",
    },
    "group_total.yoy_price_change_fen": {
        "description_zh": "本周集团度电均价同比变化",
        "unit": "分",
    },
    "group_total.mom_price_change_fen": {
        "description_zh": "本周集团度电均价环比变化",
        "unit": "分",
    },
    # === 报告期 ===
    "report_period.year": {"description_zh": "报告年份", "unit": ""},
    "report_period.week": {"description_zh": "周次", "unit": ""},
    "report_period.start_date": {"description_zh": "周开始日期", "unit": ""},
    "report_period.end_date": {"description_zh": "周结束日期", "unit": ""},
    # === 5 大品类核心字段 ===
    "by_category.hydro.volume_yi_kwh": {
        "description_zh": "本周水电上网电量",
        "unit": "亿千瓦时",
    },
    "by_category.hydro.avg_price_yuan_per_kwh": {
        "description_zh": "本周水电度电均价",
        "unit": "元/千瓦时",
    },
    "by_category.hydro.revenue_yi_yuan": {
        "description_zh": "本周水电发电收入",
        "unit": "亿元",
    },
    "by_category.hydro.share_pct": {
        "description_zh": "水电电量占比",
        "unit": "%",
    },
    "by_category.renewables.volume_yi_kwh": {
        "description_zh": "本周新能源（风+光）上网电量",
        "unit": "亿千瓦时",
    },
    "by_category.renewables.avg_price_yuan_per_kwh": {
        "description_zh": "本周新能源度电均价",
        "unit": "元/千瓦时",
    },
    "by_category.renewables.revenue_yi_yuan": {
        "description_zh": "本周新能源发电收入",
        "unit": "亿元",
    },
    "by_category.renewables.share_pct": {
        "description_zh": "新能源电量占比",
        "unit": "%",
    },
    "by_category.thermal.volume_yi_kwh": {
        "description_zh": "本周火电上网电量",
        "unit": "亿千瓦时",
    },
    "by_category.thermal.avg_price_yuan_per_kwh": {
        "description_zh": "本周火电度电均价",
        "unit": "元/千瓦时",
    },
    "by_category.thermal.revenue_yi_yuan": {
        "description_zh": "本周火电发电收入",
        "unit": "亿元",
    },
    "by_category.thermal.share_pct": {
        "description_zh": "火电电量占比",
        "unit": "%",
    },
    "by_category.wind.volume_yi_kwh": {
        "description_zh": "本周风电上网电量",
        "unit": "亿千瓦时",
    },
    "by_category.wind.avg_price_yuan_per_kwh": {
        "description_zh": "本周风电度电均价",
        "unit": "元/千瓦时",
    },
    "by_category.solar.volume_yi_kwh": {
        "description_zh": "本周光伏上网电量",
        "unit": "亿千瓦时",
    },
    "by_category.solar.avg_price_yuan_per_kwh": {
        "description_zh": "本周光伏度电均价",
        "unit": "元/千瓦时",
    },
    # === 国际段核心 ===
    "international.total_volume_yi_kwh": {
        "description_zh": "本周国际上网电量",
        "unit": "亿千瓦时",
    },
    "international.total_revenue_yi_yuan": {
        "description_zh": "本周国际发电收入",
        "unit": "亿元",
    },
    "international.avg_price_yuan_per_kwh": {
        "description_zh": "本周国际度电均价",
        "unit": "元/千瓦时",
    },
    "international.avg_price_yoy_change_fen": {
        "description_zh": "本周国际度电均价同比变化",
        "unit": "分",
    },
    "international.avg_price_mom_change_fen": {
        "description_zh": "本周国际度电均价环比变化",
        "unit": "分",
    },
    # === 汇率 ===
    "exchange_rates.CNY_USD.current": {
        "description_zh": "人民币兑美元当前汇率",
        "unit": "",
    },
    "exchange_rates.CNY_USD.yoy_pct": {
        "description_zh": "人民币兑美元汇率同比",
        "unit": "%",
    },
    "exchange_rates.CNY_USD.mom_pct": {
        "description_zh": "人民币兑美元汇率环比",
        "unit": "%",
    },
    "exchange_rates.CNY_BRL.current": {
        "description_zh": "人民币兑巴西雷亚尔当前汇率",
        "unit": "",
    },
    "exchange_rates.CNY_BRL.yoy_pct": {
        "description_zh": "人民币兑巴西雷亚尔汇率同比",
        "unit": "%",
    },
    "exchange_rates.CNY_BRL.mom_pct": {
        "description_zh": "人民币兑巴西雷亚尔汇率环比",
        "unit": "%",
    },
    "exchange_rates.CNY_EUR.current": {
        "description_zh": "人民币兑欧元当前汇率",
        "unit": "",
    },
    "exchange_rates.CNY_EUR.yoy_pct": {
        "description_zh": "人民币兑欧元汇率同比",
        "unit": "%",
    },
    "exchange_rates.CNY_EUR.mom_pct": {
        "description_zh": "人民币兑欧元汇率环比",
        "unit": "%",
    },
    # === 环境资产 - 绿证 ===
    "environmental_assets.green_cert.weekly_issued_wan": {
        "description_zh": "绿证本周核发量",
        "unit": "万张",
    },
    "environmental_assets.green_cert.weekly_sold_wan": {
        "description_zh": "绿证本周销售量",
        "unit": "万张",
    },
    "environmental_assets.green_cert.weekly_sold_count": {
        "description_zh": "绿证本周销售张数",
        "unit": "张",
    },
    "environmental_assets.green_cert.weekly_avg_price": {
        "description_zh": "绿证本周成交均价",
        "unit": "元/张",
    },
    "environmental_assets.green_cert.cumulative_issued_wan": {
        "description_zh": "绿证累计核发量",
        "unit": "万张",
    },
    "environmental_assets.green_cert.cumulative_sold_wan": {
        "description_zh": "绿证累计销售量",
        "unit": "万张",
    },
    "environmental_assets.green_cert.cumulative_sold_count": {
        "description_zh": "绿证累计销售张数",
        "unit": "张",
    },
    # === 环境资产 - CCER ===
    "environmental_assets.ccer.weekly_sold_tons": {
        "description_zh": "CCER 本周销售量",
        "unit": "吨",
    },
    "environmental_assets.ccer.weekly_avg_price": {
        "description_zh": "CCER 本周成交均价",
        "unit": "元/吨",
    },
    "environmental_assets.ccer.cumulative_sold_tons": {
        "description_zh": "CCER 累计销售量",
        "unit": "吨",
    },
    "environmental_assets.ccer.cumulative_avg_price": {
        "description_zh": "CCER 累计成交均价",
        "unit": "元/吨",
    },
    # === 按省份（4 省 × 4 字段 = 16 条）===
    "by_region.hubei.yoy_price_change_fen": {
        "description_zh": "湖北电价同比变化",
        "unit": "分",
    },
    "by_region.hubei.mom_price_change_fen": {
        "description_zh": "湖北电价环比变化",
        "unit": "分",
    },
    "by_region.hubei.long_term_position_pct": {
        "description_zh": "湖北长期合约持仓",
        "unit": "%",
    },
    "by_region.hubei.spot_avg_price_yuan": {
        "description_zh": "湖北现货均价",
        "unit": "元/千瓦时",
    },
    "by_region.shandong.yoy_price_change_fen": {
        "description_zh": "山东电价同比变化",
        "unit": "分",
    },
    "by_region.shandong.mom_price_change_fen": {
        "description_zh": "山东电价环比变化",
        "unit": "分",
    },
    "by_region.shandong.long_term_position_pct": {
        "description_zh": "山东长期合约持仓",
        "unit": "%",
    },
    "by_region.shandong.spot_avg_price_yuan": {
        "description_zh": "山东现货均价",
        "unit": "元/千瓦时",
    },
    "by_region.shaanxi.yoy_price_change_fen": {
        "description_zh": "陕西电价同比变化",
        "unit": "分",
    },
    "by_region.shaanxi.mom_price_change_fen": {
        "description_zh": "陕西电价环比变化",
        "unit": "分",
    },
    "by_region.shaanxi.long_term_position_pct": {
        "description_zh": "陕西长期合约持仓",
        "unit": "%",
    },
    "by_region.shaanxi.spot_avg_price_yuan": {
        "description_zh": "陕西现货均价",
        "unit": "元/千瓦时",
    },
    "by_region.jiangsu.yoy_price_change_fen": {
        "description_zh": "江苏电价同比变化",
        "unit": "分",
    },
    "by_region.jiangsu.mom_price_change_fen": {
        "description_zh": "江苏电价环比变化",
        "unit": "分",
    },
    "by_region.jiangsu.long_term_position_pct": {
        "description_zh": "江苏长期合约持仓",
        "unit": "%",
    },
    "by_region.jiangsu.spot_avg_price_yuan": {
        "description_zh": "江苏现货均价",
        "unit": "元/千瓦时",
    },
    # === 按公司（3 公司 × 7 字段 = 21 条）===
    "by_company.three_gorges_intl.name": {
        "description_zh": "三峡国际",
        "unit": "",
    },
    "by_company.three_gorges_intl.yoy_change_fen": {
        "description_zh": "三峡国际电价同比变化",
        "unit": "分",
    },
    "by_company.three_gorges_intl.mom_change_fen": {
        "description_zh": "三峡国际电价环比变化",
        "unit": "分",
    },
    "by_company.three_gorges_intl.yoy_real_business_fen": {
        "description_zh": "三峡国际真本事同比变化",
        "unit": "分",
    },
    "by_company.three_gorges_intl.mom_real_business_fen": {
        "description_zh": "三峡国际真本事环比变化",
        "unit": "分",
    },
    "by_company.three_gorges_intl.group_impact_yoy_fen": {
        "description_zh": "三峡国际对集团同比影响",
        "unit": "分",
    },
    "by_company.three_gorges_intl.group_impact_mom_fen": {
        "description_zh": "三峡国际对集团环比影响",
        "unit": "分",
    },
    "by_company.cyg_intl.name": {
        "description_zh": "长江电力国际",
        "unit": "",
    },
    "by_company.cyg_intl.yoy_change_fen": {
        "description_zh": "长江电力国际电价同比变化",
        "unit": "分",
    },
    "by_company.cyg_intl.mom_change_fen": {
        "description_zh": "长江电力国际电价环比变化",
        "unit": "分",
    },
    "by_company.cyg_intl.yoy_real_business_fen": {
        "description_zh": "长江电力国际真本事同比变化",
        "unit": "分",
    },
    "by_company.cyg_intl.mom_real_business_fen": {
        "description_zh": "长江电力国际真本事环比变化",
        "unit": "分",
    },
    "by_company.cyg_intl.group_impact_yoy_fen": {
        "description_zh": "长江电力国际对集团同比影响",
        "unit": "分",
    },
    "by_company.cyg_intl.group_impact_mom_fen": {
        "description_zh": "长江电力国际对集团环比影响",
        "unit": "分",
    },
    "by_company.hubei_energy.name": {
        "description_zh": "湖北能源",
        "unit": "",
    },
    "by_company.hubei_energy.yoy_change_fen": {
        "description_zh": "湖北能源电价同比变化",
        "unit": "分",
    },
    "by_company.hubei_energy.mom_change_fen": {
        "description_zh": "湖北能源电价环比变化",
        "unit": "分",
    },
    "by_company.hubei_energy.yoy_real_business_fen": {
        "description_zh": "湖北能源真本事同比变化",
        "unit": "分",
    },
    "by_company.hubei_energy.mom_real_business_fen": {
        "description_zh": "湖北能源真本事环比变化",
        "unit": "分",
    },
    "by_company.hubei_energy.group_impact_yoy_fen": {
        "description_zh": "湖北能源对集团同比影响",
        "unit": "分",
    },
    "by_company.hubei_energy.group_impact_mom_fen": {
        "description_zh": "湖北能源对集团环比影响",
        "unit": "分",
    },
}


# ============================================================
# 入口函数
# ============================================================
def describe_field(path: str) -> Dict[str, str]:
    """生成字段的中文描述和单位。

    优先级：CURATED_OVERRIDES > 智能推断 > 英文路径兜底

    Args:
        path: 完整字段路径，如 "by_category.hydro.volume_yi_kwh"
            或 "by_country_category[0].country"

    Returns:
        {
            "description_zh": "本周水电上网电量",  # 或 "本周水电上网电量（亿千瓦时）"
            "unit": "亿千瓦时",
        }
    """
    # 1. 优先用人工校对
    if path in CURATED_OVERRIDES:
        return CURATED_OVERRIDES[path]

    # 2. 智能推断
    # 2a. 路径标准化：by_country_category[0].country → by_country_category.0.country
    path_normalized = re.sub(r"\[(\d+)\]", r".\1.", path)
    parts = [p for p in path_normalized.split(".") if p]

    if not parts:
        return {"description_zh": path, "unit": ""}

    section = parts[0]
    sub_parts = parts[1:]

    # 2b. 翻译子节
    sub_zh, remaining = _translate_subsection(section, sub_parts)

    # 2c. 提取单位（v3.2：先查路径前缀 hint，再 fallback 到 leaf 后缀）
    leaf_name = remaining[-1] if remaining else section
    unit = _extract_unit_hint(path_normalized) or _extract_unit(leaf_name)

    # 2d. 提取业务含义
    meaning = _extract_meaning(leaf_name)

    # 2e. 组合描述
    parts_zh: List[str] = []
    if sub_zh:
        parts_zh.append(sub_zh)

    # v3.2 修复：只有 remaining 还有内容时才追加 leaf 含义
    # 否则会出现 "环比·电量·domestic"（leaf_name 重复 section 名）
    if remaining:
        if meaning:
            parts_zh.append(meaning)
        elif leaf_name and leaf_name not in (sub_zh,):
            # 推断不出含义时，保留原字段名（避免信息丢失）
            parts_zh.append(leaf_name)

    desc = "·".join(parts_zh) if parts_zh else path

    # 没有子节时，加上 section 上下文（仅在含义也推断不出来时）
    if not sub_zh and not meaning:
        section_zh = SECTION_ZH.get(section, section)
        if section_zh and section_zh not in desc:
            desc = f"{section_zh}·{leaf_name}" if leaf_name and leaf_name != section else section_zh

    # 加上单位（如果有）
    if unit and unit not in desc:
        desc = f"{desc}（{unit}）"

    return {
        "description_zh": desc,
        "unit": unit,
    }


def get_curated_count() -> int:
    """返回已人工校对的字段数（用于统计覆盖率）。"""
    return len(CURATED_OVERRIDES)
