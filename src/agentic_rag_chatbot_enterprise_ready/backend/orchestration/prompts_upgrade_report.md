# `prompts.py` — Upgrade Report

## Sequential status

This is **File 7** in the strict one-file-at-a-time upgrade sequence.

Completed:

1. `agentic_ai_system.py`
2. `code_interpreter.py`
3. `graph_rag.py`
4. `llm_loader.py`
5. `llm_models.py`
6. `pandasai_system.py`

This pass covers only `prompts.py`.

## Source-derived baseline

The original `prompts.py` provides the prompt constants consumed by
`agentic_ai_system.py`, including:

- `THREAD_TITLE_PROMPT`
- `AGENTIC_AI_CODEX_PROMPT`
- `AGENTIC_AI_SYSTEM_PROMPT`
- `AGENTIC_PANDAS_QUERY_ENGINE_INSTRUCTION_PROMPT`
- `AGENTIC_PANDAS_QUERY_ENGINE_PANDAS_PROMPT`
- `AGENTIC_PANDAS_QUERY_ENGINE_RESPONSE_SYNTHESIS_PROMPT`

The agent imports these constants directly. The original orchestration layer
formats the agent prompts with `{now_str}` and formats the structured-data
prompts with dataframe/metadata context. fileciteturn21file2L1-L4

The original prompt content already establishes PERE domain behavior, security,
data integrity, file analysis, dependency awareness, modernization,
documentation, error handling, and continuous improvement. fileciteturn25file0L1-L3

## Important conclusion

Unlike the previous files, `prompts.py` does **not have a meaningful module
upgrade target**.

It is a pure prompt-definition module. There is no LLM SDK/API dependency in
the file itself to upgrade.

Therefore this pass focuses on:

- prompt correctness
- placeholder compatibility
- tool-routing clarity
- grounding behavior
- trust-boundary handling
- structured-data safety
- prompt injection resilience
- deterministic output contracts
- testability
- versioning

No unnecessary framework dependency was introduced.

## Critical defects identified

### 1. Empty organization references

The original prompt contains partially empty organization references such as:

```text
You are the ** Technical Architect...
Act as ... for 's investment...
... within .
... evolving  standards...
```

This is a real prompt-quality defect, not a stylistic preference.

The upgraded prompt removes the broken placeholders and uses neutral,
non-invented enterprise language.

No organization name was invented because the supplied source does not
reliably provide one.

### 2. Prompt injection trust boundary was implicit

The original prompt discusses security, but does not explicitly establish:

```text
retrieved content = data
```

versus:

```text
system instructions = authority
```

That distinction is essential for this application because the agent consumes:

- retrieved enterprise documents
- uploaded files
- web results
- graph results
- CSV contents
- tool outputs

Microsoft's current agent-security guidance explicitly warns that retrieved
content can contain indirect prompt injections and recommends treating these
trust boundaries carefully. citeturn0search10turn0search9

The upgraded prompts now explicitly state that documents, files, web pages,
tool outputs, and metadata are data—not instructions.

### 3. Tool selection was under-specified

The application currently exposes:

- semantic retrieval
- uploaded-file retrieval
- internet search
- GraphRAG
- code interpreter
- structured CSV analysis

The original prompt did not provide sufficiently precise routing rules.

The upgraded prompt now defines the intended tool boundary and explicitly says:

```text
Do not call a tool merely because it exists.
```

This is important for latency, cost, reliability, and avoiding unnecessary
agent loops.

### 4. Structured data safety was under-specified

The application has a structured-data execution path.

The upgraded Pandas prompts now explicitly treat dataframe cell contents as
untrusted data and prohibit using cell values to change instructions, access
secrets, or perform unrelated operations.

### 5. Hallucination controls strengthened

The new prompts distinguish:

1. supported facts
2. derived calculations
3. interpretation
4. unavailable information

This is especially important for PERE analysis, where a plausible-looking
number can be more dangerous than an explicit "data unavailable."

### 6. Financial calculation discipline strengthened

The prompt now explicitly addresses:

- IRR
- NPV
- NOI
- cap rate
- yield-on-cost
- multiples
- units
- currency
- scale
- time period
- assumptions

