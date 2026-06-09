"""质量指标计算器 - 4 重检测 + 段位评分

设计原则：
    1. 4 重检测（数字保留/长度合理/禁词扫描/专业度）每个独立函数
    2. 复用现有算法（reason_polisher._validate_output / llm_orchestrator._validate_numbers）
    3. 行业术语从 data/dictionaries/*.json 的 short_names 字段聚合
    4. @lru_cache 避免每次都读磁盘
    5. 函数均为纯函数（无副作用），方便单测

使用：
    from streamlit_app.core.quality_metrics import compute_slot_metrics
    metrics = compute_slot_metrics(slot)
    print(metrics.overall_score)  # 0-100
"""
from __future__ import annotations

import functools
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from streamlit_app.core.pipeline_state import PolishedSlot, QualityMetrics

logger = logging.getLogger(__name__)


# ============================================================================
# 常量
# ============================================================================

# 复用 reason_polisher.py:383-388 禁词词表
FORBIDDEN_WORDS: Tuple[str, ...] = (
    "预计将", "据预测", "有望", "可能会", "或将", "可能将",
)

# 复用 reason_polisher.py:390-393 长度阈值
LENGTH_RATIO_MIN = 0.5
LENGTH_RATIO_MAX = 1.8

# 数字一致性容差（复用 llm_orchestrator.py:349）
NUMBER_TOLERANCE = 0.011

# 专业度检测词表
STRUCTURE_MARKERS: Tuple[str, ...] = (
    "一是", "二是", "三是", "1、", "2、", "3、",
    "主因", "影响", "拉动", "受…影响", "受..影响",
)

COLLOQUIAL_WORDS: Tuple[str, ...] = (
    "我们", "我觉得", "其实", "挺", "蛮",
)

# 降级硬编码（当 data/dictionaries/ 缺失时使用）
FALLBACK_TERMS: Tuple[str, ...] = (
    "上网电量", "上网电价", "同比", "环比", "市场化交易",
    "现货均价", "合约电价", "发电能力", "利用小时", "电源结构",
)

# 各维度满分数
SCORE_NUMBERS = 30
SCORE_LENGTH = 20
SCORE_FORBIDDEN = 20
SCORE_PROFESSIONALISM = 20
SCORE_DEVIATION = 10


# ============================================================================
# 行业术语加载
# ============================================================================

@dataclass(frozen=True)
class IndustryTerms:
    """从 data/dictionaries/ 加载的行业术语集合。"""
    terms: Tuple[str, ...]
    source_files: Tuple[str, ...]
    fallback: bool = False  # True 表示 JSON 加载失败，使用降级词表


@functools.lru_cache(maxsize=1)
def load_industry_terms() -> IndustryTerms:
    """从 data/dictionaries/ 加载行业术语（带缓存）。

    聚合 metrics.json + energy_types.json + organizations.json
    所有 short_names 字段。

    失败时降级为 FALLBACK_TERMS。
    """
    # 项目根目录 = streamlit_app/core/quality_metrics.py 的 3 层上级
    project_root = Path(__file__).resolve().parent.parent.parent
    dict_dir = project_root / "data" / "dictionaries"

    all_terms: List[str] = []
    source_files: List[str] = []
    fallback = False

    for filename in ("metrics.json", "energy_types.json", "organizations.json"):
        path = dict_dir / filename
        if not path.exists():
            logger.warning("Dictionaries file not found: %s", path)
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            source_files.append(filename)
            for entry in data.values():
                if not isinstance(entry, dict):
                    continue
                # short_names 是首选
                if "short_names" in entry and isinstance(entry["short_names"], list):
                    all_terms.extend(str(s) for s in entry["short_names"])
                # 兜底：name 字段
                elif "name" in entry:
                    all_terms.append(str(entry["name"]))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load dictionary %s: %s", path, e)
            continue

    if not all_terms:
        logger.warning("No industry terms loaded from dictionaries, using fallback")
        return IndustryTerms(terms=FALLBACK_TERMS, source_files=(), fallback=True)

    # 去重 + 按长度倒序（长词优先匹配，避免"电量"误匹配"上网电量"的子串）
    unique = sorted(set(all_terms), key=lambda x: -len(x))
    return IndustryTerms(terms=tuple(unique), source_files=tuple(source_files))


