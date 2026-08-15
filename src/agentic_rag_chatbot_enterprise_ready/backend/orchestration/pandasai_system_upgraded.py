from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

import pandas as pd

try:
    import pandasai as pai
except ImportError:  # pragma: no cover
    pai = None  # type: ignore[assignment]

try:
    from pandasai import SmartDataframe
except ImportError:  # pragma: no cover
    SmartDataframe = None  # type: ignore[assignment]

try:
    from pandasai_openai import AzureOpenAI as PandasAIAzureOpenAI
except ImportError:  # pragma: no cover
    PandasAIAzureOpenAI = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


class PandasAISystemError(RuntimeError):
    """Base exception for PandasAI CSV analysis failures."""


class PandasAIConfigurationError(PandasAISystemError):
    """Raised when PandasAI or Azure OpenAI configuration is invalid."""


class PandasAIQueryError(PandasAISystemError):
    """Raised when a PandasAI query cannot be completed."""


@dataclass(frozen=True)
class PandasAIConfig:
    """Configuration for one PandasAI dataframe session."""

    verbose: bool = False
    enforce_privacy: bool = True
    max_retries: int = 3
    temperature: Optional[float] = 0.0
    enable_cache: bool = False

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0.")
        if self.temperature is not None and not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be between 0 and 2.")


def _as_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PandasAIConfigurationError(f"{name} must be a mapping.")
    return value


def _get_aoai_config(config: Any) -> Mapping[str, Any]:
    llms = getattr(config, "llms", None)
    llms = _as_mapping(llms, "config.llms")

    aoai = llms.get("aoai")
    if aoai is None:
        raise PandasAIConfigurationError(
            "Azure OpenAI configuration 'llms.aoai' is missing."
        )

    return _as_mapping(aoai, "config.llms.aoai")


def _get_key_vault_secret(
    credential_manager: Any,
    secret_name: Optional[str],
) -> Optional[str]:
    if credential_manager is None or not secret_name:
        return None

    getter = getattr(credential_manager, "get_secret", None)
    if not callable(getter):
        raise PandasAIConfigurationError(
            "credential_manager must expose get_secret()."
        )

    value = getter(secret_name)
    return str(value) if value else None


def _resolve_api_key(
    *,
    credential_manager: Any,
    config: Any,
    secret_name: Optional[str] = None,
) -> str:
    aoai = _get_aoai_config(config)
    key_vault = getattr(config, "key_vault", None) or {}

    if isinstance(key_vault, Mapping):
        configured_secret = (
            key_vault.get("azure_openai_api_key_name")
            or key_vault.get("openai_api_key_name")
        )
    else:
        configured_secret = None

    secret_name = (
        secret_name
        or aoai.get("api-key-secret-name")
        or aoai.get("api_key_secret_name")
        or configured_secret
        or os.getenv("AZURE_OPENAI_API_KEY_SECRET_NAME")
    )

    api_key = _get_key_vault_secret(credential_manager, secret_name)
    api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")

    if not api_key:
        raise PandasAIConfigurationError(
            "Azure OpenAI API key is not configured for PandasAI. "
            "Configure Key Vault or AZURE_OPENAI_API_KEY."
        )

    return api_key


