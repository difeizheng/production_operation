"""分析文本生成器 - 基于句式模板生成周报分析段落

根据模板文件（数据模板0602.docx）中的标注句式，
结合综合分析表的数值数据，自动生成分析文本。

设计原则：
    - 数值填入：全自动（从综合分析表读取）
    - 原因描述：留占位符"···"（需人工或LLM补充）
    - 方向判断：自动（提高/下降）
    - 单位转换：自动（万千瓦时→亿千瓦时，元/千瓦时→分）
"""

from typing import Any, Dict, List, Optional


# ============================================================================
# 工具函数
# ============================================================================


def format_direction(value: Optional[float], positive: str = "提高", negative: str = "下降") -> str:
    """根据数值正负自动选择方向词。

    Args:
        value: 变化值（正=提高，负=下降）
        positive: 正值时使用的词
        negative: 负值时使用的词

    Returns:
        方向词字符串
    """
    if value is None:
        return "···"
    return positive if value >= 0 else negative


def format_pct(value: Optional[float], with_direction: bool = True) -> str:
    """格式化百分比。

    Args:
        value: 比率值（如 0.033 表示 3.3%）
        with_direction: 是否自动加"提高/下降"

    Returns:
        如 "提高3.3%" 或 "下降3.3%"
    """
    if value is None:
        return "···"
    pct = abs(value) * 100
    if with_direction:
        direction = format_direction(value)
        return f"{direction}{pct:.1f}%"
    return f"{pct:.1f}%"


def format_fen(value: Optional[float]) -> str:
    """将元/千瓦时变化值转换为"分"并格式化。

    Args:
        value: 元/千瓦时的变化量（如 -0.009 表示下降0.9分）

    Returns:
        如 "下降0.9分" 或 "提高1.3分"
    """
    if value is None:
        return "···"
    fen = abs(value) * 100
    direction = format_direction(value)
    return f"{direction}{fen:.1f}分"


def format_billion(value: Optional[float], unit: str = "亿千瓦时") -> str:
    """将万千瓦时转为亿千瓦时并格式化。

    Args:
        value: 万千瓦时
        unit: 单位后缀

    Returns:
        如 "80.3亿千瓦时"
    """
    if value is None:
        return "···"
    return f"{value / 10000:.1f}{unit}"


def format_yuan(value: Optional[float]) -> str:
    """格式化元/千瓦时电价。

    Args:
        value: 元/千瓦时

    Returns:
        如 "0.311"
    """
    if value is None:
        return "···"
    return f"{value:.3f}"


def format_pct_points(value: Optional[float]) -> str:
    """格式化百分点变化。

    Args:
        value: 占比变化（如 0.023 表示 2.3个百分点）

    Returns:
        如 "提高2.3个百分点" 或 "下降1.2个百分点"
    """
    if value is None:
        return "···"
    pts = abs(value) * 100
    direction = format_direction(value)
    return f"{direction}{pts:.1f}个百分点"


def format_revenue_billion(value: Optional[float]) -> str:
    """将万元转为亿元并格式化。

    Args:
        value: 万元

    Returns:
        如 "24.9亿元"
    """
    if value is None:
        return "···"
    return f"{value / 10000:.1f}亿元"


# ============================================================================
# 段落生成函数
# ============================================================================


def generate_electricity_summary(data: Dict[str, Any]) -> str:
    """生成电量概述段落。

    对应模板：'上周，集团公司合计上网电量[综合分析表（I4+I41）/10000]亿千瓦时，
    其中，国内上网电量[综合分析表I4/10000]亿千瓦时，
    国际上网电量[综合分析表I41/10000]亿千瓦时。'
    """
    dom = data.get("domestic", {})
    intl = data.get("international", {})

    dom_elec = dom.get("electricity", {}).get("total")
    intl_elec = intl.get("electricity", {}).get("total")

    if dom_elec is None or intl_elec is None:
        return "（待补充）"

    total = dom_elec + intl_elec
    total_b = format_billion(total)
    dom_b = format_billion(dom_elec)
    intl_b = format_billion(intl_elec)

    return (
        f"上周，集团公司合计上网电量{total_b}，"
        f"其中，国内上网电量{dom_b}，国际上网电量{intl_b}。"
    )


def generate_domestic_yoy_paragraph(data: Dict[str, Any]) -> str:
    """生成国内电量同比环比分析段落。

    对应模板第二段：
    '上周，集团公司国内上网电量X亿千瓦时、同比提高/下降X%，
    主要原因是···。上网电量环比提高/下降X%，主要原因是···。'
    """
    dom = data.get("domestic", {})
    reasons = data.get("reasons", {})

    elec = dom.get("electricity", {}).get("total")
    yoy = dom.get("yoy", {}).get("electricity")
    wow = dom.get("wow", {}).get("electricity")

    if elec is None:
        return "（待补充）"

    elec_b = format_billion(elec)
    yoy_text = format_pct(yoy)
    wow_text = format_pct(wow)

    # 原因文本：优先使用汇总表的实际原因，否则保留占位符
    yoy_reason = reasons.get("yoy_summary") or "···"
    wow_reason = reasons.get("wow_summary") or "···"

    return (
        f"上周，集团公司国内上网电量{elec_b}、同比{yoy_text}，"
        f"主要原因是{yoy_reason}。"
        f"上网电量环比{wow_text}，主要原因是{wow_reason}。"
    )