def clear_industry_terms_cache() -> None:
    """清除 lru_cache（测试用）。"""
    load_industry_terms.cache_clear()


# ============================================================================
# 4 重检测算子
# ============================================================================

def _extract_numbers(text: str) -> List[str]:
    """提取文本中所有数字（保留正负号和小数点）。"""
    return re.findall(r"-?\d+\.?\d*", text)


def validate_numbers(raw: str, polished: str) -> bool:
    """数字保留检测（30 分）。

    算法：polished 中所有 ≥2 位数字必须出现在 raw 中（容差 ±0.011）。
    复用 llm_orchestrator._validate_numbers 逻辑。
    """
    input_numbers = _extract_numbers(raw)
    output_numbers = _extract_numbers(polished)
    if not output_numbers:
        return True

    # 只校验"显著"数字（≥2 位或含小数点）
    input_sig = {n for n in input_numbers if len(n) >= 2 or "." in n}
    output_sig = {n for n in output_numbers if len(n) >= 2 or "." in n}

    for on in output_sig:
        if on in input_sig:
            continue
        try:
            on_f = float(on)
            if any(
                abs(on_f - float(inum)) < NUMBER_TOLERANCE
                for inum in input_sig
            ):
                continue
        except ValueError:
            pass
        return False
    return True


def check_length(raw: str, polished: str) -> Tuple[bool, float]:
    """长度合理检测（20 分）。

    返回 (pass, ratio)。ratio = len(polished) / max(len(raw), 1)。
    """
    raw_len = max(len(raw), 1)
    ratio = len(polished) / raw_len
    return LENGTH_RATIO_MIN <= ratio <= LENGTH_RATIO_MAX, ratio


def check_forbidden(polished: str) -> Tuple[bool, List[str]]:
    """禁词扫描检测（20 分）。

    返回 (pass, matched_words)。
    """
    matched = [w for w in FORBIDDEN_WORDS if w in polished]
    return len(matched) == 0, matched


def compute_professionalism(polished: str) -> Tuple[int, List[str]]:
    """专业度检测（20 分，返回 0/10/20 离散分数）。

    维度：
        A. 行业术语命中（从词典加载）
        B. 结构化句式标记
        C. 段落长度区间
        D. 无口语化
    """
    score = SCORE_PROFESSIONALISM
    warnings: List[str] = []
    p = polished.strip()

    if not p:
        return 0, ["空文本"]

    # A. 行业术语命中
    terms_obj = load_industry_terms()
    hits = sum(1 for t in terms_obj.terms if t in p)
    if hits < 2:
        score -= 10
        warnings.append(
            f"行业术语稀疏(命中{hits}/{len(terms_obj.terms)})"
        )

    # B. 结构化句式
    if not any(m in p for m in STRUCTURE_MARKERS):
        score -= 5
        warnings.append("缺乏并列/因果结构标记")

    # C. 长度区间
    if len(p) < 50:
        score -= 5
        warnings.append("段落过短(疑似未充分改写)")
    elif len(p) > 600:
        score -= 5
        warnings.append("段落过长(可能注水)")

    # D. 口语化
    if any(c in p for c in COLLOQUIAL_WORDS):
        score -= 5
        warnings.append("含口语化表达")

    # 离散化为 0/10/20
    score = max(0, min(SCORE_PROFESSIONALISM, score))
    if score > 10:
        score = SCORE_PROFESSIONALISM
    elif score > 0:
        score = 10
    else:
        score = 0
    return score, warnings