def _resolve_endpoint_and_version(config: Any) -> tuple[str, str]:
    aoai = _get_aoai_config(config)

    endpoint = (
        aoai.get("endpoint-east-us-2")
        or aoai.get("endpoint")
        or os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    api_version = (
        aoai.get("api-version-east-us-2")
        or aoai.get("api-version")
        or os.getenv("AZURE_OPENAI_API_VERSION")
    )

    if not endpoint:
        raise PandasAIConfigurationError(
            "Azure OpenAI endpoint is missing."
        )
    if not api_version:
        raise PandasAIConfigurationError(
            "Azure OpenAI API version is missing."
        )

    return str(endpoint), str(api_version)


def _resolve_deployment(config: Any, selected_model: Any) -> str:
    aoai = _get_aoai_config(config)

    model_value = getattr(selected_model, "value", selected_model)
    model_value = str(model_value)

    deployment = (
        aoai.get(f"pandasai-{model_value}")
        or aoai.get(f"deployment-{model_value}")
        or aoai.get("pandasai-deployment-name")
        or aoai.get("deployment-name")
        or aoai.get("deployment_name")
        or model_value
    )

    if isinstance(deployment, Mapping):
        deployment = deployment.get("name") or deployment.get("deployment")

    if not deployment:
        raise PandasAIConfigurationError(
            f"PandasAI Azure deployment is missing for model '{model_value}'."
        )

    return str(deployment)


def _build_pandasai_llm(
    *,
    config: Any,
    credential_manager: Any,
    selected_model: Any,
    api_key: Optional[str] = None,
    llm_factory: Any = None,
) -> Any:
    factory = llm_factory or PandasAIAzureOpenAI
    if factory is None:
        raise PandasAIConfigurationError(
            "pandasai-openai is not installed. "
            "Install pandasai-openai alongside pandasai."
        )

    endpoint, api_version = _resolve_endpoint_and_version(config)
    deployment = _resolve_deployment(config, selected_model)

    resolved_key = api_key or _resolve_api_key(
        credential_manager=credential_manager,
        config=config,
    )

    # pandasai-openai's Azure integration uses the Azure endpoint,
    # deployment name and API version. api_token is supported by the
    # current extension examples and avoids leaking the credential into
    # global environment state.
    kwargs = {
        "api_token": resolved_key,
        "azure_endpoint": endpoint,
        "api_version": api_version,
        "deployment_name": deployment,
    }

    try:
        return factory(**kwargs)
    except TypeError:
        # Some installed extension builds expose api_key instead of
        # api_token. Keep compatibility without silently swallowing other
        # construction failures.
        kwargs["api_key"] = kwargs.pop("api_token")
        try:
            return factory(**kwargs)
        except Exception as exc:
            raise PandasAIConfigurationError(
                "Failed to initialize the PandasAI Azure OpenAI integration."
            ) from exc
    except Exception as exc:
        raise PandasAIConfigurationError(
            "Failed to initialize the PandasAI Azure OpenAI integration."
        ) from exc


def _build_pandasai_dataframe(
    dataframe: pd.DataFrame,
    *,
    llm: Any,
    pandasai_config: Optional[PandasAIConfig] = None,
    dataframe_factory: Any = None,
) -> Any:
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("dataframe must be a pandas.DataFrame.")

    if dataframe.empty:
        raise ValueError("dataframe must contain at least one row.")

    cfg = pandasai_config or PandasAIConfig()

    # PandasAI 3.x recommends pai.DataFrame over the older
    # SmartDataframe constructor. Keep a SmartDataframe fallback for
    # installations that still expose only the compatibility API.
    factory = dataframe_factory
    if factory is None:
        if pai is not None and callable(getattr(pai, "DataFrame", None)):
            factory = pai.DataFrame
        elif SmartDataframe is not None:
            factory = SmartDataframe

    if factory is None:
        raise PandasAIConfigurationError(
            "PandasAI is not installed or its DataFrame API is unavailable."
        )

    config: dict[str, Any] = {
        "llm": llm,
        "verbose": cfg.verbose,
        "enforce_privacy": cfg.enforce_privacy,
        "max_retries": cfg.max_retries,
    }

    # v3 no longer guarantees that every legacy config option is honored.
    # Temperature is supported by the OpenAI integration but should be
    # omitted when None.
    if cfg.temperature is not None:
        config["temperature"] = cfg.temperature

    try:
        return factory(dataframe, config=config)
    except TypeError:
        # Compatibility with factories that don't accept every v3 config
        # option. Retry only with the minimal stable contract.
        minimal_config = {
            "llm": llm,
            "verbose": cfg.verbose,
            "enforce_privacy": cfg.enforce_privacy,
        }
        try:
            return factory(dataframe, config=minimal_config)
        except Exception as exc:
            raise PandasAIConfigurationError(
                "Failed to initialize the PandasAI dataframe."
            ) from exc
    except Exception as exc:
        raise PandasAIConfigurationError(
            "Failed to initialize the PandasAI dataframe."
        ) from exc


class PandasAIDataFrameEngine:
    """Production adapter around PandasAI's current dataframe API.

    The adapter preserves the application's legacy ``query()`` contract
    while using PandasAI 3.x's dataframe API internally.

    Important security property:
    PandasAI generates and executes Python/SQL as part of analysis. The
    application must therefore treat this component as an execution boundary.
    For untrusted multi-tenant workloads, configure an appropriate PandasAI
    sandbox rather than executing generated code directly on the application
    host.
    """

    def __init__(
        self,
        dataframe: pd.DataFrame,
        *,
        config: Any,
        credential_manager: Any,
        selected_model: Any,
        pandasai_config: Optional[PandasAIConfig] = None,
        api_key: Optional[str] = None,
        llm_factory: Any = None,
        dataframe_factory: Any = None,
    ) -> None:
        self.dataframe = dataframe
        self.pandasai_config = pandasai_config or PandasAIConfig()

        self.llm = _build_pandasai_llm(
            config=config,
            credential_manager=credential_manager,
            selected_model=selected_model,
            api_key=api_key,
            llm_factory=llm_factory,
        )

        self.engine = _build_pandasai_dataframe(
            dataframe,
            llm=self.llm,
            pandasai_config=self.pandasai_config,
            dataframe_factory=dataframe_factory,
        )

    def query(self, question: str) -> str:
        """Backward-compatible query interface used by the agent tool."""
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string.")

        try:
            response = self.engine.chat(question)
        except Exception as exc:
            logger.exception("PandasAI query failed.")
            raise PandasAIQueryError(
                "PandasAI could not complete the data-analysis query."
            ) from exc

        return self._normalize_response(response)

    def chat(self, question: str) -> str:
        """Modern PandasAI naming; delegates to the stable query contract."""
        return self.query(question)

    @staticmethod
    def _normalize_response(response: Any) -> str:
        if response is None:
            return ""

        if isinstance(response, str):
            return response

        # PandasAI may return scalar/dataframe/chart-like objects.
        if isinstance(response, (int, float, bool)):
            return str(response)

        return str(response)


class PandasAICSVEngineBuilder:
    """Compatibility builder for the existing AsyncAgenticAiSystem.

    Replace the old ``__build_csv_engine`` body with a call to
    ``build_from_blob``. The rest of the agent can continue to call
    ``self.csv_engine.query(question)``.
    """

    def __init__(
        self,
        *,
        config: Any,
        credential_manager: Any,
        selected_model: Any,
        pandasai_config: Optional[PandasAIConfig] = None,
    ) -> None:
        self.config = config
        self.credential_manager = credential_manager
        self.selected_model = selected_model
        self.pandasai_config = pandasai_config or PandasAIConfig()

    def build_from_blob(
        self,
        csv_bytes: bytes,
        metadata: Optional[Any] = None,
    ) -> PandasAIDataFrameEngine:
        if not isinstance(csv_bytes, (bytes, bytearray)):
            raise TypeError("csv_bytes must be bytes or bytearray.")
        if not csv_bytes:
            raise ValueError("csv_bytes must not be empty.")

        dataframe = self._load_csv(csv_bytes)

        logger.info(
            "Creating PandasAI CSV engine: rows=%d columns=%d",
            len(dataframe),
            len(dataframe.columns),
        )

        return PandasAIDataFrameEngine(
            dataframe,
            config=self.config,
            credential_manager=self.credential_manager,
            selected_model=self.selected_model,
            pandasai_config=self.pandasai_config,
        )

    @staticmethod
    def _load_csv(csv_bytes: bytes) -> pd.DataFrame:
        # Keep the application's legacy latin1 compatibility, but use
        # optional date parsing so a valid CSV without these Salesforce
        # columns does not fail.
        from io import BytesIO

        dataframe = pd.read_csv(
            BytesIO(csv_bytes),
            encoding="latin1",
            low_memory=False,
        )

        if dataframe.empty:
            raise ValueError("CSV contains no data rows.")

        for column in ("createddate", "activitydate"):
            if column in dataframe.columns:
                dataframe[column] = pd.to_datetime(
                    dataframe[column],
                    errors="coerce",
                )

        return dataframe
