from pathlib import Path


def test_pdf_compatibility_helper_is_exported_by_canonical_indexer():
    source = Path("src/agentic_rag_chatbot_enterprise_ready/backend/indexer/llama_indexer.py").read_text()
    pdf_source = Path("src/agentic_rag_chatbot_enterprise_ready/backend/indexer/pdf_indexer.py").read_text()

    assert "def upsert_documents_to_index(" in source
    assert "upsert_documents_to_index" in pdf_source


def test_ingestion_compatibility_surface_does_not_reintroduce_legacy_service_context():
    source = Path("src/agentic_rag_chatbot_enterprise_ready/backend/indexer/llama_indexer.py").read_text()

    assert "from llama_index.core import ServiceContext" not in source
    assert "nest_asyncio" not in source
