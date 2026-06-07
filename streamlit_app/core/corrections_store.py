"""修正样本库 - 反馈环持久化

设计原则：
    1. 追加写：每次管理员编辑都追加一条记录（不覆盖）
    2. JSONL 格式：每行一个 JSON 对象，便于流式处理和导出训练数据
    3. 按段位分文件：<slot_id>.jsonl 便于快速查询同段位历史
    4. 可导出：export_training_data() 生成 SFT 格式数据

数据流：
    管理员编辑 → save() → .streamlit_cache/user_corrections/<slot_id>.jsonl
    未来训练 → export_training_data() → JSONL
    未来润色 → get_for_slot() → few-shot examples
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# 存储路径
# ============================================================================

CORRECTIONS_DIR = Path(__file__).resolve().parent.parent.parent / ".streamlit_cache" / "user_corrections"


# ============================================================================
# 数据类
# ============================================================================

@dataclass(frozen=True)
class Correction:
    """单条人工修正记录。

    Attributes:
        slot_id: 段位 ID
        placeholder: 模板占位符
        original_raw: 原始提取的文本
        llm_output: LLM 生成的输出（如果有）
        human_edited: 人工编辑后的最终文本
        quality_score: 当时的质量分（0-100，None 表示未评分）
        model_used: 当时使用的 LLM 模型
        generation_mode: 当时的生成模式
        timestamp: 编辑时间
        metadata: 额外元数据（如温度、prompt 等）
    """
    slot_id: str
    placeholder: str
    original_raw: str
    llm_output: Optional[str]
    human_edited: str
    quality_score: Optional[int] = None
    model_used: str = "none"
    generation_mode: str = "extract"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Correction":
        return cls(**data)

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_jsonl_line(cls, line: str) -> "Correction":
        return cls.from_dict(json.loads(line))


# ============================================================================
# 核心类
# ============================================================================

class CorrectionsStore:
    """修正样本库管理器。

    用法：
        store = CorrectionsStore()
        store.save(Correction(...))
        history = store.load_for_slot("dom.elec.yoy.changjiang")
        all_records = store.load_all()
        jsonl = store.export_training_data()
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or CORRECTIONS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info("CorrectionsStore 初始化: %s", self.base_dir)

    def _get_path(self, slot_id: str) -> Path:
        """获取指定段位的 JSONL 文件路径。"""
        # 清理 slot_id 中的非法字符
        safe_id = slot_id.replace("/", "_").replace("\\", "_").replace(":", "_")
        return self.base_dir / f"{safe_id}.jsonl"

    def save(self, correction: Correction) -> Path:
        """追加一条修正记录。

        Returns:
            写入的文件路径
        """
        path = self._get_path(correction.slot_id)
        with path.open("a", encoding="utf-8") as f:
            f.write(correction.to_jsonl_line() + "\n")
        logger.info(
            "Correction saved: slot=%s, edited_len=%d",
            correction.slot_id,
            len(correction.human_edited),
        )
        return path

    def load_for_slot(self, slot_id: str) -> List[Correction]:
        """加载指定段位的历史修正记录。"""
        path = self._get_path(slot_id)
        if not path.exists():
            return []
        corrections = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                corrections.append(Correction.from_jsonl_line(line))
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning("跳过无效行: %s", e)
        return corrections

    def load_all(self) -> List[Correction]:
        """加载所有段位的历史修正记录。"""
        all_corrections: List[Correction] = []
        for path in sorted(self.base_dir.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    all_corrections.append(Correction.from_jsonl_line(line))
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning("跳过无效行 (%s): %s", path.name, e)
        return all_corrections

    def count(self, slot_id: Optional[str] = None) -> int:
        """统计记录数（指定段位或全部）。"""
        if slot_id:
            return len(self.load_for_slot(slot_id))
        return len(self.load_all())

    def get_recent_for_slot(self, slot_id: str, n: int = 3) -> List[Correction]:
        """获取指定段位最近 N 条修正。"""
        history = self.load_for_slot(slot_id)
        return history[-n:] if history else []

    def get_summary(self) -> Dict[str, Any]:
        """获取库统计信息。"""
        all_records = self.load_all()
        by_slot: Dict[str, int] = {}
        for c in all_records:
            by_slot[c.slot_id] = by_slot.get(c.slot_id, 0) + 1
        return {
            "total_corrections": len(all_records),
            "unique_slots": len(by_slot),
            "by_slot": by_slot,
            "files": sorted([p.name for p in self.base_dir.glob("*.jsonl")]),
        }

    def export_training_data(self) -> str:
        """导出为训练数据 JSONL 格式。

        格式（OpenAI/Anthropic fine-tuning 兼容）：
        {"messages": [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "原始文本 + 编辑指令"},
            {"role": "assistant", "content": "人工编辑后的文本"}
        ]}
        """
        all_records = self.load_all()
        lines = []
        for c in all_records:
            training_example = {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是能源行业（电力营销）资深周报撰写专家。"
                            "你的任务是根据原始提取的文本，改写为更专业、更精炼的周报段落。"
                            "必须保留所有数字，不得编造任何数据。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"【段位】{c.placeholder}\n"
                            f"【模式】{c.generation_mode}\n"
                            f"【原始文本】\n{c.original_raw}\n"
                            f"【请改写为更专业的版本】"
                        ),
                    },
                    {
                        "role": "assistant",
                        "content": c.human_edited,
                    },
                ],
                "metadata": {
                    "slot_id": c.slot_id,
                    "model_used": c.model_used,
                    "quality_score": c.quality_score,
                    "timestamp": c.timestamp,
                },
            }
            lines.append(json.dumps(training_example, ensure_ascii=False))
        return "\n".join(lines)

    def export_to_file(self, output_path: Optional[Path] = None) -> Path:
        """导出训练数据到文件。"""
        output_path = output_path or (self.base_dir / "training_data.jsonl")
        output_path.write_text(self.export_training_data(), encoding="utf-8")
        logger.info("训练数据已导出: %s", output_path)
        return output_path

    def clear_slot(self, slot_id: str) -> None:
        """清空指定段位的所有修正记录。"""
        path = self._get_path(slot_id)
        if path.exists():
            path.unlink()
            logger.warning("清空段位修正: %s", slot_id)

    def clear_all(self) -> None:
        """清空所有修正记录（谨慎使用）。"""
        for path in self.base_dir.glob("*.jsonl"):
            if path.name != "training_data.jsonl":  # 保留导出文件
                path.unlink()
        logger.warning("清空所有修正记录")


# ============================================================================
# 便利函数
# ============================================================================

def get_corrections_store() -> CorrectionsStore:
    """获取全局 CorrectionsStore（单例）。"""
    return CorrectionsStore()
