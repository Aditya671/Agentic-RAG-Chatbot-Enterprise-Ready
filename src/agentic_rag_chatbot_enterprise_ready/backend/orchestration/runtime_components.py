"""Provider-facing factories for optional agent runtime components."""
from __future__ import annotations

from typing import Any

from backend.ai_models import AIModelTypes
from backend.llm_loader import load_llm
from backend.orchestration.code_interpreter import CodeInterpreterSandbox
from backend.orchestration.graph_rag import GraphRAGSystem
from backend.orchestration.reranker import initialize_reranker


def build_reranker(
    *,
    enabled: bool,
    index_name: str,
    similarity_top_k: int,
    callback_manager: Any,
) -> Any:
    """Build the optional reranker, returning ``None`` when disabled/unavailable."""
    if not enabled:
        return None
    try:
        rerank_llm = load_llm(
            model=AIModelTypes.GPT41_MINI,
            index_name=index_name,
            use_azure=True,
            callback_manager=callback_manager,
        )
        return initialize_reranker(llm=rerank_llm, top_n=min(5, similarity_top_k))
    except Exception:
        return None


def build_graph_rag(*, enabled: bool, llm: Any, embed_model: Any) -> Any:
    """Build the optional GraphRAG component."""
    if not enabled:
        return None
    try:
        return GraphRAGSystem(llm=llm, embed_model=embed_model)
    except Exception:
        return None


def build_code_interpreter(*, enabled: bool) -> Any:
    """Build the optional isolated code-execution component."""
    if not enabled:
        return None
    try:
        return CodeInterpreterSandbox()
    except Exception:
        return None
