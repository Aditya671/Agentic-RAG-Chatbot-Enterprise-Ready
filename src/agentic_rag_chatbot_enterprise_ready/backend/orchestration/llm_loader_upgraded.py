from __future__ import annotations

import logging
import os
from copy import deepcopy
from typing import Any, Mapping, Optional, Union

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from llama_index.core.llms.llm import LLM
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.llms.openai import OpenAI

from backend.ai_models import AIModelTypes
from backend.azure_credential_manager import AzureCredentialManager
from backend.config import IndexConfig, config


DEFAULT_TEMPERATURE = 0.1
DEFAULT_TIMEOUT = 10.0
AZURE_COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"

logger = logging.getLogger(__name__)


class LLMConfigurationError(ValueError):
    """Raised when an LLM/embedding configuration is invalid."""


def _get_index_config(index_name: str) -> IndexConfig:
    if not isinstance(index_name, str) or not index_name.strip():
        raise LLMConfigurationError("index_name must be a non-empty string.")

    index_config = config.indexes.get(index_name)
    if index_config is None:
        raise LLMConfigurationError(
            f"Configuration for index '{index_name}' not found."
        )
    return index_config


def _validate_timeout(timeout: Optional[float]) -> Optional[float]:
    if timeout is None:
        return None
    try:
        value = float(timeout)
    except (TypeError, ValueError) as exc:
        raise LLMConfigurationError("timeout must be a positive number or None.") from exc

    if value <= 0:
        raise LLMConfigurationError("timeout must be greater than zero.")
    return value


def _validate_temperature(temperature: Optional[float]) -> Optional[float]:
    if temperature is None:
        return None
    try:
        value = float(temperature)
    except (TypeError, ValueError) as exc:
        raise LLMConfigurationError(
            "temperature must be a number between 0 and 2 or None."
        ) from exc

    if not 0 <= value <= 2:
        raise LLMConfigurationError("temperature must be between 0 and 2.")
    return value


def _copy_kwargs(additional_kwargs: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    if additional_kwargs is None:
        return {}
    if not isinstance(additional_kwargs, Mapping):
        raise TypeError("additional_kwargs must be a mapping or None.")
    return deepcopy(dict(additional_kwargs))


def _get_aoai_config(index_config: IndexConfig) -> Mapping[str, Any]:
    llms = getattr(index_config, "llms", None) or {}
    aoai = llms.get("aoai")
    if not isinstance(aoai, Mapping):
        raise LLMConfigurationError(
            "Azure OpenAI configuration ('llms.aoai') is missing."
        )
    return aoai


def _get_azure_endpoint_and_api_version(
    index_config: IndexConfig,
) -> tuple[str, str]:
    aoai = _get_aoai_config(index_config)
    endpoint = aoai.get("endpoint-east-us-2") or aoai.get("endpoint")
    api_version = aoai.get("api-version-east-us-2") or aoai.get("api-version")

    if not endpoint:
        raise LLMConfigurationError("Azure OpenAI endpoint is missing.")
    if not api_version:
        raise LLMConfigurationError("Azure OpenAI API version is missing.")

    return str(endpoint), str(api_version)


def _get_key_vault_manager(
    index_config: IndexConfig,
) -> Optional[AzureCredentialManager]:
    key_vault = getattr(index_config, "key_vault", None) or {}
    url = key_vault.get("url") if isinstance(key_vault, Mapping) else None

    if not url:
        return None

    return AzureCredentialManager(key_vault_url=url)


def _get_secret(
    credential_manager: Optional[AzureCredentialManager],
    secret_name: Optional[str],
) -> Optional[str]:
    if not credential_manager or not secret_name:
        return None
    value = credential_manager.get_secret(secret_name)
    return value or None


def _get_openai_api_key(
    index_config: IndexConfig,
    credential_manager: Optional[AzureCredentialManager],
) -> Optional[str]:
    key_vault = getattr(index_config, "key_vault", None) or {}
    secret_name = (
        key_vault.get("openai_api_key_name")
        if isinstance(key_vault, Mapping)
        else None
    )
    secret_name = secret_name or os.getenv("OPENAI_API_KEY_SECRET_NAME")

    return _get_secret(credential_manager, secret_name) or os.getenv(
        "OPENAI_API_KEY"
    )


def _get_azure_api_key(
    index_config: IndexConfig,
    credential_manager: Optional[AzureCredentialManager],
) -> Optional[str]:
    aoai = _get_aoai_config(index_config)
    key_vault = getattr(index_config, "key_vault", None) or {}

    secret_name = (
        aoai.get("api-key-secret-name")
        or aoai.get("api_key_secret_name")
        or (
            key_vault.get("azure_openai_api_key_name")
            if isinstance(key_vault, Mapping)
            else None
        )
        or os.getenv("AZURE_OPENAI_API_KEY_SECRET_NAME")
    )

    return _get_secret(credential_manager, secret_name) or os.getenv(
        "AZURE_OPENAI_API_KEY"
    )


def _get_azure_auth_kwargs(
    index_config: IndexConfig,
    use_azure_ad: bool,
    credential_manager: Optional[AzureCredentialManager],
) -> dict[str, Any]:
    if not use_azure_ad:
        api_key = _get_azure_api_key(index_config, credential_manager)
        if not api_key:
            raise LLMConfigurationError(
                "Azure OpenAI API key is required when azure_openai_use_azure_ad=False."
            )
        return {"api_key": api_key}

    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential,
        AZURE_COGNITIVE_SCOPE,
    )
    return {
        "azure_ad_token_provider": token_provider,
        "use_azure_ad": True,
    }


