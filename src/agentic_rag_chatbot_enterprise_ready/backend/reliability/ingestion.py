"""Provider-neutral contract around the maintained uploaded-document indexer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class IngestionArtifact:
    """Stable identity and outcome for one uploaded artifact."""

    filename: str
    status: str
    artifact_id: str | None = None
    checksum: str | None = None
    chunks: int | None = None
    reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Stable result for a batch of uploaded artifacts."""

    artifacts: tuple[IngestionArtifact, ...]
    raw_metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> tuple[IngestionArtifact, ...]:
        return tuple(a for a in self.artifacts if a.status in {"indexed", "skipped"})

    @property
    def failed(self) -> tuple[IngestionArtifact, ...]:
        return tuple(a for a in self.artifacts if a.status == "failed")


class DocumentIngestionService:
    """Orchestrate upload/indexing without duplicating the maintained indexer."""

    def __init__(self, indexer: Any, *, indexer_call: Callable[..., Awaitable[Any]] | None = None) -> None:
        self.indexer = indexer
        self._indexer_call = indexer_call

    async def ingest(self, uploaded_files: Sequence[Any]) -> IngestionResult:
        if not isinstance(uploaded_files, (list, tuple)) or not uploaded_files:
            raise ValueError("uploaded_files must be a non-empty sequence")

        result = await self._call_indexer(uploaded_files)
        return self._normalize_result(result)

    async def _call_indexer(self, uploaded_files: Sequence[Any]) -> Any:
        if self._indexer_call is not None:
            return await self._indexer_call(uploaded_files)
        method = getattr(self.indexer, "index_uploaded_files", None)
        if not callable(method):
            raise TypeError("indexer must expose async index_uploaded_files")
        return await method(file_list=list(uploaded_files))

    @staticmethod
    def _normalize_result(result: Any) -> IngestionResult:
        if not isinstance(result, Mapping):
            raise TypeError("indexer result must be a mapping")

        indexed = result.get("indexed", ())
        skipped = result.get("skipped", ())
        failed = result.get("failed", ())
        chunks = result.get("chunks")
        summaries = result.get("summaries", {})

        artifacts: list[IngestionArtifact] = []
        for name in indexed if isinstance(indexed, (list, tuple)) else ():
            artifacts.append(IngestionArtifact(filename=str(name), status="indexed", chunks=chunks))
        for name in skipped if isinstance(skipped, (list, tuple)) else ():
            artifacts.append(IngestionArtifact(filename=str(name), status="skipped", chunks=0, reason="unchanged"))
        if isinstance(failed, Mapping):
            for name, reason in failed.items():
                artifacts.append(IngestionArtifact(filename=str(name), status="failed", reason=str(reason)))
        elif isinstance(failed, (list, tuple)):
            for name in failed:
                artifacts.append(IngestionArtifact(filename=str(name), status="failed"))

        metadata = dict(result)
        if isinstance(summaries, Mapping):
            metadata["summaries"] = dict(summaries)
        return IngestionResult(artifacts=tuple(artifacts), raw_metadata=metadata)
