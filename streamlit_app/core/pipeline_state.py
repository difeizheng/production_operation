"""Pipeline 状态管理 - session_state 封装

设计原则：
    1. 不可变数据：所有数据用 frozen dataclass，避免流式状态被意外修改
    2. 单一数据源：所有页面通过 PipelineStateManager 读写
    3. 状态分离：原始数据 / 中间结果 / 用户编辑 / 审计日志 分开存储
    4. 可恢复：支持保存/恢复快照（用于重置、对比）

数据流：
    bundle["data"] → slot_results → polished_slots → human_edits → final_docx
                    ↓                ↓                  ↓
                    提取            LLM 润色          人工编辑
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

logger = logging.getLogger(__name__)


# ============================================================================
# 数据类
# ============================================================================

@dataclass(frozen=True)
class PolishedSlot:
    """单个段位的润色结果（可被人工编辑）。

    Attributes:
        slot_id: 段位 ID（如 'dom.elec.yoy.changjiang'）
        placeholder: 模板占位符（如 '{{ v4_P5_overview }}'）
        raw_text: 从 Excel 提取的原始文本
        llm_output: LLM 润色后的输出（None 表示未润色）
        final_text: 最终使用的文本（可能是 LLM 输出，也可能是人工编辑）
        is_edited_by_human: 是否经过人工编辑
        generation_mode: 生成模式（extract / grounded_category / fallback）
        automation_level: 自动化等级（HIGH / MEDIUM / MANUAL）
        tokens_used: LLM 消耗的 token 数
        model_used: 使用的模型名
        is_fallback: 是否走了 fallback
        error: 错误信息（如果有）
        timestamp: 编辑时间戳
    """
    slot_id: str
    placeholder: str
    raw_text: str
    llm_output: Optional[str]
    final_text: str
    is_edited_by_human: bool = False
    generation_mode: str = "extract"
    automation_level: str = "MANUAL"
    tokens_used: int = 0
    model_used: str = "none"
    is_fallback: bool = False
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolishedSlot":
        return cls(**data)


@dataclass(frozen=True)
class QualityMetrics:
    """单个段位的质量指标。

    4 重检测（数字保留 30 / 长度合理 20 / 禁词扫描 20 / 专业度 20）
    + 原文偏差 10 = 满 100 分。
    """
    slot_id: str
    numbers_consistency: bool = True   # 30 分
    length_reasonable: bool = True    # 20 分
    no_forbidden_words: bool = True   # 20 分
    professionalism: int = 20         # 20 分（0/10/20）
    original_deviation: float = 1.0   # 10 分（0-1 比率）
    overall_score: int = 100          # 0-100 综合分
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def passed(self) -> bool:
        """是否通过（>=80 分）。"""
        return self.overall_score >= 80

    @property
    def issues(self) -> List[str]:
        """问题列表（warnings 的别名）。"""
        return list(self.warnings)

    @property
    def score_breakdown(self) -> Dict[str, int]:
        """分维度分值明细。"""
        return {
            "numbers": 30 if self.numbers_consistency else 0,
            "length": 20 if self.length_reasonable else 0,
            "forbidden": 20 if self.no_forbidden_words else 0,
            "professionalism": self.professionalism,
            "deviation": int(round(self.original_deviation * 10)),
        }


@dataclass(frozen=True)
class PipelineState:
    """整个管线的状态快照。"""
    current_step: int = 1
    raw_data: Optional[Dict[str, Any]] = None
    excel_path: Optional[str] = None
    summary_path: Optional[str] = None
    mappings: List[Dict[str, Any]] = field(default_factory=list)
    slot_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # ReasonResult 序列化
    polished_slots: Dict[str, PolishedSlot] = field(default_factory=dict)
    human_edits: Dict[str, str] = field(default_factory=dict)  # slot_id -> edited text
    quality_metrics: Dict[str, QualityMetrics] = field(default_factory=dict)
    final_docx: Optional[bytes] = None
    docx_path: Optional[str] = None
    audit_log: Dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_step": self.current_step,
            "raw_data": self.raw_data,
            "excel_path": self.excel_path,
            "summary_path": self.summary_path,
            "mappings": self.mappings,
            "slot_results": self.slot_results,
            "polished_slots": {k: v.to_dict() for k, v in self.polished_slots.items()},
            "human_edits": self.human_edits,
            "quality_metrics": {k: v.to_dict() for k, v in self.quality_metrics.items()},
            "final_docx_b64": None,  # 不序列化二进制
            "docx_path": self.docx_path,
            "audit_log": self.audit_log,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
        }


# ============================================================================
# 状态管理器
# ============================================================================

class PipelineStateManager:
    """Streamlit session_state 封装。

    用法：
        manager = PipelineStateManager()
        state = manager.get()  # 获取当前状态
        new_state = dataclasses.replace(state, current_step=2)  # 不可变更新
        manager.update(new_state)  # 写入 session_state
    """

    SESSION_KEY = "_pipeline_state"
    SNAPSHOT_DIR = Path(__file__).resolve().parent.parent.parent / ".streamlit_cache" / "snapshots"

    def __init__(self) -> None:
        self.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        if self.SESSION_KEY not in st.session_state:
            st.session_state[self.SESSION_KEY] = PipelineState()

    def get(self) -> PipelineState:
        """获取当前状态。"""
        return st.session_state[self.SESSION_KEY]

    def update(self, new_state: PipelineState) -> None:
        """更新状态（带 updated_at 时间戳）。"""
        from dataclasses import replace
        stamped = replace(new_state, updated_at=datetime.now().isoformat())
        st.session_state[self.SESSION_KEY] = stamped
        logger.debug("Pipeline state updated: step=%d", stamped.current_step)

    def update_field(self, **kwargs: Any) -> None:
        """便捷方法：更新部分字段。

        用法：
            manager.update_field(current_step=3)
            manager.update_field(polished_slots={...})
        """
        current = self.get()
        from dataclasses import replace
        new_state = replace(current, **kwargs)
        self.update(new_state)

    def reset(self) -> None:
        """重置为初始状态。"""
        st.session_state[self.SESSION_KEY] = PipelineState()
        logger.info("Pipeline state reset")

    # ========================================================================
    # 槽位操作
    # ========================================================================

    def upsert_polished_slot(self, slot: PolishedSlot) -> None:
        """插入或更新单个 PolishedSlot。"""
        current = self.get()
        new_slots = {**current.polished_slots, slot.slot_id: slot}
        self.update_field(polished_slots=new_slots)

    def record_human_edit(self, slot_id: str, edited_text: str) -> None:
        """记录人工编辑。

        同时更新 polished_slots 中对应槽位的 final_text + is_edited_by_human。
        """
        current = self.get()
        new_edits = {**current.human_edits, slot_id: edited_text}
        new_polished = dict(current.polished_slots)
        if slot_id in new_polished:
            old = new_polished[slot_id]
            new_polished[slot_id] = PolishedSlot(
                slot_id=old.slot_id,
                placeholder=old.placeholder,
                raw_text=old.raw_text,
                llm_output=old.llm_output,
                final_text=edited_text,
                is_edited_by_human=True,
                generation_mode=old.generation_mode,
                automation_level=old.automation_level,
                tokens_used=old.tokens_used,
                model_used=old.model_used,
                is_fallback=old.is_fallback,
                error=old.error,
            )
        self.update_field(
            human_edits=new_edits,
            polished_slots=new_polished,
        )
        logger.info("Human edit recorded: slot=%s, len=%d", slot_id, len(edited_text))

    def upsert_quality_metric(self, slot_id: str, metric: QualityMetrics) -> None:
        """插入或更新单个 QualityMetrics。

        用法：
            manager.upsert_quality_metric(slot.slot_id, compute_slot_metrics(slot))
        """
        current = self.get()
        new_metrics = {**current.quality_metrics, slot_id: metric}
        self.update_field(quality_metrics=new_metrics)
        logger.debug(
            "Quality metric updated: slot=%s, score=%d",
            slot_id, metric.overall_score,
        )

    def aggregate_quality(self) -> Dict[str, Any]:
        """汇总当前所有 QualityMetrics 的统计信息。

        返回：
            avg_score, pass_rate, min_score, max_score, count
            fallback_ratio: fallback 段位比例
            blocked_count: BLOCK 段位数（<60）
            warning_count: WARN 段位数（<80）
        """
        state = self.get()
        metrics = state.quality_metrics
        slots = state.polished_slots

        if not metrics:
            return {
                "avg_score": 0.0,
                "pass_rate": 0.0,
                "min_score": 0,
                "max_score": 0,
                "count": 0,
                "fallback_ratio": 0.0,
                "blocked_count": 0,
                "warning_count": 0,
            }

        scores = [m.overall_score for m in metrics.values()]
        total = len(state.polished_slots)
        fallback_count = sum(1 for s in slots.values() if s.is_fallback)

        return {
            "avg_score": round(sum(scores) / len(scores), 1),
            "pass_rate": round(sum(1 for s in scores if s >= 80) / len(scores), 3),
            "min_score": min(scores),
            "max_score": max(scores),
            "count": len(scores),
            "fallback_ratio": round(fallback_count / total, 3) if total > 0 else 0.0,
            "blocked_count": sum(1 for s in scores if s < 60),
            "warning_count": sum(1 for s in scores if 60 <= s < 80),
        }

    # ========================================================================
    # 快照
    # ========================================================================

    def save_snapshot(self, name: str = "default") -> Path:
        """保存状态快照到磁盘（不包含 docx 二进制）。"""
        state = self.get()
        snapshot_path = self.SNAPSHOT_DIR / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        snapshot_path.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Snapshot saved: %s", snapshot_path)
        return snapshot_path

    def load_snapshot(self, snapshot_path: Path) -> None:
        """从磁盘加载快照。"""
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        # 反序列化 nested dataclass
        polished = {
            k: PolishedSlot.from_dict(v)
            for k, v in data.get("polished_slots", {}).items()
        }
        quality = {
            k: QualityMetrics(**v)
            for k, v in data.get("quality_metrics", {}).items()
        }
        from dataclasses import replace
        restored = replace(
            PipelineState(),
            current_step=data.get("current_step", 1),
            raw_data=data.get("raw_data"),
            excel_path=data.get("excel_path"),
            summary_path=data.get("summary_path"),
            mappings=data.get("mappings", []),
            slot_results=data.get("slot_results", {}),
            polished_slots=polished,
            human_edits=data.get("human_edits", {}),
            quality_metrics=quality,
            docx_path=data.get("docx_path"),
            audit_log=data.get("audit_log", {}),
            started_at=data.get("started_at"),
            updated_at=data.get("updated_at"),
        )
        self.update(restored)
        logger.info("Snapshot loaded: %s", snapshot_path)

    # ========================================================================
    # 统计
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """获取当前状态的统计信息。"""
        state = self.get()
        slots = state.polished_slots
        total = len(slots)
        by_level: Dict[str, int] = {}
        by_mode: Dict[str, int] = {}
        polished_count = 0
        edited_count = 0
        fallback_count = 0
        total_tokens = 0

        for slot in slots.values():
            by_level[slot.automation_level] = by_level.get(slot.automation_level, 0) + 1
            by_mode[slot.generation_mode] = by_mode.get(slot.generation_mode, 0) + 1
            if slot.llm_output is not None:
                polished_count += 1
            if slot.is_edited_by_human:
                edited_count += 1
            if slot.is_fallback:
                fallback_count += 1
            total_tokens += slot.tokens_used

        return {
            "current_step": state.current_step,
            "total_slots": total,
            "by_level": by_level,
            "by_mode": by_mode,
            "polished_count": polished_count,
            "edited_count": edited_count,
            "fallback_count": fallback_count,
            "total_tokens": total_tokens,
            "automation_rate": (
                (by_level.get("HIGH", 0) + by_level.get("MEDIUM", 0)) / total
                if total > 0 else 0.0
            ),
        }


# ============================================================================
# 便利函数
# ============================================================================

def get_state_manager() -> PipelineStateManager:
    """获取全局状态管理器（单例）。"""
    return PipelineStateManager()