def _resolve_deployment_name(
    aoai_config: Mapping[str, Any],
    model: AIModelTypes,
) -> str:
    # Preserve the existing contract: deployment defaults to model.value.
    # Allow configuration to override this when Azure deployment names differ.
    deployment = (
        aoai_config.get(model.value)
        or aoai_config.get(f"deployment-{model.value}")
        or aoai_config.get("deployment-name")
        or aoai_config.get("deployment_name")
        or model.value
    )

    if isinstance(deployment, Mapping):
        deployment = deployment.get("name") or deployment.get("deployment")

    if not deployment:
        raise LLMConfigurationError(
            f"Azure OpenAI deployment is missing for model '{model.value}'."
        )
    return str(deployment)


def load_llm(
    model: AIModelTypes,
    index_name: str,
    temperature: Optional[float] = DEFAULT_TEMPERATURE,
    timeout: Optional[float] = DEFAULT_TIMEOUT,
    azure_openai_use_azure_ad: bool = True,
    additional_kwargs: Optional[Mapping[str, Any]] = None,
    callback_manager: Optional[Any] = None,
    use_azure: bool = True,
) -> LLM:
    """Load an OpenAI-compatible LlamaIndex LLM.

    Azure OpenAI remains the default for compatibility with the application.
    Authentication can use Microsoft Entra ID (managed identity/default
    credential) or an Azure OpenAI API key. Non-Azure mode uses the OpenAI
    integration and supports Key Vault or ``OPENAI_API_KEY`` authentication.

    ``additional_kwargs`` is copied per call so callers cannot accidentally
    mutate shared configuration between requests.
    """
    try:
        model = AIModelTypes(model)
    except (TypeError, ValueError) as exc:
        raise LLMConfigurationError(f"Unsupported model: {model!r}") from exc

    temperature = _validate_temperature(temperature)
    timeout = _validate_timeout(timeout)
    model_kwargs = _copy_kwargs(additional_kwargs)

    index_config = _get_index_config(index_name)
    credential_manager = _get_key_vault_manager(index_config)

    logger.info(
        "Loading LLM model=%s index=%s provider=%s",
        model.value,
        index_name,
        "azure-openai" if use_azure else "openai",
    )

    if use_azure:
        aoai = _get_aoai_config(index_config)
        endpoint, api_version = _get_azure_endpoint_and_api_version(index_config)
        deployment_name = _resolve_deployment_name(aoai, model)

        auth_kwargs = _get_azure_auth_kwargs(
            index_config,
            azure_openai_use_azure_ad,
            credential_manager,
        )

        kwargs: dict[str, Any] = {
            "model": model.value,
            "engine": deployment_name,
            "temperature": temperature,
            "azure_endpoint": endpoint,
            "api_version": api_version,
            "request_timeout": timeout,
            "additional_kwargs": model_kwargs,
            "callback_manager": callback_manager,
            **auth_kwargs,
        }

        # Avoid sending None values to Pydantic constructors.
        kwargs = {key: value for key, value in kwargs.items() if value is not None}

        try:
            llm = AzureOpenAI(**kwargs)
        except Exception as exc:
            logger.exception(
                "Failed to initialize Azure OpenAI model=%s index=%s",
                model.value,
                index_name,
            )
            raise LLMConfigurationError(
                f"Failed to initialize Azure OpenAI model '{model.value}'."
            ) from exc

        logger.info(
            "LLM loaded successfully: model=%s provider=azure-openai deployment=%s",
            model.value,
            deployment_name,
        )
        return llm

    api_key = _get_openai_api_key(index_config, credential_manager)
    if not api_key:
        raise LLMConfigurationError(
            "OpenAI API key is required. Configure Key Vault or OPENAI_API_KEY."
        )

    # Preserve the legacy O4_MINI_HIGH semantic without duplicating
    # reasoning_effort when the caller already supplied it.
    if model == AIModelTypes.O4_MINI_HIGH:
        model_name = AIModelTypes.O4_MINI.value
        model_kwargs.setdefault("reasoning_effort", "high")
    else:
        model_name = model.value

    kwargs = {
        "model": model_name,
        "temperature": temperature,
        "api_key": api_key,
        "timeout": timeout,
        "additional_kwargs": model_kwargs,
        "callback_manager": callback_manager,
    }
    kwargs = {key: value for key, value in kwargs.items() if value is not None}

    try:
        llm = OpenAI(**kwargs)
    except Exception as exc:
        logger.exception(
            "Failed to initialize OpenAI model=%s index=%s",
            model_name,
            index_name,
        )
        raise LLMConfigurationError(
            f"Failed to initialize OpenAI model '{model_name}'."
        ) from exc

    logger.info(
        "LLM loaded successfully: model=%s provider=openai",
        model_name,
    )
    return llm


