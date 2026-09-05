# Phase 72 — Persistence & Conversation State

## Purpose

Phase 72 gives the canonical application runtime a provider-neutral conversation state boundary without replacing the existing Cosmos DB or MongoDB data layers.

```text
ApplicationRequest
    ↓
conversation_id + actor_id + session_id
    ↓
ConversationService
    ↓
ConversationStore contract
    ├── deterministic in-memory store (tests)
    └── Chainlit data-layer adapter
            ├── Azure Cosmos DB data layer
            └── MongoDB data layer
    ↓
user message + assistant message
    ↓
conversation history
```

The existing provider implementations remain responsible for SDK behavior, database configuration, indexes/partitioning, connection lifecycle, and Chainlit compatibility. The application only depends on the stable `ConversationStore` contract.

## Canonical contracts

`Conversation` identifies a conversation by:

- `conversation_id`;
- `actor_id`;
- `session_id`;
- creation/update timestamps;
- bounded metadata.

`ConversationMessage` identifies a persisted turn by:

- `message_id`;
- `conversation_id`;
- `actor_id`;
- role (`user`, `assistant`, or `system`);
- message content;
- timestamp;
- optional execution `run_id`;
- bounded metadata.

Message identity is separate from execution identity. A run can therefore be traced independently from the messages it produced.

## Runtime integration

`ApplicationRuntime` accepts an optional `conversation_store`.

When persistence is configured for a question request:

1. `conversation_id`, `actor_id`, and `session_id` are required;
2. the conversation is created or ownership is verified;
3. the canonical question handler executes normally;
4. only a successful answer is persisted as a user/assistant turn;
5. the execution trace records the conversation identity;
6. a `conversation.persisted` lifecycle event is emitted;
7. callers can retrieve bounded history through `ApplicationRuntime.history()`.

Upload and index-status capabilities are not implicitly persisted as chat turns. This keeps message semantics explicit.

## Isolation boundary

Conversation access is scoped to the actor and session established when the conversation is created.

The deterministic store rejects:

- a different actor accessing the conversation;
- the same actor using a different session;
- messages from a different actor;
- duplicate message IDs.

The Chainlit adapter performs the same actor ownership check against the persisted thread before reading or writing messages.

A missing conversation is not silently recreated during message append. The application must establish the conversation first.

## Cosmos DB and MongoDB boundary

The repository already contains production-oriented Chainlit data layers for both Azure Cosmos DB and MongoDB. Phase 72 does not create duplicate database implementations.

`ChainlitConversationStore` translates the provider-neutral contract into existing thread/step operations:

- `ensure_conversation()` → existing `update_thread()` / `get_thread()`;
- `append_message()` → existing `create_step()`;
- `list_messages()` → existing `get_thread()` step data;
- `delete_conversation()` → existing `delete_thread()`.

This keeps provider-specific persistence behind the existing data-layer boundary.

## Serialization and trace linkage

Conversation messages remain structured records rather than arbitrary serialized Python objects. Execution traces now retain `conversation_id`, `session_id`, and `actor_id` through JSONL reload so operational inspection can connect a run back to the conversation that produced it.

No message content is copied into reliability telemetry merely to make tracing easier.

## Failure semantics

Persistence errors are explicit runtime failures. The application does not convert a failed persistence operation into a successful request.

A retrieval/model failure does not create an assistant message. Conversation creation may exist after such a failure, but no false assistant answer is persisted.

The provider adapter does not introduce retries. Retry/idempotency remains the responsibility of the later background-processing phase.

## Deterministic validation

Phase 72 tests cover:

- successful runtime question persistence;
- history ordering and run linkage;
- missing identity rejection;
- no assistant turn after a failed handler;
- actor/session isolation;
- duplicate message identity;
- scoped conversation deletion;
- Chainlit adapter translation through a fake data layer.

No Cosmos DB, MongoDB, Azure credential, LLM, vector service, or network dependency is required for these tests.

## Deliberate non-goals

Phase 72 does not:

- replace the existing Cosmos DB data layer;
- replace the existing MongoDB data layer;
- select a provider automatically;
- introduce a new database dependency;
- introduce background jobs or retries;
- expose conversation history directly to the LLM without an explicit application decision;
- claim transactional multi-message writes across arbitrary providers.

## Exit criterion

The canonical runtime can persist and retrieve conversation turns through a provider-neutral contract, existing Cosmos/Mongo data layers can be used through an adapter, actor/session isolation is enforced, execution traces retain conversation identity, and deterministic tests cover the persistence lifecycle.

## Next integration gate

Phase 73 should address asynchronous/background ingestion and artifact-level idempotency. Celery retries remain disabled until the artifact identity and retry semantics are explicitly demonstrated.