def generate_domestic_price_yoy_paragraph(data: Dict[str, Any]) -> str:
    """生成国内上网电价同比分析段落。

    对应模板：
    '上周，集团公司国内平均上网电价约每千瓦时X元，
    同比度电提高/下降X分，上网电量同比提高/下降X%、
    发电收入同比提高/下降X%。
    （电量结构变化影响度电均价提高/下降X分、
    电价变化影响度电均价提高/下降X分。
    各品类中：水电电量占比提高/下降X个百分点、度电电价提高/下降X分，
    量价变化合计影响集团度电均价提高/下降约X分；
    新能源电量占比提高/下降X个百分点、度电电价提高/下降X分，
    量价变化合计影响集团度电均价提高/下降约X分；
    火电电量占比提高/下降X个百分点、度电电价提高/下降X分，
    量价变化合计影响集团度电均价提高/下降约X分）'
    """
    dom = data.get("domestic", {})
    yoy = dom.get("yoy", {})

    price = dom.get("price", {}).get("total")
    price_change = yoy.get("price_change")
    elec_yoy = yoy.get("electricity")
    revenue_yoy = yoy.get("revenue")

    if price is None:
        return "（待补充）"

    # 计算分项影响
    share_impact = yoy.get("share_impact")  # 电量占比变化影响（含所有品类合计）
    price_impact = yoy.get("price_impact")  # 电价变化影响

    # 品类分解
    hydro = yoy.get("hydro", {})
    ne = yoy.get("new_energy", {})
    thermal = yoy.get("thermal", {})

    text = (
        f"上周，集团公司国内平均上网电价约每千瓦时{format_yuan(price)}元，"
        f"同比度电{format_fen(price_change)}，"
        f"上网电量同比{format_pct(elec_yoy)}、"
        f"发电收入同比{format_pct(revenue_yoy)}。"
        f"（电量结构变化影响度电均价{format_fen(share_impact)}、"
        f"电价变化影响度电均价{format_fen(price_impact)}。"
        f"各品类中：水电电量占比{format_pct_points(hydro.get('share_change'))}、"
        f"度电电价{format_fen(hydro.get('price_change'))}，"
        f"量价变化合计影响集团度电均价{format_fen(hydro.get('combined_impact'))}；"
        f"新能源电量占比{format_pct_points(ne.get('share_change'))}、"
        f"度电电价{format_fen(ne.get('price_change'))}，"
        f"量价变化合计影响集团度电均价{format_fen(ne.get('combined_impact'))}；"
        f"火电电量占比{format_pct_points(thermal.get('share_change'))}、"
        f"度电电价{format_fen(thermal.get('price_change'))}，"
        f"量价变化合计影响集团度电均价{format_fen(thermal.get('combined_impact'))}）"
    )
    return text


def generate_domestic_price_wow_paragraph(data: Dict[str, Any]) -> str:
    """生成国内上网电价环比分析段落。

    对应模板类似同比，但使用环比数据。
    """
    dom = data.get("domestic", {})
    wow = dom.get("wow", {})

    price_change = wow.get("price_change")
    elec_wow = wow.get("electricity")

    # 电费数据
    revenue = dom.get("revenue", {}).get("total")
    revenue_wow = wow.get("revenue")

    share_impact = wow.get("share_impact")
    price_impact = wow.get("price_impact")

    hydro = wow.get("hydro", {})
    ne = wow.get("new_energy", {})
    thermal = wow.get("thermal", {})

    text = (
        f"国内平均上网电价环比度电{format_fen(price_change)}，"
        f"国内上网电量环比{format_pct(elec_wow)}，"
        f"发电收入{format_revenue_billion(revenue)}、环比{format_pct(revenue_wow)}。"
        f"（电量结构变化影响度电均价{format_fen(share_impact)}、"
        f"电价变化影响度电均价{format_fen(price_impact)}。"
        f"各品类中：水电电量占比{format_pct_points(hydro.get('share_change'))}、"
        f"度电电价{format_fen(hydro.get('price_change'))}，"
        f"量价变化合计影响集团度电均价{format_fen(hydro.get('combined_impact'))}；"
        f"新能源电量占比{format_pct_points(ne.get('share_change'))}、"
        f"度电电价{format_fen(ne.get('price_change'))}，"
        f"量价变化合计影响集团度电均价{format_fen(ne.get('combined_impact'))}；"
        f"火电电量占比{format_pct_points(thermal.get('share_change'))}、"
        f"度电电价{format_fen(thermal.get('price_change'))}，"
        f"量价变化合计对集团度电基本无影响）"
    )
    return text


