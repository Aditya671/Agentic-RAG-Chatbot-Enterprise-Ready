# Agentic-RAG-Chatbot-Enterprise-Ready

An enterprise-ready multi-agent AI assistant featuring hybrid search, automated CSV data analysis, persistent conversation memory using Azure Cosmos DB, user-upload indexing, internet grounding, and optional coding/GraphRAG capabilities.

---

## Core capabilities

- **Hybrid enterprise retrieval:** Azure AI Search backed retrieval for unstructured enterprise documents.
- **Structured analysis:** CSV questions can be routed to a Pandas-based query engine for tabular reasoning and calculations.
- **Persistent memory:** Conversation state is designed around Azure Cosmos DB so sessions are not tied to a single application process.
- **User file ingestion:** Uploaded files are staged safely, deduplicated by the indexing layer, and processed asynchronously through the existing task workflow.
- **Agentic tools:** Internet grounding, document retrieval, structured analysis, and optional coding/GraphRAG capabilities are exposed as tools to the agent.
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
                         │ Agentic RAG Runtime │
                         │  routing + memory   │
                         └──────────┬──────────┘
                                    │
             ┌──────────────────────┼──────────────────────┐
             ▼                      ▼                      ▼
      ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
      │ Azure AI    │        │ CSV /       │        │ Internet /  │
      │ Search RAG  │        │ Pandas      │        │ external    │
      └─────────────┘        └─────────────┘        └─────────────┘
             │                      │                      │
             └──────────────────────┼──────────────────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ Grounded response + │
                         │ source metadata     │
                         └──────────┬──────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ Azure Cosmos DB     │
                         │ conversation state │
                         └─────────────────────┘
```

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
| Structured analysis | Pandas / LlamaIndex Pandas Query Engine |

## Configuration

The repository deliberately does **not** contain a live `config.yml` because configuration can contain environment-specific resource names and secret references.

Start from the safe template:

```bash
cp config.example.yml config.yml
```

Then replace the placeholders with the Azure resources for the environment. Keep `config.yml` and `.env` outside version control.

The runtime reads `CONFIG_PATH` when supplied; otherwise it looks for `./config.yml`.

Secrets should preferably be supplied through Azure Key Vault or environment variables. Do not place API keys, connection strings, or access tokens in YAML committed to Git.

## Authentication

- Local development can use `AzureCliCredential` through the credential manager.
- Cloud deployments use `DefaultAzureCredential` and managed identity where configured.
- Azure Key Vault is used for secrets that are not supplied through environment variables.

## Running locally

Install the package and development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run the deterministic startup/package checks:

```bash
agentic-rag --check
```

Run the Chainlit application:

```bash
agentic-rag --frontend
```

The application will fail fast if the selected index configuration is missing rather than partially initializing and failing later during retrieval.

## Testing

The repository CI validates Python 3.12 and 3.13, compilation, Ruff, and pytest:

```bash
pytest
ruff check .
python -m compileall -q src main.py
```

Cloud-backed end-to-end tests require real Azure resources and credentials and should be executed in an environment provisioned for the application. The default test suite is intentionally safe to run without Azure access.

## Engineering decisions

### Structured vs. unstructured data

Semantic retrieval is useful for documents but is not a substitute for deterministic tabular calculations. The existing architecture therefore keeps the two paths separate and lets the agent choose the appropriate tool.

### Conversation state

The agent keeps session context while Azure Cosmos DB provides the persistence layer required for restart and horizontal-scaling scenarios.

### Inference and ingestion cost

The system retains max-loop protections and upload deduplication so repeated files and uncontrolled agent loops do not unnecessarily consume model or indexing capacity.

### Compatibility-first modernization

The current modernization keeps the existing business behavior and import contracts while moving the runtime toward a single canonical implementation. Compatibility shims are temporary migration boundaries rather than additional business logic.

## Roadmap

- [ ] Replace deprecated experimental structured-query dependency with its supported successor once the equivalent stable API is adopted.
- [ ] Consolidate remaining `*_upgraded.py` compatibility copies after their contracts are covered by tests.
- [ ] Add provider-level integration tests using mocked Azure clients.
- [ ] Add end-to-end retrieval/evaluation fixtures.
- [ ] Add production observability and distributed tracing.
- [ ] Harden RBAC/tenant-aware access control.
- [ ] Add production deployment manifests and worker scaling configuration.

## License

MIT
