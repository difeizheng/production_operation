"""JSON 数据存储器 - 管理数据的读写和版本控制"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class JSONStore:
    """JSON 数据存储器"""

    def __init__(self, base_dir: str = "data/processed"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        data: Dict,
        year: int,
        week: int,
        version: Optional[str] = None
    ) -> str:
        """
        保存数据到 JSON 文件

        Args:
            data: 数据
            year: 年份
            week: 周数
            version: 版本标识

        Returns:
            文件路径
        """
        filename = f"{year}_week{week}"
        if version:
            filename += f"_v{version}"
        filename += ".json"

        file_path = self.base_dir / filename

        # 添加保存时间
        data["meta"]["saved_at"] = datetime.now().isoformat()

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return str(file_path)

    def load(self, year: int, week: int, version: Optional[str] = None) -> Optional[Dict]:
        """
        加载指定周数据

        Args:
            year: 年份
            week: 周数
            version: 版本标识

        Returns:
            数据字典，不存在返回 None
        """
        filename = f"{year}_week{week}"
        if version:
            filename += f"_v{version}"
        filename += ".json"

        file_path = self.base_dir / filename

        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_latest(self, year: int, week: int) -> Optional[Dict]:
        """
        加载最新版本数据

        Args:
            year: 年份
            week: 周数

        Returns:
            数据字典
        """
        # 查找所有版本
        pattern = f"{year}_week{week}_v*.json"
        versions = list(self.base_dir.glob(pattern))

        if not versions:
            # 尝试无版本文件
            return self.load(year, week)

        # 按版本号排序，取最新
        versions.sort(key=lambda x: x.stem.split("_v")[-1], reverse=True)
        latest = versions[0]

        with open(latest, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_weeks(self, year: Optional[int] = None) -> List[Dict]:
        """
        列出所有周数据

        Args:
            year: 年份（可选，不指定则全部）

        Returns:
            [{year, week, file, size, modified}]
        """
        pattern = "*.json"
        files = list(self.base_dir.glob(pattern))

        weeks = []
        for file in files:
            # 解析文件名
            stem = file.stem
            parts = stem.split("_")
            if len(parts) >= 2:
                try:
                    year_part = parts[0]
                    week_part = parts[1].replace("week", "").split("_v")[0]

                    file_year = int(year_part)
                    file_week = int(week_part)

                    if year and file_year != year:
                        continue

                    weeks.append({
                        "year": file_year,
                        "week": file_week,
                        "file": str(file),
                        "size": file.stat().st_size,
                        "modified": datetime.fromtimestamp(file.stat().st_mtime).isoformat()
                    })
                except (ValueError, IndexError):
                    continue

        # 按周数排序
        weeks.sort(key=lambda x: (x["year"], x["week"]))
        return weeks

    def exists(self, year: int, week: int) -> bool:
        """检查数据是否存在"""
        filename = f"{year}_week{week}.json"
        file_path = self.base_dir / filename
        return file_path.exists()

    def get_history(self, year: int, week: int, count: int = 4) -> List[Dict]:
        """
        获取历史数据（前 N 周）

        Args:
            year: 当前年份
            week: 当前周数
            count: 周数

        Returns:
            历史数据列表（按时间倒序）
        """
        history = []

        for i in range(1, count + 1):
            prev_week = week - i
            prev_year = year

            if prev_week <= 0:
                prev_year = year - 1
                prev_week = 52 + prev_week  # 简化处理

            data = self.load_latest(prev_year, prev_week)
            if data:
                history.append({
                    "year": prev_year,
                    "week": prev_week,
                    "data": data
                })

        return history

    def merge_weeks(self, weeks: List[Dict], strategy: str = "latest") -> Dict:
        """
        合并多周数据

        Args:
            weeks: 周数据列表
            strategy: 合并策略（latest, sum, avg）

        Returns:
            合合后的数据
        """
        if not weeks:
            return {}

        if strategy == "latest":
            return weeks[0]["data"]

        merged = {"organizations": {}}

        for week_info in weeks:
            data = week_info["data"]
            for org_name, org_data in data.get("organizations", {}).items():
                if org_name not in merged["organizations"]:
                    merged["organizations"][org_name] = org_data
                else:
                    # 合并指标
                    existing = merged["organizations"][org_name]
                    for energy_type, metrics in org_data.get("metrics", {}).items():
                        if energy_type not in existing["metrics"]:
                            existing["metrics"][energy_type] = metrics

        return merged

    def archive(self, year: int, week: int, archive_dir: str = "archive") -> str:
        """
        归档数据

        Args:
            year: 年份
            week: 周数
            archive_dir: 归档目录

        Returns:
            归档文件路径
        """
        data = self.load_latest(year, week)
        if not data:
            raise FileNotFoundError(f"数据不存在: {year}_week{week}")

        archive_path = Path(archive_dir) / str(year) / f"week{week}"
        archive_path.mkdir(parents=True, exist_ok=True)

        archive_file = archive_path / "data.json"

        with open(archive_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return str(archive_file)

    def get_statistics(self, year: int, week: int) -> Dict:
        """
        获取数据统计

        Args:
            year: 年份
            week: 周数

        Returns:
            统计信息
        """
        data = self.load_latest(year, week)
        if not data:
            return {"error": "数据不存在"}

        stats = {
            "org_count": len(data.get("organizations", {})),
            "energy_types": [],
            "metrics": [],
            "coverage": data.get("validation_report", {}).get("coverage", 0),
            "errors": len(data.get("validation_report", {}).get("errors", []))
        }

        # 统计能源类型和指标
        for org_data in data.get("organizations", {}).values():
            for energy_type in org_data.get("metrics", {}).keys():
                if energy_type not in stats["energy_types"]:
                    stats["energy_types"].append(energy_type)

            for energy_metrics in org_data.get("metrics", {}).values():
                for metric in energy_metrics.keys():
                    if metric not in stats["metrics"]:
                        stats["metrics"].append(metric)

        return stats


def main():
    """测试"""
    store = JSONStore()

    # 列出所有周数据
    weeks = store.list_weeks()
    print(f"已有数据周数: {len(weeks)}")
    for w in weeks:
        print(f"  {w['year']}年第{w['week']}周")


if __name__ == "__main__":
    main()