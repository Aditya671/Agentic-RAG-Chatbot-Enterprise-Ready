"""Construct explicit document/page/table relationships for hierarchical retrieval."""

from __future__ import annotations

import logging
from typing import Any

try:
    from llama_index.core.schema import Document, NodeRelationship, TextNode
    LLAMA_INDEX_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    LLAMA_INDEX_AVAILABLE = False

logger = logging.getLogger(__name__)


class HierarchicalIndexer:
    """Construct a document -> page -> table hierarchy using LlamaIndex nodes."""

    def construct_hierarchy(
        self,
        doc_id: str,
        file_name: str,
        pages_data: list[dict[str, Any]],
        global_metadata: dict[str, Any] | None = None,
    ) -> list[Any]:
        if not isinstance(doc_id, str) or not doc_id.strip():
            raise ValueError("doc_id must be a non-empty string.")
        if not isinstance(file_name, str) or not file_name.strip():
            raise ValueError("file_name must be a non-empty string.")
        if not isinstance(pages_data, list):
            raise TypeError("pages_data must be a list.")

        metadata = dict(global_metadata or {})
        if not LLAMA_INDEX_AVAILABLE:
            return pages_data

        parent_doc = Document(
            id_=doc_id,
            text=f"DOCUMENT PARENT: {file_name}",
            metadata={
                **metadata,
                "file_name": file_name,
                "node_type": "parent_document",
            },
        )
        nodes: list[Any] = [parent_doc]
        page_ids: set[str] = set()

        for index, page in enumerate(pages_data, start=1):
            if not isinstance(page, dict):
                raise TypeError(f"pages_data[{index - 1}] must be a dictionary.")

            page_num = page.get("page_number", page.get("page_num", index))
            page_text = str(page.get("text") or "")
            page_id = f"{doc_id}_page_{page_num}"
            if page_id in page_ids:
                raise ValueError(f"Duplicate page identifier: {page_id}")
            page_ids.add(page_id)

            page_node = TextNode(
                id_=page_id,
                text=page_text,
                metadata={
                    **metadata,
                    "file_name": file_name,
                    "page_number": page_num,
                    "node_type": "page",
                },
            )
            page_node.relationships[NodeRelationship.PARENT] = parent_doc.as_related_node_info()
            parent_doc.relationships.setdefault(NodeRelationship.CHILD, []).append(
                page_node.as_related_node_info()
            )
            nodes.append(page_node)

            tables = page.get("tables") or []
            if not isinstance(tables, list):
                raise TypeError(f"tables for page {page_num} must be a list.")

            for table_index, table in enumerate(tables):
                table_id = f"{page_id}_table_{table_index}"
                table_node = TextNode(
                    id_=table_id,
                    text=f"TABLE EXTRACT:\n{table}",
                    metadata={
                        **metadata,
                        "file_name": file_name,
                        "page_number": page_num,
                        "node_type": "table_chunk",
                    },
                )
                table_node.relationships[NodeRelationship.PARENT] = page_node.as_related_node_info()
                page_node.relationships.setdefault(NodeRelationship.CHILD, []).append(
                    table_node.as_related_node_info()
                )
                nodes.append(table_node)

        logger.info("Constructed %d hierarchical nodes for %s", len(nodes), file_name)
        return nodes
