"""Step 3: 批量标注 reason_map.json + 回归测试

运行方式：
    PYTHONPATH=. python examples/build_reason_map.py

输入：
    - data/processed/reason_segments.json （Step 2 输出）
    - data/dictionaries/reason_slots.json （槽位定义）
    - files/2026年第21周周数据汇总表.xlsx

输出：
    - data/dictionaries/reason_map.json （V4 段落 ↔ Excel 单元格映射）
    - 覆盖率报告（终端打印）

设计原则：
    1. 映射是显式的（V4 段号 → Excel 槽位），不做模糊匹配
    2. 一个 V4 段落可映射 1+ 个槽位（拼装）
    3. 槽位不存在或内容为空时，标记为 "manual"（保持手动）
    4. 回归测试验证每个映射：槽位存在 + 单元格非空
"""
from __future__ import annotations

import io
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.collector.reason_collector import ALL_REASON_SLOTS, ReasonCollector, ReasonSlot


# ============================================================================
# 数据类
# ============================================================================

@dataclass(frozen=True)
class ReasonMapping:
    """V4 段落 → Excel 槽位 的映射。"""
    v4_index: int                          # V4 中的段落编号
    v4_text: str                           # V4 中的原文
    template_placeholder: str              # 模板中的占位符
    source_slots: List[str]                # 主要槽位 ID 列表
    automation_level: str                  # HIGH / MEDIUM / LOW / MANUAL
    polish_required: bool                  # 是否需要 LLM 润色
    fallback_text: Optional[str] = None    # 兜底文本（槽位为空时使用）
    notes: Optional[str] = None            # 备注


# ============================================================================
# 手动标注的映射表（这是人工劳动的核心）
# ============================================================================

# 这个表是 Step 3 的核心产物。
# 每条记录对应 V4 中一个"原因/分析"段落，定义了：
#   - 它在模板中的占位符
#   - 它在 Excel 中的数据源（哪些槽位）
#   - 它的自动化等级

