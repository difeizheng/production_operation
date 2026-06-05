"""
分析器基类 (Base Analyzer)
==========================

所有具体分析器（国内/国际/市场化/碳资产）的抽象基类。
设计参考: docs/design/report-generator-v2-architecture.md 第 2.2 节
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AnalysisResult:
    """分析结果统一数据结构

    所有 4 个 Analyzer 的输出都遵循此结构，
    便于 Streamlit UI 和 Word 生成器统一处理。
    """
    # 基础信息
    dimension: str                    # 维度名: "国内" / "国际" / "市场化" / "碳资产"
    section_ids: List[int]            # 包含的段: [1, 2] / [3, 4] / [5, 6, 7] / [8]
    analyzer_name: str                # 分析器类名

    # 一句话总结
    summary: str                      # 一句话总结: "以量补价，量增价跌..."
    story: str                        # 业务故事（多段）

    # 关键指标
    kpis: Dict[str, Any] = field(default_factory=dict)
    # 格式: {"总电量": 89.1, "度电均价": 0.311, "同比变化": -0.9, ...}

    # 同比 / 环比
    yoy_data: Dict[str, Any] = field(default_factory=dict)
    mom_data: Dict[str, Any] = field(default_factory=dict)

    # 表格数据
    tables: List[Dict[str, Any]] = field(default_factory=list)
    # 格式: [{"title": "5大品类", "data": [...]}]

    # 图表数据（Plotly 友好）
    charts: List[Dict[str, Any]] = field(default_factory=list)
    # 格式: [{"title": "同比环比对比", "type": "bar", "data": {...}}]

    # 关键洞察
    insights: List[str] = field(default_factory=list)

    # 异常检测结果
    anomalies: List[Dict[str, Any]] = field(default_factory=list)
    # 格式: [{"level": "warning", "message": "..."}]

    # 元数据
    computed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "2.0.0-skeleton"


class BaseAnalyzer(ABC):
    """所有分析器的基类

    核心原则:
    1. 单一职责: 每个 Analyzer 负责一个维度
    2. 可测试: 清晰输入输出，便于单元测试
    3. 可插拔: 接口统一，可任意替换
    4. 文档化: 与分析框架文档严格对齐
    """

    # 子类必须定义
    dimension_name: str = ""           # 维度名
    section_ids: List[int] = []       # 对应段号
    analyzer_name: str = ""           # 分析器类名

    def __init__(self, json_data: dict, config: Optional[dict] = None):
        """
        初始化分析器

        Args:
            json_data: 从 data/processed/ 读取的标准化 JSON
            config: 配置参数（如阈值、显示选项）
        """
        self.data = json_data or {}
        self.config = config or {}
        self.result: Optional[AnalysisResult] = None

    @abstractmethod
    def analyze(self) -> AnalysisResult:
        """执行分析，返回标准化的 AnalysisResult

        子类必须实现此方法，完成以下步骤:
        1. 提取所需数据 (从 self.data)
        2. 同比/环比计算
        3. 量价分解或其他归因
        4. 异常检测
        5. 生成故事文本
        6. 构造 AnalysisResult 返回
        """
        pass

    @abstractmethod
    def validate_inputs(self) -> bool:
        """检查输入数据是否完整

        子类必须实现:
        - 验证必需的字段是否存在
        - 返回 True / False
        - 可选: 收集缺失字段到 self.missing_fields
        """
        pass

    # === 通用计算方法（子类可复用） ===

    def calculate_yoy(self, current: float, last_year: float) -> float:
        """同比计算（百分比，带零值保护）

        Args:
            current: 本期值
            last_year: 去年同期值

        Returns:
            同比变化百分比（如 +3.3 表示 +3.3%）
        """
        if last_year == 0:
            return 0.0
        return (current - last_year) / last_year * 100

    def calculate_mom(self, current: float, last_week: float) -> float:
        """环比计算（百分比，带零值保护）"""
        if last_week == 0:
            return 0.0
        return (current - last_week) / last_week * 100

    def calculate_yoy_fen(self, current: float, last_year: float) -> float:
        """同比计算（分/度，电价专用）"""
        return (current - last_year) * 100

    def calculate_mom_fen(self, current: float, last_week: float) -> float:
        """环比计算（分/度，电价专用）"""
        return (current - last_week) * 100

    def verify_value(
        self,
        computed: float,
        expected: float,
        tolerance: float = 0.01,
        label: str = ""
    ) -> bool:
        """勾稽验证（验算数字是否一致）

        Args:
            computed: 计算值
            expected: 期望值
            tolerance: 容差
            label: 验证项名称

        Returns:
            是否通过验证
        """
        diff = abs(computed - expected)
        passed = diff < tolerance
        if not passed:
            self._log_verification_failure(label, computed, expected, diff)
        return passed

    def _log_verification_failure(
        self, label: str, computed: float, expected: float, diff: float
    ):
        """记录勾稽验证失败"""
        if not hasattr(self, '_verification_failures'):
            self._verification_failures = []
        self._verification_failures.append({
            "label": label,
            "computed": computed,
            "expected": expected,
            "diff": diff
        })

    def get_verification_failures(self) -> List[Dict]:
        """获取所有勾稽验证失败"""
        return getattr(self, '_verification_failures', [])

    # === 辅助方法 ===

    def safe_get(self, *keys, default=None) -> Any:
        """安全获取嵌套字典值

        Example:
            self.safe_get("group_total", "domestic_ongrid_volume_yi_kwh", default=0)
        """
        value = self.data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value if value is not None else default


# === 工具函数（模块级） ===

def create_empty_result(dimension: str, section_ids: List[int]) -> AnalysisResult:
    """创建空 AnalysisResult（用于输入校验失败时）"""
    return AnalysisResult(
        dimension=dimension,
        section_ids=section_ids,
        analyzer_name="",
        summary="输入数据不完整",
        story="",
        insights=["数据校验失败，请检查输入"],
        anomalies=[{
            "level": "error",
            "message": "输入数据不完整"
        }]
    )


# === 自检 ===
class _TestAnalyzer(BaseAnalyzer):
    """用于自检的最小具体实现"""
    dimension_name = "测试"
    section_ids = [0]
    analyzer_name = "TestAnalyzer"

    def analyze(self):
        return create_empty_result("测试", [0])

    def validate_inputs(self):
        return True


if __name__ == "__main__":
    # 简单的自检测试
    print("=" * 60)
    print("BaseAnalyzer 自检")
    print("=" * 60)

    # 1. 测试同比环比计算
    ta = _TestAnalyzer({})
    print(f"\n同比测试: ta.calculate_yoy(103.3, 100) = {ta.calculate_yoy(103.3, 100):.2f}%")
    print(f"环比测试: ta.calculate_mom(115.7, 100) = {ta.calculate_mom(115.7, 100):.2f}%")
    print(f"分/度测试: ta.calculate_yoy_fen(0.311, 0.320) = {ta.calculate_yoy_fen(0.311, 0.320):.2f} 分")

    # 2. 测试勾稽验证
    print(f"\n勾稽验证 1 (pass): {ta.verify_value(3.9, 3.9, label='total_change')}")
    print(f"勾稽验证 2 (fail): {ta.verify_value(3.9, 4.0, label='total_change_2')}")
    print(f"验证失败记录: {ta.get_verification_failures()}")

    # 3. 测试安全获取
    test_data = {"a": {"b": {"c": 42}}}
    ta.data = test_data
    print(f"\n安全获取: {ta.safe_get('a', 'b', 'c', default=0)}")
    print(f"安全获取（缺失）: {ta.safe_get('a', 'x', 'y', default='default')}")

    # 4. 测试 AnalysisResult
    result = ta.analyze()
    print(f"\nAnalysisResult 测试:")
    print(f"  dimension: {result.dimension}")
    print(f"  section_ids: {result.section_ids}")
    print(f"  summary: {result.summary}")

    print("\nBaseAnalyzer 自检通过")
