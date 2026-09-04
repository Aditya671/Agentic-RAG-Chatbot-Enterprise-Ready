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
- `motor`
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