MANUAL_MAPPINGS: List[Dict[str, Any]] = [
    # ====================================================================
    # P5: 概览（数据拼装，无原因文本）
    # ====================================================================
    {
        "v4_index": 5,
        "template_placeholder": "{{ v4_P5_overview }}",
        "source_slots": [],  # 数据拼装（不走 reason_collector）
        "automation_level": "HIGH",
        "polish_required": False,
        "fallback_text": "上周，集团公司合计上网电量 {total} 亿千瓦时，其中国内 {domestic} 亿千瓦时，国际 {international} 亿千瓦时。",
        "notes": "纯数据段落，从综合分析表 I41/I4 拼装",
    },
    # ====================================================================
    # P6: 国内电量同比/环比原因（核心映射点）
    # ====================================================================
    {
        "v4_index": 6,
        "template_placeholder": "{{ v4_P6_dom_elec_yoy_wow }}",
        "source_slots": ["dom.elec.yoy.changjiang", "dom.elec.wow.changjiang"],
        "automation_level": "HIGH",
        "polish_required": True,
        "notes": "H29 + H53 拼装，LLM 润色",
    },
    # ====================================================================
    # P11: 国内电价同比 品类原因
    # ====================================================================
    {
        "v4_index": 11,
        "template_placeholder": "{{ v4_P11_dom_price_yoy }}",
        "source_slots": ["dom.price.yoy.changjiang", "dom.price.yoy.new_energy", "dom.price.yoy.thermal"],
        "automation_level": "MEDIUM",
        "polish_required": True,
        "notes": "H101 (changjiang) 为主，H104/H105 补充品类细节",
    },
    # ====================================================================
    # P12: 国内电价环比 品类原因
    # ====================================================================
    {
        "v4_index": 12,
        "template_placeholder": "{{ v4_P12_dom_price_wow }}",
        "source_slots": ["dom.elec.wow.summary", "dom.elec.wow.changjiang"],
        "automation_level": "MEDIUM",
        "polish_required": True,
        "notes": "H71 汇总 + H53 changjiang",
    },
    # ====================================================================
    # P13-P16: 品类级环比原因（数据驱动 LLM 生成 - Step 8 新增）
    # ====================================================================
    {
        "v4_index": 13,
        "template_placeholder": "{{ v4_P13_hydro_price_wow }}",
        "source_slots": [],
        "automation_level": "HIGH",
        "polish_required": True,
        "generation_mode": "grounded_category",
        "context": {
            "category": "hydro",
            "metric": "price_change_wow",
            "scope": "domestic",
        },
        "fallback_text": "水电电价环比下降的原因：[待人工补充] 主要原因是电价较高的金下梯级电站电量在大水电中占比下降。",
        "notes": "数据驱动生成（综合分析表 R78-86 品类数据）",
    },
    {
        "v4_index": 14,
        "template_placeholder": "{{ v4_P14_wind_price_wow }}",
        "source_slots": [],
        "automation_level": "HIGH",
        "polish_required": True,
        "generation_mode": "grounded_category",
        "context": {
            "category": "wind",
            "metric": "price_change_wow",
            "scope": "domestic",
        },
        "fallback_text": "风电电价环比提高的原因：[待人工补充] 主要原因是海上风电占比提高。",
        "notes": "数据驱动生成",
    },
    {
        "v4_index": 15,
        "template_placeholder": "{{ v4_P15_solar_price_wow }}",
        "source_slots": [],
        "automation_level": "HIGH",
        "polish_required": True,
        "generation_mode": "grounded_category",
        "context": {
            "category": "solar",
            "metric": "price_change_wow",
            "scope": "domestic",
        },
        "fallback_text": "光伏电价环比提高的原因：[待人工补充] 主要原因是内蒙、青海、山西等低价地区电量环比下降。",
        "notes": "数据驱动生成",
    },
    {
        "v4_index": 16,
        "template_placeholder": "{{ v4_P16_thermal_price_wow }}",
        "source_slots": [],
        "automation_level": "HIGH",
        "polish_required": True,
        "generation_mode": "grounded_category",
        "context": {
            "category": "thermal",
            "metric": "price_change_wow",
            "scope": "domestic",
        },
        "fallback_text": "火电电价环比提高原因：[待人工补充] 主要原因是上周现货电价较低，欠发套利较多。",
        "notes": "数据驱动生成",
    },
    # ====================================================================
    # P18: 国内发电收入
    # ====================================================================
    {
        "v4_index": 18,
        "template_placeholder": "{{ v4_P18_dom_revenue }}",
        "source_slots": ["dom.elec.yoy.changjiang", "dom.elec.wow.changjiang"],
        "automation_level": "HIGH",
        "polish_required": True,
        "notes": "复用 P6 数据",
    },
    # ====================================================================
    # P20: 国际电价同比
    # ====================================================================
    {
        "v4_index": 20,
        "template_placeholder": "{{ v4_P20_intl_price_yoy }}",
        "source_slots": ["intl.elec.yoy.h", "intl.price.yoy.t"],
        "automation_level": "HIGH",
        "polish_required": True,
        "notes": "H14 + T14 拼装",
    },
    # ====================================================================
    # P21: 国际电价环比
    # ====================================================================
    {
        "v4_index": 21,
        "template_placeholder": "{{ v4_P21_intl_price_wow }}",
        "source_slots": ["intl.elec.wow.h", "intl.price.wow.t"],
        "automation_level": "HIGH",
        "polish_required": True,
        "notes": "H15 + T15 拼装",
    },
    # ====================================================================
    # P23: 市场化交易水电
    # ====================================================================
    {
        "v4_index": 23,
        "template_placeholder": "{{ v4_P23_market_hydro }}",
        "source_slots": ["dom.elec.yoy.summary", "dom.elec.wow.summary"],
        "automation_level": "HIGH",
        "polish_required": True,
        "notes": "H47 + H71 汇总",
    },
    # ====================================================================
    # P24: 市场化交易新能源（来自现货价格）
    # ====================================================================
    {
        "v4_index": 24,
        "template_placeholder": "{{ v4_P24_market_new_energy }}",
        "source_slots": [],  # 来自现货价格表
        "automation_level": "MEDIUM",
        "polish_required": True,
        "notes": "现货市场均价（10 地区）拼装，summary_collector 已采集",
    },
    # ====================================================================
    # P25: 市场化交易火电
    # ====================================================================
    {
        "v4_index": 25,
        "template_placeholder": "{{ v4_P25_market_thermal }}",
        "source_slots": [],
        "automation_level": "MEDIUM",
        "polish_required": True,
        "notes": "现货 + 中长期合同数据拼装",
    },
    # ====================================================================
    # P27: 绿证
    # ====================================================================
    {
        "v4_index": 27,
        "template_placeholder": "{{ v4_P27_green_cert }}",
        "source_slots": ["carbon.green_cert.t", "carbon.green_cert.t2"],
        "automation_level": "MEDIUM",
        "polish_required": True,
        "notes": "T4 + T17 拼装",
    },
]


# ============================================================================
# 映射验证 + JSON 生成
# ============================================================================

