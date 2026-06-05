"""
Streamlit 数据加载器
====================

提供统一的 JSON 加载接口：
- 支持文件上传
- 支持默认 fixture（演示模式）
- 自动执行 4 个 Analyzer 并返回结果
"""

import json
import sys
from pathlib import Path
from typing import Dict, Optional, Any

# 添加项目根到 sys.path
import streamlit as st

# 项目根 = streamlit_app/../../
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.analyzer import (
    DomesticAnalyzer,
    InternationalAnalyzer,
    MarketTradingAnalyzer,
    EnvironmentalAnalyzer,
)


# === 4 个 Analyzer 工厂 ===

def _run_domestic(data: dict):
    return DomesticAnalyzer(data).analyze()


def _run_international(data: dict):
    return InternationalAnalyzer(data).analyze()


def _run_market_trading(data: dict):
    return MarketTradingAnalyzer(data).analyze()


def _run_environmental(data: dict):
    return EnvironmentalAnalyzer(data).analyze()


ANALYZER_FACTORY = {
    "domestic": _run_domestic,
    "international": _run_international,
    "market_trading": _run_market_trading,
    "environmental": _run_environmental,
}


# === 加载默认 fixture ===

DEFAULT_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "weekly_report_merged.json"


@st.cache_data
def load_default_data() -> dict:
    """加载默认 fixture 数据（5/22 周报合并）"""
    with open(DEFAULT_FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


# === 加载上传文件 ===

def load_uploaded_file(uploaded_file) -> Optional[dict]:
    """解析用户上传的 JSON 文件"""
    if uploaded_file is None:
        return None
    try:
        content = uploaded_file.read()
        # 尝试 UTF-8 解码
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("gbk")
        return json.loads(text)
    except Exception as e:
        st.error(f"文件解析失败: {e}")
        return None


# === 执行 4 Analyzer ===

@st.cache_data
def run_all_analyzers(data: dict) -> Dict[str, Any]:
    """执行 4 个 Analyzer 并返回结果字典

    Returns:
        dict: {
            "domestic": AnalysisResult,
            "international": AnalysisResult,
            "market_trading": AnalysisResult,
            "environmental": AnalysisResult,
        }
    """
    results = {}
    for key, factory in ANALYZER_FACTORY.items():
        try:
            results[key] = factory(data)
        except Exception as e:
            st.warning(f"{key} Analyzer 执行失败: {e}")
            results[key] = None
    return results


# === 一站式加载 ===

def load_data_and_analyze(
    uploaded_file=None,
    use_default: bool = True,
) -> Dict[str, Any]:
    """一站式加载数据 + 执行 4 Analyzer

    Args:
        uploaded_file: Streamlit 上传的文件对象
        use_default: 是否使用默认 fixture

    Returns:
        dict: {
            "data": 原始数据,
            "results": 4 个 Analyzer 结果,
            "source": "default" / "uploaded"
        }
    """
    # 1. 加载数据
    if uploaded_file is not None:
        data = load_uploaded_file(uploaded_file)
        source = "uploaded"
    elif use_default:
        data = load_default_data()
        source = "default"
    else:
        return {"data": None, "results": {}, "source": "none"}

    # 2. 执行 4 Analyzer
    results = run_all_analyzers(data)

    return {
        "data": data,
        "results": results,
        "source": source,
    }


# === 辅助函数 ===

def get_analyzer_dimension_label(key: str) -> str:
    """获取 Analyzer 维度的中文标签"""
    labels = {
        "domestic": "🏠 国内",
        "international": "🌍 国际",
        "market_trading": "💹 市场化",
        "environmental": "🌱 碳资产",
    }
    return labels.get(key, key)


def get_report_meta(data: dict) -> Dict[str, str]:
    """提取报告元信息（报告ID/周期）"""
    if not data:
        return {}
    return {
        "report_id": data.get("report_id", "未知"),
        "year": data.get("report_period", {}).get("year", "?"),
        "week": data.get("report_period", {}).get("week", "?"),
        "start_date": data.get("report_period", {}).get("start_date", "?"),
        "end_date": data.get("report_period", {}).get("end_date", "?"),
    }
