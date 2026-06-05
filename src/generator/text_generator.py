"""文本生成器 - 生成报告文本内容"""

from typing import Dict, List, Optional
from datetime import datetime


class TextGenerator:
    """文本生成器，生成周报所需的文本内容"""

    def __init__(self):
        self.templates = {
            "header": "{{year}}年第{{week}}周生产情况（{{start_date}}至{{end_date}}）",
            "electricity_summary": "上周，集团公司合计上网电量{{total}}亿千瓦时，同比{{yoy}}%，环比{{mom}}%。",
            "organization_intro": "{{org_name}}上周上网电量{{electricity}}万千瓦时，电价{{price}}元/千瓦时，电费{{revenue}}万元。",
            "energy_breakdown": "其中，{{energy_type}}发电量{{value}}万千瓦时，占比{{percentage}}%。",
            "market_price": "上周市场平均电价{{price}}元/千瓦时，{{trend}}。",
            "policy_update": "{{title}}（{{date}}）：{{content}}"
        }

    def format_value(self, value: Optional[float], unit: str = "", precision: int = 2) -> str:
        """格式化数值"""
        if value is None:
            return "数据缺失"

        # 大数值转亿
        if unit == "万千瓦时" and value > 10000:
            return f"{value / 10000:.{precision}f}亿千瓦时"

        # 格式化
        formatted = f"{value:.{precision}f}"
        if unit:
            formatted += unit

        return formatted

    def format_percentage(self, value: Optional[float]) -> str:
        """格式化百分比（同比/环比）"""
        if value is None:
            return "数据缺失"

        if value > 0:
            return f"增长{value:.1f}%"
        elif value < 0:
            return f"下降{abs(value):.1f}%"
        else:
            return "持平"

    def generate_header(self, meta: Dict) -> str:
        """生成报告标题"""
        year = meta.get("year", "")
        week = meta.get("week", "")
        start_date = meta.get("start_date", "")
        end_date = meta.get("end_date", "")

        return f"{year}年第{week}周生产情况（{start_date}至{end_date}）"

    def generate_electricity_summary(self, data: Dict) -> str:
        """生成电量概述"""
        organizations = data.get("organizations", {})

        # 计算总量
        total = 0
        for org_data in organizations.values():
            metrics = org_data.get("metrics", {})
            if "合计" in metrics:
                electricity = metrics["合计"].get("电量", {})
                value = electricity.get("value", 0) or 0
                total += value

        # 转为亿千瓦时
        total_billion = total / 10000 if total > 10000 else total

        # 同比环比（简化，实际需要历史数据）
        yoy = self.format_percentage(data.get("同比", None))
        mom = self.format_percentage(data.get("环比", None))

        return f"上周，集团公司合计上网电量{total_billion:.2f}亿千瓦时。"

    def generate_organization_section(self, org_name: str, org_data: Dict) -> List[str]:
        """生成组织段落"""
        texts = []

        metrics = org_data.get("metrics", {})

        # 总体概述
        total_electricity = 0
        total_price = 0
        total_revenue = 0

        if "合计" in metrics:
            electricity = metrics["合计"].get("电量", {}).get("value", 0) or 0
            price = metrics["合计"].get("电价", {}).get("value", 0) or 0
            revenue = metrics["合计"].get("电费", {}).get("value", 0) or 0

            total_electricity = electricity
            total_price = price
            total_revenue = revenue

        # 组织概述
        full_name = org_data.get("full_name", org_name)
        texts.append(
            f"（一）{full_name}\n"
            f"{org_name}上周上网电量{self.format_value(total_electricity, '万千瓦时')}，"
            f"平均电价{self.format_value(total_price, '元/千瓦时', 3)}，"
            f"电费收入{self.format_value(total_revenue, '万元')}。"
        )

        # 各能源类型详情
        energy_details = []
        for energy_type, energy_metrics in metrics.items():
            if energy_type == "合计":
                continue

            value = energy_metrics.get("电量", {}).get("value", 0) or 0
            if value > 0:
                percentage = value / total_electricity * 100 if total_electricity > 0 else 0
                energy_details.append(
                    f"其中，{energy_type}发电量{self.format_value(value, '万千瓦时')}，"
                    f"占比{percentage:.1f}%。"
                )

        if energy_details:
            texts.append("".join(energy_details))

        return texts

    def generate_external_info(self, data: Dict) -> str:
        """生成外部信息段落"""
        external = data.get("external_info", {})

        texts = ["二、外部信息\n"]

        # 市场价格
        market_price = external.get("market_price", {})
        if market_price:
            price = market_price.get("value", 0)
            source = market_price.get("source", "")
            texts.append(
                f"（一）市场价格\n"
                f"上周电力市场平均价格{self.format_value(price, '元/千瓦时', 3)}，"
                f"数据来源：{source}。"
            )

        # 政策更新
        policies = external.get("policy_updates", [])
        if policies:
            texts.append("（二）政策动态")
            for policy in policies:
                title = policy.get("title", "")
                content = policy.get("content", "")
                date = policy.get("date", "")
                texts.append(f"  {title}（{date}）：{content}")

        return "\n".join(texts)

    def generate_full_report_text(self, data: Dict) -> str:
        """生成完整报告文本"""
        sections = []

        # 标题
        meta = data.get("meta", {})
        sections.append(self.generate_header(meta))
        sections.append("")  # 空行

        # 一、上周销售情况
        sections.append("一、上周销售情况")
        sections.append("")

        # 电量概述
        sections.append("（一）电量销售情况")
        sections.append(self.generate_electricity_summary(data))
        sections.append("")

        # 各组织详情
        organizations = data.get("organizations", {})
        org_texts = []
        for org_name, org_data in organizations.items():
            org_section = self.generate_organization_section(org_name, org_data)
            org_texts.extend(org_section)
            org_texts.append("")  # 空行

        sections.extend(org_texts)

        # 二、外部信息
        if data.get("external_info"):
            sections.append(self.generate_external_info(data))
            sections.append("")

        # 结尾
        sections.append("三、本周重点工作安排")
        sections.append("（待补充）")

        return "\n".join(sections)

    def generate_summary_table(self, data: Dict) -> List[Dict]:
        """生成汇总表格数据"""
        rows = []

        organizations = data.get("organizations", {})
        for org_name, org_data in organizations.items():
            metrics = org_data.get("metrics", {})

            if "合计" in metrics:
                electricity = metrics["合计"].get("电量", {}).get("value")
                price = metrics["合计"].get("电价", {}).get("value")
                revenue = metrics["合计"].get("电费", {}).get("value")

                rows.append({
                    "组织": org_name,
                    "电量": self.format_value(electricity, "万千瓦时"),
                    "电价": self.format_value(price, "元/千瓦时", 3),
                    "电费": self.format_value(revenue, "万元")
                })

        return rows


def main():
    """测试"""
    generator = TextGenerator()

    # 测试示例数据
    test_data = {
        "meta": {
            "year": 2026,
            "week": 21,
            "start_date": "2026-05-18",
            "end_date": "2026-05-24"
        },
        "organizations": {
            "长江电力": {
                "full_name": "中国长江电力股份有限公司",
                "metrics": {
                    "合计": {
                        "电量": {"value": 550544.26},
                        "电价": {"value": 0.268},
                        "电费": {"value": 147525.88}
                    },
                    "水电": {
                        "电量": {"value": 548700}
                    }
                }
            }
        }
    }

    text = generator.generate_full_report_text(test_data)
    print(text)


if __name__ == "__main__":
    main()