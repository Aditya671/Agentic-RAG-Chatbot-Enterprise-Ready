import logging
from typing import List, Dict, Any

try:
    from llama_index.core.schema import Document, TextNode, IndexNode
    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    LLAMA_INDEX_AVAILABLE = False

logger = logging.getLogger(__name__)

class HierarchicalIndexer:
    """
    Constructs a sophisticated LlamaIndex Document -> Page -> Chunk hierarchy.
    This enables an agentic RAG workflow to execute precise retrievals (e.g.,
    "Give me the summary of Page 5 of the Azure Architecture document").
    """
    def __init__(self):
        if not LLAMA_INDEX_AVAILABLE:
            logger.warning("LlamaIndex core not available. Hierarchical indexer will yield basic dicts.")

    def construct_hierarchy(
        self, 
        doc_id: str, 
        file_name: str, 
        pages_data: List[Dict[str, Any]], 
        global_metadata: Dict[str, Any]
    ) -> List[Any]:
        """
        Takes raw page-level extraction data and constructs LlamaIndex Node hierarchies.
        pages_data format expected: [{"page_num": 1, "text": "...", "tables": [...]}, ...]
        """
        logger.info(f"Constructing Hierarchical LlamaIndex nodes for {file_name}")
        
        if not LLAMA_INDEX_AVAILABLE:
            return pages_data # Fallback

        nodes = []
        
        # 1. Create the Parent Document Node
        parent_doc = Document(
            id_=doc_id,
            text=f"DOCUMENT PARENT: {file_name}",
            metadata={
                "file_name": file_name,
                "node_type": "parent_document",
                **global_metadata
            }
        )
        nodes.append(parent_doc)

        # 2. Create Page Nodes linked to Parent Document
        for page in pages_data:
            page_num = page.get("page_number", 0)
            page_text = page.get("text", "")
            
            page_id = f"{doc_id}_page_{page_num}"
            
            page_node = TextNode(
                id_=page_id,
                text=page_text,
                metadata={
                    "file_name": file_name,
                    "page_number": page_num,
                    "node_type": "page",
                    **global_metadata
                }
            )
            
            # Establish Relationship: Page -> Document
            page_node.relationships[1] = parent_doc.as_related_node_info() # 1 typically represents SOURCE
            parent_doc.relationships[3] = parent_doc.relationships.get(3, []) + [page_node.as_related_node_info()] # 3 typically represents CHILD

            nodes.append(page_node)
            
            # 3. Create Chunk/Table Nodes linked to Page
            tables = page.get("tables", [])
            for idx, table in enumerate(tables):
                chunk_id = f"{page_id}_table_{idx}"
                table_text = f"TABLE EXTRACT:\n{table}"
                
                table_node = TextNode(
                    id_=chunk_id,
                    text=table_text,
                    metadata={
                        "file_name": file_name,
                        "page_number": page_num,
                        "node_type": "table_chunk",
                    }
                )
                # Establish Relationship: Table -> Page
                table_node.relationships[1] = page_node.as_related_node_info()
                page_node.relationships[3] = page_node.relationships.get(3, []) + [table_node.as_related_node_info()]
                
                nodes.append(table_node)

        logger.info(f"Constructed {len(nodes)} hierarchical nodes for {file_name}")
        return nodes