def load_embed(
    index_name: str,
    azure_openai_use_azure_ad: bool = True,
    use_azure: bool = True,
    callback_manager: Optional[Any] = None,
    timeout: Optional[float] = DEFAULT_TIMEOUT,
) -> Union[AzureOpenAIEmbedding, OpenAIEmbedding]:
    """Load the embedding model configured for an index.

    The embedding model name remains controlled by ``index_config.embed.model``.
    Azure deployments default to the same name for backward compatibility but
    may be overridden through ``llms.aoai`` deployment configuration.
    """
    timeout = _validate_timeout(timeout)
    index_config = _get_index_config(index_name)

    embed_config = getattr(index_config, "embed", None) or {}
    if not isinstance(embed_config, Mapping):
        raise LLMConfigurationError("Embedding configuration is missing.")

    model = embed_config.get("model")
    if not model:
        raise LLMConfigurationError(
            f"Embedding model is missing for index '{index_name}'."
        )

    credential_manager = _get_key_vault_manager(index_config)

    logger.info(
        "Loading embedding model=%s index=%s provider=%s",
        model,
        index_name,
        "azure-openai" if use_azure else "openai",
    )

    if use_azure:
        aoai = _get_aoai_config(index_config)
        endpoint, api_version = _get_azure_endpoint_and_api_version(index_config)

        # Allow embedding-specific deployment configuration without breaking
        # existing configs where model == deployment name.
        deployment = (
            aoai.get(f"embedding-{model}")
            or aoai.get(f"embedding_deployment-{model}")
            or aoai.get("embedding-deployment-name")
            or aoai.get("embedding_deployment_name")
            or model
        )
        if isinstance(deployment, Mapping):
            deployment = deployment.get("name") or deployment.get("deployment")
        if not deployment:
            raise LLMConfigurationError(
                f"Azure embedding deployment is missing for model '{model}'."
            )

        auth_kwargs = _get_azure_auth_kwargs(
            index_config,
            azure_openai_use_azure_ad,
            credential_manager,
        )

        kwargs: dict[str, Any] = {
            "model": model,
            "deployment_name": str(deployment),
            "azure_endpoint": endpoint,
            "api_version": api_version,
            "request_timeout": timeout,
            "callback_manager": callback_manager,
            **auth_kwargs,
        }
        kwargs = {key: value for key, value in kwargs.items() if value is not None}

        try:
            embedding = AzureOpenAIEmbedding(**kwargs)
        except Exception as exc:
            logger.exception(
                "Failed to initialize Azure OpenAI embedding model=%s index=%s",
                model,
                index_name,
            )
            raise LLMConfigurationError(
                f"Failed to initialize Azure OpenAI embedding model '{model}'."
            ) from exc

        logger.info(
            "Embedding model loaded successfully: model=%s provider=azure-openai deployment=%s",
            model,
            deployment,
        )
        return embedding

    api_key = _get_openai_api_key(index_config, credential_manager)
    if not api_key:
        raise LLMConfigurationError(
            "OpenAI API key is required for embeddings. Configure Key Vault or OPENAI_API_KEY."
        )

    kwargs = {
        "model": model,
        "api_key": api_key,
        "timeout": timeout,
        "callback_manager": callback_manager,
    }
    kwargs = {key: value for key, value in kwargs.items() if value is not None}

    try:
        embedding = OpenAIEmbedding(**kwargs)
    except Exception as exc:
        logger.exception(
            "Failed to initialize OpenAI embedding model=%s index=%s",
            model,
            index_name,
        )
        raise LLMConfigurationError(
            f"Failed to initialize OpenAI embedding model '{model}'."
        ) from exc

    logger.info(
        "Embedding model loaded successfully: model=%s provider=openai",
        model,
    )
    return embedding
