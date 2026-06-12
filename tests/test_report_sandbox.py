"""报告沙盘组件单元测试

覆盖：
    - TrustScoreResult / compute_trust_score
    - build_field_to_paragraphs 反向索引
    - detect_action_items 行动项检测
    - _filter_paragraphs 过滤
    - _find_trace 字段查找
"""
from __future__ import annotations

import pytest

from src.collector.trace_builder import (
    CellTrace,
    ParagraphTrace,
    SlotDataRef,
    TraceReport,
)
from streamlit_app.components.report_sandbox import (
    build_field_to_paragraphs,
    detect_action_items,
    _filter_paragraphs,
    _find_trace,
)
from streamlit_app.components.trust_score import (
    TrustScoreResult,
    compute_trust_score,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_cell_traces() -> tuple:
    """创建 4 条示例 CellTrace。"""
    return (
        CellTrace(
            field_name="dom.electricity.total",
            cell_ref="I4",
            sheet_name="综合分析表",
            section="国内",
            metric_type="电量",
            value=803000.0,
            value_display="803,000 万千瓦时",
            unit="万千瓦时",
            description_zh="国内合计电量",
            validation_status="正常",
            validation_detail="803,000 在 [0, 10,000,000] 范围内",
        ),
        CellTrace(
            field_name="dom.electricity.hydro",
            cell_ref="C4",
            sheet_name="综合分析表",
            section="国内",
            metric_type="电量",
            value=425000.0,
            value_display="425,000 万千瓦时",
            unit="万千瓦时",
            description_zh="国内水电电量",
            validation_status="正常",
            validation_detail="425,000 在 [0, 10,000,000] 范围内",
        ),
        CellTrace(
            field_name="dom.yoy.electricity",
            cell_ref="I17",
            sheet_name="综合分析表",
            section="国内",
            metric_type="同比",
            value=None,
            value_display="—",
            unit="%",
            description_zh="国内电量同比",
            validation_status="缺值",
            validation_detail="字段未采集到",
        ),
        CellTrace(
            field_name="dom.price.total",
            cell_ref="I7",
            sheet_name="综合分析表",
            section="国内",
            metric_type="电价",
            value=999.0,
            value_display="999.0 元/千瓦时",
            unit="元/千瓦时",
            description_zh="国内平均电价",
            validation_status="超范围",
            validation_detail="999.0 超出 [0, 1] 范围",
        ),
    )


@pytest.fixture
def sample_trace_report(sample_cell_traces) -> TraceReport:
    """创建示例 TraceReport。"""
    return TraceReport(
        traces=sample_cell_traces,
        total_fields=4,
        collected_fields=3,
        missing_fields=1,
        out_of_range_fields=1,
        coverage_pct=75.0,
        by_section={"国内": 4},
        by_metric_type={"电量": 2, "同比": 1, "电价": 1},
    )


@pytest.fixture
def sample_slot_refs() -> tuple:
    """创建示例 SlotDataRef。"""
    return (
        SlotDataRef(
            slot_name="dom.electricity.overview",
            slot_type="numeric_field",
            resolved_fields=("dom.electricity.total", "dom.electricity.hydro"),
            cell_refs=("I4", "C4"),
            notes="I4+C4 拼装",
        ),
        SlotDataRef(
            slot_name="dom.elec.yoy.changjiang",
            slot_type="reason_text",
            resolved_fields=("dom.yoy.electricity",),
            cell_refs=("I17",),
            notes="H17 汇总表原因列",
        ),
    )


@pytest.fixture
def sample_paragraph_traces(sample_slot_refs) -> list:
    """创建示例 ParagraphTrace 列表。"""
    return [
        ParagraphTrace(
            v4_index=5,
            placeholder="{{ v4_P5_overview }}",
            preview="集团上网电量 80.3 亿千瓦时",
            automation_level="HIGH",
            polish_required=False,
            data_refs=(sample_slot_refs[0],),
            fallback_text=None,
            notes="纯数据段落",
        ),
        ParagraphTrace(
            v4_index=6,
            placeholder="{{ v4_P6_dom_elec_yoy_wow }}",
            preview="国内电量同比提高3.3%",
            automation_level="HIGH",
            polish_required=True,
            data_refs=(sample_slot_refs[1],),
            fallback_text="数据缺失时使用",
            notes="H29 + H53 拼装",
        ),
        ParagraphTrace(
            v4_index=11,
            placeholder="{{ v4_P11_dom_price_yoy }}",
            preview="",
            automation_level="MEDIUM",
            polish_required=True,
            data_refs=(),
            fallback_text=None,
            notes="电价同比",
        ),
        ParagraphTrace(
            v4_index=27,
            placeholder="{{ v4_P27_green_cert }}",
            preview="",
            automation_level="MANUAL",
            polish_required=True,
            data_refs=(),
            fallback_text=None,
            notes="绿证",
        ),
    ]


# ============================================================================
# TestTrustScore
# ============================================================================


class TestComputeTrustScore:
    """信任度评分计算。"""

    def test_basic_score(self, sample_trace_report, sample_paragraph_traces):
        """基本评分计算。"""
        result = compute_trust_score(sample_trace_report, sample_paragraph_traces)
        assert isinstance(result, TrustScoreResult)
        assert 0 <= result.score <= 100
        assert result.coverage_pct == 75.0
        assert result.issue_count == 2  # 1 missing + 1 out_of_range
        assert result.high_count == 2
        assert result.medium_count == 1
        assert result.manual_count == 1
        assert result.missing_count == 1
        assert result.out_of_range_count == 1

    def test_perfect_score(self):
        """全覆盖 + 全 HIGH → 高分。"""
        report = TraceReport(
            traces=(),
            total_fields=0,
            collected_fields=0,
            missing_fields=0,
            out_of_range_fields=0,
            coverage_pct=100.0,
            by_section={},
            by_metric_type={},
        )
        paras = [
            ParagraphTrace(
                v4_index=i,
                placeholder=f"P{i}",
                preview="",
                automation_level="HIGH",
                polish_required=False,
                data_refs=(),
                fallback_text=None,
                notes="",
            )
            for i in range(10)
        ]
        result = compute_trust_score(report, paras)
        assert result.score >= 90
        assert result.grade.startswith("A")

    def test_low_coverage(self):
        """低覆盖率 + MANUAL → 低分。"""
        report = TraceReport(
            traces=(),
            total_fields=100,
            collected_fields=10,
            missing_fields=90,
            out_of_range_fields=0,
            coverage_pct=10.0,
            by_section={},
            by_metric_type={},
        )
        paras = [
            ParagraphTrace(
                v4_index=1,
                placeholder="P1",
                preview="",
                automation_level="MANUAL",
                polish_required=True,
                data_refs=(),
                fallback_text=None,
                notes="",
            )
        ]
        result = compute_trust_score(report, paras)
        assert result.score < 50

    def test_empty_traces(self):
        """空数据。"""
        report = TraceReport(
            traces=(),
            total_fields=0,
            collected_fields=0,
            missing_fields=0,
            out_of_range_fields=0,
            coverage_pct=0.0,
            by_section={},
            by_metric_type={},
        )
        result = compute_trust_score(report, [])
        assert result.score == 10.0  # 只有基础分
        assert result.high_count == 0

    def test_out_of_range_penalty(self):
        """超范围惩罚。"""
        report_low = TraceReport(
            traces=(),
            total_fields=10,
            collected_fields=10,
            missing_fields=0,
            out_of_range_fields=0,
            coverage_pct=100.0,
            by_section={},
            by_metric_type={},
        )
        report_high = TraceReport(
            traces=(),
            total_fields=10,
            collected_fields=10,
            missing_fields=0,
            out_of_range_fields=5,
            coverage_pct=100.0,
            by_section={},
            by_metric_type={},
        )
        paras = [
            ParagraphTrace(
                v4_index=1,
                placeholder="P1",
                preview="",
                automation_level="HIGH",
                polish_required=False,
                data_refs=(),
                fallback_text=None,
                notes="",
            )
        ]
        low = compute_trust_score(report_low, paras)
        high = compute_trust_score(report_high, paras)
        assert low.score > high.score

    def test_grade_labels(self):
        """评级标签。"""
        assert TrustScoreResult(
            score=95, coverage_pct=100, issue_count=0,
            high_count=10, medium_count=0, manual_count=0,
            missing_count=0, out_of_range_count=0,
        ).grade.startswith("A")
        assert TrustScoreResult(
            score=85, coverage_pct=80, issue_count=1,
            high_count=8, medium_count=2, manual_count=0,
            missing_count=1, out_of_range_count=0,
        ).grade.startswith("B")
        assert TrustScoreResult(
            score=65, coverage_pct=60, issue_count=5,
            high_count=5, medium_count=3, manual_count=2,
            missing_count=3, out_of_range_count=2,
        ).grade.startswith("C")
        assert TrustScoreResult(
            score=30, coverage_pct=20, issue_count=10,
            high_count=1, medium_count=2, manual_count=7,
            missing_count=8, out_of_range_count=2,
        ).grade.startswith("D")

    def test_frozen(self, sample_trace_report, sample_paragraph_traces):
        """TrustScoreResult 不可变。"""
        result = compute_trust_score(sample_trace_report, sample_paragraph_traces)
        with pytest.raises(AttributeError):
            result.score = 999


# ============================================================================
# TestReverseIndex
# ============================================================================


class TestBuildFieldToParagraphs:
    """字段 → 段落反向索引。"""

    def test_basic_index(self, sample_paragraph_traces):
        """基本反向索引构建。"""
        index = build_field_to_paragraphs(sample_paragraph_traces)
        # dom.electricity.total 和 dom.electricity.hydro 被 P5 引用
        assert "dom.electricity.total" in index
        assert 5 in index["dom.electricity.total"]
        assert "dom.electricity.hydro" in index
        assert 5 in index["dom.electricity.hydro"]
        # dom.yoy.electricity 被 P6 引用
        assert "dom.yoy.electricity" in index
        assert 6 in index["dom.yoy.electricity"]

    def test_empty_traces(self):
        """空段落列表 → 空索引。"""
        index = build_field_to_paragraphs([])
        assert index == {}

    def test_no_data_refs(self):
        """段落无 data_refs → 不在索引中。"""
        paras = [
            ParagraphTrace(
                v4_index=99,
                placeholder="P99",
                preview="",
                automation_level="HIGH",
                polish_required=False,
                data_refs=(),
                fallback_text=None,
                notes="",
            )
        ]
        index = build_field_to_paragraphs(paras)
        assert index == {}

    def test_multiple_refs_to_same_field(self):
        """多个段落引用同一字段。"""
        ref1 = SlotDataRef(
            slot_name="s1",
            slot_type="numeric_field",
            resolved_fields=("dom.electricity.total",),
            cell_refs=("I4",),
            notes="",
        )
        ref2 = SlotDataRef(
            slot_name="s2",
            slot_type="numeric_field",
            resolved_fields=("dom.electricity.total",),
            cell_refs=("I4",),
            notes="",
        )
        paras = [
            ParagraphTrace(5, "P5", "", "HIGH", False, (ref1,), None, ""),
            ParagraphTrace(6, "P6", "", "HIGH", False, (ref2,), None, ""),
        ]
        index = build_field_to_paragraphs(paras)
        assert index["dom.electricity.total"] == [5, 6]


# ============================================================================
# TestActionItems
# ============================================================================


class TestDetectActionItems:
    """行动项检测。"""

    def test_missing_items(
        self, sample_trace_report, sample_paragraph_traces
    ):
        """检测缺失字段。"""
        missing, out_of_range = detect_action_items(
            sample_trace_report, sample_paragraph_traces
        )
        assert len(missing) == 1
        assert missing[0]["field_name"] == "dom.yoy.electricity"
        assert missing[0]["cell_ref"] == "I17"
        # P6 引用了该字段
        assert 6 in missing[0]["affected_paragraphs"]

    def test_out_of_range_items(
        self, sample_trace_report, sample_paragraph_traces
    ):
        """检测超范围字段。"""
        missing, out_of_range = detect_action_items(
            sample_trace_report, sample_paragraph_traces
        )
        assert len(out_of_range) == 1
        assert out_of_range[0]["field_name"] == "dom.price.total"
        assert out_of_range[0]["value"] == 999.0

    def test_no_issues(self):
        """无问题 → 空列表。"""
        good_trace = CellTrace(
            field_name="good.field",
            cell_ref="A1",
            sheet_name="Sheet1",
            section="国内",
            metric_type="电量",
            value=100.0,
            value_display="100.0",
            unit="万千瓦时",
            description_zh="好字段",
            validation_status="正常",
            validation_detail="正常",
        )
        report = TraceReport(
            traces=(good_trace,),
            total_fields=1,
            collected_fields=1,
            missing_fields=0,
            out_of_range_fields=0,
            coverage_pct=100.0,
            by_section={},
            by_metric_type={},
        )
        missing, out_of_range = detect_action_items(report, [])
        assert missing == []
        assert out_of_range == []

    def test_unreferenced_missing_field(self):
        """缺失字段无段落引用 → affected_paragraphs 为空。"""
        missing_trace = CellTrace(
            field_name="orphan.field",
            cell_ref="Z99",
            sheet_name="Sheet1",
            section="其他",
            metric_type="其他",
            value=None,
            value_display="—",
            unit="",
            description_zh="孤立字段",
            validation_status="缺值",
            validation_detail="未采集",
        )
        report = TraceReport(
            traces=(missing_trace,),
            total_fields=1,
            collected_fields=0,
            missing_fields=1,
            out_of_range_fields=0,
            coverage_pct=0.0,
            by_section={},
            by_metric_type={},
        )
        missing, _ = detect_action_items(report, [])
        assert len(missing) == 1
        assert missing[0]["affected_paragraphs"] == []


# ============================================================================
# TestFilterParagraphs
# ============================================================================


class TestFilterParagraphs:
    """段落过滤。"""

    def test_no_filter(self, sample_paragraph_traces):
        """无过滤 → 返回全部。"""
        result = _filter_paragraphs(sample_paragraph_traces, [], "")
        assert len(result) == len(sample_paragraph_traces)

    def test_level_filter_high(self, sample_paragraph_traces):
        """只看 HIGH。"""
        result = _filter_paragraphs(sample_paragraph_traces, ["HIGH"], "")
        assert all(p.automation_level == "HIGH" for p in result)
        assert len(result) == 2

    def test_level_filter_medium(self, sample_paragraph_traces):
        """只看 MEDIUM。"""
        result = _filter_paragraphs(sample_paragraph_traces, ["MEDIUM"], "")
        assert len(result) == 1

    def test_search_by_index(self, sample_paragraph_traces):
        """按段落编号搜索。"""
        result = _filter_paragraphs(sample_paragraph_traces, [], "5")
        assert len(result) == 1
        assert result[0].v4_index == 5

    def test_search_by_placeholder(self, sample_paragraph_traces):
        """按占位符搜索。"""
        result = _filter_paragraphs(
            sample_paragraph_traces, [], "P5_overview"
        )
        assert len(result) == 1

    def test_search_by_preview(self, sample_paragraph_traces):
        """按预览文本搜索。"""
        result = _filter_paragraphs(
            sample_paragraph_traces, [], "80.3"
        )
        assert len(result) == 1

    def test_combined_filter(self, sample_paragraph_traces):
        """等级 + 搜索组合过滤。"""
        result = _filter_paragraphs(
            sample_paragraph_traces, ["HIGH"], "P5"
        )
        assert len(result) == 1
        assert result[0].v4_index == 5

    def test_no_match(self, sample_paragraph_traces):
        """无匹配。"""
        result = _filter_paragraphs(
            sample_paragraph_traces, [], "不存在的关键词"
        )
        assert result == []


# ============================================================================
# TestFindTrace
# ============================================================================


class TestFindTrace:
    """字段查找。"""

    def test_found(self, sample_trace_report):
        """找到字段。"""
        trace = _find_trace("dom.electricity.total", sample_trace_report)
        assert trace is not None
        assert trace.value == 803000.0

    def test_not_found(self, sample_trace_report):
        """未找到字段。"""
        trace = _find_trace("nonexistent.field", sample_trace_report)
        assert trace is None
