from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from backend.orchestration.retrieval_contract import RetrievalConfig


def test_defaults_preserve_current_agent_retrieval_policy() -> None:
    config = RetrievalConfig()

    assert config.top_k == 5
    assert config.query_mode == "semantic_hybrid"
    assert config.as_kwargs() == {
        "similarity_top_k": 5,
        "vector_store_query_mode": "semantic_hybrid",
    }


def test_custom_top_k_is_propagated_without_mutation() -> None:
    config = RetrievalConfig(top_k=12)
    kwargs = config.as_kwargs()

    assert kwargs["similarity_top_k"] == 12
    assert kwargs["vector_store_query_mode"] == "semantic_hybrid"


def test_top_k_rejects_bool_and_non_positive_values() -> None:
    for value in (True, False, 0, -1):
        with pytest.raises(ValueError):
            RetrievalConfig(top_k=value)  # type: ignore[arg-type]


def test_query_mode_must_be_semantic_hybrid() -> None:
    for value in ("", "   ", "vector", "similarity"):
        with pytest.raises(ValueError):
            RetrievalConfig(query_mode=value)


def test_query_mode_can_be_resolved_at_provider_boundary() -> None:
    config = RetrievalConfig()

    assert config.resolve_query_mode(str.upper) == "SEMANTIC_HYBRID"

    with pytest.raises(TypeError):
        config.resolve_query_mode(None)  # type: ignore[arg-type]


def test_config_is_immutable() -> None:
    config = RetrievalConfig()

    with pytest.raises(FrozenInstanceError):
        config.top_k = 10  # type: ignore[misc]
