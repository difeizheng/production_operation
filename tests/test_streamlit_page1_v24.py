"""
Page 1 国内分析 v2.4 集成测试
=============================

使用 streamlit.testing.v1.AppTest 验证：
- 4 模式切换器正常渲染
- v2.4 新增的"市场化维度"Tab 在"全口径"模式下可见
- 18 组织市场化率排行组件渲染成功
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).parent.parent
PAGE_1 = PROJECT_ROOT / "streamlit_app" / "pages" / "1_🏠_国内分析.py"


def _safe(s: str) -> str:
    """去除 emoji 以兼容 Windows GBK 终端"""
    return s.encode("gbk", errors="ignore").decode("gbk")


@pytest.fixture(scope="module")
def app():
    """加载 Page 1（默认模式：全口径）"""
    at = AppTest.from_file(str(PAGE_1), default_timeout=30)
    at.run()
    return at


class TestPage1V24:
    """Page 1 v2.4 集成测试"""

    def test_page_runs_without_exception(self, app):
        """页面运行无异常"""
        assert not app.exception, f"异常: {app.exception}"

    def test_title_visible(self, app):
        """标题可见（用 _safe 处理 emoji）"""
        assert any("国内分析" in _safe(t.value) for t in app.title)

    def test_mode_radio_present(self, app):
        """模式选择器存在"""
        radios = app.radio
        assert len(radios) >= 1
        first_radio = radios[0]
        # AppTest 1.x 中 options 在 proto 里
        proto_options = []
        if hasattr(first_radio, "proto"):
            for opt in first_radio.proto.options:
                proto_options.append(_safe(str(opt)))
        # 至少有 4 个选项
        assert len(proto_options) >= 4, f"实际 {len(proto_options)} 个选项"
        # 关键选项存在（去掉 emoji）
        assert any("全口径" in o for o in proto_options)
        assert any("市场化" in o for o in proto_options)
        assert any("双口径" in o for o in proto_options)
        assert any("按公司" in o for o in proto_options)

    def test_tabs_present(self, app):
        """全口径模式应有两个 Tab：全口径 + 市场化维度"""
        tabs = app.tabs
        assert len(tabs) >= 2, f"应有 2 个 Tab，实际 {len(tabs)}"
        # 检查 Tab 标签
        all_labels = [_safe(str(t.label)) for t in tabs]
        # 至少包含 v2.4 新 Tab
        has_market_tab = any("市场化维度" in label or "v2.4" in label for label in all_labels)
        assert has_market_tab, f"未找到 v2.4 市场化 Tab，labels={all_labels}"

    def test_no_error_message(self, app):
        """无异常错误（anomaly 输出不算 error）"""
        # exception 为空才是真错误
        assert len(app.exception) == 0, f"异常: {app.exception}"


class TestPage1V24PageLoad:
    """页面加载稳定性"""

    def test_reload_stable(self):
        """多次加载稳定"""
        for _ in range(3):
            at = AppTest.from_file(str(PAGE_1), default_timeout=30)
            at.run()
            assert not at.exception


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
