"""streamlit_app.core - Pipeline 核心模块

包含：
    - pipeline_state: session_state 封装
    - corrections_store: 反馈环持久化
    - llm_orchestrator: LLM 调参包装
    - data_bridge: v2/v3 数据桥接
    - version_router: URL 参数 + 版本路由
"""

from streamlit_app.core.pipeline_state import (
    PipelineState,
    PipelineStateManager,
    PolishedSlot,
    QualityMetrics,
    get_state_manager,
)
from streamlit_app.core.quality_metrics import (
    IndustryTerms,
    aggregate_overall,
    check_forbidden,
    check_length,
    clear_industry_terms_cache,
    compute_batch_metrics,
    compute_deviation,
    compute_professionalism,
    compute_slot_metrics,
    load_industry_terms,
    validate_numbers,
)
from streamlit_app.core.quality_gate import (
    GateConfig,
    GateResult,
    GateVerdict,
    combine_with_fallback,
    evaluate,
    should_block_button,
)
from streamlit_app.core.corrections_store import (
    Correction,
    CorrectionsStore,
    get_corrections_store,
)
from streamlit_app.core.llm_orchestrator import (
    LLMCallParams,
    LLMOrchestrator,
    OrchestratorStats,
    get_orchestrator,
)
from streamlit_app.core.data_bridge import (
    auto_sync,
    clear_all,
    ensure_bundle,
    get_shared_data,
    get_sync_status,
    sync_v2_to_v3,
    sync_v3_to_v2,
)
from streamlit_app.core.safe_page_config import safe_set_page_config
from streamlit_app.core.version_router import (
    DEFAULT_VERSION,
    VERSION_KEY,
    VALID_VERSIONS,
    VERSION_LABELS,
    get_current_version,
    get_switch_url,
    render_cross_version_prompt,
    render_version_switcher,
    set_version,
    switch_to_version,
)

__all__ = [
    # pipeline_state
    "PipelineState",
    "PipelineStateManager",
    "PolishedSlot",
    "QualityMetrics",
    "get_state_manager",
    # quality_metrics
    "IndustryTerms",
    "aggregate_overall",
    "check_forbidden",
    "check_length",
    "clear_industry_terms_cache",
    "compute_batch_metrics",
    "compute_deviation",
    "compute_professionalism",
    "compute_slot_metrics",
    "load_industry_terms",
    "validate_numbers",
    # quality_gate
    "GateConfig",
    "GateResult",
    "GateVerdict",
    "combine_with_fallback",
    "evaluate",
    "should_block_button",
    # corrections_store
    "Correction",
    "CorrectionsStore",
    "get_corrections_store",
    # llm_orchestrator
    "LLMCallParams",
    "LLMOrchestrator",
    "OrchestratorStats",
    "get_orchestrator",
    # data_bridge
    "auto_sync",
    "clear_all",
    "ensure_bundle",
    "get_shared_data",
    "get_sync_status",
    "sync_v2_to_v3",
    "sync_v3_to_v2",
    # safe_set_page_config（独立零依赖模块）
    "safe_set_page_config",
    # version_router
    "DEFAULT_VERSION",
    "VERSION_KEY",
    "VALID_VERSIONS",
    "VERSION_LABELS",
    "get_current_version",
    "get_switch_url",
    "render_cross_version_prompt",
    "render_version_switcher",
    "set_version",
    "switch_to_version",
]
