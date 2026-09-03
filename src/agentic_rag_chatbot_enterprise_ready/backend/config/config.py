"""Configuration loading and validation for the application runtime.

The loader deliberately remains backward compatible with the existing YAML
shape while making path resolution deterministic and keeping configuration
loading free of secret values in logs.
"""

from __future__ import annotations

import logging
import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

DEFAULT_ENVIRONMENT = "local"
VALID_ENVIRONMENTS = {
    "local",
    "local_emulator",
    "development",
    "uat",
    "staging",
    "production",
}


class ConfigurationError(ValueError):
    """Raised when configuration is structurally invalid for runtime use."""


class Environment(str, Enum):
    LOCAL = "local"
    LOCAL_EMULATOR = "local_emulator"
    DEVELOPMENT = "development"
    UAT = "uat"
    STAGING = "staging"
    PRODUCTION = "production"


class CloudProvider(str, Enum):
    AZURE = "azure"
    AWS = "aws"
    GCP = "gcp"


class DatabaseProvider(str, Enum):
    COSMOS_DB = "cosmos_db"
    DYNAMO_DB = "dynamo_db"
    POSTGRESQL = "postgresql"
    MONGODB = "mongodb"


class IndexConfig:
    """Represents the configuration for one retrieval/index target."""

    def __init__(self, name: str, settings: Dict[str, Any]) -> None:
        self.name = name
        self.settings = settings

    @property
    def azure_ai_search(self) -> Dict[str, Any]:
        return self.settings.get("azure_ai_search", {})

    @property
    def storage_account(self) -> Dict[str, Any]:
        return self.settings.get("storage_account", {})

    @property
    def s3_bucket(self) -> Dict[str, Any]:
        return self.settings.get("s3_bucket", {})

    @property
    def embed(self) -> Dict[str, Any]:
        return self.settings.get("embed", {})

    @property
    def rag(self) -> Dict[str, Any]:
        return self.settings.get("rag", {})

    @property
    def key_vault(self) -> Dict[str, Any]:
        return self.settings.get("key_vault", {})

    @property
    def secrets_manager(self) -> Dict[str, Any]:
        return self.settings.get("secrets_manager", {})

    @property
    def di(self) -> Dict[str, Any]:
        return self.settings.get("di", {})

    @property
    def llms(self) -> Dict[str, Any]:
        return self.settings.get("llms", {})

    @property
    def dev_cosmos_db(self) -> Dict[str, Any]:
        return self.settings.get("dev_cosmos_db", {})

    @property
    def uat_cosmos_db(self) -> Dict[str, Any]:
        return self.settings.get("uat_cosmos_db", {})

    @property
    def prod_cosmos_db(self) -> Dict[str, Any]:
        return self.settings.get("prod_cosmos_db", {})

    @property
    def dynamo_db(self) -> Dict[str, Any]:
        return self.settings.get("dynamo_db", {})

    @property
    def postgresql(self) -> Dict[str, Any]:
        return self.settings.get("postgresql", {})

    @property
    def mongodb(self) -> Dict[str, Any]:
        return self.settings.get("mongodb", {})

    @property
    def ai_service(self) -> Dict[str, Any]:
        return self.settings.get("ai_service", {})


