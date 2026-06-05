"""数据清洗器 - 清洗和标准化数据"""

import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class DataCleaner:
    """数据清洗器"""

    # 合理范围定义
    RANGES = {
        "电量": {"min": 0, "max": 10_000_000, "unit": "万千瓦时"},
        "电价": {"min": 0, "max": 1, "unit": "元/千瓦时"},
        "电费": {"min": 0, "max": 1_000_000, "unit": "万元"},
        "同比": {"min": -100, "max": 500, "unit": "%"},
        "环比": {"min": -50, "max": 50, "unit": "%"}
    }

    # 精度定义
    PRECISION = {
        "电量": 2,
        "电价": 3,
        "电费": 2,
        "同比": 1,
        "环比": 1
    }

    def __init__(self):
        pass

    def clean_value(
        self,
        value: Optional[float],
        metric: str,
        source: Optional[Dict] = None
    ) -> Tuple[Optional[float], Dict]:
        """
        清洗单个数值

        Args:
            value: 原始值
            metric: 指标名称
            source: 数据源信息

        Returns:
            (清洗后的值, 清洗报告)
        """
        report = {
            "original": value,
            "cleaned": None,
            "actions": [],
            "warnings": []
        }

        if value is None:
            report["actions"].append("null_value")
            return None, report

        # 1. 数值转换
        if isinstance(value, str):
            value = self._parse_string(value)
            report["actions"].append("string_conversion")

        if value is None:
            report["warnings"].append("conversion_failed")
            return None, report

        # 2. 范围检查
        range_info = self.RANGES.get(metric, {})
        min_val = range_info.get("min", 0)
        max_val = range_info.get("max", float("inf"))

        if value < min_val or value > max_val:
            report["warnings"].append(f"out_of_range ({min_val}-{max_val})")

        # 3. 精度处理
        precision = self.PRECISION.get(metric, 2)
        cleaned_value = round(value, precision)
        report["cleaned"] = cleaned_value

        if cleaned_value != value:
            report["actions"].append(f"precision_rounded({precision})")

        # 4. 添加置信度
        report["confidence"] = 1.0 if not report["warnings"] else 0.8

        return cleaned_value, report

    def _parse_string(self, text: str) -> Optional[float]:
        """从字符串解析数值"""
        text = str(text).strip()

        # 空值
        if not text or text in ["-", "—", "N/A", "无", ""]:
            return None

        # 移除逗号
        text = text.replace(",", "").replace("，", "")

        # 处理百分号
        if "%" in text:
            text = text.replace("%", "").strip()
            try:
                return float(text)
            except ValueError:
                return None

        # 处理单位（万千瓦时等）
        text = re.sub(r"[万千瓦时元元/千瓦时]", "", text)

        try:
            return float(text)
        except ValueError:
            return None

    def clean_organization_data(
        self,
        org_data: Dict,
        org_name: str
    ) -> Tuple[Dict, List[Dict]]:
        """
        清洗组织数据

        Args:
            org_data: 组织数据
            org_name: 组织名称

        Returns:
            (清洗后的数据, 清洗报告列表)
        """
        cleaned_data = org_data.copy()
        reports = []

        metrics = cleaned_data.get("metrics", {})

        for energy_type, energy_metrics in metrics.items():
            for metric_name, metric_data in energy_metrics.items():
                if isinstance(metric_data, dict) and "value" in metric_data:
                    original_value = metric_data.get("value")
                    source = metric_data.get("source")

                    cleaned_value, report = self.clean_value(
                        original_value,
                        metric_name,
                        source
                    )

                    # 更新数据
                    metric_data["value"] = cleaned_value
                    metric_data["cleaned"] = report.get("cleaned")
                    metric_data["confidence"] = report.get("confidence", 1.0)

                    # 记录报告
                    if report["warnings"]:
                        reports.append({
                            "org": org_name,
                            "energy_type": energy_type,
                            "metric": metric_name,
                            "warnings": report["warnings"],
                            "original": original_value,
                            "cleaned": cleaned_value
                        })

        return cleaned_data, reports

    def clean_full_data(self, data: Dict) -> Tuple[Dict, List[Dict]]:
        """
        清洗完整数据集

        Args:
            data: 完整数据

        Returns:
            (清洗后的数据, 清洗报告)
        """
        cleaned_data = data.copy()
        all_reports = []

        organizations = cleaned_data.get("organizations", {})

        for org_name, org_data in organizations.items():
            cleaned_org, org_reports = self.clean_organization_data(org_data, org_name)
            cleaned_data["organizations"][org_name] = cleaned_org
            all_reports.extend(org_reports)

        # 更新验证报告
        if "validation_report" in cleaned_data:
            cleaned_data["validation_report"]["cleaning_report"] = {
                "cleaned_count": len(organizations),
                "warning_count": len(all_reports),
                "cleaned_at": datetime.now().isoformat()
            }

        return cleaned_data, all_reports

    def fill_missing_values(
        self,
        data: Dict,
        strategy: str = "null"
    ) -> Tuple[Dict, List[Dict]]:
        """
        填充缺失值

        Args:
            data: 数据
            strategy: 填充策略（null, zero, mean, last_week）

        Returns:
            (填充后的数据, 填充报告)
        """
        filled_data = data.copy()
        reports = []

        for org_name, org_data in filled_data.get("organizations", {}).items():
            metrics = org_data.get("metrics", {})

            for energy_type, energy_metrics in metrics.items():
                for metric_name, metric_data in energy_metrics.items():
                    if isinstance(metric_data, dict) and metric_data.get("value") is None:
                        # 填充策略
                        fill_value = None

                        if strategy == "zero":
                            fill_value = 0.0

                        # 未来可扩展：mean, last_week

                        if fill_value is not None:
                            metric_data["value"] = fill_value
                            metric_data["filled"] = True
                            metric_data["fill_strategy"] = strategy

                            reports.append({
                                "org": org_name,
                                "energy_type": energy_type,
                                "metric": metric_name,
                                "filled_with": fill_value,
                                "strategy": strategy
                            })

        return filled_data, reports

    def calculate_derived_metrics(self, data: Dict) -> Dict:
        """
        计算衍生指标（电费、同比、环比）

        Args:
            data: 数据

        Returns:
            计算后的数据
        """
        calculated_data = data.copy()

        for org_name, org_data in calculated_data.get("organizations", {}).items():
            metrics = org_data.get("metrics", {})

            for energy_type, energy_metrics in metrics.items():
                # 计算电费（电量 × 电价）
                electricity = energy_metrics.get("电量", {})
                price = energy_metrics.get("电价", {})

                e_val = electricity.get("value")
                p_val = price.get("value")

                if e_val and p_val and "电费" not in energy_metrics:
                    revenue = round(e_val * p_val / 10000, 2)  # 万元
                    energy_metrics["电费"] = {
                        "value": revenue,
                        "calculated": True,
                        "formula": "电量 × 电价 / 10000"
                    }

        return calculated_data


def main():
    """测试"""
    cleaner = DataCleaner()

    # 测试数值清洗
    print("数值清洗测试:")
    tests = [
        (550544.26, "电量"),
        (0.268, "电价"),
        ("-", "电量"),
        ("125,680.5", "电量"),
        ("25.3%", "同比"),
        (9999999, "电量")  # 超出范围
    ]

    for value, metric in tests:
        cleaned, report = cleaner.clean_value(value, metric)
        print(f"  {value} ({metric}) -> {cleaned}")
        if report["warnings"]:
            print(f"    警告: {report['warnings']}")


if __name__ == "__main__":
    main()