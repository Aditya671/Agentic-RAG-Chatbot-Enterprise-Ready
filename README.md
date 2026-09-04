# Agentic-RAG-Chatbot-Enterprise-Ready

An enterprise-ready agentic AI assistant featuring hybrid search, automated CSV data analysis, persistent conversation memory using Azure Cosmos DB, user-upload indexing, internet grounding, and optional coding/GraphRAG capabilities.

---

## Core capabilities

- **Hybrid enterprise retrieval:** Azure AI Search backed retrieval for unstructured enterprise documents.
- **Structured analysis:** CSV questions can be routed to a stable structured-query adapter backed by the existing Pandas query implementation.
- **Persistent memory:** Conversation state is designed around Azure Cosmos DB so sessions are not tied to a single application process.
- **User file ingestion:** Uploaded files are staged safely, deduplicated by the indexing layer, and processed asynchronously through the existing task workflow.
- **Agentic tools:** Internet grounding, document retrieval, structured analysis, and optional coding/GraphRAG capabilities are exposed as tools to the agent.
- **Stable runtime contracts:** Retrieval policy and agent responses are represented by application-level contracts, with Azure/LlamaIndex translation isolated at provider boundaries.
- **Enterprise identity:** Azure managed identity / developer credentials and Azure Key Vault are supported for service authentication and secret retrieval.

## Architecture

```text
                         ┌─────────────────────┐
                         │       Chainlit      │
                         │        UI           │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Canonical Agentic   │
                         │ RAG Runtime         │
                         └──────────┬──────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 ▼                  ▼                  ▼
          ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
          │ Retrieval   │    │ Structured  │    │ Internet /  │
          │ provider    │    │ query edge  │    │ external    │
          └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
                 │                  │                  │
                 └──────────────────┼──────────────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ Stable application  │
                         │ response + sources  │
                         └──────────┬──────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ Azure Cosmos DB     │
                         │ conversation state │
                         └─────────────────────┘
```

## Runtime layering

The canonical import surface is:

```python
from backend.orchestration.agentic_ai_system import AsyncAgenticAiSystem
```

Existing callers keep this import path while receiving the converged runtime. Application retrieval policy is expressed through `RetrievalConfig`; provider-specific query-mode enums and structured-query dependencies are resolved only at the provider edge.

The older `agentic_ai_system_upgraded.py` implementation remains as an internal migration source. New application code should not depend on its provider-specific implementation details.

## Technology baseline

| Layer | Technology |
|---|---|
| Interface | Chainlit 2.12.x |
| Agent orchestration | LlamaIndex 0.14.x |
| LLM | Azure OpenAI |
| Embeddings | Azure OpenAI embeddings |
| Vector / hybrid retrieval | Azure AI Search |
| Persistent memory | Azure Cosmos DB |
| File storage | Azure Blob Storage |
| Secrets / identity | Azure Key Vault + Azure Identity |
| Background ingestion | Celery |
| Structured analysis | Pandas / LlamaIndex Pandas Query Engine via adapter |

## Configuration

The repository deliberately does **not** contain a live `config.yml` because configuration can contain environment-specific resource names and secret references.

Start from the safe template:

```bash
cp config.example.yml config.yml
```

Then replace the placeholders with the Azure resources for the environment. Keep `config.yml` and `.env` outside version control.

The runtime reads `CONFIG_PATH` when supplied; otherwise it looks for `./config.yml`.

Secrets should preferably be supplied through Azure Key Vault or environment variables. Do not place API keys, connection strings, or access tokens in YAML committed to Git.
