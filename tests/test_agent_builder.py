from __future__ import annotations

from types import SimpleNamespace

import backend.orchestration.agent_builder as agent_builder


class FakeTool:
    def __init__(self, name):
        self.name = name


class FakeAgent:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_builder_uses_runtime_owned_retriever_and_optional_reranker(monkeypatch):
    captured = {}

    def fake_retriever(**kwargs):
        captured["kwargs"] = kwargs
        return "provider-retriever"

    monkeypatch.setattr(agent_builder, "FunctionAgent", FakeAgent)
    monkeypatch.setattr(
        agent_builder,
        "build_retriever_tool",
        lambda **kwargs: FakeTool(kwargs["name"]),
    )
    monkeypatch.setattr(
        agent_builder,
        "build_function_tool",
        lambda fn, name, description: FakeTool(name),
    )

    system = SimpleNamespace(
        build_provider_retriever=fake_retriever,
        reranker="reranker",
        graph_rag_system=None,
        csv_engine=None,
        llm="llm",
        upload_and_index_files_async=lambda files: "task",
        check_indexing_status=lambda task_id: "ok",
        query_local_file_index=lambda query: "local",
        bing_grounding_tool=lambda query: "web",
    )

    agent = agent_builder.build_agent(system)

    assert captured["kwargs"] == {"node_postprocessors": ["reranker"]}
    assert agent.kwargs["llm"] == "llm"
    assert [tool.name for tool in agent.kwargs["tools"]] == [
        "im_retriever_tool",
        "upload_and_index_user_file_tool",
        "check_indexing_status_tool",
        "query_user_upload_file_indexes_tool",
        "internet_search_tool",
    ]


def test_builder_adds_supported_graph_and_csv_tools(monkeypatch):
    monkeypatch.setattr(agent_builder, "FunctionAgent", FakeAgent)
    monkeypatch.setattr(
        agent_builder,
        "build_retriever_tool",
        lambda **kwargs: FakeTool(kwargs["name"]),
    )
    monkeypatch.setattr(
        agent_builder,
        "build_function_tool",
        lambda fn, name, description: FakeTool(name),
    )

    system = SimpleNamespace(
        build_provider_retriever=lambda **kwargs: "retriever",
        reranker=None,
        graph_rag_system=SimpleNamespace(index=True, query=lambda query: "graph"),
        csv_engine=SimpleNamespace(query=lambda query: "csv"),
        llm="llm",
        upload_and_index_files_async=lambda files: "task",
        check_indexing_status=lambda task_id: "ok",
        query_local_file_index=lambda query: "local",
        bing_grounding_tool=lambda query: "web",
    )

    agent = agent_builder.build_agent(system)

    assert [tool.name for tool in agent.kwargs["tools"]][-2:] == [
        "graph_rag_tool",
        "csv_tool",
    ]
