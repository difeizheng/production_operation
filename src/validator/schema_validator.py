"""Schema 校验器 - 验证数据是否符合 JSON Schema"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from jsonschema import validate, ValidationError, Draft7Validator


class SchemaValidator:
    """JSON Schema 校验器"""

    def __init__(self, schema_path: str = "data/schema/weekly_data.schema.json"):
        self.schema_path = Path(schema_path)
        self.schema: Dict = {}
        self._load_schema()

    def _load_schema(self) -> None:
        """加载 JSON Schema"""
        if self.schema_path.exists():
            with open(self.schema_path, "r", encoding="utf-8") as f:
                self.schema = json.load(f)
        else:
            raise FileNotFoundError(f"Schema 文件不存在: {self.schema_path}")

    def validate(self, data: Dict) -> Tuple[bool, List[Dict]]:
        """
        校验数据是否符合 Schema

        Args:
            data: 待校验数据

        Returns:
            (是否通过, 错误列表)
        """
        errors = []

        # 使用 jsonschema 校验
        validator = Draft7Validator(self.schema)

        for error in validator.iter_errors(data):
            errors.append({
                "level": "ERROR",
                "path": list(error.absolute_path),
                "message": error.message,
                "validator": error.validator,
                "expected": error.schema.get("type") if "type" in error.schema else None
            })

        return len(errors) == 0, errors

    def validate_structure(self, data: Dict) -> Dict:
        """
        校验数据结构（快速检查）

        Args:
            data: 待校验数据

        Returns:
            校验结果摘要
        """
        result = {
            "has_meta": False,
            "has_organizations": False,
            "has_validation_report": False,
            "org_count": 0,
            "missing_fields": []
        }

        # 检查必填字段
        required_fields = ["meta", "organizations", "validation_report"]
        for field in required_fields:
            if field not in data:
                result["missing_fields"].append(field)

        result["has_meta"] = "meta" in data
        result["has_organizations"] = "organizations" in data
        result["has_validation_report"] = "validation_report" in data

        if result["has_organizations"]:
            result["org_count"] = len(data["organizations"])

        return result

    def validate_business_rules(self, data: Dict) -> List[Dict]:
        """
        校验业务规则（电费一致性等）

        Args:
            data: 待校验数据

        Returns:
            业务校验错误列表
        """
        errors = []

        # 检查电费一致性（电费 ≈ 电量 × 电价）
        for org_name, org_data in data.get("organizations", {}).items():
            metrics = org_data.get("metrics", {})

            for energy_type, energy_metrics in metrics.items():
                electricity = energy_metrics.get("电量", {})
                price = energy_metrics.get("电价", {})
                revenue = energy_metrics.get("电费", {})

                e_val = electricity.get("value")
                p_val = price.get("value")
                r_val = revenue.get("value")

                if e_val and p_val and r_val:
                    # 计算预期电费
                    expected = e_val * p_val / 10000  # 万千瓦时 × 元/千瓦时 = 万元
                    actual = r_val
                    diff_pct = abs(expected - actual) / actual * 100 if actual != 0 else 0

                    if diff_pct > 5:  # 误差超过 5%
                        errors.append({
                            "level": "WARN",
                            "message": f"{org_name}.{energy_type} 电费不一致",
                            "field": f"{org_name}.{energy_type}.电费",
                            "expected": round(expected, 2),
                            "actual": actual,
                            "diff_pct": round(diff_pct, 2)
                        })

        return errors

    def full_validate(self, data: Dict) -> Dict:
        """
        完整校验（Schema + 结构 + 业务）

        Args:
            data: 待校验数据

        Returns:
            完整校验报告
        """
        # Schema 校验
        schema_pass, schema_errors = self.validate(data)

        # 结构校验
        structure_result = self.validate_structure(data)

        # 业务校验
        business_errors = self.validate_business_rules(data)

        # 合并错误
        all_errors = schema_errors + business_errors

        # 确定状态
        error_count = len([e for e in all_errors if e["level"] == "ERROR"])
        warn_count = len([e for e in all_errors if e["level"] == "WARN"])

        if error_count > 0:
            status = "error"
        elif warn_count > 0:
            status = "warning"
        else:
            status = "pass"

        return {
            "status": status,
            "schema_valid": schema_pass,
            "structure": structure_result,
            "errors": all_errors,
            "error_count": error_count,
            "warn_count": warn_count,
            "summary": f"校验完成：{status}，{error_count} 错误，{warn_count} 警告"
        }


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="JSON Schema 校验")
    parser.add_argument("--json", required=True, help="JSON 文件路径")
    parser.add_argument("--schema", default="data/schema/weekly_data.schema.json", help="Schema 文件")

    args = parser.parse_args()

    validator = SchemaValidator(args.schema)

    # 加载 JSON
    with open(args.json, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 完整校验
    result = validator.full_validate(data)

    print(f"\n校验状态: {result['status']}")
    print(f"Schema 有效: {result['schema_valid']}")
    print(f"组织数量: {result['structure']['org_count']}")
    print(f"\n错误 ({result['error_count']}):")
    for err in result["errors"]:
        if err["level"] == "ERROR":
            print(f"  - {err['message']}")

    print(f"\n警告 ({result['warn_count']}):")
    for err in result["errors"]:
        if err["level"] == "WARN":
            print(f"  - {err['message']}")


if __name__ == "__main__":
    main()