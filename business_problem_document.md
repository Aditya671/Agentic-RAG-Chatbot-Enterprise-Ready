# Business Problem Document

## Project Name
Agentic RAG Chatbot Azure Native

## Executive Summary
The project is building an enterprise-grade, Azure-native intelligent assistant that helps users find, synthesize, and act on information across unstructured documents, structured tabular data, and connected enterprise systems.

The core business problem is simple: organizations store critical knowledge in too many places, in too many formats, and with too much manual effort required to use it. Employees waste time searching PDFs, reading long documents, querying CSVs, checking blob storage, and reconciling information across systems. The application is intended to reduce that friction by combining retrieval, reasoning, persistence, and secure access into a single chat-based experience.

## Business Problem
Modern enterprise teams need fast, trustworthy answers from internal knowledge, but the information they need is fragmented across:

- PDFs and reports
- CSV and spreadsheet data
- Blob storage and file shares
- Enterprise systems such as Salesforce, SAP, SharePoint, and ServiceNow
- Session history and user feedback

This creates several recurring business pains:

- Knowledge is hard to find
- Answers are slow to produce
- Manual analysis is repetitive and error-prone
- Context is lost between sessions
- Sensitive information must be handled carefully
- Teams need answers grounded in internal sources, not guesses

The business opportunity is to turn scattered enterprise information into an interactive, secure, conversational system that supports retrieval, analysis, and workflow acceleration.

## Target Users
The application is designed for:

- Business analysts
- Operations teams
- Knowledge workers
- Technical architects
- Support and service teams
- Enterprise users who need grounded answers from company data

## Core Value Proposition
The system aims to:

- Reduce time spent searching for information
- Improve answer quality by grounding responses in enterprise data
- Support both semantic retrieval and structured data analysis
- Preserve conversation context across sessions
- Offer secure, auditable access to data and tools
- Enable scalable ingestion and retrieval across multiple file types and sources

## Project Capabilities

### 1. Conversational Enterprise Assistant
The application provides a chat interface for interacting with enterprise knowledge in a natural language format.

Capabilities include:

- Streaming chat responses
- Session-aware interaction
- Prompt-driven assistant behavior
- Multi-turn conversation support

### 2. Retrieval-Augmented Generation
The system is designed to answer questions using retrieved context rather than relying only on model memory.

Capabilities include:

- Document retrieval over indexed content
- Vector search with Azure AI Search
- Hybrid retrieval patterns where appropriate
- Source-grounded response generation

### 3. Structured Data Analysis
The platform supports tabular reasoning for CSV and spreadsheet-like data.

Capabilities include:

- Pandas-based analysis
- Query engines for structured datasets
- Natural language questions over tables
- Data-centric reasoning for numeric or record-based questions

### 4. Document Ingestion and Indexing
The application can ingest uploaded files and prepare them for retrieval.

Capabilities include:

- Local file upload handling
- File hash-based duplicate detection
- PDF indexing
- Summary generation for uploaded content
- Persistent storage of indexed artifacts

### 5. Persistent Conversation Memory
The system stores and restores chat state so that conversations do not depend only on RAM.

Capabilities include:

- Persistent chat history
- Session-based memory
- Conversation summarization for long threads
- Cloud-backed state management

### 6. Enterprise Security and Identity
The platform is designed for controlled access in enterprise environments.

Capabilities include:

- Azure Active Directory / Entra ID-style authentication patterns
- Azure Key Vault-backed secret management
- Azure credential handling
- Environment-aware configuration

### 7. Multi-Source Connectivity
The architecture is intended to support multiple storage and enterprise systems.

Capabilities include:

- Azure Blob Storage retrieval
- AWS S3 retrieval support
- SharePoint connectors
- Salesforce connectors
- ServiceNow connectors
- SAP connectors

### 8. Background Processing
The system supports asynchronous processing for expensive or long-running operations.

Capabilities include:

- Celery-based task execution
- File indexing in background jobs
- Decoupling of ingestion from user interaction

### 9. Extensibility for Advanced Reasoning
The project also contains architectural hooks for more advanced enterprise AI patterns.

Capabilities include:

- Reranking
- GraphRAG-style reasoning
- Code interpreter sandbox support
- Multi-model orchestration
- Future-ready processing pipeline for richer document workflows

## Business Outcomes
If implemented and stabilized correctly, the system should deliver:

- Faster access to knowledge
- Lower manual research effort
- Better decision support
- Higher confidence in answers
- Reduced duplication of work
- Better handling of enterprise-scale content
- A reusable platform for future AI workflows

## Success Criteria
The project is successful if it can:

- Start reliably in local and cloud environments
- Ingest and retrieve documents without breaking the app
- Answer questions from both unstructured and structured sources
- Preserve user context safely
- Authenticate users and protect secrets
- Run regression tests successfully
- Be deployable as a production-grade web application

## Constraints And Risks

### Constraints
- Must work with Azure-native services
- Must support enterprise security requirements
- Must remain maintainable as features grow
- Must avoid fragile assumptions around package layout and imports

