# Package Plan

This document captures the package strategy for the enterprise RAG application.

## Runtime packages

- `chainlit`
- `llama-index`
- `llama-index-llms-azure-openai`
- `llama-index-embeddings-azure-openai`
- `llama-index-vector-stores-azureaisearch`
- `azure-identity`
- `azure-keyvault-secrets`
- `azure-storage-blob`
- `azure-cosmos`
- `azure-search-documents`
- `azure-ai-projects`
- `openai`
- `pandas`
- `python-dotenv`
- `requests`
- `PyMuPDF`
- `celery`
- `pymongo`
- `boto3`
- `botocore`

## Development packages

- `pytest`
- `pytest-asyncio`
- `ruff`
- `mypy`
- `build`

## Deliberately excluded

The application does **not** include a remote sandbox or arbitrary code-execution SDK. E2B and related code-interpreter packages are intentionally excluded from the runtime dependency set.

## Selection rule

Use a package only when it solves a concrete application requirement. Prefer managed Azure-native services and deterministic application logic over adding another execution or infrastructure dependency.

## Current dependency policy

The authoritative dependency versions live in `pyproject.toml`. This document is architectural guidance, not a second dependency manifest.

`azure-ai-projects==2.4.0` is intentionally retained while the application uses the LlamaIndex 0.14.x line. Azure AI Projects 2.5.0 requires OpenAI 3.x, while the LlamaIndex OpenAI integration used by this application requires OpenAI <3; keeping 2.4.0 and `openai>=2.8.0,<3` avoids that resolver conflict until the LlamaIndex/OpenAI stack is upgraded together.
