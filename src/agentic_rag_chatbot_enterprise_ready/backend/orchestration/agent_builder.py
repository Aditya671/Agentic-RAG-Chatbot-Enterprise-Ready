"""Provider-aware agent construction for the canonical orchestration path."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from llama_index.core.agent.workflow import FunctionAgent

from backend.orchestration.provider_boundaries import build_retriever
from backend.orchestration.tool_factory import build_function_tool, build_retriever_tool
from backend.prompts import AGENTIC_AI_CODEX_PROMPT, AGENTIC_AI_SYSTEM_PROMPT


def build_agent(system: Any) -> FunctionAgent:
    """Build the integrated agent from application policy and public tools."""
    retrieval = system.runtime_boundary.retrieval
    retriever_kwargs: dict[str, Any] = {}
    if system.reranker:
        retriever_kwargs["node_postprocessors"] = [system.reranker]

    retriever = build_retriever(system.index, retrieval, **retriever_kwargs)

    tools = [
        build_retriever_tool(
            retriever=retriever,
            name="im_retriever_tool",
            description=(
                "Query unstructured enterprise documents using semantic/hybrid "
                "retrieval. Use this for document-grounded questions."
            ),
        ),
        build_function_tool(
            system.upload_and_index_files_async,
            "upload_and_index_user_file_tool",
            "Upload files and start background indexing. Returns a task ID.",
        ),
        build_function_tool(
            system.check_indexing_status,
            "check_indexing_status_tool",
            "Check the status of a background file-indexing task.",
        ),
        build_function_tool(
            system.query_local_file_index,
            "query_user_upload_file_indexes_tool",
            "Query content from previously uploaded and indexed files.",
        ),
        build_function_tool(
            system.bing_grounding_tool,
            "internet_search_tool",
            "Search the internet through the configured Azure AI web-search agent.",
        ),
    ]

    if system.graph_rag_system and getattr(system.graph_rag_system, "index", None):
        tools.append(
            build_function_tool(
                system.graph_rag_system.query,
                "graph_rag_tool",
                "Query entity relationships and multi-hop knowledge graph facts.",
            )
        )

    if system.enable_coding_assistant and system.code_interpreter:
        tools.append(
            build_function_tool(
                system.code_interpreter.run_python,
                "code_interpreter_tool",
                "Execute Python code in the configured isolated sandbox.",
            )
        )

    if system.csv_engine is not None:
        tools.append(
            build_function_tool(
                lambda q: str(system.csv_engine.query(q)),
                "csv_tool",
                "Query the configured Salesforce meeting-data CSV.",
            )
        )

    system_prompt = (
        AGENTIC_AI_CODEX_PROMPT
        if system.enable_coding_assistant
        else AGENTIC_AI_SYSTEM_PROMPT
    ).format(now_str=datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    return FunctionAgent(
        tools=tools,
        llm=system.llm,
        system_prompt=system_prompt,
        verbose=True,
    )
