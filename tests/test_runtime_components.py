from __future__ import annotations

import backend.orchestration.runtime_components as runtime_components


def test_disabled_optional_components_are_not_constructed(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("disabled component was constructed")

    monkeypatch.setattr(runtime_components, "GraphRAGSystem", unexpected)
    monkeypatch.setattr(runtime_components, "CodeInterpreterSandbox", unexpected)

    assert runtime_components.build_graph_rag(enabled=False, llm=None, embed_model=None) is None
    assert runtime_components.build_code_interpreter(enabled=False) is None


def test_reranker_uses_bounded_top_n(monkeypatch):
    captured = {}

    monkeypatch.setattr(runtime_components, "load_llm", lambda **kwargs: captured.setdefault("llm", object()))
    monkeypatch.setattr(
        runtime_components,
        "initialize_reranker",
        lambda **kwargs: captured.setdefault("reranker", kwargs),
    )

    result = runtime_components.build_reranker(
        enabled=True,
        index_name="aiim",
        similarity_top_k=20,
        callback_manager=object(),
    )

    assert result["top_n"] == 5
    assert result["llm"] is captured["llm"]


def test_reranker_preserves_small_retrieval_depth(monkeypatch):
    monkeypatch.setattr(runtime_components, "load_llm", lambda **kwargs: object())
    monkeypatch.setattr(
        runtime_components,
        "initialize_reranker",
        lambda **kwargs: kwargs,
    )

    result = runtime_components.build_reranker(
        enabled=True,
        index_name="aiim",
        similarity_top_k=3,
        callback_manager=object(),
    )

    assert result["top_n"] == 3
