from __future__ import annotations

import ast
import asyncio
import contextlib
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv

import chainlit as cl
from chainlit.input_widget import Select, Slider, Switch
from chainlit.types import Feedback
from chainlit.user import User
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from backend.UploadFileWrapper import UploadedFileWrapper
from backend.utility import generate_blob_sas_url
from backend.azure_blob_file_retriever import AzureBlobFileRetriever
from backend.cosmos_db_date_layer import CosmosDBDataLayer
from backend.ai_models import AIModelTypes
from backend.config import config, Environment
from backend.credentials.azure_credential_manager import AzureCredentialManager
from backend.agentic_ai_system import AsyncAgenticAiSystem
from app_logger import setup_logger


CURRENT_DIR = Path(__file__).resolve().parent
load_dotenv(CURRENT_DIR.parent.parent / ".env")

logger, log_filename = setup_logger("chainlit_app_logger")
MODEL_ENUM = AIModelTypes
DEFAULT_MODEL = AIModelTypes.GPT51
DEFAULT_INDEX = "aiim"
DEFAULT_SETTINGS = {
    "select_index": DEFAULT_INDEX,
    "select_ai_model": DEFAULT_MODEL.value,
    "select_response_mode": "low",
    "set_model_top_k": 20,
    "set_creativity_level": 0.1,
    "enable_coding_assistant": False,
    "enable_reranker": True,
    "enable_graph_rag": False,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _available_indexes() -> list[str]:
    indexes = getattr(config, "indexes", {}) or {}
    return list(indexes.keys())


def _normalize_settings(settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize persisted/UI settings and tolerate settings from older versions."""
    source = {**DEFAULT_SETTINGS, **(settings or {})}

    indexes = _available_indexes()
    if indexes and source["select_index"] not in indexes:
        source["select_index"] = DEFAULT_INDEX if DEFAULT_INDEX in indexes else indexes[0]

    valid_models = [model.value for model in MODEL_ENUM]
    if source["select_ai_model"] not in valid_models:
        source["select_ai_model"] = DEFAULT_MODEL.value

    source["set_model_top_k"] = max(0, min(30, int(source["set_model_top_k"])))
    source["set_creativity_level"] = max(
        0.0, min(1.0, float(source["set_creativity_level"]))
    )
    source["select_response_mode"] = (
        "high" if source["select_response_mode"] == "high" else "low"
    )

    for key in (
        "enable_coding_assistant",
        "enable_reranker",
        "enable_graph_rag",
    ):
        source[key] = bool(source[key])

    return source


def app_default_setting(**overrides):
    settings = _normalize_settings(overrides)
    indexes = _available_indexes()

    return [
        Select(
            id="select_index",
            label="Select KnowledgeBase",
            initial_value=settings["select_index"],
            values=indexes,
            description="Select the Knowledge Base",
        ),
        Select(
            id="select_ai_model",
            label="Choose AI Model",
            initial_value=settings["select_ai_model"],
            items={model.name: model.value for model in MODEL_ENUM},
            description="Choose the AI model for reasoning",
        ),
        Select(
            id="select_response_mode",
            label="Response Conciseness",
            initial_value=settings["select_response_mode"],
            items={
                "Brief (short, to-the-point answers)": "low",
                "Expanded (in-depth explanations)": "high",
            },
            description="Adjust response conciseness.",
        ),
        Slider(
            id="set_model_top_k",
            label="Adjust Top Search Results",
            initial=settings["set_model_top_k"],
            min=0,
            max=30,
            step=1,
            description=(
                "Choose how many documents to include in your search. "
                "More documents broaden context but may increase latency."
            ),
        ),
        Slider(
            id="set_creativity_level",
            label="Tune Creativity Level",
            initial=settings["set_creativity_level"],
            min=0.0,
            max=1.0,
            step=0.1,
            description=(
                "Lower values favor consistency; higher values allow more variation."
            ),
        ),
        Switch(
            id="enable_coding_assistant",
            label="Enable Coding Assistant",
            initial=settings["enable_coding_assistant"],
            tooltip="Enable or disable the coding assistant",
            description="Toggles coding-assistant availability.",
        ),
        Switch(
            id="enable_reranker",
            label="Enable Neural Reranker",
            initial=settings["enable_reranker"],
            description="Re-ranks search results for better relevance.",
        ),
        Switch(
            id="enable_graph_rag",
            label="Enable GraphRAG",
            initial=settings["enable_graph_rag"],
            description="Enables relationship-oriented retrieval.",
        ),
    ]


def _get_index_config(index_name: str):
    try:
        return config.indexes[index_name]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Unknown knowledge-base index: {index_name!r}") from exc


def _get_blob_storage_client(index_name: str):
    index_config = _get_index_config(index_name)
    storage = index_config.storage_account
    credential_manager = AzureCredentialManager(
        key_vault_url=index_config.key_vault.get("url")
    )

    # Prefer passwordless auth when an account URL can be derived.
    account_name = storage.get("storage_account_name")
    container_name = storage.get("container_name")
    if account_name and container_name:
        credential = DefaultAzureCredential()
        service = BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=credential,
        )
        return service.get_container_client(container_name), credential_manager

    # Backward-compatible fallback for existing deployments.
    secret_name = storage.get("connection_string")
    if not secret_name:
        raise ValueError(
            f"Storage configuration for index '{index_name}' has neither "
            "storage_account_name/container_name nor connection_string."
        )

    connection_string = credential_manager.client.get_secret(secret_name).value
    service = BlobServiceClient.from_connection_string(connection_string)
    return service.get_container_client(container_name), credential_manager


def load_blob_bytes(index_name: str = DEFAULT_INDEX) -> Dict[str, str | bytes]:
    """Load the application metadata blob lazily instead of during module import."""
    container_client, _ = _get_blob_storage_client(index_name)
    retriever = AzureBlobFileRetriever(container_client_service=container_client)

    blob_stream = retriever.get_latest_file_stream(prefix="your_file", extension=".csv")
    blob_bytes = blob_stream.to_bytes() if blob_stream else b""

    if blob_stream:
        logger.info(
            "[AgenticAiSystem] Downloaded blob name=%s size=%s",
            blob_stream.name,
            blob_stream.size,
        )

    metadata = retriever.get_blob("metadata.json")
    return {"bytes": blob_bytes, "metadata": metadata.to_str()}


async def _get_session_blob_context(index_name: str) -> Dict[str, str | bytes]:
    cached = cl.user_session.get("blob_context")
    cached_index = cl.user_session.get("blob_context_index")
    if cached is not None and cached_index == index_name:
        return cached

    context = await asyncio.to_thread(load_blob_bytes, index_name)
    cl.user_session.set("blob_context", context)
    cl.user_session.set("blob_context_index", index_name)
    return context


async def _graph_groups(token: str) -> list[dict[str, str]]:
    if not token:
        return []

    url = "https://graph.microsoft.com/v1.0/me/memberOf"
    params = {"$select": "displayName,mail,id"}
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            groups = response.json().get("value", [])
    except httpx.HTTPError:
        logger.exception("Microsoft Graph group lookup failed")
        return []

    return [
        {"displayName": group.get("displayName", ""), "id": group.get("id", "")}
        for group in groups
        if group.get("@odata.type") == "#microsoft.graph.group"
    ]


@cl.oauth_callback
async def on_oauth_callback(
    provider_id: str,
    token: str,
    raw_user: Dict[str, str],
    default_user: User,
    id_token: Optional[str] = None,
) -> Optional[User]:
    # Store only what is required for this session. Do not log tokens.
    default_user.metadata["id_token"] = token
    default_user.metadata["claims"] = raw_user
    default_user.metadata["tenant"] = raw_user.get("tid")
    default_user.metadata["groups"] = await _graph_groups(token)
    default_user.display_name = raw_user.get("displayName")
    return default_user


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Ask me questions about anything...",
            message="Tell me about your capabilities.",
            icon="/public/favicon.png",
        ),
        cl.Starter(
            label="What can you do?",
            message="What can you help me with?",
            icon="/public/favicon.png",
        ),
    ]


@cl.on_settings_update
async def on_settings_change(settings):
    normalized = _normalize_settings(settings)
    logger.info("[AgenticAiSystem] App settings changed")

    cl.user_session.set("settings", normalized)
    agent = cl.user_session.get("agentic_engine")
    if agent is not None:
        _apply_agent_settings(agent, normalized)
    return normalized


@cl.data_layer
def get_data_layer():
    """Establish the Cosmos DB data layer without logging secrets."""
    select_index = DEFAULT_INDEX
    environment = os.getenv("ENVIRONMENT", "local")
    index_config = _get_index_config(select_index)
    credential_manager = AzureCredentialManager(
        key_vault_url=index_config.key_vault.get("url")
    )

    environment_configs = {
        "local": index_config.dev_cosmos_db,
        Environment.DEVELOPMENT.value: index_config.dev_cosmos_db,
        Environment.UAT.value: index_config.uat_cosmos_db,
        Environment.PRODUCTION.value: index_config.prod_cosmos_db,
    }
    cosmos_config = environment_configs.get(
        environment, index_config.dev_cosmos_db
    )

    url = credential_manager.client.get_secret(cosmos_config["uri"]).value
    database_id = cosmos_config["database_id"]
    container_id = cosmos_config["container_id"]

    # Never log the URI/connection secret.
    logger.info(
        "[AgenticAiSystem] Data layer configured database=%s container=%s environment=%s",
        database_id,
        container_id,
        environment,
    )

    return CosmosDBDataLayer(
        credential=DefaultAzureCredential(),
        url=url,
        database_id=database_id,
        container_id=container_id,
    )


def _build_agent(settings: Dict[str, Any], chat_history: list, blob_context: dict):
    settings = _normalize_settings(settings)
    return AsyncAgenticAiSystem(
        selected_model=MODEL_ENUM(settings["select_ai_model"]) or DEFAULT_MODEL,
        similarity_top_k=settings["set_model_top_k"],
        reasoning_effect=settings["select_response_mode"],
        llm_creativity_level=settings["set_creativity_level"],
        index_name=settings["select_index"],
        session_id=cl.user_session.get("id"),
        upload_root_dir=tempfile.mkdtemp(prefix="llama_index_"),
        conversation_thread=chat_history,
        blob_bytes=blob_context["bytes"],
        enable_coding_assistant=settings["enable_coding_assistant"],
        enable_reranker=settings["enable_reranker"],
        enable_graph_rag=settings["enable_graph_rag"],
    )


def _apply_agent_settings(agent, settings: Dict[str, Any]) -> None:
    settings = _normalize_settings(settings)
    agent.set_selected_model(selected_model=settings["select_ai_model"])
    agent.set_llm_creativity_level(
        llm_creativity_level=settings["set_creativity_level"]
    )
    agent.set_reasoning_effect(reasoning_effect=settings["select_response_mode"])
    agent.set_similarity_top_k(similarity_top_k=settings["set_model_top_k"])
    agent.set_index_name(index_name=settings["select_index"])
    agent.set_coding_assistant(
        enable_coding_assistant=settings["enable_coding_assistant"]
    )
    agent.set_reranker(enable_reranker=settings["enable_reranker"])
    agent.set_graph_rag(enable_graph_rag=settings["enable_graph_rag"])


async def _ensure_user_groups(user: Optional[User]) -> None:
    if user is None or "groups" in user.metadata:
        return

    groups = await _graph_groups(user.metadata.get("id_token", ""))
    user.metadata["groups"] = groups
    cl.user_session.set("user", user)


async def _ensure_settings() -> Dict[str, Any]:
    settings = cl.user_session.get("settings")
    if settings is None:
        settings = await cl.ChatSettings(app_default_setting()).send()
    settings = _normalize_settings(settings)
    cl.user_session.set("settings", settings)
    return settings


async def _ensure_agent(settings: Dict[str, Any]):
    agent = cl.user_session.get("agentic_engine")
    if agent is None:
        blob_context = await _get_session_blob_context(settings["select_index"])
        agent = _build_agent(
            settings,
            cl.user_session.get("chat_history") or [],
            blob_context,
        )
        cl.user_session.set("agentic_engine", agent)
    else:
        _apply_agent_settings(agent, settings)
        agent.set_conversation_thread(
            thread=cl.user_session.get("chat_history") or []
        )
    return agent


@cl.on_chat_start
async def start():
    try:
        cl.user_session.set("chat_history", [])
        await _ensure_user_groups(cl.user_session.get("user"))
        settings = await _ensure_settings()
        await _ensure_agent(settings)

        user = cl.user_session.get("user")
        logger.info(
            "[AgenticAiSystem] New thread user=%s session=%s settings=%s",
            getattr(user, "identifier", "local_user"),
            cl.user_session.get("id"),
            settings,
        )
        return True
    except Exception:
        logger.exception("Chat initialization failed")
        await cl.Message(
            content="Unable to initialize this chat session. Please try again."
        ).send()
        return False


def _restore_settings_from_thread(thread: Dict[str, Any]) -> Dict[str, Any]:
    thread_settings = thread.get("settings")
    if thread_settings:
        return _normalize_settings(thread_settings)
    return _normalize_settings(cl.user_session.get("settings"))


@cl.on_chat_resume
async def on_chat_resume(thread):
    settings = _restore_settings_from_thread(thread)
    settings = await cl.ChatSettings(app_default_setting(**settings)).send()
    settings = _normalize_settings(settings)
    cl.user_session.set("settings", settings)

    if "elements" in thread:
        await _restore_pdf_elements(thread, settings)

    await _ensure_user_groups(cl.user_session.get("user"))
    await _ensure_agent(settings)


async def _restore_pdf_elements(thread: Dict[str, Any], settings: Dict[str, Any]):
    credential_manager = _get_blob_storage_client(settings["select_index"])[1]
    index_config = _get_index_config(settings["select_index"])
    storage = index_config.storage_account

    for element in thread.get("elements", []):
        if element.get("type") != "pdf" or not element.get("name"):
            continue

        if element.get("url"):
            element["url"] = generate_blob_sas_url(
                account_name=storage["storage_account_name"],
                account_key=credential_manager.client.get_secret(
                    storage["account_key"]
                ).value,
                container_name=storage["container_name"],
                blob_name=element["name"],
            )
        else:
            element["path"] = str(element["name"])


@cl.on_feedback
async def on_feedback(feedback: Feedback):
    chat_history = cl.user_session.get("chat_history") or []

    for step in chat_history:
        if step.get("stepId") == feedback.forId:
            step["feedbackScore"] = feedback.value
            step["feedbackComment"] = feedback.comment or ""

    cl.user_session.set("chat_history", chat_history)


def _remove_branch_from_history(chat_history: list, message_id: str) -> list:
    reference = next(
        (item for item in chat_history if item.get("stepId") == message_id),
        None,
    )
    if reference is None:
        return chat_history

    created_at = reference.get("createdAt")
    if not created_at:
        return [
            item for item in chat_history if item.get("stepId") != message_id
        ]

    reference_time = datetime.fromisoformat(created_at)
    return [
        item
        for item in chat_history
        if item.get("stepId") != message_id
        and (
            not item.get("createdAt")
            or datetime.fromisoformat(item["createdAt"]) < reference_time
        )
    ]


def _append_history(
    chat_history: list,
    *,
    step_id: str,
    parent_id: Optional[str],
    role: str,
    content: str,
    feedback_score=None,
    feedback_comment="",
) -> None:
    chat_history.append(
        {
            "stepId": step_id,
            "parentId": parent_id,
            "role": role,
            "content": content,
            # JSON-serializable: Chainlit persists user-session data.
            "createdAt": _utc_now_iso(),
            "feedbackScore": feedback_score,
            "feedbackComment": feedback_comment,
        }
    )


@cl.on_message
async def on_message(message: cl.Message):
    chat_history = cl.user_session.get("chat_history") or []
    cl.user_session.set("chat_history", chat_history)

    try:
        chat_history = _remove_branch_from_history(chat_history, message.id)
        cl.user_session.set("chat_history", chat_history)

        settings = await _ensure_settings()
        agentic_engine = await _ensure_agent(settings)

        user_prompt = (message.content or "").strip()
        if not user_prompt:
            await cl.Message(
                content="⚠️ Prompt is empty. Please type something."
            ).send()
            return

        _append_history(
            chat_history,
            step_id=message.id,
            parent_id=message.parent_id,
            role="user",
            content=user_prompt,
        )

        processing_message = cl.Message(content="Processing the Query.")
        await processing_message.send()

        async def animate_status():
            dots = "."
            while True:
                processing_message.content = f"Processing the Query{dots}"
                await processing_message.update()
                await asyncio.sleep(0.35)
                dots = "." if len(dots) >= 8 else dots + "."

        animation_task = asyncio.create_task(animate_status())

        try:
            uploaded_files = message.elements or []
            if uploaded_files:
                file_wrappers = [
                    UploadedFileWrapper(file.path, file.name)
                    for file in uploaded_files
                ]
                uploaded_files_summary = await agentic_engine.upload_and_index_files(
                    file_wrappers
                )

                for user_file in uploaded_files:
                    confirmation = await cl.Message(
                        content="File uploaded and indexed successfully."
                    ).send()
                    await cl.Text(
                        name=user_file.name,
                        content=uploaded_files_summary.get(
                            user_file.name, "No summary"
                        ),
                    ).send(for_id=confirmation.id)

                _append_history(
                    chat_history,
                    step_id=f"{message.id}:files",
                    parent_id=message.id,
                    role="system",
                    content=(
                        "Uploaded files: "
                        + ", ".join(file.name for file in uploaded_files)
                    ),
                )

            result = await agentic_engine.run_agent_async(user_prompt)
            await stream_answer_and_citations(
                processing_message,
                result.response.content,
                settings,
            )

            _append_history(
                chat_history,
                step_id=processing_message.id,
                parent_id=message.id,
                role="assistant",
                content=result.response.content,
            )

            assistant_count = sum(
                1 for item in chat_history if item.get("role") == "assistant"
            )
            if assistant_count == 1:
                thread_id = getattr(message, "thread_id", None)
                if thread_id:
                    data_layer = get_data_layer()
                    await data_layer.update_thread(
                        thread_id=thread_id,
                        name=agentic_engine.generate_thread_title(),
                    )

            cl.user_session.set("chat_history", chat_history)

        except Exception:
            logger.exception("Message processing failed")
            await cl.Message(
                content="❌ The request could not be completed. Please try again."
            ).send()
            _append_history(
                chat_history,
                step_id=f"{message.id}:error",
                parent_id=message.id,
                role="assistant",
                content="❌ The request could not be completed.",
            )
            cl.user_session.set("chat_history", chat_history)
        finally:
            animation_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await animation_task

    except Exception:
        logger.exception("Unhandled message-processing error")
        await cl.Message(
            content="InternalServerError: the request could not be processed."
        ).send()
        cl.user_session.set("chat_history", chat_history)


def _extract_citation_list(response_content: str) -> list[dict[str, Any]]:
    """Safely extract the Python-list citation payload after 'Citations:'."""
    marker = "Citations:"
    index = response_content.find(marker)
    if index == -1:
        return []

    remainder = response_content[index + len(marker):].lstrip()
    start = remainder.find("[")
    if start == -1:
        return []

    # Find the matching closing bracket while respecting quoted strings.
    depth = 0
    quote = None
    escaped = False

    for position in range(start, len(remainder)):
        char = remainder[position]

        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if char in ("'", '"'):
            quote = char
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                candidate = remainder[start:position + 1]
                try:
                    value = ast.literal_eval(candidate)
                except (SyntaxError, ValueError):
                    return []
                return value if isinstance(value, list) else []

    return []


def _render_source_name(source: dict[str, Any]) -> str:
    title = str(source.get("title") or source.get("source_node") or "Source")
    return title.rsplit("/", 1)[-1]


async def stream_answer_and_citations(
    target_msg_element: cl.Message,
    response_content: str,
    thread_settings: Dict[str, Any],
):
    """Render the answer and validated citation metadata."""
    target_msg_element.content = ""
    await target_msg_element.update()

    marker = "Citations:"
    citation_index = response_content.find(marker)
    main_content = (
        response_content[:citation_index].strip()
        if citation_index >= 0
        else response_content
    )

    for token in main_content.split():
        await target_msg_element.stream_token(token + " ")

    source_list = _extract_citation_list(response_content)
    index_config = _get_index_config(thread_settings["select_index"])
    storage = index_config.storage_account

    credential_manager = None
    if any(
        source.get("mimetype") == "pdf"
        for source in source_list
        if isinstance(source, dict)
    ):
        credential_manager = _get_blob_storage_client(
            thread_settings["select_index"]
        )[1]

    rendered_references = []

    for list_index, source in enumerate(source_list):
        if not isinstance(source, dict):
            continue

        mimetype = source.get("mimetype")
        source_node = source.get("source_node")
        if not source_node:
            continue

        if mimetype == "pdf":
            page_number = source.get("page_number")
            if page_number is None:
                logger.warning("PDF citation missing page number: %s", source_node)
                continue

            is_user_upload = "user_uploads" in source_node
            url = None
            if not is_user_upload and credential_manager is not None:
                url = generate_blob_sas_url(
                    account_name=storage["storage_account_name"],
                    account_key=credential_manager.client.get_secret(
                        storage["account_key"]
                    ).value,
                    container_name=storage["container_name"],
                    blob_name=source_node,
                )

            await cl.Pdf(
                name=source_node,
                size="small",
                url=url,
                path=source_node if is_user_upload else None,
                display="side",
                page=int(page_number),
            ).send(for_id=target_msg_element.id)

            rendered_references.append(
                f"&emsp;**Reference [{list_index + 1}]**:&NewLine;"
                f"&emsp;&emsp;**Source**: {_render_source_name(source)} "
                f"(**PageNumber**: {page_number})&NewLine;"
                f"&emsp;&emsp;**SourcePath**: {source_node}&NewLine;"
            )

        elif mimetype == "url":
            title = source.get("title") or source_node
            rendered_references.append(
                f"&emsp;**Reference [{list_index + 1}]**:&NewLine;"
                f"&emsp;&emsp;**Source**: [{title}]({source_node})&NewLine;"
            )

    if rendered_references:
        citation_text = (
            "&NewLine;&NewLine; **Citations (References)**:&NewLine;"
            + "".join(rendered_references)
        )
        for token in citation_text.split():
            await target_msg_element.stream_token(token + " ")

    await target_msg_element.update()
