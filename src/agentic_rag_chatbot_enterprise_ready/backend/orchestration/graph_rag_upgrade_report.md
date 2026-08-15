# `graph_rag.py` — Upgrade Report

## Sequential status

This is **File 3** in the requested one-file-at-a-time upgrade sequence.

Completed before this file:
1. `agentic_ai_system.py`
2. `code_interpreter.py`

This pass modifies only the GraphRAG implementation and its regression suite.

## Original architecture

The uploaded file used:

- `KnowledgeGraphIndex`
- `SimpleGraphStore`
- `NebulaGraphStore`
- `StorageContext`
- global `Settings.llm` / `Settings.embed_model` mutation
- `max_triplets_per_chunk=2`
- `include_embeddings=True`
- `embedding_mode="hybrid"`

## Critical finding: the LlamaIndex graph API is deprecated

Current LlamaIndex documentation explicitly marks `KnowledgeGraphIndex` as deprecated since 0.10.53 and recommends `PropertyGraphIndex`.

The current stable LlamaIndex release found during research is:

- `llama-index`: **0.14.23**
- `llama-index-core`: **0.14.23**

PyPI confirms 0.14.23 as the current release line checked on 2026-08-08.

Therefore this was not a cosmetic upgrade. The GraphRAG implementation needed a structural migration.

## New architecture

```text
Documents
    |
    v
PropertyGraphIndex
    |
    +--------------------+
    |                    |
    v                    v
Graph Store          Vector Store
    |                    |
NebulaGraph        SimpleVectorStore*
    |                    |
    +---------+----------+
              |
              v
      Property Graph
        Retriever
              |
              v
        Query Engine
```

`*` The vector store is intentionally injectable. `SimpleVectorStore` is the compatibility default; a production deployment should use a durable vector store if graph embeddings must survive process restarts.

## Why a separate vector store?

The current LlamaIndex Nebula property-graph documentation states that `NebulaPropertyGraphStore.vector_query()` is not implemented.

Therefore the old idea of storing graph structure and expecting Nebula to perform vector retrieval is not correct for the current integration.

LlamaIndex's PropertyGraph architecture explicitly supports a separate graph store and vector store. Current documentation lists:

- `SimplePropertyGraphStore`
- `Neo4jPropertyGraphStore`
- `NebulaPropertyGraphStore`
- other property graph stores

and shows `PropertyGraphIndex.from_existing()` for loading an existing graph.

## Major fixes

### 1. Deprecated `KnowledgeGraphIndex` removed

Replaced:

```python
KnowledgeGraphIndex
```

with:

```python
PropertyGraphIndex
```

### 2. Deprecated `SimpleGraphStore` removed

Replaced with:

```python
SimplePropertyGraphStore
```

This is important because `PropertyGraphIndex` works with property-graph semantics rather than the older triplet-only graph abstraction.

### 3. Nebula integration upgraded

Current package:

```text
llama-index-graph-stores-nebula 0.6.0
```

was verified on PyPI.

The integration exposes:

```python
NebulaPropertyGraphStore
```

for property graphs.

### 4. Nebula configuration is now explicit

Supported environment variables:

```text
NEBULA_SPACE_NAME
NEBULA_SPACE
NEBULA_URL
NEBULA_PORT
NEBULA_USERNAME
NEBULA_PASSWORD
```

The original implementation required only:

```text
NEBULA_SPACE_NAME
```

and relied on implicit/default connection behavior.

### 5. No broad exception fallback from persistent graph to memory

The original did:

```text
Nebula failure
      |
      v
SimpleGraphStore
```

This is dangerous for an enterprise application because a production configuration failure can silently turn persistent GraphRAG into ephemeral GraphRAG.

The upgraded implementation instead:

```text
Nebula explicitly configured
        |
        +-- success --> persistent graph
        |
        +-- failure --> explicit configuration error
```

Memory mode is selected deliberately by not enabling Nebula.

