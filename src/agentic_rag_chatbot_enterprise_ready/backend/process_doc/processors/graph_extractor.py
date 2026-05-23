import logging
from typing import List, Dict, Any

try:
    from langchain_core.documents import Document
    from langchain_experimental.graph_transformers import LLMGraphTransformer
    from langchain_openai import ChatOpenAI
    LANGCHAIN_GRAPH_AVAILABLE = True
except ImportError:
    LANGCHAIN_GRAPH_AVAILABLE = False

logger = logging.getLogger(__name__)

class GraphEntityExtractor:
    """
    Extracts nodes and relationships (Knowledge Graphs) directly from the digitized text 
    using LangChain's LLMGraphTransformer.
    """
    def __init__(self, llm=None):
        if not LANGCHAIN_GRAPH_AVAILABLE:
            logger.warning("LangChain experimental graph tools not available.")
            self.transformer = None
        else:
            # Recommend using a stronger model like GPT-4 for graph extraction
            self.llm = llm or ChatOpenAI(temperature=0, model="gpt-4o")
            self.transformer = LLMGraphTransformer(llm=self.llm)

    def extract_graph_data(self, text: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Identifies entities and their relationships.
        """
        logger.info("Extracting Graph RAG entities and relationships...")
        
        if not self.transformer:
            return {"nodes": [], "relationships": []}
            
        try:
            # Graph extraction is token-intensive. In a real scenario, text should be chunked.
            snippet = text[:3000]
            documents = [Document(page_content=snippet)]
            graph_documents = self.transformer.convert_to_graph_documents(documents)
            
            if not graph_documents:
                return {"nodes": [], "relationships": []}
                
            graph = graph_documents[0]
            
            nodes = [{"id": node.id, "label": node.type} for node in graph.nodes]
            relationships = [
                {"source": rel.source.id, "target": rel.target.id, "type": rel.type} 
                for rel in graph.relationships
            ]
            
            return {
                "nodes": nodes,
                "relationships": relationships
            }
        except Exception as e:
            logger.error(f"Error extracting graph data: {e}")
            return {"nodes": [], "relationships": []}
