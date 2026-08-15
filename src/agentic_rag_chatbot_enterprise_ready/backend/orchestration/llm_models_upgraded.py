from __future__ import annotations

from enum import Enum
from typing import Final, Mapping, FrozenSet


class AIResponseMode(str, Enum):
    """Controls response verbosity exposed by the application UI."""

    DETAILED = "detailed"
    CONCISE = "concise"


class AIModelTypes(str, Enum):
    """Supported model identifiers used by the application.

    Existing model values are retained for backward compatibility. GPT-5.6
    is added as the current recommended GPT-family alias; the application can
    still select GPT-5.1 without changing existing deployments.
    """

    O4_MINI = "o4-mini"
    O4_MINI_HIGH = "o4-mini-high"
    GPT4O = "gpt-4o"
    GPT41 = "gpt-4.1"
    GPT41_MINI = "gpt-4.1-mini"
    GPT51 = "gpt-5.1"
    GPT56 = "gpt-5.6"


# Model context windows verified against the current OpenAI model catalog.
#
# These are model capabilities, not necessarily the amount of memory the
# application should consume in every request. MODEL_TOKEN_LIMITS is kept as
# the public application-facing mapping for backward compatibility.
MODEL_CONTEXT_WINDOWS: Final[Mapping[AIModelTypes, int]] = {
    AIModelTypes.O4_MINI: 200_000,
    AIModelTypes.O4_MINI_HIGH: 200_000,
    AIModelTypes.GPT4O: 128_000,
    AIModelTypes.GPT41: 1_047_576,
    AIModelTypes.GPT41_MINI: 1_047_576,
    AIModelTypes.GPT51: 400_000,
    AIModelTypes.GPT56: 1_050_000,
}

# Preserve the historical public name while correcting the stale values.
# The application memory layer may intentionally use a fraction of this
# capacity; callers should not interpret this as "tokens available for output".
MODEL_TOKEN_LIMITS: Final[Mapping[AIModelTypes, int]] = MODEL_CONTEXT_WINDOWS


# Maximum output-token limits documented for the corresponding current models.
MODEL_MAX_OUTPUT_TOKENS: Final[Mapping[AIModelTypes, int]] = {
    AIModelTypes.O4_MINI: 100_000,
    AIModelTypes.O4_MINI_HIGH: 100_000,
    AIModelTypes.GPT4O: 16_384,
    AIModelTypes.GPT41: 32_768,
    AIModelTypes.GPT41_MINI: 32_768,
    AIModelTypes.GPT51: 128_000,
    AIModelTypes.GPT56: 128_000,
}


# Reasoning defaults are application policy, not claims about every model's
# server-side default. Non-reasoning models are deliberately absent.
DEFAULT_REASONING_EFFORT: Final[Mapping[AIModelTypes, str]] = {
    AIModelTypes.O4_MINI: "high",
    AIModelTypes.O4_MINI_HIGH: "high",
}


# GPT-5.x models support a broader reasoning range. Keep this separate from
# DEFAULT_REASONING_EFFORT so callers can validate UI/request values without
# coupling validation to one default.
REASONING_EFFORTS: Final[Mapping[AIModelTypes, FrozenSet[str]]] = {
    AIModelTypes.O4_MINI: frozenset({"low", "medium", "high"}),
    AIModelTypes.O4_MINI_HIGH: frozenset({"low", "medium", "high"}),
    AIModelTypes.GPT51: frozenset({"none", "low", "medium", "high"}),
    AIModelTypes.GPT56: frozenset({"none", "low", "medium", "high", "xhigh", "max"}),
}


# Models that are explicitly non-reasoning in the current OpenAI catalog.
NON_REASONING_MODELS: Final[FrozenSet[AIModelTypes]] = frozenset(
    {
        AIModelTypes.GPT4O,
        AIModelTypes.GPT41,
        AIModelTypes.GPT41_MINI,
    }
)


# Compatibility aliases for code that wants capability-oriented names.
MODEL_CONTEXT_LIMITS = MODEL_CONTEXT_WINDOWS


def normalize_model(model: AIModelTypes | str) -> AIModelTypes:
    """Normalize an enum member or model-id string to AIModelTypes."""
    if isinstance(model, AIModelTypes):
        return model
    try:
        return AIModelTypes(model)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Unsupported AI model: {model!r}") from exc


def get_model_token_limit(model: AIModelTypes | str) -> int:
    """Return the verified context-window size for a supported model."""
    return MODEL_TOKEN_LIMITS[normalize_model(model)]


def get_model_max_output_tokens(model: AIModelTypes | str) -> int:
    """Return the documented maximum output-token size for a supported model."""
    return MODEL_MAX_OUTPUT_TOKENS[normalize_model(model)]


def get_default_reasoning_effort(
    model: AIModelTypes | str,
) -> str | None:
    """Return the application's default reasoning effort, if applicable."""
    return DEFAULT_REASONING_EFFORT.get(normalize_model(model))


def get_supported_reasoning_efforts(
    model: AIModelTypes | str,
) -> FrozenSet[str]:
    """Return reasoning values explicitly supported by the model."""
    normalized = normalize_model(model)
    return REASONING_EFFORTS.get(normalized, frozenset())


def is_reasoning_model(model: AIModelTypes | str) -> bool:
    """Return whether the model has explicit reasoning-effort controls."""
    return bool(get_supported_reasoning_efforts(model))


def validate_reasoning_effort(
    model: AIModelTypes | str,
    reasoning_effort: str,
) -> str:
    """Validate and normalize a reasoning-effort value for a model."""
    if not isinstance(reasoning_effort, str) or not reasoning_effort.strip():
        raise ValueError("reasoning_effort must be a non-empty string.")

    normalized_model = normalize_model(model)
    effort = reasoning_effort.strip().lower()
    supported = get_supported_reasoning_efforts(normalized_model)

    if not supported:
        raise ValueError(
            f"Model '{normalized_model.value}' does not expose reasoning_effort."
        )

    if effort not in supported:
        allowed = ", ".join(sorted(supported))
        raise ValueError(
            f"Unsupported reasoning_effort '{effort}' for "
            f"'{normalized_model.value}'. Allowed values: {allowed}."
        )

    return effort