### 6. Removed global `Settings` mutation

The old implementation temporarily changed:

```python
Settings.llm
Settings.embed_model
```

around graph construction.

This is global process state and is unsafe when multiple GraphRAG systems, users, models, or concurrent operations exist.

The upgraded implementation passes:

```python
embed_model=self.embed_model
```

directly to `PropertyGraphIndex`.

The LLM is retained as the component's explicit dependency.

### 7. Graph construction is no longer hidden inside application startup assumptions

The new class supports:

```python
build_graph_from_documents(...)
```

and:

```python
insert_documents(...)
```

and:

```python
load_existing_graph(...)
```

This separates:

- initial ingestion
- incremental ingestion
- loading an existing graph
- querying

That is much better suited to the application's Celery/background indexing architecture.

### 8. Existing graph support added

The new implementation supports:

```python
PropertyGraphIndex.from_existing(...)
```

which is important for production deployments where the graph should not be rebuilt every time the application starts.

### 9. Embedding behavior made explicit

The implementation uses:

```python
embed_kg_nodes=True
```

by default.

The vector store is explicitly injected into the property graph index.

This addresses a major limitation of the original `KnowledgeGraphIndex` design.

### 10. Query semantics modernized

Old:

```python
embedding_mode="hybrid"
```

has been replaced by the PropertyGraph retrieval model:

```python
include_text=True
similarity_top_k=5
path_depth=1
```

The values are configurable.

### 11. Empty/invalid documents handled

Empty documents are skipped.

Invalid document types raise immediately.

### 12. Stable errors

Added:

```text
GraphRAGError
GraphRAGConfigurationError
```

rather than returning:

```text
"Knowledge graph is not available for querying."
```

This is important because a tool should distinguish a real application failure from a legitimate textual answer.

### 13. Lifecycle management

Added:

```python
close()
```

and context-manager support.

## Important limitation retained deliberately

The old parameter:

```python
max_triplets_per_chunk=2
```

does not map directly to the new `PropertyGraphIndex` constructor.

The new architecture controls graph extraction using `kg_extractors`.

Therefore the upgraded code does not silently pretend that the old setting still controls extraction.

If the application requires an exact two-triplet-per-chunk policy, the correct place to enforce that is a configured LlamaIndex graph extractor, not a fake constructor parameter.

## Regression suite

The regression suite covers:

- default property graph store
- Nebula configuration
- explicit Nebula enablement
- missing Nebula space
- invalid top-k
- invalid path depth
- empty documents
- empty document filtering
- invalid document types
- deprecated API removal
- PropertyGraphIndex construction
- separate vector store
- embedding configuration
- custom KG extractors
- legacy triplet parameter handling
- incremental insertion
- existing graph loading
- retriever configuration
- query engine configuration
- query validation
- query result normalization
- resource cleanup
- context-manager cleanup
- Nebula port validation
- explicit-vs-environment configuration
- graph-build failure translation
- existing-graph failure translation

## Verification

The regression suite is dependency-isolated and does not require a live NebulaGraph server.

Production integration testing still needs:

- real NebulaGraph
- actual Nebula schema
- graph ingestion
- vector-store persistence
- graph embedding generation
- multi-hop retrieval
- query-engine answer quality
- graph-store reconnect/restart behavior
- existing-graph loading
- concurrent graph reads
- concurrent ingestion
- large-graph performance

## Production recommendation

For the final application architecture, I recommend:

```text
                Celery ingestion
                      |
                      v
               PropertyGraphIndex
                  /          \
                 /            \
                v              v
         NebulaGraph       Durable Vector DB
                \              /
                 \            /
                  v          v
                 Hybrid Property
                    Graph RAG
                       |
                       v
                 Agent Tool
```

The important point is that **graph storage and vector retrieval should not be conflated**.

Nebula should own graph topology and relationships; the vector layer should own semantic retrieval; PropertyGraphIndex should orchestrate both.
