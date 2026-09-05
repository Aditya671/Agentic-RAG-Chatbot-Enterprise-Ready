"""Provider-neutral contract for retrieval results entering the application boundary."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .contracts import Evidence


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """A generated answer plus only source metadata returned by retrieval."""

    response_text: str
    evidence: tuple[Evidence, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def grounded(self) -> bool:
        """Whether the answer has at least one source-backed evidence record."""
        return bool(self.evidence)


class RetrievalService:
    """Adapt the maintained agent question path into a stable retrieval contract."""

    def __init__(self, agent: Any) -> None:
        self.agent = agent

    async def answer(self, question: str) -> RetrievalResult:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")
        response = await self.agent.get_response(question.strip())
        if not isinstance(response, Mapping):
            raise TypeError("agent response must be a mapping")
        text = str(response.get("response_text", "")).strip()
        if not text:
            raise ValueError("agent response contains no response_text")
        metadata = response.get("response_metadata", ())
        return RetrievalResult(
            response_text=text,
            evidence=tuple(self._evidence_from_source(source) for source in self._source_items(metadata)),
            metadata=metadata if isinstance(metadata, Mapping) else {"sources": metadata},
        )

    @staticmethod
    def _source_items(metadata: Any) -> list[Any]:
        if isinstance(metadata, Mapping):
            sources = metadata.get("sources", metadata.get("source_nodes", ()))
        else:
            sources = metadata
        if isinstance(sources, (list, tuple)):
            return list(sources)
        return []

    @staticmethod
    def _evidence_from_source(source: Any) -> Evidence:
        if not isinstance(source, Mapping):
            raise TypeError("retrieval source must be a mapping")
        source_id = str(
            source.get("id")
            or source.get("source")
            or source.get("file_name")
            or source.get("filename")
            or "unknown"
        )
        locator = source.get("locator") or source.get("page") or source.get("url")
        score = source.get("score")
        relevance = float(score) if isinstance(score, (int, float)) else None
        metadata = {
            key: value
            for key, value in source.items()
            if key not in {"content", "excerpt", "text"}
        }
        return Evidence(
            source_id=source_id,
            source_type=str(source.get("type") or "retrieval"),
            locator=str(locator) if locator is not None else None,
            relevance=relevance,
            metadata=metadata,
        )