The assistant is instructed not to silently invent missing definitions.

### 7. Title generation contract strengthened

The original title prompt specifies a maximum of eight words and named entities,
but it does not explicitly require exactly one title or prohibit invented
entities. fileciteturn21file0L1-L6

The upgraded contract now requires:

- one title
- maximum eight words
- no markdown
- no generic filler
- no invented entities
- no trailing punctuation

## Prompt versioning

Added:

```python
PROMPT_VERSION = "2.0"
```

This gives production telemetry and regression tests a stable prompt version
without coupling prompts to an LLM provider.

## Prompt registry

Added:

```python
PROMPT_TEMPLATES
```

with stable names.

This allows future code to retrieve prompts without duplicating string references.

## Rendering helpers

Added:

```python
render_agent_prompt()
render_pandas_instruction()
render_pandas_query_prompt()
get_prompt()
validate_prompt_contracts()
```

The important benefit is that prompt formatting can now be unit-tested without
instantiating LlamaIndex or making an LLM request.

## Placeholder contracts preserved

The application currently depends on these placeholders.

### Agent prompts

```text
{now_str}
```

### Pandas instruction prompt

```text
{df_info}
{metadata_str}
{instruction_str}
```

### Pandas query prompt

```text
{df_str}
{metadata_str}
{column_info}
{instruction_str}
```

These contracts are explicitly tested.

## No dependency modernization required

The prompt module contains no:

- OpenAI SDK
- Azure SDK
- LlamaIndex import
- Pandas import
- network client
- credential client

This is deliberate.

Prompt definitions should remain dependency-free so they can be:

- imported during startup
- tested in isolation
- linted
- versioned
- evaluated
- reused across providers

## Security research applied

Microsoft's current guidance identifies prompt injection as a major agent risk
and specifically distinguishes user-prompt attacks from indirect attacks
embedded in documents and tool responses. citeturn0search2turn0search7

Current Foundry guardrail guidance also defines intervention points at:

- user input
- tool calls
- tool responses
- output

and supports blocking or annotating risky content at those boundaries.
citeturn0search11turn0search8

The prompts therefore now reinforce the application-level trust boundary,
but the prompt itself is **not treated as the sole security mechanism**.

That distinction is important.

The final system should still use deterministic application/tool controls and,
where appropriate, Azure/Foundry Prompt Shields or equivalent guardrails.
Microsoft explicitly describes Prompt Shields for both user prompt attacks and
document attacks. citeturn0search2

## Regression suite

Added **40 regression tests**.

Coverage includes:

- all public prompt constants
- prompt version
- agent placeholder contracts
- Pandas placeholder contracts
- prompt rendering
- type validation
- empty input validation
- prompt registry
- unknown prompt handling
- trust-boundary language
- grounding rules
- tool selection rules
- PERE domain rules
- structured-data safety
- missing-column behavior
- missing-value behavior
- response synthesis rules
- title-generation contract
- secret placeholder detection
- external command detection
- accidental empty organization references
- legacy broken placeholder detection
- whitespace normalization
- dependency-free import contract

## Verification

Final regression suite:

```text
40 passed
```

**40/40 passed.**

The tests are dependency-free and make no LLM/API/network calls.

## Files

Production implementation:

`prompts_upgraded.py`

Regression suite:

`test_prompts.py`

Upgrade report:

`prompts_upgrade_report.md`

## Integration note

The application can replace the existing `prompts.py` constants directly because
the public constant names and runtime placeholders are preserved.

The new helper functions are additive and do not require changes to the already
completed `agentic_ai_system.py`.

## Security note

Prompt-level defenses reduce risk but are not deterministic authorization.

For this application, the actual security boundary should remain:

```text
User input
   ↓
Input validation / guardrails
   ↓
Agent
   ↓
Tool authorization
   ↓
Tool
   ↓
Tool-output validation
   ↓
Agent
   ↓
Output validation
```

Retrieved documents and tool responses must never be treated as trusted
instructions merely because the prompt says so. Microsoft's current agent
security guidance makes the same distinction for indirect prompt injection.
citeturn0search10
