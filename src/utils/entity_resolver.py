"""实体解析器 - 词典匹配与同义词转换"""

import json
from pathlib import Path
from typing import Dict, Optional, List, Tuple


class EntityResolver:
    """实体解析器，负责词典匹配和同义词转换"""

    def __init__(self, dict_dir: str = "data/dictionaries"):
        self.dict_dir = Path(dict_dir)
        self.organizations: Dict = {}
        self.energy_types: Dict = {}
        self.metrics: Dict = {}
        self.synonyms: Dict = {}
        self._load_dictionaries()

    def _load_dictionaries(self) -> None:
        """加载所有词典"""
        self.organizations = self._load_json("organizations.json")
        self.energy_types = self._load_json("energy_types.json")
        self.metrics = self._load_json("metrics.json")
        self.synonyms = self._load_json("synonyms.json")

    def _load_json(self, filename: str) -> Dict:
        """加载 JSON 词典文件"""
        file_path = self.dict_dir / filename
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def resolve_organization(self, text: str) -> Tuple[Optional[str], Optional[Dict]]:
        """
        解析组织名称

        Args:
            text: 待解析文本

        Returns:
            (标准名称, 组织信息) 或 (None, None)
        """
        if not text:
            return None, None

        text = str(text).strip()

        # 1. 直接匹配
        if text in self.organizations:
            return text, self.organizations[text]

        # 2. 同义词匹配
        org_synonyms = self.synonyms.get("organizations", {})
        if text in org_synonyms:
            std_name = org_synonyms[text]
            return std_name, self.organizations.get(std_name)

        # 3. 简称匹配
        for org_name, org_info in self.organizations.items():
            short_names = org_info.get("short_names", [])
            if text in short_names:
                return org_name, org_info

        # 4. 模糊匹配（包含）
        for org_name in self.organizations.keys():
            if org_name in text or text in org_name:
                return org_name, self.organizations[org_name]

        return None, None

    def resolve_energy_type(self, text: str) -> Tuple[Optional[str], Optional[Dict]]:
        """
        解析能源类型

        Args:
            text: 待解析文本

        Returns:
            (标准名称, 能源信息) 或 (None, None)
        """
        if not text:
            return None, None

        text = str(text).strip()

        # 1. 直接匹配
        if text in self.energy_types:
            return text, self.energy_types[text]

        # 2. 同义词匹配
        energy_synonyms = self.synonyms.get("energy_types", {})
        if text in energy_synonyms:
            std_name = energy_synonyms[text]
            return std_name, self.energy_types.get(std_name)

        # 3. 模糊匹配
        for energy_name in self.energy_types.keys():
            if energy_name in text or text in energy_name:
                return energy_name, self.energy_types[energy_name]

        return None, None

    def resolve_metric(self, text: str) -> Tuple[Optional[str], Optional[Dict]]:
        """
        解析指标名称

        Args:
            text: 待解析文本

        Returns:
            (标准名称, 指标信息) 或 (None, None)
        """
        if not text:
            return None, None

        text = str(text).strip()

        # 1. 直接匹配
        if text in self.metrics:
            return text, self.metrics[text]

        # 2. 同义词匹配
        metric_synonyms = self.synonyms.get("metrics", {})
        if text in metric_synonyms:
            std_name = metric_synonyms[text]
            return std_name, self.metrics.get(std_name)

        # 3. 模糊匹配
        for metric_name in self.metrics.keys():
            if metric_name in text or text in metric_name:
                return metric_name, self.metrics[metric_name]

        return None, None

    def resolve_cell_header(self, header_text: str) -> Dict:
        """
        解析表头单元格，提取能源类型和指标

        Args:
            header_text: 表头文本，如 "水电电量(万千瓦时)"

        Returns:
            {"energy_type": str, "metric": str, "unit": str}
        """
        result = {
            "energy_type": None,
            "metric": None,
            "unit": None
        }

        if not header_text:
            return result

        text = str(header_text).strip()

        # 提取单位（括号内）
        unit_match = None
        if "(" in text or "（" in text:
            # 中文括号
            if "（" in text:
                parts = text.split("（")
                text = parts[0]
                if len(parts) > 1:
                    unit_match = parts[1].replace("）", "").strip()
            # 英文括号
            elif "(" in text:
                parts = text.split("(")
                text = parts[0]
                if len(parts) > 1:
                    unit_match = parts[1].replace(")", "").strip()

        result["unit"] = unit_match

        # 尝试匹配能源类型 + 指标组合
        for energy_name in self.energy_types.keys():
            if energy_name in text:
                result["energy_type"] = energy_name
                remaining = text.replace(energy_name, "").strip()
                if remaining:
                    metric_name, _ = self.resolve_metric(remaining)
                    if metric_name:
                        result["metric"] = metric_name
                break

        # 如果未找到能源类型，尝试匹配指标
        if not result["metric"]:
            metric_name, _ = self.resolve_metric(text)
            if metric_name:
                result["metric"] = metric_name

        return result

    def get_all_org_names(self) -> List[str]:
        """获取所有组织名称列表"""
        return list(self.organizations.keys())

    def get_all_energy_names(self) -> List[str]:
        """获取所有能源类型名称列表"""
        return list(self.energy_types.keys())

    def get_all_metric_names(self) -> List[str]:
        """获取所有指标名称列表"""
        return list(self.metrics.keys())


if __name__ == "__main__":
    # 测试
    resolver = EntityResolver()

    # 测试组织解析
    print("组织解析测试:")
    tests = ["长江电力", "长电", "新能源", "三峡集团"]
    for t in tests:
        name, info = resolver.resolve_organization(t)
        print(f"  '{t}' -> {name}")

    # 测试能源解析
    print("\n能源类型解析测试:")
    tests = ["水电", "水力发电", "风电", "太阳能"]
    for t in tests:
        name, info = resolver.resolve_energy_type(t)
        print(f"  '{t}' -> {name}")

    # 测试指标解析
    print("\n指标解析测试:")
    tests = ["电量", "上网电量", "电价", "平均电价"]
    for t in tests:
        name, info = resolver.resolve_metric(t)
        print(f"  '{t}' -> {name}")

    # 测试表头解析
    print("\n表头解析测试:")
    tests = ["水电电量(万千瓦时)", "风电电价（元/千瓦时）", "合计"]
    for t in tests:
        result = resolver.resolve_cell_header(t)
        print(f"  '{t}' -> {result}")