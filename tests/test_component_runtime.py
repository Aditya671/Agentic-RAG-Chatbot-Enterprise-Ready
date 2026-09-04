from __future__ import annotations

from backend.orchestration.component_runtime import (
    build_code_interpreter,
    build_graph_rag,
    build_reranker,
)


class _Logger:
    def __init__(self):
        self.calls = 0

    def exception(self, *_args, **_kwargs):
        self.calls += 1


def test_disabled_components_do_not_initialize():
    logger = _Logger()
    called = []
    initialize = lambda **kwargs: called.append(kwargs)

    assert build_reranker(enabled=False, llm=object(), top_n=5, initialize=initialize, logger=logger) is None
    assert build_graph_rag(enabled=False, llm=object(), embed_model=object(), initialize=initialize, logger=logger) is None
    assert build_code_interpreter(enabled=False, initialize=lambda: called.append(True), logger=logger) is None
    assert called == []


def test_reranker_fail_open_preserves_existing_behavior():
    logger = _Logger()

    def initialize(**_kwargs):
        raise RuntimeError("provider unavailable")

    assert build_reranker(enabled=True, llm=object(), top_n=5, initialize=initialize, logger=logger) is None
    assert logger.calls == 1


def test_graph_rag_passes_provider_inputs():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        return "graph"

    result = build_graph_rag(enabled=True, llm="llm", embed_model="embed", initialize=initialize, logger=_Logger())
    assert result == "graph"
    assert captured == {"llm": "llm", "embed_model": "embed"}


def test_code_interpreter_fail_open_returns_none():
    logger = _Logger()

    def initialize():
        raise RuntimeError("sandbox unavailable")

    assert build_code_interpreter(enabled=True, initialize=initialize, logger=logger) is None
    assert logger.calls == 1
