"""Converged runtime integration for the canonical agent runtime."""
from __future__ import annotations

from typing import Any

from backend.ai_models import AIModelTypes
from backend.llm_loader import load_llm
from backend.orchestration.agent_builder import build_agent
from backend.orchestration.agentic_ai_system_runtime import AsyncAgenticAiSystem, logger
from backend.orchestration.component_runtime import build_graph_rag, build_reranker
from backend.orchestration.execution_contract import AgentResponse, extract_text
from backend.orchestration.graph_rag import GraphRAGSystem
from backend.orchestration.provider_boundaries import build_retriever, build_structured_query_engine
from backend.orchestration.reranker import initialize_reranker
from backend.orchestration.retrieval_contract import RetrievalConfig
from backend.orchestration.runtime_boundary import AgentRuntimeBoundary
from backend.orchestration.runtime_policy import validate_top_k
from backend.orchestration.structured_csv_runtime import build_csv_runtime


class IntegratedAsyncAgenticAiSystem(AsyncAgenticAiSystem):
    """Compatibility agent whose runtime path uses explicit provider seams."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.pop("enable_coding_assistant", None)
        similarity_top_k = validate_top_k(kwargs.get("similarity_top_k", 20))
        self.runtime_boundary = AgentRuntimeBoundary(RetrievalConfig(top_k=similarity_top_k))
        super().__init__(*args, **kwargs)
        self._refresh_runtime_boundary()
        self._rebuild_converged_runtime()

    @staticmethod
    def _validate_top_k(value: int) -> int:
        return validate_top_k(value)

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        """Use the execution contract as the single response-text normalizer."""
        return extract_text(response)

    def _refresh_runtime_boundary(self) -> None:
        self.runtime_boundary = AgentRuntimeBoundary(
            RetrievalConfig(top_k=self._validate_top_k(self.similarity_top_k))
        )

    def _rebuild_converged_runtime(self) -> None:
        self.reranker = self._build_reranker_runtime()
        self.graph_rag_system = self._build_graph_rag_runtime()
        self.csv_engine = self._build_structured_csv_engine() if self._csv_is_configured() else None
        self.agent = build_agent(self)

    def _build_reranker_runtime(self) -> Any:
        rerank_llm = None
        if self.enable_reranker:
            rerank_llm = load_llm(
                model=AIModelTypes.GPT41_MINI,
                index_name=self.index_name,
                use_azure=True,
                callback_manager=self.callback_manager,
            )
        return build_reranker(
            enabled=self.enable_reranker,
            llm=rerank_llm,
            top_n=min(5, self.similarity_top_k),
            initialize=initialize_reranker,
            logger=logger,
        )

    def _build_graph_rag_runtime(self) -> Any:
        return build_graph_rag(
            enabled=self.enable_graph_rag,
            llm=self.llm,
            embed_model=self.embed,
            initialize=GraphRAGSystem,
            logger=logger,
        )

    def _build_structured_csv_engine(self) -> Any:
        return build_csv_runtime(
            csv_bytes=self.blob_bytes["bytes"],
            metadata=self.blob_bytes.get("metadata", {}),
            load_csv_file=self.load_csv_file,
            llm=self.llm,
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

    def build_provider_retriever(self, index: Any | None = None, **kwargs: Any) -> Any:
        target_index = self.index if index is None else index
        return build_retriever(target_index, self.runtime_boundary.retrieval, **kwargs)

    @staticmethod
    def build_structured_query_engine(dataframe: Any, *, engine_kwargs: dict[str, Any] | None = None) -> Any:
        return build_structured_query_engine(dataframe, engine_kwargs=engine_kwargs)

    def get_response_contract(self, response_block: Any) -> AgentResponse:
        return self.runtime_boundary.response(response_block, self.get_retriever_metadata(response_block))

    async def get_response(self, question: str) -> dict[str, Any]:
        response = self.get_response_contract(await self.run_agent_async(question))
        return {"response_text": response.response_text, "response_metadata": response.response_metadata}

    def get_response_async(self, question: str) -> dict[str, Any]:
        response_block = super().get_response_async(question)
        response = self.runtime_boundary.response(
            response_block.get("response_text", ""), response_block.get("response_metadata", [])
        )
        return {"response_text": response.response_text, "response_metadata": response.response_metadata}

    async def collect_response_stream(self, response: Any) -> str:
        return await self.runtime_boundary.collect_stream(self.stream_response(response))
