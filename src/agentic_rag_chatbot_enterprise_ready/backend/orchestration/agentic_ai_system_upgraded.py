from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv

from app_logger import setup_logger
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from celery.result import AsyncResult

from llama_index.core import Document, Settings
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.core.callbacks import CallbackManager, TokenCountingHandler
from llama_index.core.llms import ChatMessage, MessageRole, TextBlock
from llama_index.core.memory import Memory
from llama_index.core.prompts import PromptTemplate
from llama_index.core.tools import FunctionTool, RetrieverTool, ToolMetadata
from llama_index.core.vector_stores.types import VectorStoreQueryMode
from llama_index.experimental.query_engine.pandas import PandasQueryEngine

from backend.ai_models import (
    AIModelTypes,
    DEFAULT_REASONING_EFFORT,
    MODEL_TOKEN_LIMITS,
)
from backend.azure_credential_manager import AzureCredentialManager
from backend.config import config
from backend.indexer.azure_search_initializer import initialize_index
from backend.llm_loader import load_embed, load_llm
from backend.orchestration.code_interpreter import CodeInterpreterSandbox
from backend.orchestration.graph_rag import GraphRAGSystem
from backend.orchestration.reranker import initialize_reranker
from backend.prompts import (
    AGENTIC_AI_CODEX_PROMPT,
    AGENTIC_AI_SYSTEM_PROMPT,
    AGENTIC_PANDAS_QUERY_ENGINE_INSTRUCTION_PROMPT,
    AGENTIC_PANDAS_QUERY_ENGINE_PANDAS_PROMPT,
    AGENTIC_PANDAS_QUERY_ENGINE_RESPONSE_SYNTHESIS_PROMPT,
)
from backend.tasks import index_files_task
from backend.user_uploaded_file_indexer import UserUploadedFileIndexer
from backend.utils import parse_response_sources


logger, log_filename = setup_logger("agentic_chat_engine")


