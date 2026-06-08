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
    """从字段名后缀推断单位。"""
    name_lower = leaf_name.lower()
    for suffix, unit in UNIT_SUFFIX_MAP:
        if name_lower.endswith(suffix):
            return unit
    return ""


# ============================================================
# 子节翻译字典
# ============================================================
CATEGORY_ZH = {
    "hydro": "水电",
    "renewables": "新能源",
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

SECTION_ZH = {
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
}


def _translate_subsection(
    section: str, parts: List[str]
) -> Tuple[str, List[str]]:
    """翻译路径中的子节名，返回 (中文名, 剩余 parts)。

    不同 section 的子节翻译策略不同：
        - by_category.X.Y → 翻译 X（水电/火电等），返回 ("水电", [Y])
        - by_country_category[0].X → 数组下标不翻译，返回 ("国家[0]", [X])
        - exchange_rates.CNY_USD.X → 翻译货币对
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
    # 单关键词
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

    # 2c. 提取单位
    leaf_name = remaining[-1] if remaining else section
    unit = _extract_unit(leaf_name)

    # 2d. 提取业务含义
    meaning = _extract_meaning(leaf_name)

    # 2e. 组合描述
    parts_zh: List[str] = []
    if sub_zh:
        parts_zh.append(sub_zh)
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
            desc = f"{section_zh}·{leaf_name}" if leaf_name else section_zh

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