class Config:
    """Load application configuration without requiring cloud access at import."""

    def __init__(self, config_path: Optional[str | Path] = None) -> None:
        self._config_path = self._resolve_config_path(config_path)
        self._config: Optional[Dict[str, Any]] = None
        self._load_env_if_local()
        logger.info("Configuration path: %s", self._config_path)

    @staticmethod
    def _resolve_config_path(config_path: Optional[str | Path]) -> Path:
        """Resolve an explicit path, CONFIG_PATH, or a repository-local config."""
        if config_path:
            candidate = Path(config_path).expanduser()
        elif os.getenv("CONFIG_PATH"):
            candidate = Path(os.environ["CONFIG_PATH"]).expanduser()
        else:
            candidate = Path("config.yml")

        if candidate.is_absolute():
            return candidate

        # Resolve relative paths from the current working directory first.
        cwd_candidate = Path.cwd() / candidate
        if cwd_candidate.exists():
            return cwd_candidate.resolve()

        # This also makes `agentic-rag` predictable when invoked outside the repo.
        # The package lives under <repo>/src/<package>/backend/config/config.py.
        repo_root = Path(__file__).resolve().parents[4]
        return (repo_root / candidate).resolve()

    def _load_env_if_local(self) -> None:
        """Load .env.local/.env only for local development."""
        if self.environment != Environment.LOCAL:
            return
        package_root = Path(__file__).resolve().parents[4]
        env_file = package_root / ".env.local"
        if not env_file.exists():
            env_file = package_root / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            logger.debug("Loaded local environment variables from %s", env_file)

    @property
    def environment(self) -> Environment:
        env_str = os.getenv("ENVIRONMENT", DEFAULT_ENVIRONMENT).strip().lower()
        try:
            return Environment(env_str)
        except ValueError:
            raise ConfigurationError(
                f"Invalid ENVIRONMENT value {env_str!r}; expected one of "
                f"{sorted(VALID_ENVIRONMENTS)}"
            ) from None

    @property
    def is_local(self) -> bool:
        return self.environment == Environment.LOCAL

    @property
    def is_cloud(self) -> bool:
        return self.environment in {
            Environment.DEVELOPMENT,
            Environment.STAGING,
            Environment.PRODUCTION,
        }

    @property
    def key_vault_url(self) -> Optional[str]:
        azure_url = os.getenv("AZURE_KEY_VAULT_URL")
        if azure_url:
            return azure_url
        return self._get_config().get("azure", {}).get("key_vault", {}).get("url")

    def _get_config(self) -> Dict[str, Any]:
        """Load YAML once; missing config remains non-fatal until validation/runtime use."""
        if self._config is not None:
            return self._config

        try:
            with self._config_path.open("r", encoding="utf-8") as config_file:
                loaded_config = yaml.safe_load(config_file) or {}
        except FileNotFoundError:
            logger.warning("Configuration file not found: %s", self._config_path)
            self._config = {}
            return self._config
        except yaml.YAMLError as exc:
            raise ConfigurationError(
                f"Unable to parse YAML configuration at {self._config_path}: {exc}"
            ) from exc

        if not isinstance(loaded_config, dict):
            raise ConfigurationError(
                f"Configuration root must be a YAML mapping: {self._config_path}"
            )
        self._config = loaded_config
        return self._config

    @property
    def indexes(self) -> Dict[str, IndexConfig]:
        indexes_config = self._get_config().get("indexes", {})
        if not isinstance(indexes_config, dict):
            raise ConfigurationError("'indexes' must be a mapping")
        return {
            name: IndexConfig(name, settings if isinstance(settings, dict) else {})
            for name, settings in indexes_config.items()
        }

    @property
    def cloud_provider(self) -> CloudProvider:
        provider = str(self._get_config().get("cloud", {}).get("provider", "azure")).lower()
        try:
            return CloudProvider(provider)
        except ValueError:
            raise ConfigurationError(
                f"Invalid cloud provider {provider!r}; expected azure, aws, or gcp"
            ) from None

    @property
    def database_provider(self) -> DatabaseProvider:
        provider = str(
            self._get_config().get("database", {}).get("provider", "cosmos_db")
        ).lower()
        try:
            return DatabaseProvider(provider)
        except ValueError:
            raise ConfigurationError(
                f"Invalid database provider {provider!r}; expected cosmos_db, dynamo_db, "
                "postgresql, or mongodb"
            ) from None

    @property
    def llms(self) -> Dict[str, Any]:
        return self._get_config().get("llms", {})

    def get_llm_config(self, model_name: str) -> Dict[str, Any]:
        llm_config = self.llms.get(model_name)
        if not llm_config:
            raise KeyError(f"Configuration for LLM model '{model_name}' not found in config file")
        return llm_config

    @property
    def document_intelligence_api_key_name(self) -> Optional[str]:
        return self._get_config().get("azure", {}).get("key_vault", {}).get(
            "document_intelligence_api_key_name"
        )

    @property
    def document_intelligence_endpoint(self) -> Optional[str]:
        return self._get_config().get("azure", {}).get("key_vault", {}).get(
            "document_intelligence_endpoint"
        )

    @property
    def openai_api_key_name(self) -> Optional[str]:
        return self._get_config().get("azure", {}).get("key_vault", {}).get(
            "openai_api_key_name"
        )

    @property
    def secrets_management(self) -> Dict[str, Any]:
        if self.cloud_provider == CloudProvider.AZURE:
            return self._get_config().get("azure", {}).get("key_vault", {})
        if self.cloud_provider == CloudProvider.AWS:
            return self._get_config().get("aws", {}).get("secrets_manager", {})
        return self._get_config().get("secrets", {})

    @property
    def cosmos_db_uri(self) -> Optional[str]:
        return self._get_config().get("azure", {}).get("key_vault", {}).get("uri")

    @property
    def dynamo_db_table(self) -> Optional[str]:
        return self._get_config().get("aws", {}).get("dynamo_db", {}).get("table_name")

    @property
    def postgresql_config(self) -> Dict[str, Any]:
        return self._get_config().get("database", {}).get("postgresql", {})

    @property
    def mongodb_config(self) -> Dict[str, Any]:
        return self._get_config().get("database", {}).get("mongodb", {})

    @property
    def ai_service(self) -> Dict[str, Any]:
        return self._get_config().get("ai_service", {})

    def validate_runtime_config(self) -> None:
        """Validate the minimum configuration needed before starting cloud services.

        This is intentionally explicit rather than executed at module import so
        tooling, tests, and package discovery can run without Azure credentials.
        """
        config = self._get_config()
        if not config:
            raise ConfigurationError(
                f"No runtime configuration found at {self._config_path}. "
                "Copy config.example.yml to config.yml and provide environment-specific values."
            )

        missing_sections = [section for section in ("indexes", "llms") if not config.get(section)]
        if missing_sections:
            raise ConfigurationError(
                "Missing required configuration sections: " + ", ".join(missing_sections)
            )

        if self.cloud_provider == CloudProvider.AZURE and not self.key_vault_url:
            raise ConfigurationError(
                "Azure configuration requires azure.key_vault.url or AZURE_KEY_VAULT_URL"
            )


config: Config = Config()