def compute_deviation(raw: str, polished: str) -> float:
    """原文偏差（10 分）。

    0-1 比率：1 - (Levenshtein 距离 / max(len))。
    1.0 = 完全相同；0.0 = 完全不同。
    """
    if not raw and not polished:
        return 1.0
    if not raw or not polished:
        return 0.0

    # 简单的字符级编辑距离（避免引入外部依赖）
    m, n = len(raw), len(polished)
    if m == 0 or n == 0:
        return 0.0

    # 用集合操作近似（O(m+n) 复杂度）
    raw_set = set(raw)
    polished_set = set(polished)
    common = raw_set & polished_set
    total = raw_set | polished_set
    if not total:
        return 1.0
    return len(common) / len(total)


# ============================================================================
# 段位评分
# ============================================================================

def compute_slot_metrics(slot: PolishedSlot) -> QualityMetrics:
    """计算单个段位的 QualityMetrics。

    输入：PolishedSlot（用 raw_text 和 final_text 计算）
    输出：QualityMetrics（5 维 + warnings + overall_score）
    """
    raw = slot.raw_text or ""
    polished = slot.final_text or slot.llm_output or ""

    # 4 重检测
    numbers_ok = validate_numbers(raw, polished)
    length_ok, length_ratio = check_length(raw, polished)
    forbidden_ok, forbidden_matched = check_forbidden(polished)
    prof_score, prof_warnings = compute_professionalism(polished)
    deviation = compute_deviation(raw, polished)

    # 聚合 warnings
    warnings: List[str] = list(prof_warnings)
    if not numbers_ok:
        warnings.append("数字与原文不一致")
    if not length_ok:
        if length_ratio > LENGTH_RATIO_MAX:
            warnings.append(f"过长(原文{len(raw)}字→改写{len(polished)}字，{length_ratio:.1f}x)")
        else:
            warnings.append(f"过短(原文{len(raw)}字→改写{len(polished)}字，{length_ratio:.1f}x)")
    for w in forbidden_matched:
        warnings.append(f"含禁词: {w}")

    # 计算 overall_score
    overall = (
        (SCORE_NUMBERS if numbers_ok else 0)
        + (SCORE_LENGTH if length_ok else 0)
        + (SCORE_FORBIDDEN if forbidden_ok else 0)
        + prof_score
        + int(round(deviation * SCORE_DEVIATION))
    )
    overall = max(0, min(100, overall))

    return QualityMetrics(
        slot_id=slot.slot_id,
        numbers_consistency=numbers_ok,
        length_reasonable=length_ok,
        no_forbidden_words=forbidden_ok,
        professionalism=prof_score,
        original_deviation=round(deviation, 3),
        overall_score=overall,
        warnings=warnings,
    )


def compute_batch_metrics(
    slots: Dict[str, PolishedSlot],
) -> Dict[str, QualityMetrics]:
    """批量计算多个段位的 QualityMetrics。

    返回 {slot_id: QualityMetrics}。
    """
    return {slot_id: compute_slot_metrics(slot) for slot_id, slot in slots.items()}


def aggregate_overall(
    metrics: Dict[str, QualityMetrics],
) -> Dict[str, Any]:
    """聚合统计。

    返回：
        avg_score: float 平均分
        pass_rate: float 通过率（≥80 比例）
        min_score: int 最低分
        max_score: int 最高分
        count: int 段位数
        sum_tokens: int（保留接口，暂未使用）
    """
    if not metrics:
        return {
            "avg_score": 0.0,
            "pass_rate": 0.0,
            "min_score": 0,
            "max_score": 0,
            "count": 0,
        }

    scores = [m.overall_score for m in metrics.values()]
    return {
        "avg_score": round(sum(scores) / len(scores), 1),
        "pass_rate": round(sum(1 for s in scores if s >= 80) / len(scores), 3),
        "min_score": min(scores),
        "max_score": max(scores),
        "count": len(scores),
    }