class AsyncAgenticAiSystem:
    """Async agentic RAG engine for structured and unstructured enterprise data.

    This is a compatibility-oriented upgrade of the original engine. Public
    method names are retained while fixing mutable defaults, async misuse,
    conversation ordering/summarization, credential duplication, unsafe file
    paths, CSV initialization failures, and fragile response parsing.
    """

    _LOCAL_ENVIRONMENTS = frozenset({"local", "local_emulator", "development", "dev"})
    _DEFAULT_SESSION_TOKEN_RATIO = 0.7
    _MAX_THREAD_MESSAGES_BEFORE_SUMMARY = 8
    _DEFAULT_SUMMARY_KEEP_MESSAGES = 40

    def __init__(
        self,
        selected_model: AIModelTypes = AIModelTypes.GPT51,
        llm_creativity_level: float = 0.1,
        similarity_top_k: int = 20,
        reasoning_effect: str = "low",
        enable_reranker: bool = True,
        enable_graph_rag: bool = False,
        index_name: Optional[str] = None,
        session_id: Optional[str] = None,
        upload_root_dir: Optional[str] = None,
        conversation_thread: Optional[List[Dict[str, Any]]] = None,
        blob_bytes: Optional[Dict[str, Any]] = None,
        enable_coding_assistant: bool = False,
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
        self.enable_coding_assistant = bool(enable_coding_assistant)

        self.index_name = index_name or os.getenv("INDEX_NAME", "aiim")
        self.session_id = session_id or str(uuid.uuid4())
        self.upload_root_dir = upload_root_dir or tempfile.mkdtemp(prefix="llama_index_")
        Path(self.upload_root_dir).mkdir(parents=True, exist_ok=True)

        self.blob_bytes = blob_bytes or {
            "bytes": b"",
            "metadata": {},
        }

        self.config = config.indexes.get(self.index_name)
        if self.config is None:
            raise ValueError(f"No index configuration found for '{self.index_name}'")

        logger.info(
            "[AgenticAi] Initializing index '%s' for session %s",
            self.index_name,
            self.session_id,
        )

        self.token_counter = TokenCountingHandler()
        self.callback_manager = CallbackManager([self.token_counter])

        self.credential_manager = AzureCredentialManager(
            key_vault_url=self.config.key_vault.get("url")
        )
        self.credential = self._get_shared_credential()

        self.memory = self._new_memory()
        self.conversation_thread: List[Dict[str, Any]] = []
        self.set_conversation_thread(conversation_thread or [])

        self.embed = load_embed(
            index_name=self.index_name,
            use_azure=True,
            callback_manager=self.callback_manager,
        )
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
        self.code_interpreter = self.__build_code_interpreter()

        # CSV is optional. The old implementation built it for every index,
        # causing empty/default blob payloads to fail application startup.
        self.csv_engine = self.__build_csv_engine() if self._csv_is_configured() else None

        self.local_file_indexer = UserUploadedFileIndexer(
            root_dir=self.upload_root_dir,
            index_name=self.index_name,
            model=self.selected_model,
            memory=self.memory,
            similarity_top_k=self.similarity_top_k,
        )

        self.agent = self.__build_agent()

    # ------------------------------------------------------------------
    # Validation / internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_temperature(value: float) -> float:
        value = float(value)
        if not 0 <= value <= 2:
            raise ValueError("llm_creativity_level must be between 0 and 2.")
        return value

    @staticmethod
    def _validate_top_k(value: int) -> int:
        value = int(value)
        if value < 1:
            raise ValueError("similarity_top_k must be >= 1.")
        return value

    def _build_reasoning_config(self, reasoning_effect: Optional[str]) -> Dict[str, Any]:
        requested = (reasoning_effect or "").strip().lower()

        if self.selected_model == AIModelTypes.GPT51:
            # GPT-5.1 reasoning is explicitly disabled by default in this
            # application; verbosity is controlled separately.
            return {
                "reasoning_effort": "none",
                "verbosity": "high" if requested == "high" else "low",
            }

        default_effort = DEFAULT_REASONING_EFFORT.get(self.selected_model)
        if default_effort:
            effort = "high" if requested == "high" else default_effort
        else:
            effort = requested or "low"

        return {"reasoning_effort": effort}

    def _get_shared_credential(self):
        """Reuse the credential owned by AzureCredentialManager when possible."""
        credential = getattr(self.credential_manager, "credential", None)
        return credential or DefaultAzureCredential()

    def _new_memory(self) -> Memory:
        return Memory.from_defaults(
            session_id=self.session_id,
            token_limit=MODEL_TOKEN_LIMITS[self.selected_model],
            chat_history_token_ratio=self._DEFAULT_SESSION_TOKEN_RATIO,
        )

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str):
            try:
                normalized = value.strip().replace("Z", "+00:00")
                dt = datetime.fromisoformat(normalized)
            except ValueError:
                return None
        else:
            return None

        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @classmethod
    def _sort_thread(cls, thread: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return a new chronological list without mutating caller-owned data."""
        with_timestamp = []
        without_timestamp = []

        for position, message in enumerate(thread):
            if not isinstance(message, dict):
                continue
            timestamp = cls._parse_timestamp(message.get("createdAt"))
            item = (timestamp, position, message)
            if timestamp is None:
                without_timestamp.append(item)
            else:
                with_timestamp.append(item)

        with_timestamp.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in with_timestamp] + [item[2] for item in without_timestamp]

    @staticmethod
    def _message_role(role: Any) -> Optional[MessageRole]:
        role_value = role.value if isinstance(role, MessageRole) else str(role).lower()
        mapping = {
            "user": MessageRole.USER,
            "assistant": MessageRole.ASSISTANT,
            "system": MessageRole.SYSTEM,
        }
        return mapping.get(role_value)

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        """Normalize LlamaIndex agent outputs across response representations."""
        if response is None:
            return ""

        if isinstance(response, str):
            return response

        # Agent/workflow outputs commonly expose a response object.
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
            parts = []
            for block in blocks:
                text = getattr(block, "text", None)
                if text:
                    parts.append(str(text))
            if parts:
                return "".join(parts)

        return str(response)

    @staticmethod
    def _safe_tool_calls(response: Any) -> list:
        calls = getattr(response, "tool_calls", None)
        return list(calls) if calls else []

    def _csv_is_configured(self) -> bool:
        if self.index_name != "capitalraising":
            return False
        raw = self.blob_bytes.get("bytes") if isinstance(self.blob_bytes, dict) else None
        return isinstance(raw, (bytes, bytearray)) and bool(raw)

    def _safe_upload_path(self, filename: str) -> Path:
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError("Uploaded file must have a non-empty name.")

        # Never trust client-controlled path components.
        safe_name = Path(filename).name
        if safe_name in {"", ".", ".."}:
            raise ValueError("Invalid uploaded file name.")

        root = Path(self.upload_root_dir).resolve()
        target = (root / safe_name).resolve()
        if target.parent != root:
            raise ValueError("Invalid uploaded file path.")

        return target

    # ------------------------------------------------------------------
    # Session / configuration setters
    # ------------------------------------------------------------------

    def set_memory(self, conversation_thread: Optional[List[Dict[str, Any]]] = None) -> None:
        """Rebuild memory from a supplied thread without duplicating messages."""
        messages = conversation_thread or []
        self.memory = self._new_memory()

        for step in messages:
            role = self._message_role(step.get("role"))
            content = step.get("content")
            if role is None or content is None:
                continue

            self.memory.put(
                ChatMessage(
                    role=role,
                    blocks=[TextBlock(text=str(content))],
                )
            )

    def set_conversation_thread(
        self,
        thread: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Normalize, summarize, and load conversation history chronologically."""
        source_thread = list(thread or [])
        ordered = self._sort_thread(source_thread)

        now = datetime.now(timezone.utc)
        start_of_yesterday = datetime(
            now.year,
            now.month,
            now.day,
            tzinfo=timezone.utc,
        ) - timedelta(days=1)

        dated = [
            message for message in ordered if self._parse_timestamp(message.get("createdAt"))
        ]
        undated = [
            message for message in ordered if not self._parse_timestamp(message.get("createdAt"))
        ]

        past = [
            message
            for message in dated
            if self._parse_timestamp(message.get("createdAt")) <= start_of_yesterday
        ]
        current = [
            message
            for message in dated
            if self._parse_timestamp(message.get("createdAt")) > start_of_yesterday
        ]

        # Preserve undated messages rather than silently dropping them.
        current.extend(undated)

        if past and current:
            summary = self.__summarize_thread(past)
            normalized = [
                {"role": "system", "content": summary},
                *current,
            ]
        elif not past and len(current) > self._MAX_THREAD_MESSAGES_BEFORE_SUMMARY:
            cutoff = max(1, int(len(current) * 0.6))
            summary = self.__summarize_thread(current[:cutoff])
            normalized = [
                {"role": "system", "content": summary},
                *current[cutoff:],
            ]
        else:
            normalized = current or ordered

        self.conversation_thread = normalized
        self.set_memory(normalized)
        return list(normalized)

    def set_selected_model(self, selected_model: AIModelTypes) -> None:
        self.selected_model = AIModelTypes(selected_model)
        self.reasoning_effect = self._build_reasoning_config(
            self.reasoning_effect.get("reasoning_effort", "low")
        )

        logger.info("[AgenticAi] LLM model changed to %s", self.selected_model)

        self.llm = load_llm(
            model=self.selected_model,
            temperature=self.llm_creativity_level,
            index_name=self.index_name,
            use_azure=True,
            additional_kwargs=self.reasoning_effect,
            callback_manager=self.callback_manager,
        )
        Settings.llm = self.llm

        # Rebuild memory because token capacity is model-specific.
        self.set_memory(self.conversation_thread)
        self.local_file_indexer = UserUploadedFileIndexer(
            root_dir=self.upload_root_dir,
            index_name=self.index_name,
            model=self.selected_model,
            memory=self.memory,
            similarity_top_k=self.similarity_top_k,
        )
        self.index = self.reinitialize_index()
        self.agent = self.__build_agent()

    def set_embed_model(self) -> None:
        logger.info("[AgenticAi] Reloading embedding model for index %s", self.index_name)
        self.embed = load_embed(
            index_name=self.index_name,
            use_azure=True,
            callback_manager=self.callback_manager,
        )
        Settings.embed_model = self.embed
        self.index = self.reinitialize_index()
        self.agent = self.__build_agent()

    def set_llm_creativity_level(self, llm_creativity_level: float) -> None:
        self.llm_creativity_level = self._validate_temperature(llm_creativity_level)
        logger.info("[AgenticAi] Creativity level changed to %s", self.llm_creativity_level)

        self.llm = load_llm(
            model=self.selected_model,
            temperature=self.llm_creativity_level,
            index_name=self.index_name,
            use_azure=True,
            additional_kwargs=self.reasoning_effect,
            callback_manager=self.callback_manager,
        )
        Settings.llm = self.llm
        self.index = self.reinitialize_index()
        self.agent = self.__build_agent()

    def set_similarity_top_k(self, similarity_top_k: int) -> None:
        self.similarity_top_k = self._validate_top_k(similarity_top_k)
        logger.info("[AgenticAi] Top-k changed to %s", self.similarity_top_k)

        self.local_file_indexer = UserUploadedFileIndexer(
            root_dir=self.upload_root_dir,
            index_name=self.index_name,
            model=self.selected_model,
            memory=self.memory,
            similarity_top_k=self.similarity_top_k,
        )
        self.index = self.reinitialize_index()
        self.reranker = self.__build_reranker()
        self.agent = self.__build_agent()

    def set_reasoning_effect(self, reasoning_effect: str) -> None:
        self.reasoning_effect = self._build_reasoning_config(reasoning_effect)
        logger.info("[AgenticAi] Reasoning configuration changed")

        self.llm = load_llm(
            model=self.selected_model,
            temperature=self.llm_creativity_level,
            index_name=self.index_name,
            use_azure=True,
            additional_kwargs=self.reasoning_effect,
            callback_manager=self.callback_manager,
        )
        Settings.llm = self.llm
        self.index = self.reinitialize_index()
        self.agent = self.__build_agent()

    def set_index_name(self, index_name: str) -> None:
        if not index_name or not str(index_name).strip():
            raise ValueError("index_name must not be empty.")

        new_config = config.indexes.get(index_name)
        if new_config is None:
            raise ValueError(f"No index configuration found for '{index_name}'")

        logger.info("[AgenticAi] Index changed from %s to %s", self.index_name, index_name)
        self.index_name = index_name
        self.config = new_config

        self.credential_manager = AzureCredentialManager(
            key_vault_url=self.config.key_vault.get("url")
        )
        self.credential = self._get_shared_credential()

        self.embed = load_embed(
            index_name=self.index_name,
            use_azure=True,
            callback_manager=self.callback_manager,
        )
        Settings.embed_model = self.embed

        self.llm = load_llm(
            model=self.selected_model,
            temperature=self.llm_creativity_level,
            index_name=self.index_name,
            use_azure=True,
            additional_kwargs=self.reasoning_effect,
            callback_manager=self.callback_manager,
        )
        Settings.llm = self.llm

        self.index = self.reinitialize_index()
        self.reranker = self.__build_reranker()
        self.csv_engine = self.__build_csv_engine() if self._csv_is_configured() else None
        self.local_file_indexer = UserUploadedFileIndexer(
            root_dir=self.upload_root_dir,
            index_name=self.index_name,
            model=self.selected_model,
            memory=self.memory,
            similarity_top_k=self.similarity_top_k,
        )
        self.agent = self.__build_agent()

    def set_reranker(self, enable_reranker: bool = False) -> None:
        self.enable_reranker = bool(enable_reranker)
        self.reranker = self.__build_reranker()
        self.agent = self.__build_agent()

    def set_graph_rag(self, enable_graph_rag: bool = False) -> None:
        self.enable_graph_rag = bool(enable_graph_rag)
        self.graph_rag_system = self.__build_graph_rag_system()
        self.agent = self.__build_agent()

    def set_coding_assistant(self, enable_coding_assistant: bool = False) -> None:
        self.enable_coding_assistant = bool(enable_coding_assistant)
        self.code_interpreter = self.__build_code_interpreter()
        self.agent = self.__build_agent()

    # ------------------------------------------------------------------
    # Safety / validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def guardrail_check(user_input: str) -> bool:
        """Return True when the input passes the lightweight local guardrail."""
        if not isinstance(user_input, str):
            return False

        prohibited = ("password", "secret_key", "internal_url")
        normalized = user_input.casefold()
        return not any(word in normalized for word in prohibited)

    @staticmethod
    async def self_correction_loop(llm, response: str, context: str) -> bool:
        """Ask the LLM for a strict YES/NO grounding verdict."""
        verification_prompt = (
            "Evaluate whether the answer is fully supported by the supplied context.\n"
            "Reply with exactly YES or NO.\n\n"
            f"ANSWER:\n{response}\n\nCONTEXT:\n{context}"
        )
        verdict = await llm.acomplete(verification_prompt)
        verdict_text = getattr(verdict, "text", str(verdict)).strip().upper()
        return verdict_text == "YES"

    # ------------------------------------------------------------------
    # Conversation utilities
    # ------------------------------------------------------------------

    def generate_thread_title(self) -> str:
        first_question = ""
        first_answer = ""

        for message in self.memory.get_all():
            role = getattr(message, "role", None)
            content = getattr(message, "content", "") or ""

            if role == MessageRole.USER and not first_question:
                first_question = content
            elif role == MessageRole.ASSISTANT and not first_answer:
                first_answer = content

            if first_question and first_answer:
                break

        conversation_text = (
            f"User: {first_question}\nAssistant: {first_answer}"
        )

        title_response = load_llm(
            model=AIModelTypes.GPT41_MINI,
            index_name=self.index_name,
            use_azure=True,
            callback_manager=self.callback_manager,
        ).complete(
            "Give me a short descriptive title based on this conversation. "
            "Maximum 8 words; do not use generic words such as Conversation, "
            "Overview, or Request.\n\n" + conversation_text
        )
        return self._extract_response_text(title_response).strip()

    def __summarize_thread(
        self,
        messages: Optional[List[Dict[str, Any]]] = None,
        start_idx: int = 0,
        end_idx: Optional[int] = None,
    ) -> str:
        messages = messages or []
        if end_idx is None:
            end_idx = len(messages)

        snippets = []
        for msg in messages[start_idx:end_idx]:
            role = str(msg.get("role", "unknown")).capitalize()
            content = str(msg.get("content", ""))
            if content:
                snippets.append(f"{role}: {content}")

        if not snippets:
            return "No prior conversation context."

        summary_prompt = (
            "Summarize the following conversation while preserving important "
            "requirements, decisions, constraints, entities, and unresolved "
            "questions. Do not invent information.\n\n"
            + "\n".join(snippets)
        )

        summary = load_llm(
            model=AIModelTypes.GPT41_MINI,
            index_name=self.index_name,
            use_azure=True,
            callback_manager=self.callback_manager,
        ).complete(summary_prompt)

        return self._extract_response_text(summary).strip()

    def get_token_counts(self) -> Dict[str, Any]:
        model_limit = MODEL_TOKEN_LIMITS[self.selected_model]
        prompt = self.token_counter.prompt_llm_token_count
        completion = self.token_counter.completion_llm_token_count
        total = self.token_counter.total_llm_token_count

        return {
            "Model": self.selected_model,
            "ModelLimit": model_limit,
            "PromptTokens": prompt,
            "PromptTokensExhausted": (prompt / model_limit) * 100,
            "CompletionTokens": completion,
            "CompletionTokensExhausted": (completion / model_limit) * 100,
            "TotalTokens": total,
            "TotalTokensExhausted": (total / model_limit) * 100,
        }

    # ------------------------------------------------------------------
    # Index / component builders
    # ------------------------------------------------------------------

    def reinitialize_index(self):
        search_config = self.config.azure_ai_search
        logger.info(
            "[AgenticAi] Initializing search index '%s' for profile '%s'",
            search_config.get("index_name"),
            self.index_name,
        )

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
        if not self.enable_reranker:
            return None

        try:
            rerank_llm = load_llm(
                model=AIModelTypes.GPT41_MINI,
                index_name=self.index_name,
                use_azure=True,
                callback_manager=self.callback_manager,
            )
            top_n = min(5, self.similarity_top_k)
            return initialize_reranker(llm=rerank_llm, top_n=top_n)
        except Exception:
            logger.exception("[AgenticAi] Reranker initialization failed; disabling it")
            return None

    def __build_graph_rag_system(self):
        if not self.enable_graph_rag:
            return None

        try:
            logger.info("[AgenticAi] Initializing GraphRAG system")
            return GraphRAGSystem(llm=self.llm, embed_model=self.embed)
        except Exception:
            logger.exception("[AgenticAi] GraphRAG initialization failed; disabling it")
            return None

    def __build_code_interpreter(self):
        if not self.enable_coding_assistant:
            return None

        try:
            logger.info("[AgenticAi] Initializing code interpreter sandbox")
            return CodeInterpreterSandbox()
        except Exception:
            logger.exception("[AgenticAi] Code interpreter initialization failed")
            return None

    def __dummy_function(self, *args, **kwargs):
        return {
            "status": "bypassed",
            "message": "Tool is unavailable.",
        }

    def __build_function_tool(
        self,
        fn,
        name: str,
        description: str,
    ) -> FunctionTool:
        if not callable(fn):
            raise TypeError(f"Tool '{name}' function must be callable.")

        return FunctionTool.from_defaults(
            fn=fn,
            name=name,
            description=description,
        )

    def __build_retriever_tool(
        self,
        retriever,
        name: str,
        description: str,
    ) -> RetrieverTool:
        if retriever is None:
            raise ValueError(f"Retriever for tool '{name}' cannot be None.")

        return RetrieverTool(
            retriever=retriever,
            metadata=ToolMetadata(
                name=name,
                description=description,
            ),
        )

    def __build_csv_engine(self) -> Optional[PandasQueryEngine]:
        if not self._csv_is_configured():
            return None

        df, meta = self.load_csv_file(
            self.blob_bytes["bytes"],
            self.blob_bytes.get("metadata", {}),
        )

        column_info = (
            f"Columns ({len(df.columns)} total): {', '.join(df.columns.tolist())}\n"
            f"Data types: {dict(df.dtypes)}\n"
            f"DataFrame shape: {df.shape[0]} rows, {df.shape[1]} columns"
        )

        df_info = f"{df.head(5).to_string()}\n{column_info}"
        metadata_str = (
            json.dumps(meta, default=str)
            if isinstance(meta, dict)
            else str(meta)
        )

        pandas_prompt = PromptTemplate(
            template=AGENTIC_PANDAS_QUERY_ENGINE_PANDAS_PROMPT,
            metadata=meta if isinstance(meta, dict) else {},
        ).partial_format(
            df_str=df.head(5).to_string(),
            metadata_str=metadata_str,
            column_info=column_info,
            instruction_str=AGENTIC_PANDAS_QUERY_ENGINE_INSTRUCTION_PROMPT.format(
                df_info=df_info,
                metadata_str=metadata_str,
            ),
        )

        response_prompt = PromptTemplate(
            AGENTIC_PANDAS_QUERY_ENGINE_RESPONSE_SYNTHESIS_PROMPT
        )

        return PandasQueryEngine(
            df=df,
            instruction_str=AGENTIC_PANDAS_QUERY_ENGINE_INSTRUCTION_PROMPT.format(
                df_info=df_info,
                metadata_str=metadata_str,
            ),
            pandas_prompt=pandas_prompt,
            response_synthesis_prompt=response_prompt,
            llm=self.llm,
        )

    def load_csv_file(
        self,
        csv_file_bytes_content: bytes,
        metadata: Any = None,
    ):
        if not isinstance(csv_file_bytes_content, (bytes, bytearray)) or not csv_file_bytes_content:
            raise ValueError("CSV content must be non-empty bytes.")

        metadata = {} if metadata is None else metadata

        try:
            # Read without parse_dates first so missing date columns do not
            # cause an otherwise valid CSV to fail.
            df = pd.read_csv(
                BytesIO(csv_file_bytes_content),
                encoding="latin1",
                low_memory=False,
            )

            for date_column in ("createddate", "activitydate"):
                if date_column in df.columns:
                    df[date_column] = pd.to_datetime(
                        df[date_column],
                        errors="coerce",
                    )

            logger.info(
                "[AgenticAi] CSV loaded: rows=%s columns=%s",
                df.shape[0],
                df.shape[1],
            )
            return df, metadata
        except Exception:
            logger.exception("[AgenticAi] CSV loading failed")
            raise

    # ------------------------------------------------------------------
    # File indexing / external tools
    # ------------------------------------------------------------------

    def query_local_file_index(self, query: str) -> str:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string.")

        try:
            chat_engine = self.local_file_indexer.create_local_citation_chat_engine()
            response = chat_engine.chat(query)
            return self._extract_response_text(response)
        except Exception:
            logger.exception("[AgenticAi] User-file query failed")
            raise

    def upload_and_index_files_async(self, uploaded_files: List[Dict[str, Any]]) -> str:
        if not isinstance(uploaded_files, list) or not uploaded_files:
            raise ValueError("uploaded_files must be a non-empty list.")

        file_paths_for_task = []
        try:
            for file_data in uploaded_files:
                if not isinstance(file_data, dict):
                    raise TypeError("Each uploaded file must be a dictionary.")

                content = file_data.get("content")
                if not isinstance(content, (bytes, bytearray)):
                    raise TypeError(
                        f"File '{file_data.get('name', '<unknown>')}' has invalid content."
                    )

                path = self._safe_upload_path(file_data.get("name", ""))
                path.write_bytes(content)
                file_paths_for_task.append(
                    {
                        "name": path.name,
                        "path": str(path),
                    }
                )

            task = index_files_task.delay(
                file_list=file_paths_for_task,
                root_dir=self.upload_root_dir,
                index_name=self.index_name,
                model=self.selected_model.value,
                similarity_top_k=self.similarity_top_k,
            )
            task_id = getattr(task, "id", None)
            if not task_id:
                raise RuntimeError("Indexing task did not return a task ID.")

            logger.info("[AgenticAi] File indexing task started: %s", task_id)
            return (
                "File indexing has been started in the background. "
                f"Your Task ID is: {task_id}. "
                "Use the 'check_indexing_status' tool to check progress."
            )
        except Exception:
            logger.exception("[AgenticAi] Failed to start file indexing task")
            raise

    def check_indexing_status(self, task_id: str) -> str:
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string.")

        try:
            task_result = AsyncResult(task_id)
            if not task_result.ready():
                return (
                    f"Task {task_id} is still in progress. "
                    f"Status: {task_result.state}"
                )

            if task_result.successful():
                return (
                    f"Task {task_id} completed successfully. "
                    f"Result: {task_result.get()}"
                )

            return f"Task {task_id} failed. Error: {task_result.info}"
        except Exception:
            logger.exception("[AgenticAi] Failed to check task status")
            raise

    def bing_grounding_tool(self, query: str) -> Any:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string.")

        project_endpoint = self.config.ai_service.get("endpoint")
        agent_id = self.config.ai_service.get("agent_id")

        if not project_endpoint or not agent_id:
            raise ValueError(
                "Azure AI Project endpoint and agent_id are required for web search."
            )

        client = AIProjectClient(
            endpoint=project_endpoint,
            credential=self.credential,
        )

        try:
            azure_agent = client.agents.get_agent(agent_id=agent_id)
            thread = client.agents.threads.create()
            client.agents.messages.create(
                thread_id=thread.id,
                role="user",
                content=query,
            )
            run = client.agents.runs.create_and_process(
                thread_id=thread.id,
                agent_id=azure_agent.id,
            )

            if getattr(run, "status", None) == "failed":
                raise RuntimeError("Azure AI web-search agent run failed.")

            messages = client.agents.messages.list(thread_id=thread.id)
            for message in messages:
                if str(getattr(message, "role", "")).lower() == "assistant":
                    return message

            return next(iter(messages), None)
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()

    # ------------------------------------------------------------------
    # Agent
    # ------------------------------------------------------------------

    def __build_agent(self) -> FunctionAgent:
        retriever_kwargs = {
            "vector_store_query_mode": VectorStoreQueryMode.SEMANTIC_HYBRID,
            "similarity_top_k": self.similarity_top_k,
        }

        if self.reranker:
            retriever_kwargs["node_postprocessors"] = [self.reranker]

        retriever = self.index.as_retriever(**retriever_kwargs)
        im_retriever_tool = self.__build_retriever_tool(
            retriever=retriever,
            name="im_retriever_tool",
            description=(
                "Query unstructured enterprise documents using semantic/hybrid "
                "retrieval. Use this for document-grounded questions."
            ),
        )

        agent_tools = [im_retriever_tool]

        agent_tools.extend(
            [
                self.__build_function_tool(
                    self.upload_and_index_files_async,
                    "upload_and_index_user_file_tool",
                    "Upload files and start background indexing. Returns a task ID.",
                ),
                self.__build_function_tool(
                    self.check_indexing_status,
                    "check_indexing_status_tool",
                    "Check the status of a background file-indexing task.",
                ),
                self.__build_function_tool(
                    self.query_local_file_index,
                    "query_user_upload_file_indexes_tool",
                    "Query content from previously uploaded and indexed files.",
                ),
                self.__build_function_tool(
                    self.bing_grounding_tool,
                    "internet_search_tool",
                    "Search the internet through the configured Azure AI web-search agent.",
                ),
            ]
        )

        if self.graph_rag_system and getattr(self.graph_rag_system, "index", None):
            agent_tools.append(
                self.__build_function_tool(
                    self.graph_rag_system.query,
                    "graph_rag_tool",
                    "Query entity relationships and multi-hop knowledge graph facts.",
                )
            )

        if self.enable_coding_assistant and self.code_interpreter:
            agent_tools.append(
                self.__build_function_tool(
                    self.code_interpreter.run_python,
                    "code_interpreter_tool",
                    "Execute Python code in the configured isolated sandbox.",
                )
            )

        if self.csv_engine is not None:
            agent_tools.append(
                self.__build_function_tool(
                    lambda q: str(self.csv_engine.query(q)),
                    "csv_tool",
                    "Query the configured Salesforce meeting-data CSV.",
                )
            )

        system_prompt = (
            AGENTIC_AI_CODEX_PROMPT
            if self.enable_coding_assistant
            else AGENTIC_AI_SYSTEM_PROMPT
        ).format(now_str=datetime.now(timezone.utc).strftime("%Y-%m-%d"))

        return FunctionAgent(
            tools=agent_tools,
            llm=self.llm,
            system_prompt=system_prompt,
            verbose=True,
        )

    # ------------------------------------------------------------------
    # Execution / response handling
    # ------------------------------------------------------------------

    async def run_agent_async(self, question: str) -> Any:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string.")

        logger.info("[AgenticAi] Processing session %s", self.session_id)

        try:
            # Current LlamaIndex AgentWorkflow/FunctionAgent owns the turn
            # lifecycle when Memory is supplied. Passing both a manually-mutated
            # chat_history and user_msg duplicates the user message.
            response = await self.agent.run(
                user_msg=question,
                memory=self.memory,
            )

            for tool_call in self._safe_tool_calls(response):
                logger.info(
                    "[AgenticAi] Tool executed: %s",
                    getattr(tool_call, "tool_name", "unknown"),
                )

            return response
        except Exception:
            logger.exception("[AgenticAi] Agent execution failed")
            raise

    async def run_agent(self, question: str) -> Any:
        """Compatibility wrapper; no nested event-loop patching is required."""
        return await self.run_agent_async(question)

    async def stream_response(self, response: Any) -> AsyncGenerator[str, None]:
        """Yield response text in meaningful chunks instead of one character at a time."""
        text = self._extract_response_text(response)
        if not text:
            return

        # If the response exposes an actual async/sync response generator,
        # preserve it; otherwise emit the normalized final text.
        response_gen = getattr(response, "response_gen", None)
        if response_gen is not None:
            if hasattr(response_gen, "__aiter__"):
                async for chunk in response_gen:
                    if chunk:
                        yield str(chunk)
                return

            for chunk in response_gen:
                if chunk:
                    yield str(chunk)
            return

        yield text

    async def collect_async_generator_result(
        self,
        gen: AsyncGenerator[str, None],
    ) -> str:
        result: List[str] = []
        async for chunk in gen:
            result.append(str(chunk))
        return "".join(result)

    def get_retriever_metadata(self, response_block: Any) -> Any:
        for tool_call in self._safe_tool_calls(response_block):
            if getattr(tool_call, "tool_name", None) != "im_retriever_tool":
                continue

            tool_output = getattr(tool_call, "tool_output", None)
            raw_output = getattr(tool_output, "raw_output", None)
            if raw_output is None:
                continue

            try:
                parsed = parse_response_sources(response_sources=raw_output)
                if isinstance(parsed, str):
                    return json.loads(parsed)
                return parsed
            except (TypeError, ValueError, json.JSONDecodeError):
                logger.warning("[AgenticAi] Unable to parse retriever metadata")
                return []

        return []

    def get_response_async(self, question: str) -> Dict[str, Any]:
        """Synchronous bridge for callers that are not already inside an event loop."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            response_block = asyncio.run(self.run_agent_async(question))
        else:
            raise RuntimeError(
                "get_response_async() cannot be called from a running event loop; "
                "use 'await get_response()' instead."
            )

        response_text = self._extract_response_text(response_block)
        return {
            "response_text": response_text,
            "response_metadata": self.get_retriever_metadata(response_block),
        }

    async def get_response(self, question: str) -> Dict[str, Any]:
        response_block = await self.run_agent_async(question)
        response_text = self._extract_response_text(response_block)

        return {
            "response_text": response_text,
            "response_metadata": self.get_retriever_metadata(response_block),
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release local resources owned by this engine."""
        if self.code_interpreter:
            self.code_interpreter.close()

        close = getattr(self.credential_manager, "close", None)
        if callable(close):
            close()
