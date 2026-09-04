"""Converged runtime integration for the compatibility agent."""
from __future__ import annotations

import json
from typing import Any

from llama_index.core.prompts import PromptTemplate

from backend.orchestration.agent_builder import build_agent
from backend.orchestration.agentic_ai_system_upgraded import AsyncAgenticAiSystem
from backend.orchestration.execution_contract import AgentResponse
from backend.orchestration.provider_boundaries import build_structured_query_engine
from backend.orchestration.retrieval_contract import RetrievalConfig
from backend.orchestration.runtime_boundary import AgentRuntimeBoundary
from backend.orchestration.runtime_policy import validate_top_k
from backend.prompts import (
    AGENTIC_PANDAS_QUERY_ENGINE_INSTRUCTION_PROMPT,
    AGENTIC_PANDAS_QUERY_ENGINE_PANDAS_PROMPT,
    AGENTIC_PANDAS_QUERY_ENGINE_RESPONSE_SYNTHESIS_PROMPT,
)


class IntegratedAsyncAgenticAiSystem(AsyncAgenticAiSystem):
    """Compatibility agent whose runtime path uses explicit provider seams."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        similarity_top_k = validate_top_k(kwargs.get("similarity_top_k", 20))
        self.runtime_boundary = AgentRuntimeBoundary(
            RetrievalConfig(top_k=similarity_top_k)
        )
        super().__init__(*args, **kwargs)
        self._refresh_runtime_boundary()
        self._rebuild_converged_runtime()

    @staticmethod
    def _validate_top_k(value: int) -> int:
        """Expose the shared retrieval-policy validator on the runtime surface."""
        return validate_top_k(value)

    def _refresh_runtime_boundary(self) -> None:
        self.runtime_boundary = AgentRuntimeBoundary(
            RetrievalConfig(top_k=self._validate_top_k(self.similarity_top_k))
        )

    def _rebuild_converged_runtime(self) -> None:
        """Synchronize provider-facing agent and structured-query state."""
        if self._csv_is_configured():
            self.csv_engine = self._build_structured_csv_engine()
        else:
            self.csv_engine = None
        self.agent = build_agent(self)

    def _build_structured_csv_engine(self) -> Any:
        """Build the CSV engine through the stable structured-query adapter."""
        df, meta = self.load_csv_file(
            self.blob_bytes["bytes"],
            self.blob_bytes.get("metadata", {}),
        )
        column_info = (
            f"Columns ({len(df.columns)} total): {', '.join(df.columns.tolist())}\n"
            f"Data types: {dict(df.dtypes)}\n"
            f"DataFrame shape: {df.shape[0]} rows, {df.shape[1]} columns"
        )
        df_info = f"{df.head(5).to_string()}\n{column_info}"
        metadata_str = json.dumps(meta, default=str) if isinstance(meta, dict) else str(meta)
        pandas_prompt = PromptTemplate(
            template=AGENTIC_PANDAS_QUERY_ENGINE_PANDAS_PROMPT,
            metadata=meta if isinstance(meta, dict) else {},
        ).partial_format(
            df_str=df.head(5).to_string(),
            metadata_str=metadata_str,
            column_info=column_info,
            instruction_str=AGENTIC_PANDAS_QUERY_ENGINE_INSTRUCTION_PROMPT.format(
                df_info=df_info,
                metadata_str=metadata_str,
            ),
        )
        response_prompt = PromptTemplate(
            AGENTIC_PANDAS_QUERY_ENGINE_RESPONSE_SYNTHESIS_PROMPT
        )
        return build_structured_query_engine(
            df,
            engine_kwargs={
                "instruction_str": AGENTIC_PANDAS_QUERY_ENGINE_INSTRUCTION_PROMPT.format(
                    df_info=df_info,
                    metadata_str=metadata_str,
                ),
                "pandas_prompt": pandas_prompt,
                "response_synthesis_prompt": response_prompt,
                "llm": self.llm,
            },
        )

    def set_similarity_top_k(self, similarity_top_k: int) -> None:
        super().set_similarity_top_k(self._validate_top_k(similarity_top_k))
        self._refresh_runtime_boundary()
        self._rebuild_converged_runtime()

    def set_selected_model(self, selected_model: Any) -> None:
        super().set_selected_model(selected_model)
        self._refresh_runtime_boundary()
        self._rebuild_converged_runtime()

    def set_embed_model(self) -> None:
        super().set_embed_model()
        self._refresh_runtime_boundary()
        self._rebuild_converged_runtime()

    def set_llm_creativity_level(self, llm_creativity_level: float) -> None:
        super().set_llm_creativity_level(llm_creativity_level)
        self._refresh_runtime_boundary()
        self._rebuild_converged_runtime()

    def set_reasoning_effect(self, reasoning_effect: str) -> None:
        super().set_reasoning_effect(reasoning_effect)
        self._refresh_runtime_boundary()
        self._rebuild_converged_runtime()

    def set_index_name(self, index_name: str) -> None:
        super().set_index_name(index_name)
        self._refresh_runtime_boundary()
        self._rebuild_converged_runtime()

    def set_reranker(self, enable_reranker: bool = False) -> None:
        super().set_reranker(enable_reranker)
        self._refresh_runtime_boundary()
        self._rebuild_converged_runtime()

    def set_graph_rag(self, enable_graph_rag: bool = False) -> None:
        super().set_graph_rag(enable_graph_rag)
        self._refresh_runtime_boundary()
        self._rebuild_converged_runtime()

    def set_coding_assistant(self, enable_coding_assistant: bool = False) -> None:
        super().set_coding_assistant(enable_coding_assistant)
        self._refresh_runtime_boundary()
        self._rebuild_converged_runtime()

    def build_provider_retriever(self, index: Any | None = None, **kwargs: Any) -> Any:
        """Build a provider retriever using the current validated runtime policy."""
        from backend.orchestration.provider_boundaries import build_retriever

        target_index = self.index if index is None else index
        return build_retriever(target_index, self.runtime_boundary.retrieval, **kwargs)

    @staticmethod
    def build_structured_query_engine(
        dataframe: Any,
        *,
        engine_kwargs: dict[str, Any] | None = None,
    ) -> Any:
        """Build structured querying through its isolated adapter."""
        return build_structured_query_engine(dataframe, engine_kwargs=engine_kwargs)

    def get_response_contract(self, response_block: Any) -> AgentResponse:
        return self.runtime_boundary.response(
            response_block,
            self.get_retriever_metadata(response_block),
        )

    async def get_response(self, question: str) -> dict[str, Any]:
        response = self.get_response_contract(await self.run_agent_async(question))
        return {
            "response_text": response.response_text,
            "response_metadata": response.response_metadata,
        }

    def get_response_async(self, question: str) -> dict[str, Any]:
        response_block = super().get_response_async(question)
        response = self.runtime_boundary.response(
            response_block.get("response_text", ""),
            response_block.get("response_metadata", []),
        )
        return {
            "response_text": response.response_text,
            "response_metadata": response.response_metadata,
        }

    async def collect_response_stream(self, response: Any) -> str:
        return await self.runtime_boundary.collect_stream(self.stream_response(response))