def build_reason_map(
    manual_mappings: List[Dict[str, Any]],
    v4_segments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """构建 reason_map.json 字典。"""
    # V4 段号 → 段落信息
    v4_by_index = {s["index"]: s for s in v4_segments}

    mappings: List[Dict[str, Any]] = []
    for m in manual_mappings:
        v4_idx = m["v4_index"]
        v4_seg = v4_by_index.get(v4_idx, {})
        mapping = {
            "v4_index": v4_idx,
            "v4_text_preview": v4_seg.get("text", "")[:200],
            "template_placeholder": m["template_placeholder"],
            "source_slots": m["source_slots"],
            "automation_level": m["automation_level"],
            "polish_required": m["polish_required"],
            "fallback_text": m.get("fallback_text"),
            "notes": m.get("notes"),
        }
        mappings.append(mapping)

    return {
        "version": "1.0",
        "description": "V4 段落 → Excel 槽位 的映射表",
        "total_mappings": len(mappings),
        "mappings": mappings,
    }


def validate_mappings(
    reason_map: Dict[str, Any],
    available_slots: List[ReasonSlot],
) -> Tuple[List[str], List[str]]:
    """验证所有映射。

    Returns:
        (errors, warnings)
    """
    slot_ids = {s.slot_id for s in available_slots}
    errors: List[str] = []
    warnings: List[str] = []

    for m in reason_map["mappings"]:
        v4_idx = m["v4_index"]
        for slot_id in m["source_slots"]:
            if slot_id not in slot_ids:
                errors.append(
                    f"P{v4_idx}: 槽位 '{slot_id}' 不在 ALL_REASON_SLOTS 中"
                )
        if m["automation_level"] == "MANUAL" and not m["fallback_text"]:
            warnings.append(
                f"P{v4_idx}: 标记为 MANUAL 但无 fallback_text"
            )

    return errors, warnings


def test_extraction_coverage(
    reason_map: Dict[str, Any],
    file_path: str,
) -> Dict[str, Any]:
    """实测每个 mapping 的提取情况。"""
    collector = ReasonCollector()
    results, _ = collector.collect(file_path)

    coverage: Dict[str, Any] = {
        "total": len(reason_map["mappings"]),
        "high_auto_pass": 0,    # HIGH 且能取到数据
        "high_auto_fail": 0,    # HIGH 但取不到数据
        "manual_count": 0,
        "medium_count": 0,
    }

    for m in reason_map["mappings"]:
        if m["automation_level"] == "MANUAL":
            coverage["manual_count"] += 1
            continue

        if m["automation_level"] == "MEDIUM":
            coverage["medium_count"] += 1

        # 尝试提取 source_slots
        if m["source_slots"]:
            all_empty = True
            for slot_id in m["source_slots"]:
                if slot_id in results and not results[slot_id].is_empty:
                    all_empty = False
                    break
            if all_empty:
                if m["automation_level"] == "HIGH":
                    coverage["high_auto_fail"] += 1
            else:
                if m["automation_level"] == "HIGH":
                    coverage["high_auto_pass"] += 1

    return coverage


def print_coverage_report(coverage: Dict[str, Any]) -> None:
    """打印覆盖率报告。"""
    total = coverage["total"]
    auto_count = coverage["high_auto_pass"] + coverage["medium_count"] + coverage["high_auto_fail"]

    print("\n" + "=" * 70)
    print("📊 覆盖率报告")
    print("=" * 70)
    print(f"\n总段落: {total}")
    print(f"  HIGH 自动化（已验证可取到数据）: {coverage['high_auto_pass']}")
    print(f"  HIGH 自动化（取不到数据 ⚠️）: {coverage['high_auto_fail']}")
    print(f"  MEDIUM 自动化: {coverage['medium_count']}")
    print(f"  MANUAL（保留手动）: {coverage['manual_count']}")
    print()
    if total > 0:
        auto_pct = (coverage["high_auto_pass"] + coverage["medium_count"]) / total * 100
        print(f"✅ 自动化覆盖: {auto_pct:.0f}%")
        if coverage["high_auto_fail"] > 0:
            print(f"⚠️  需修复: {coverage['high_auto_fail']} 个 HIGH 段落取不到数据")


# ============================================================================
# 主流程
# ============================================================================

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # 加载 Step 2 输出
    segments_path = PROJECT_ROOT / "data" / "processed" / "reason_segments.json"
    if not segments_path.exists():
        print(f"❌ 请先运行 Step 2: python examples/inventory_v4_reasons.py")
        return

    with open(segments_path, "r", encoding="utf-8") as f:
        segments_data = json.load(f)

    # 构建映射
    reason_map = build_reason_map(MANUAL_MAPPINGS, segments_data["needs_mapping"])

    # 验证
    errors, warnings = validate_mappings(reason_map, ALL_REASON_SLOTS)
    if errors:
        print("\n❌ 验证错误:")
        for e in errors:
            print(f"  - {e}")
        return
    if warnings:
        print("\n⚠️  验证警告:")
        for w in warnings:
            print(f"  - {w}")

    # 写入 JSON
    output_path = PROJECT_ROOT / "data" / "dictionaries" / "reason_map.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(reason_map, f, ensure_ascii=False, indent=2)
    print(f"\n✅ reason_map.json 已保存: {output_path}")
    print(f"   共 {reason_map['total_mappings']} 条映射")

    # 实测覆盖率
    summary_path = PROJECT_ROOT / "files" / "2026年第21周周数据汇总表.xlsx"
    if summary_path.exists():
        coverage = test_extraction_coverage(reason_map, str(summary_path))
        print_coverage_report(coverage)

    print("\n" + "=" * 70)
    print("📌 下一步: 实施到 report_generator")
    print("=" * 70)
    print("1. 在 data/templates/ 中创建含占位符的模板")
    print("2. 扩展 report_generator.py 接入 reason_collector + reason_polisher")
    print("3. 端到端测试: 真实 Excel → 含原因文本的 Word")


if __name__ == "__main__":
    main()