### Risks
- Package structure drift between source code and imports
- Configuration mismatch between documented and actual paths
- Overly broad architecture compared to currently implemented code
- Cloud dependency failures if fallback logic is incomplete
- Regression risk when refactoring ingestion and orchestration layers

## Technology Selection
The project currently centers on the following technologies:

- Chainlit for the chat UI
- LlamaIndex for orchestration and retrieval
- Azure OpenAI for LLM and embeddings
- Azure AI Search for vector and hybrid retrieval
- Azure Cosmos DB for persistent memory and chat state
- Azure Blob Storage for file storage
- Azure Key Vault for secrets
- Azure Identity for authentication and credential flow
- Pandas / PandasQueryEngine for structured data analysis
- Celery for asynchronous background tasks
- E2B for optional sandboxed code execution
- Boto3 and related AWS tooling for cross-cloud support

## Development Approach
Development should proceed in the following order:

1. Stabilize configuration and package imports
2. Verify the runnable entry points
3. Confirm the document ingestion and retrieval pipeline
4. Confirm structured data analysis behavior
5. Add or repair regression tests
6. Harden security and memory handling
7. Improve observability and error handling
8. Prepare production deployment workflows

## Repository Directory Structure
The following structure reflects the actual source tree relevant to this project, excluding virtual environment and generated files.

```text
Agentic-RAG-Chatbot-Azure-Native/
├─ README.md
├─ pyproject.toml
├─ Makefile
├─ app_logger.py
├─ docs/
│  ├─ PLAN.md
│  ├─ architecture.md
│  ├─ architecture.png
│  ├─ cloud_storage_future_features_plan.md
│  ├─ agentic_ai_system_future_features_plan.md
│  ├─ enterprise_setup.md
│  ├─ api_reference.md
│  └─ business_problem_document.md
├─ deployment/
│  └─ docker-compose.yaml
├─ tests/
│  ├─ test_agent_logic.py
│  └─ test_indexer_utils.py
└─ src/
   └─ agentic_rag_chatbot_enterprise_ready/
      ├─ __init__.py
      ├─ main.py
      ├─ old.py
      ├─ doc_digitization.py
      ├─ frontend/
      │  ├─ __init__.py
      │  ├─ app.py
      │  ├─ app_upgraded.py
      │  └─ test_app_regression.py
      ├─ auth/
      │  ├─ __init__.py
      │  ├─ validate_jwt.py
      │  └─ azure_ad_auth_provider.py
      └─ backend/
         ├─ __init__.py
         ├─ server.py
         ├─ tasks.py
         ├─ config/
         │  ├─ __init__.py
         │  ├─ config.py
         │  └─ config.yaml
         ├─ credentials/
         │  ├─ __init__.py
         │  ├─ azure_credential_manager.py
         │  └─ aws_credential_manager.py
         ├─ databases/
         │  ├─ __init__.py
         │  ├─ cosmos_db_date_layer.py
         │  └─ mongo_db_data_layer.py
         ├─ indexer/
         │  ├─ __init__.py
         │  ├─ azure_search_initializer.py
         │  ├─ index_engine.py
         │  ├─ llama_indexer.py
         │  ├─ pdf_indexer.py
         │  └─ user_uploaded_file_indexer.py
         ├─ integrations/
         │  ├─ __init__.py
         │  ├─ salesforce_connector.py
         │  ├─ sap_connector.py
         │  ├─ servicenow_connector.py
         │  └─ sharepoint_connector.py
         ├─ orchestration/
         │  ├─ __init__.py
         │  ├─ agentic_ai_system.py
         │  ├─ code_interpreter.py
         │  ├─ graph_rag.py
         │  ├─ llm_loader.py
         │  ├─ llm_models.py
         │  ├─ pandasai_system.py
         │  ├─ prompts.py
         │  └─ reranker.py
         ├─ process_doc/
         │  ├─ __init__.py
         │  ├─ extractors/
         │  │  ├─ __init__.py
         │  │  ├─ azure_extractor.py
         │  │  ├─ multimodal_extractor.py
         │  │  └─ office_extractor.py
         │  ├─ orchestrator/
         │  │  ├─ __init__.py
         │  │  ├─ pipeline.py
         │  │  ├─ hitl_queue.py
         │  │  └─ hierarchical_indexer.py
         │  └─ processors/
         │     ├─ __init__.py
         │     ├─ classifier.py
         │     ├─ cv_preprocessor.py
         │     ├─ graph_extractor.py
         │     ├─ local_nlp_processor.py
         │     ├─ metadata_extractor.py
         │     └─ pii_redactor.py
         ├─ retrievers/
         │  ├─ __init__.py
         │  ├─ azure_blob_file_retriever.py
         │  └─ s3_blob_file_retriever.py
         └─ utils/
            ├─ UploadFileWrapper.py
            ├─ checksum_file_path.py
            └─ helper.py
```

## Notes
This document intentionally separates the business problem from the implementation details so it can be shared with product, engineering, and stakeholders as a single source of context.

The repository currently contains some upgraded and regression files alongside the main implementation. Those are useful during development, but they should be treated as supporting artifacts rather than the primary product surface.
