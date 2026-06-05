"""数据验证脚本入口"""

import argparse
import sys
import json
from pathlib import Path

from src.validator.schema_validator import SchemaValidator


def main():
    parser = argparse.ArgumentParser(description="JSON 数据验证")

    parser.add_argument("--json", "-j", required=True, help="JSON 文件路径")
    parser.add_argument("--schema", "-s", default="data/schema/weekly_data.schema.json", help="Schema 文件")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    args = parser.parse_args()

    # 检查文件
    json_path = Path(args.json)
    if not json_path.exists():
        print(f"错误: 文件不存在 - {json_path}")
        sys.exit(1)

    # 加载数据
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 校验
    validator = SchemaValidator(args.schema)
    result = validator.full_validate(data)

    # 输出结果
    print(f"\n校验状态: {result['status']}")
    print(f"Schema 有效: {result['schema_valid']}")

    print(f"\n结构检查:")
    structure = result['structure']
    print(f"  meta: {structure['has_meta']}")
    print(f"  organizations: {structure['has_organizations']}")
    print(f"  validation_report: {structure['has_validation_report']}")
    print(f"  组织数量: {structure['org_count']}")

    if structure['missing_fields']:
        print(f"  缺失字段: {structure['missing_fields']}")

    # 输出错误
    if result['error_count'] > 0:
        print(f"\n错误 ({result['error_count']}):")
        for err in result['errors']:
            if err['level'] == 'ERROR':
                if args.verbose:
                    print(f"  - [{err.get('path', [])}] {err['message']}")
                else:
                    print(f"  - {err['message']}")

    # 输出警告
    if result['warn_count'] > 0:
        print(f"\n警告 ({result['warn_count']}):")
        for err in result['errors']:
            if err['level'] == 'WARN':
                if args.verbose:
                    print(f"  - {err['message']}")
                    if 'expected' in err and 'actual' in err:
                        print(f"    预期: {err['expected']}, 实际: {err['actual']}")
                else:
                    print(f"  - {err['message']}")

    # 返回状态
    if result['status'] == 'error':
        return 1
    elif result['status'] == 'warning':
        return 2
    else:
        print("\n✅ 校验通过")
        return 0


if __name__ == "__main__":
    sys.exit(main())