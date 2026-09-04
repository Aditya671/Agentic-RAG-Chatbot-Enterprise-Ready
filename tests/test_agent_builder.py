from __future__ import annotations

from types import SimpleNamespace

import backend.orchestration.agent_builder as agent_builder


class FakeTool:
    def __init__(self, name):
        self.name = name


class FakeAgent:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_builder_uses_runtime_retrieval_policy_and_optional_reranker(monkeypatch):
    captured = {}

    def fake_retriever(index, retrieval, **kwargs):
        captured["retrieval"] = retrieval
        captured["kwargs"] = kwargs
        return "provider-retriever"

    monkeypatch.setattr(agent_builder, "build_retriever", fake_retriever)
    monkeypatch.setattr(agent_builder, "FunctionAgent", FakeAgent)

    system = SimpleNamespace(
        runtime_boundary=SimpleNamespace(
            retrieval=SimpleNamespace(top_k=17, query_mode="semantic_hybrid")
        ),
        index="index",
        reranker="reranker",
        enable_coding_assistant=False,
        code_interpreter=None,
        graph_rag_system=None,
        csv_engine=None,
        llm="llm",
        upload_and_index_files_async=lambda files: "task",
        check_indexing_status=lambda task_id: "ok",
        query_local_file_index=lambda query: "local",
        bing_grounding_tool=lambda query: "web",
        _AsyncAgenticAiSystem__build_retriever_tool=lambda **kwargs: FakeTool(kwargs["name"]),
        _AsyncAgenticAiSystem__build_function_tool=lambda fn, name, description: FakeTool(name),
    )

    agent = agent_builder.build_agent(system)

    assert captured["retrieval"].top_k == 17
    assert captured["retrieval"].query_mode == "semantic_hybrid"
    assert captured["kwargs"] == {"node_postprocessors": ["reranker"]}
    assert agent.kwargs["llm"] == "llm"
    assert [tool.name for tool in agent.kwargs["tools"]] == [
        "im_retriever_tool",
        "upload_and_index_user_file_tool",
        "check_indexing_status_tool",
        "query_user_upload_file_indexes_tool",
        "internet_search_tool",
    ]


def test_builder_includes_csv_and_optional_tools(monkeypatch):
    monkeypatch.setattr(agent_builder, "build_retriever", lambda *args, **kwargs: "retriever")
    monkeypatch.setattr(agent_builder, "FunctionAgent", FakeAgent)

    system = SimpleNamespace(
        runtime_boundary=SimpleNamespace(retrieval=SimpleNamespace()),
        index="index",
        reranker=None,
        enable_coding_assistant=True,
        code_interpreter=SimpleNamespace(run_python=lambda code: "result"),
        graph_rag_system=SimpleNamespace(index=True, query=lambda query: "graph"),
        csv_engine=SimpleNamespace(query=lambda query: "csv"),
        llm="llm",
        upload_and_index_files_async=lambda files: "task",
        check_indexing_status=lambda task_id: "ok",
        query_local_file_index=lambda query: "local",
        bing_grounding_tool=lambda query: "web",
        _AsyncAgenticAiSystem__build_retriever_tool=lambda **kwargs: FakeTool(kwargs["name"]),
        _AsyncAgenticAiSystem__build_function_tool=lambda fn, name, description: FakeTool(name),
    )

    agent = agent_builder.build_agent(system)

    assert [tool.name for tool in agent.kwargs["tools"]][-3:] == [
        "graph_rag_tool",
        "code_interpreter_tool",
        "csv_tool",
    ]
