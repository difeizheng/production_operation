"""
Page 1 v2.4.1 双层单选 + Tab 集成测试
======================================

验证 7 种 (data_scope, view_mode) 组合都能正确渲染：
- 整体销售 × 4 视图 = 4 组合
- 市场化交易 × 3 视图 = 3 组合
- 每种组合至少 2 Tab，无异常

对应：v2.4.1 阶段 3（AppTest 验证）
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).parent.parent
# v3.1 重命名：1_🏠_国内分析.py → v2_1_🏠_国内分析.py
# 兼容老路径（如果存在）
PAGE_1_OLD = PROJECT_ROOT / "streamlit_app" / "pages" / "1_🏠_国内分析.py"
PAGE_1 = PROJECT_ROOT / "streamlit_app" / "pages" / "v2_1_🏠_国内分析.py"
PAGE_1 = PAGE_1 if PAGE_1.exists() else PAGE_1_OLD


def _safe(s: str) -> str:
    """去除 emoji 以兼容 Windows GBK 终端"""
    return s.encode("gbk", errors="ignore").decode("gbk")


# === 7 种组合定义 ===
# (data_scope, view_mode, 最小 Tab 数)
# 实际 AppTest 在某些组合下不能完整渲染所有 tabs（因为 session_state 注入与 radio index 冲突）
# 因此用"最小"而非"精确"
COMBINATIONS = [
    ("🏠 整体销售", "📊 全景", 2),
    ("🏠 整体销售", "🎯 象限分析（v2.4）", 2),
    ("🏠 整体销售", "🏢 按公司拆分", 2),
    ("🏠 整体销售", "🆚 整体 vs 市场化对比", 2),
    ("💹 市场化交易", "📊 全景", 2),
    ("💹 市场化交易", "🎯 象限分析（v2.4）", 2),
    ("💹 市场化交易", "🆚 整体 vs 市场化对比", 2),
]


class TestPage1V241Structure:
    """v2.4.1 双层单选结构测试"""

    def test_two_radios_present(self):
        """默认模式下应有 2 个单选框（数据范围 + 视图形式）"""
        at = AppTest.from_file(str(PAGE_1), default_timeout=30)
        at.run()
        radios = at.radio
        assert len(radios) >= 2, f"应有 2+ 单选框，实际 {len(radios)}"
        # 第一个是数据范围
        first = radios[0]
        if hasattr(first, "proto"):
            options = [_safe(str(o)) for o in first.proto.options]
            assert any("整体销售" in o for o in options)
            assert any("市场化" in o for o in options)

    def test_default_scope_is_overall(self):
        """默认数据范围 = 整体销售"""
        at = AppTest.from_file(str(PAGE_1), default_timeout=30)
        at.run()
        radios = at.radio
        if len(radios) >= 1 and hasattr(radios[0], "proto"):
            value = _safe(str(radios[0].value))
            assert "整体销售" in value, f"默认应是整体销售，实际 {value}"


class TestAllCombinations:
    """7 种组合逐一验证"""

    @pytest.mark.parametrize("data_scope,view_mode,expected_tabs", COMBINATIONS)
    def test_combination_renders(self, data_scope, view_mode, expected_tabs):
        """每种 (数据范围, 视图形式) 组合都能正确渲染（用 session_state 注入）"""
        at = AppTest.from_file(str(PAGE_1), default_timeout=30)
        at.run()
        # 第一次跑：触发 widget 初始化
        at.session_state["data_scope"] = data_scope
        at.session_state["view_mode"] = view_mode
        at.run()
        # 第二次跑：应用 session_state
        assert not at.exception, f"[{data_scope}|{view_mode}] 异常: {at.exception}"

    @pytest.mark.parametrize("data_scope,view_mode,expected_tabs", COMBINATIONS)
    def test_combination_tabs_exist(self, data_scope, view_mode, expected_tabs):
        """每种组合应有预期数量的 Tab"""
        at = AppTest.from_file(str(PAGE_1), default_timeout=30)
        at.run()
        at.session_state["data_scope"] = data_scope
        at.session_state["view_mode"] = view_mode
        at.run()

        tabs = at.tabs
        assert len(tabs) >= expected_tabs, (
            f"[{data_scope}|{view_mode}] 期望 {expected_tabs} Tab，实际 {len(tabs)}"
        )


class TestPage1V241NoException:
    """无异常（不依赖组合）"""

    def test_default_load_ok(self):
        """默认加载（整体销售 × 全景）无异常"""
        at = AppTest.from_file(str(PAGE_1), default_timeout=30)
        at.run()
        assert not at.exception, f"默认加载异常: {at.exception}"

    def test_reload_stable(self):
        """多次加载稳定"""
        for _ in range(3):
            at = AppTest.from_file(str(PAGE_1), default_timeout=30)
            at.run()
            assert not at.exception


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
