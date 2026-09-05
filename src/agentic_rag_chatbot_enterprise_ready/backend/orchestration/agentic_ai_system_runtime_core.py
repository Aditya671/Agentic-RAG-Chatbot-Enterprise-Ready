"""Maintained provider-neutral base runtime for the enterprise agent."""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from backend.ai_models import DEFAULT_REASONING_EFFORT, MODEL_TOKEN_LIMITS, AIModelTypes
from backend.azure_credential_manager import AzureCredentialManager
from backend.config import config
from backend.indexer.azure_search_initializer import initialize_index
from backend.llm_loader import load_embed, load_llm
from backend.orchestration.component_runtime import build_graph_rag, build_reranker
from backend.orchestration.graph_rag import GraphRAGSystem
from backend.orchestration.reranker import initialize_reranker
from backend.orchestration.structured_csv_runtime import build_csv_runtime
from backend.tasks import index_files_task
from backend.user_uploaded_file_indexer import UserUploadedFileIndexer
from backend.utils import parse_response_sources
from celery.result import AsyncResult
from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager, TokenCountingHandler
from llama_index.core.llms import ChatMessage, MessageRole, TextBlock
from llama_index.core.memory import Memory
from llama_index.core.vector_stores.types import VectorStoreQueryMode

from app_logger import setup_logger

logger, log_filename = setup_logger("agentic_chat_engine")