def generate_category_price_reason_paragraph(
    category_cn: str, data: Dict[str, Any], period: str = "wow"
) -> str:
    """生成单个品类的电价变动原因段落。

    Args:
        category_cn: 品类中文名（水电/风电/光伏/火电）
        data: 数据
        period: "yoy" 或 "wow"

    Returns:
        如 '水电电价环比下降的原因：度电电价环比下降0.4分，主要原因是···。'
    """
    # 中文名 → 数据键名映射
    cn_to_key = {
        "水电": "hydro",
        "新能源": "new_energy",
        "风电": "wind",
        "光伏": "solar",
        "火电": "thermal",
    }
    key = cn_to_key.get(category_cn)
    if not key:
        return f"（{category_cn}电价分析待补充）"

    dom = data.get("domestic", {})
    period_data = dom.get(period, {})
    cat_data = period_data.get(key, {})

    period_label = "同比" if period == "yoy" else "环比"
    price_change = cat_data.get("price_change")

    return (
        f"{category_cn}电价{period_label}{format_direction(price_change, '提高', '下降')}的原因："
        f"度电电价{period_label}{format_fen(price_change)}，"
        f"主要原因是···。"
    )


def generate_revenue_summary(data: Dict[str, Any]) -> str:
    """生成发电收入总结段落。

    对应模板：'上周，集团公司国内发电收入X亿元，同比提高/下降约X%...
    环比提高/下降X%...'
    """
    dom = data.get("domestic", {})
    yoy = dom.get("yoy", {})
    wow = dom.get("wow", {})
    reasons = data.get("reasons", {})

    revenue = dom.get("revenue", {}).get("total")
    rev_yoy = yoy.get("revenue")
    rev_wow = wow.get("revenue")
    elec_yoy = yoy.get("electricity")
    elec_wow = wow.get("electricity")

    # 品类收入同比
    hydro_rev_yoy = yoy.get("hydro", {}).get("combined_impact")
    ne_rev_yoy = yoy.get("new_energy", {}).get("combined_impact")

    # 原因文本
    yoy_reason = reasons.get("yoy_summary") or "···"
    wow_reason = reasons.get("wow_summary") or "···"

    return (
        f"上周，集团公司国内发电收入{format_revenue_billion(revenue)}，"
        f"同比{format_pct(rev_yoy)}（上网电量同比{format_pct(elec_yoy)}），"
        f"主要原因是{yoy_reason}；"
        f"环比{format_pct(rev_wow)}（上网电量环比{format_pct(elec_wow)}），"
        f"主要原因是{wow_reason}。"
    )


def generate_all_analysis_paragraphs(data: Dict[str, Any]) -> List[str]:
    """生成全部自动填充的分析段落。

    Returns:
        段落文本列表，按文档顺序排列
    """
    paragraphs = []

    # 1. 电量概述
    paragraphs.append(generate_electricity_summary(data))

    # 2. 国内电量同比/环比
    paragraphs.append(generate_domestic_yoy_paragraph(data))

    # 3. 国内上网电价同比分析
    paragraphs.append(generate_domestic_price_yoy_paragraph(data))

    # 4. 国内上网电价环比分析
    paragraphs.append(generate_domestic_price_wow_paragraph(data))

    # 5. 各品类电价变动原因
    for cat in ["水电", "风电", "光伏", "火电"]:
        paragraphs.append(generate_category_price_reason_paragraph(cat, data, "wow"))

    # 6. 发电收入总结
    paragraphs.append(generate_revenue_summary(data))

    return paragraphs


def generate_spot_price_overview(data: Dict[str, Any]) -> str:
    """生成现货市场价格概述段落。

    对应真实文档 Para 32 风格：
    '现货市场价格信息。上周，国内现货市场正式运行地区中，
    周均价最高为浙江每千瓦时0.429元、周均价最低为甘肃每千瓦时0.162元。'
    """
    spot_prices = data.get("spot_prices", {})
    regions = spot_prices.get("regions", [])
    spot_data = spot_prices.get("data", {})

    if not regions or not spot_data:
        return "现货市场价格信息。（待补充）"

    # 找最高和最低均价
    max_region = None
    min_region = None
    max_price = -1.0
    min_price = 999.0

    for region in regions:
        d = spot_data.get(region, {})
        avg = d.get("avg")
        if avg is not None:
            if avg > max_price:
                max_price = avg
                max_region = region
            if avg < min_price:
                min_price = avg
                min_region = region

    parts = ["现货市场价格信息。"]

    if max_region and min_region:
        parts.append(
            f"上周，国内现货市场正式运行地区中，"
            f"周均价最高为{max_region}每千瓦时{max_price:.3f}元、"
            f"周均价最低为{min_region}每千瓦时{min_price:.3f}元。"
        )

    # 附带各地区的同比/环比变化原因（如有）
    for region in regions:
        d = spot_data.get(region, {})
        yoy_reason = d.get("yoy_reason")
        if yoy_reason:
            parts.append(f"{region}：{yoy_reason}")
            break  # 只取第一个地区的原因作为示例

    return "".join(parts)
