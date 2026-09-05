from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Final


class AIResponseMode(StrEnum):
    """Controls response verbosity exposed by the application UI."""

    DETAILED = "detailed"
    CONCISE = "concise"


class AIModelTypes(StrEnum):
    """Supported model identifiers used by the application."""

    O4_MINI = "o4-mini"
    O4_MINI_HIGH = "o4-mini-high"
    GPT4O = "gpt-4o"
    GPT41 = "gpt-4.1"
    GPT41_MINI = "gpt-4.1-mini"
    GPT51 = "gpt-5.1"
    GPT56 = "gpt-5.6"


MODEL_CONTEXT_WINDOWS: Final[Mapping[AIModelTypes, int]] = {
    AIModelTypes.O4_MINI: 200_000,
    AIModelTypes.O4_MINI_HIGH: 200_000,
    AIModelTypes.GPT4O: 128_000,
    AIModelTypes.GPT41: 1_047_576,
    AIModelTypes.GPT41_MINI: 1_047_576,
    AIModelTypes.GPT51: 400_000,
    AIModelTypes.GPT56: 1_050_000,
}

MODEL_TOKEN_LIMITS: Final[Mapping[AIModelTypes, int]] = MODEL_CONTEXT_WINDOWS

MODEL_MAX_OUTPUT_TOKENS: Final[Mapping[AIModelTypes, int]] = {
    AIModelTypes.O4_MINI: 100_000,
    AIModelTypes.O4_MINI_HIGH: 100_000,
    AIModelTypes.GPT4O: 16_384,
    AIModelTypes.GPT41: 32_768,
    AIModelTypes.GPT41_MINI: 32_768,
    AIModelTypes.GPT51: 128_000,
    AIModelTypes.GPT56: 128_000,
}

DEFAULT_REASONING_EFFORT: Final[Mapping[AIModelTypes, str]] = {
    AIModelTypes.O4_MINI: "high",
    AIModelTypes.O4_MINI_HIGH: "high",
}

REASONING_EFFORTS: Final[Mapping[AIModelTypes, frozenset[str]]] = {
    AIModelTypes.O4_MINI: frozenset({"low", "medium", "high"}),
    AIModelTypes.O4_MINI_HIGH: frozenset({"low", "medium", "high"}),
    AIModelTypes.GPT51: frozenset({"none", "low", "medium", "high"}),
    AIModelTypes.GPT56: frozenset({"none", "low", "medium", "high", "xhigh", "max"}),
}

NON_REASONING_MODELS: Final[frozenset[AIModelTypes]] = frozenset(
    {AIModelTypes.GPT4O, AIModelTypes.GPT41, AIModelTypes.GPT41_MINI}
)

MODEL_CONTEXT_LIMITS = MODEL_CONTEXT_WINDOWS


def normalize_model(model: AIModelTypes | str) -> AIModelTypes:
    """Normalize an enum member or model-id string."""
    if isinstance(model, AIModelTypes):
        return model
    try:
        return AIModelTypes(model)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Unsupported AI model: {model!r}") from exc


def get_model_token_limit(model: AIModelTypes | str) -> int:
    return MODEL_TOKEN_LIMITS[normalize_model(model)]


def get_model_max_output_tokens(model: AIModelTypes | str) -> int:
    return MODEL_MAX_OUTPUT_TOKENS[normalize_model(model)]


def get_default_reasoning_effort(model: AIModelTypes | str) -> str | None:
    return DEFAULT_REASONING_EFFORT.get(normalize_model(model))


def get_supported_reasoning_efforts(model: AIModelTypes | str) -> frozenset[str]:
    return REASONING_EFFORTS.get(normalize_model(model), frozenset())


def is_reasoning_model(model: AIModelTypes | str) -> bool:
    return bool(get_supported_reasoning_efforts(model))


def validate_reasoning_effort(model: AIModelTypes | str, reasoning_effort: str) -> str:
    if not isinstance(reasoning_effort, str) or not reasoning_effort.strip():
        raise ValueError("reasoning_effort must be a non-empty string.")
    normalized_model = normalize_model(model)
    effort = reasoning_effort.strip().lower()
    supported = get_supported_reasoning_efforts(normalized_model)
    if not supported:
        raise ValueError(f"Model '{normalized_model.value}' does not expose reasoning_effort.")
    if effort not in supported:
        allowed = ", ".join(sorted(supported))
        raise ValueError(
            f"Unsupported reasoning_effort '{effort}' for '{normalized_model.value}'. "
            f"Allowed values: {allowed}."
        )
    return effort