class AsyncAgenticAiSystem:
    """Async enterprise agent base with deterministic structured-data tooling."""

    _LOCAL_ENVIRONMENTS = frozenset({"local", "local_emulator", "development", "dev"})
    _DEFAULT_SESSION_TOKEN_RATIO = 0.7
    _MAX_THREAD_MESSAGES_BEFORE_SUMMARY = 8

    def __init__(
        self,
        selected_model=AIModelTypes.GPT51,
        llm_creativity_level=0.1,
        similarity_top_k=20,
        reasoning_effect="low",
        enable_reranker=True,
        enable_graph_rag=False,
        index_name=None,
        session_id=None,
        upload_root_dir=None,
        conversation_thread=None,
        blob_bytes=None,
    ) -> None:
        self.env = os.getenv("ENVIRONMENT", "local").strip().lower()
        if self.env in self._LOCAL_ENVIRONMENTS:
            load_dotenv(override=True)
        self.selected_model = AIModelTypes(selected_model)
        self.llm_creativity_level = self._validate_temperature(llm_creativity_level)
        self.similarity_top_k = self._validate_top_k(similarity_top_k)
        self.reasoning_effect = self._build_reasoning_config(reasoning_effect)
        self.enable_reranker = bool(enable_reranker)
        self.enable_graph_rag = bool(enable_graph_rag)
        self.index_name = index_name or os.getenv("INDEX_NAME", "aiim")
        self.session_id = session_id or str(uuid.uuid4())
        self.upload_root_dir = upload_root_dir or tempfile.mkdtemp(prefix="agentic_rag_")
        Path(self.upload_root_dir).mkdir(parents=True, exist_ok=True)
        self.blob_bytes = blob_bytes or {"bytes": b"", "metadata": {}}
        self.config = config.indexes.get(self.index_name)
        if self.config is None:
            raise ValueError(f"No index configuration found for '{self.index_name}'")
        self.token_counter = TokenCountingHandler()
        self.callback_manager = CallbackManager([self.token_counter])
        self.credential_manager = AzureCredentialManager(key_vault_url=self.config.key_vault.get("url"))
        self.credential = self._get_shared_credential()
        self.memory = self._new_memory()
        self.conversation_thread: list[dict[str, Any]] = []
        self.set_conversation_thread(conversation_thread or [])
        self.embed = load_embed(index_name=self.index_name, use_azure=True, callback_manager=self.callback_manager)
        if self.embed is None:
            raise ValueError("Failed to load embedding model")
        Settings.embed_model = self.embed
        self.llm = load_llm(
            model=self.selected_model,
            temperature=self.llm_creativity_level,
            index_name=self.index_name,
            use_azure=True,
            additional_kwargs=self.reasoning_effect,
            callback_manager=self.callback_manager,
        )
        if self.llm is None:
            raise ValueError("Failed to load LLM")
        Settings.llm = self.llm
        self.index = self.reinitialize_index()
        if self.index is None:
            raise ValueError("Failed to initialize vector index")
        self.reranker = self.__build_reranker()
        self.graph_rag_system = self.__build_graph_rag_system()
        self.csv_engine = self._build_structured_csv_engine() if self._csv_is_configured() else None
        self.local_file_indexer = UserUploadedFileIndexer(
            root_dir=self.upload_root_dir,
            index_name=self.index_name,
            model=self.selected_model,
            memory=self.memory,
            similarity_top_k=self.similarity_top_k,
        )

    @staticmethod
    def _validate_temperature(value: Any) -> float:
        value = float(value)
        if not 0 <= value <= 2:
            raise ValueError("llm_creativity_level must be between 0 and 2.")
        return value

    @staticmethod
    def _validate_top_k(value: Any) -> int:
        value = int(value)
        if value < 1:
            raise ValueError("similarity_top_k must be >= 1.")
        return value

    def _build_reasoning_config(self, reasoning_effect: Any) -> dict[str, str]:
        requested = str(reasoning_effect or "").strip().lower()
        if self.selected_model == AIModelTypes.GPT51:
            return {"reasoning_effort": "none", "verbosity": "high" if requested == "high" else "low"}
        default_effort = DEFAULT_REASONING_EFFORT.get(self.selected_model)
        return {"reasoning_effort": ("high" if requested == "high" else default_effort) if default_effort else (requested or "low")}

    def _get_shared_credential(self):
        return getattr(self.credential_manager, "credential", None) or DefaultAzureCredential()

    def _new_memory(self):
        return Memory.from_defaults(
            session_id=self.session_id,
            token_limit=MODEL_TOKEN_LIMITS[self.selected_model],
            chat_history_token_ratio=self._DEFAULT_SESSION_TOKEN_RATIO,
        )

    @staticmethod
    def _parse_timestamp(value: Any):
        if not value:
            return None
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            return None
        return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)

    @classmethod
    def _sort_thread(cls, thread):
        dated, undated = [], []
        for position, message in enumerate(thread):
            if not isinstance(message, dict):
                continue
            timestamp = cls._parse_timestamp(message.get("createdAt"))
            item = (timestamp, position, message)
            (dated if timestamp is not None else undated).append(item)
        dated.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in dated] + [item[2] for item in undated]

    @staticmethod
    def _message_role(role):
        role_value = role.value if isinstance(role, MessageRole) else str(role).lower()
        return {"user": MessageRole.USER, "assistant": MessageRole.ASSISTANT, "system": MessageRole.SYSTEM}.get(role_value)

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        if response is None:
            return ""
        if isinstance(response, str):
            return response
        nested = getattr(response, "response", None)
        if nested is not None and nested is not response:
            text = AsyncAgenticAiSystem._extract_response_text(nested)
            if text:
                return text
        for attr in ("text", "response_txt", "content"):
            value = getattr(response, attr, None)
            if value:
                return str(value)
        blocks = getattr(response, "blocks", None)
        if blocks:
            parts = [str(block.text) for block in blocks if getattr(block, "text", None)]
            if parts:
                return "".join(parts)
        return str(response)

    @staticmethod
    def _safe_tool_calls(response):
        calls = getattr(response, "tool_calls", None)
        return list(calls) if calls else []

    def set_memory(self, conversation_thread=None):
        self.memory = self._new_memory()
        for step in conversation_thread or []:
            if not isinstance(step, dict):
                continue
            role = self._message_role(step.get("role"))
            content = step.get("content")
            if role is not None and content is not None:
                self.memory.put(ChatMessage(role=role, blocks=[TextBlock(text=str(content))]))

    def set_conversation_thread(self, thread=None):
        ordered = self._sort_thread(list(thread or []))
        now = datetime.now(UTC)
        cutoff_time = datetime(now.year, now.month, now.day, tzinfo=UTC) - timedelta(days=1)
        dated = [m for m in ordered if self._parse_timestamp(m.get("createdAt"))]
        undated = [m for m in ordered if not self._parse_timestamp(m.get("createdAt"))]
        past = [m for m in dated if self._parse_timestamp(m.get("createdAt")) <= cutoff_time]
        current = [m for m in dated if self._parse_timestamp(m.get("createdAt")) > cutoff_time] + undated
        if past and current:
            normalized = [{"role": "system", "content": self.__summarize_thread(past)}, *current]
        elif len(current) > self._MAX_THREAD_MESSAGES_BEFORE_SUMMARY:
            cutoff = max(1, int(len(current) * 0.6))
            normalized = [{"role": "system", "content": self.__summarize_thread(current[:cutoff])}, *current[cutoff:]]
        else:
            normalized = current or ordered
        self.conversation_thread = normalized
        self.set_memory(normalized)
        return list(normalized)

    def __summarize_thread(self, messages):
        snippets = [f"{str(m.get('role', 'unknown')).capitalize()}: {m.get('content', '')}" for m in messages if m.get("content")]
        if not snippets:
            return "No prior conversation context."
        llm = load_llm(model=AIModelTypes.GPT41_MINI, index_name=self.index_name, use_azure=True, callback_manager=self.callback_manager)
        response = llm.complete("Summarize this conversation without inventing information. Preserve requirements, decisions, constraints, entities, and unresolved questions.\n\n" + "\n".join(snippets))
        return self._extract_response_text(response).strip()

    def reinitialize_index(self):
        search_config = self.config.azure_ai_search
        return initialize_index(
            search_index_name=search_config.get("index_name"),
            llm=self.llm,
            embed_model=self.embed,
            embed_size=self.config.embed.get("size"),
            search_service_endpoint=search_config.get("search_service_endpoint"),
            search_service_credential=self.credential,
            old_index=False,
            aio=True,
            rag_spliter=self.config.rag.get("spliter"),
            rag_chunk_size=self.config.rag.get("chunk_size"),
            rag_chunk_overlap=self.config.rag.get("chunk_overlap"),
        )

    def __build_reranker(self):
        return build_reranker(
            enabled=self.enable_reranker,
            llm=load_llm(model=AIModelTypes.GPT41_MINI, index_name=self.index_name, use_azure=True, callback_manager=self.callback_manager),
            top_n=min(5, self.similarity_top_k),
            initialize=initialize_reranker,
            logger=logger,
        )

    def __build_graph_rag_system(self):
        return build_graph_rag(enabled=self.enable_graph_rag, llm=self.llm, embed_model=self.embed, initialize=GraphRAGSystem, logger=logger)

    def _csv_is_configured(self):
        raw = self.blob_bytes.get("bytes") if isinstance(self.blob_bytes, dict) else None
        return self.index_name == "capitalraising" and isinstance(raw, (bytes, bytearray)) and bool(raw)

    def _build_structured_csv_engine(self):
        return build_csv_runtime(
            csv_bytes=self.blob_bytes["bytes"],
            metadata=self.blob_bytes.get("metadata", {}),
            load_csv_file=self.load_csv_file,
            llm=self.llm,
        )

    def load_csv_file(self, csv_file_bytes_content, metadata=None):
        if not isinstance(csv_file_bytes_content, (bytes, bytearray)) or not csv_file_bytes_content:
            raise ValueError("CSV content must be non-empty bytes.")
        metadata = dict(metadata or {}) if isinstance(metadata, dict) else {}
        errors: list[Exception] = []
        for encoding in ("utf-8-sig", "utf-8", "latin1"):
            try:
                import io

                import pandas as pd
                df = pd.read_csv(io.BytesIO(csv_file_bytes_content), encoding=encoding, low_memory=False)
                if df.empty and len(df.columns) == 0:
                    raise ValueError("CSV contains no columns.")
                normalized = []
                seen: dict[str, int] = {}
                for raw_name in df.columns:
                    name = str(raw_name).strip()
                    if not name:
                        name = "unnamed"
                    count = seen.get(name, 0)
                    seen[name] = count + 1
                    normalized.append(name if count == 0 else f"{name}_{count + 1}")
                df.columns = normalized
                for column in df.columns:
                    lowered = column.casefold().replace("_", "").replace(" ", "")
                    if lowered.endswith("date") or lowered.endswith("datetime") or lowered in {"createdat", "activityat"}:
                        converted = pd.to_datetime(df[column], errors="coerce")
                        if converted.notna().any():
                            df[column] = converted
                return df, metadata
            except Exception as exc:
                errors.append(exc)
        raise ValueError("CSV loading failed for all supported encodings.") from errors[-1]

    def _safe_upload_path(self, filename):
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError("Uploaded file must have a non-empty name.")
        safe_name = Path(filename).name
        root = Path(self.upload_root_dir).resolve()
        target = (root / safe_name).resolve()
        if target.parent != root:
            raise ValueError("Invalid uploaded file path.")
        return target

    def upload_and_index_files_async(self, uploaded_files):
        if not isinstance(uploaded_files, list) or not uploaded_files:
            raise ValueError("uploaded_files must be a non-empty list.")
        file_paths = []
        for file_data in uploaded_files:
            if not isinstance(file_data, dict):
                raise TypeError("Each uploaded file must be a dictionary.")
            content = file_data.get("content")
            if not isinstance(content, (bytes, bytearray)):
                raise TypeError(f"File '{file_data.get('name', '<unknown>')}' has invalid content.")
            path = self._safe_upload_path(file_data.get("name", ""))
            path.write_bytes(content)
            file_paths.append({"name": path.name, "path": str(path)})
        task = index_files_task.delay(
            file_list=file_paths,
            root_dir=self.upload_root_dir,
            index_name=self.index_name,
            model=self.selected_model.value,
            similarity_top_k=self.similarity_top_k,
        )
        task_id = getattr(task, "id", None)
        if not task_id:
            raise RuntimeError("Indexing task did not return a task ID.")
        return "File indexing has been started in the background. Your Task ID is: " + task_id + ". Use the 'check_indexing_status' tool to check progress."

    def check_indexing_status(self, task_id):
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string.")
        task_result = AsyncResult(task_id)
        if not task_result.ready():
            return f"Task {task_id} is still in progress. Status: {task_result.state}"
        if task_result.successful():
            return f"Task {task_id} completed successfully. Result: {task_result.get()}"
        return f"Task {task_id} failed. Error: {task_result.info}"

    def query_local_file_index(self, query):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string.")
        response = self.local_file_indexer.create_local_citation_chat_engine().chat(query)
        return self._extract_response_text(response)

    def bing_grounding_tool(self, query):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string.")
        endpoint = self.config.ai_service.get("endpoint")
        agent_id = self.config.ai_service.get("agent_id")
        if not endpoint or not agent_id:
            raise ValueError("Azure AI Project endpoint and agent_id are required for web search.")
        client = AIProjectClient(endpoint=endpoint, credential=self.credential)
        try:
            azure_agent = client.agents.get_agent(agent_id=agent_id)
            thread = client.agents.threads.create()
            client.agents.messages.create(thread_id=thread.id, role="user", content=query)
            run = client.agents.runs.create_and_process(thread_id=thread.id, agent_id=azure_agent.id)
            if getattr(run, "status", None) == "failed":
                raise RuntimeError("Azure AI web-search agent run failed.")
            messages = client.agents.messages.list(thread_id=thread.id)
            return next((message for message in messages if str(getattr(message, "role", "")).lower() == "assistant"), next(iter(messages), None))
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()

    def build_provider_retriever(self, index=None, **kwargs):
        target = self.index if index is None else index
        from backend.orchestration.provider_boundaries import build_retriever
        retrieval = getattr(self, "runtime_boundary", None)
        if retrieval is not None:
            return build_retriever(target, retrieval.retrieval, **kwargs)
        return target.as_retriever(
            vector_store_query_mode=VectorStoreQueryMode.SEMANTIC_HYBRID,
            similarity_top_k=self.similarity_top_k,
            **kwargs,
        )

    def get_retriever_metadata(self, response_block):
        for tool_call in self._safe_tool_calls(response_block):
            if getattr(tool_call, "tool_name", None) != "im_retriever_tool":
                continue
            raw_output = getattr(getattr(tool_call, "tool_output", None), "raw_output", None)
            if raw_output is None:
                continue
            try:
                parsed = parse_response_sources(response_sources=raw_output)
                return json.loads(parsed) if isinstance(parsed, str) else parsed
            except (TypeError, ValueError, json.JSONDecodeError):
                logger.warning("Unable to parse retriever metadata")
        return []

    async def run_agent_async(self, question):
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string.")
        return await self.agent.run(user_msg=question, memory=self.memory)

    async def run_agent(self, question):
        return await self.run_agent_async(question)

    async def stream_response(self, response) -> AsyncGenerator[str, None]:
        response_gen = getattr(response, "response_gen", None)
        if response_gen is not None:
            if hasattr(response_gen, "__aiter__"):
                async for chunk in response_gen:
                    if chunk:
                        yield str(chunk)
            else:
                for chunk in response_gen:
                    if chunk:
                        yield str(chunk)
            return
        text = self._extract_response_text(response)
        if text:
            yield text

    async def collect_async_generator_result(self, gen):
        result = []
        async for chunk in gen:
            result.append(str(chunk))
        return "".join(result)

    def get_token_counts(self):
        model_limit = MODEL_TOKEN_LIMITS[self.selected_model]
        prompt = self.token_counter.prompt_llm_token_count
        completion = self.token_counter.completion_llm_token_count
        total = self.token_counter.total_llm_token_count
        return {"Model": self.selected_model, "ModelLimit": model_limit, "PromptTokens": prompt, "PromptTokensExhausted": (prompt / model_limit) * 100, "CompletionTokens": completion, "CompletionTokensExhausted": (completion / model_limit) * 100, "TotalTokens": total, "TotalTokensExhausted": (total / model_limit) * 100}

    def close(self):
        close = getattr(self.credential_manager, "close", None)
        if callable(close):
            close()

    def set_selected_model(self, selected_model):
        self.selected_model = AIModelTypes(selected_model)
        self.reasoning_effect = self._build_reasoning_config(self.reasoning_effect.get("reasoning_effort", "low"))
        self.llm = load_llm(model=self.selected_model, temperature=self.llm_creativity_level, index_name=self.index_name, use_azure=True, additional_kwargs=self.reasoning_effect, callback_manager=self.callback_manager)
        Settings.llm = self.llm
        self.set_memory(self.conversation_thread)
        self.index = self.reinitialize_index()

    def set_embed_model(self):
        self.embed = load_embed(index_name=self.index_name, use_azure=True, callback_manager=self.callback_manager)
        Settings.embed_model = self.embed
        self.index = self.reinitialize_index()

    def set_llm_creativity_level(self, value):
        self.llm_creativity_level = self._validate_temperature(value)
        self.llm = load_llm(model=self.selected_model, temperature=self.llm_creativity_level, index_name=self.index_name, use_azure=True, additional_kwargs=self.reasoning_effect, callback_manager=self.callback_manager)
        Settings.llm = self.llm
        self.index = self.reinitialize_index()

    def set_similarity_top_k(self, value):
        self.similarity_top_k = self._validate_top_k(value)
        self.local_file_indexer = UserUploadedFileIndexer(root_dir=self.upload_root_dir, index_name=self.index_name, model=self.selected_model, memory=self.memory, similarity_top_k=self.similarity_top_k)
        self.index = self.reinitialize_index()

    def set_reasoning_effect(self, value):
        self.reasoning_effect = self._build_reasoning_config(value)
        self.llm = load_llm(model=self.selected_model, temperature=self.llm_creativity_level, index_name=self.index_name, use_azure=True, additional_kwargs=self.reasoning_effect, callback_manager=self.callback_manager)
        Settings.llm = self.llm
        self.index = self.reinitialize_index()

    def set_index_name(self, index_name):
        if not index_name or not str(index_name).strip():
            raise ValueError("index_name must not be empty.")
        new_config = config.indexes.get(index_name)
        if new_config is None:
            raise ValueError(f"No index configuration found for '{index_name}'")
        self.index_name = index_name
        self.config = new_config
        self.credential_manager = AzureCredentialManager(key_vault_url=self.config.key_vault.get("url"))
        self.credential = self._get_shared_credential()
        self.embed = load_embed(index_name=self.index_name, use_azure=True, callback_manager=self.callback_manager)
        Settings.embed_model = self.embed
        self.llm = load_llm(model=self.selected_model, temperature=self.llm_creativity_level, index_name=self.index_name, use_azure=True, additional_kwargs=self.reasoning_effect, callback_manager=self.callback_manager)
        Settings.llm = self.llm
        self.index = self.reinitialize_index()
        self.csv_engine = self._build_structured_csv_engine() if self._csv_is_configured() else None

    def set_reranker(self, enable_reranker=False):
        self.enable_reranker = bool(enable_reranker)
        self.reranker = self.__build_reranker()

    def set_graph_rag(self, enable_graph_rag=False):
        self.enable_graph_rag = bool(enable_graph_rag)
        self.graph_rag_system = self.__build_graph_rag_system()

    @staticmethod
    async def guardrail_check(user_input):
        if not isinstance(user_input, str):
            return False
        return not any(word in user_input.casefold() for word in ("password", "secret_key", "internal_url"))

    @staticmethod
    async def self_correction_loop(llm, response, context):
        prompt = "Evaluate whether the answer is fully supported by the supplied context. Reply with exactly YES or NO.\n\nANSWER:\n" + response + "\n\nCONTEXT:\n" + context
        verdict = await llm.acomplete(prompt)
        return getattr(verdict, "text", str(verdict)).strip().upper() == "YES"
