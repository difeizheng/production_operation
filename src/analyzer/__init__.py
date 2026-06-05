"""
周报分析层 (Analyzers)
======================

基于业务图谱 (docs/design/business-map-master.md) 的 4 维度分析器。

包含:
- BaseAnalyzer: 所有分析器的基类
- DomesticAnalyzer: 段 1-2 (国内电量 + 国内电价) [Phase 2]
- InternationalAnalyzer: 段 3-4 (国际电价同比 + 环比) [Phase 3]
- MarketTradingAnalyzer: 段 5-7 (水电/新能源/火电市场化) [Phase 3 续]
- EnvironmentalAnalyzer: 段 8 (绿证 + CCER) [Phase 4] ✅ NEW

设计依据:
- 业务图谱: docs/design/business-map-master.md
- 架构设计: docs/design/report-generator-v2-architecture.md
- 分析框架: docs/analysis/domestic-price-analysis-framework.md

实施状态: 4 维度全覆盖（国内+国际+市场化+碳资产）✅
"""

__version__ = "2.0.0-phase4"

# 基础类
from .base import BaseAnalyzer, AnalysisResult, create_empty_result

# Phase 2
from .domestic import DomesticAnalyzer, DomesticConfig

# Phase 3
from .international import InternationalAnalyzer, InternationalConfig

# Phase 3 续
from .market_trading import MarketTradingAnalyzer, MarketTradingConfig

# Phase 4
from .environmental import EnvironmentalAnalyzer, EnvironmentalConfig

__all__ = [
    # 基础
    "BaseAnalyzer",
    "AnalysisResult",
    "create_empty_result",
    # Phase 2
    "DomesticAnalyzer",
    "DomesticConfig",
    # Phase 3
    "InternationalAnalyzer",
    "InternationalConfig",
    # Phase 3 续
    "MarketTradingAnalyzer",
    "MarketTradingConfig",
    # Phase 4
    "EnvironmentalAnalyzer",
    "EnvironmentalConfig",
]
