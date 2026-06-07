"""Step 1 PoC 演示脚本 - 展示 reason_collector + reason_polisher 的端到端工作流

运行方式：
    PYTHONPATH=. python examples/poc_reason_polish.py

输出：
    - 从汇总表采集原因文本
    - 调用 LLM 润色（如可用）
    - 对比润色前后效果

环境变量：
    ANTHROPIC_API_KEY - 可选。未配置时回退到原文
"""
from __future__ import annotations

import io
import json
import logging
import os
import sys
from pathlib import Path

# Windows 控制台 UTF-8 支持
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 让脚本可以直接从项目根目录运行
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.collector.reason_collector import ReasonCollector
from src.generator.reason_polisher import ReasonPolisher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================================
# PoC 步骤 1: 提取 1-2 个关键原因文本
# ============================================================================

def step1_extract() -> None:
    """Step 1.1: 从汇总表采集关键原因文本。"""
    print("\n" + "=" * 70)
    print("📋 STEP 1.1: 提取关键原因文本")
    print("=" * 70)

    file_path = str(PROJECT_ROOT / "files" / "2026年第21周周数据汇总表.xlsx")
    logger.info("采集文件: %s", file_path)

    collector = ReasonCollector()
    results, errors = collector.collect(file_path, year=2026, week=21)

    # 统计
    total = len(results)
    non_empty = sum(1 for r in results.values() if not r.is_empty)
    print(f"\n总槽位: {total}, 成功提取: {non_empty}")

    # 选取最有代表性的几个做演示
    demo_slots = [
        "dom.elec.yoy.changjiang",    # 长江电力+全集团 电量同比
        "dom.elec.wow.changjiang",    # 长江电力+全集团 电量环比
        "dom.price.yoy.changjiang",   # 长江电力+全集团 电价同比
        "dom.elec.yoy.new_energy",    # 新能源电量同比
    ]

    print("\n演示槽位:")
    for sid in demo_slots:
        if sid in results:
            r = results[sid]
            marker = "📝" if not r.is_empty else "⭕"
            preview = r.raw_text.replace("\n", " ⏎ ")[:100]
            print(f"  {marker} [{sid}]")
            print(f"     {preview}...")

    return results


# ============================================================================
# PoC 步骤 2: 润色前/后对比
# ============================================================================

def step2_polish(results: dict) -> None:
    """Step 1.2: 演示润色效果。"""
    print("\n" + "=" * 70)
    print("✨ STEP 1.2: 润色前后对比")
    print("=" * 70)

    polisher = ReasonPolisher()

    print(f"\nLLM 状态: {'✅ 可用（' + polisher._model + '）' if polisher.is_available else '⚠️  不可用（API key 未配置，回退到原文）'}")

    # 选 1 段做完整对比演示
    demo_slot_id = "dom.elec.yoy.changjiang"
    if demo_slot_id not in results or results[demo_slot_id].is_empty:
        print("❌ 演示槽位无内容")
        return

    raw_text = results[demo_slot_id].raw_text
    print(f"\n【演示槽位】 {demo_slot_id}")
    print(f"\n【原文】(来自 Excel 国内数据填报表 H29)")
    print("─" * 60)
    print(raw_text)
    print("─" * 60)

    result = polisher.polish(raw_text)

    print(f"\n【润色】(模型: {result.model_used}, fallback: {result.is_fallback})")
    print("─" * 60)
    print(result.polished_text)
    print("─" * 60)

    if not result.is_fallback:
        print(f"\n💰 Token 消耗: {result.tokens_used}")
        print(f"🛡️  验证: {'✅ 通过' if result.validation_passed else '❌ 失败'}")


# ============================================================================
# PoC 步骤 3: 批量润色
# ============================================================================

def step3_batch_polish(results: dict) -> None:
    """Step 1.3: 批量润色所有非空槽位。"""
    print("\n" + "=" * 70)
    print("📦 STEP 1.3: 批量润色统计")
    print("=" * 70)

    polisher = ReasonPolisher()

    # 过滤非空
    non_empty = {sid: r.raw_text for sid, r in results.items() if not r.is_empty}
    print(f"\n待润色段数: {len(non_empty)}")

    polished_results = polisher.polish_batch(non_empty)

    # 统计
    fallback_count = sum(1 for r in polished_results.values() if r.is_fallback)
    success_count = len(polished_results) - fallback_count
    total_tokens = sum(r.tokens_used for r in polished_results.values())
    validation_passed = sum(1 for r in polished_results.values() if r.validation_passed)

    print(f"  润色成功: {success_count}")
    print(f"  Fallback（原文）: {fallback_count}")
    print(f"  验证通过: {validation_passed}/{len(polished_results)}")
    print(f"  总 Token: {total_tokens}")

    # 按分类统计
    from collections import Counter
    category_counter = Counter()
    for sid, r in results.items():
        if not r.is_empty:
            category_counter[r.slot.category] += 1

    print("\n按分类统计:")
    for cat, count in category_counter.most_common():
        print(f"  {cat}: {count} 段")


# ============================================================================
# 主入口
# ============================================================================

def main() -> None:
    print("\n" + "🚀" * 35)
    print("  Step 1 PoC: reason_collector + reason_polisher")
    print("🚀" * 35)

    # 1. 提取
    results = step1_extract()

    # 2. 润色单段
    step2_polish(results)

    # 3. 批量
    step3_batch_polish(results)

    # 4. 下一步提示
    print("\n" + "=" * 70)
    print("📌 下一步: Step 2 - 盘点 V4.docx 原因段落")
    print("=" * 70)
    print("运行: PYTHONPATH=. python examples/inventory_v4_reasons.py")


if __name__ == "__main__":
    main()
