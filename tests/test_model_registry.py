from backend.orchestration.llm_models import (
    AIModelTypes,
    AIResponseMode,
    DEFAULT_REASONING_EFFORT,
    MODEL_CONTEXT_WINDOWS,
    MODEL_MAX_OUTPUT_TOKENS,
    MODEL_TOKEN_LIMITS,
    NON_REASONING_MODELS,
    REASONING_EFFORTS,
    get_model_max_output_tokens,
    get_model_token_limit,
    normalize_model,
    validate_reasoning_effort,
)


def test_canonical_registry_exposes_current_models():
    assert AIModelTypes.GPT56.value == "gpt-5.6"
    assert AIModelTypes.GPT51.value == "gpt-5.1"
    assert AIResponseMode.DETAILED.value == "detailed"
    assert AIResponseMode.CONCISE.value == "concise"


def test_context_and_output_limits_are_distinct():
    assert MODEL_TOKEN_LIMITS is MODEL_CONTEXT_WINDOWS
    assert MODEL_CONTEXT_WINDOWS[AIModelTypes.GPT56] == 1_050_000
    assert MODEL_MAX_OUTPUT_TOKENS[AIModelTypes.GPT56] == 128_000


def test_all_models_have_positive_limits():
    for model in AIModelTypes:
        assert MODEL_CONTEXT_WINDOWS[model] > 0
        assert 0 < MODEL_MAX_OUTPUT_TOKENS[model] <= MODEL_CONTEXT_WINDOWS[model]


def test_normalize_model_accepts_enum_and_string():
    assert normalize_model(AIModelTypes.GPT56) is AIModelTypes.GPT56
    assert normalize_model("gpt-5.6") is AIModelTypes.GPT56


def test_normalize_model_rejects_unknown_model():
    import pytest
    with pytest.raises(ValueError, match="Unsupported AI model"):
        normalize_model("unknown-model")


def test_reasoning_capabilities_are_explicit():
    assert REASONING_EFFORTS[AIModelTypes.GPT51] == frozenset({"none", "low", "medium", "high"})
    assert REASONING_EFFORTS[AIModelTypes.GPT56] == frozenset({"none", "low", "medium", "high", "xhigh", "max"})
    assert AIModelTypes.GPT41 in NON_REASONING_MODELS
    assert AIModelTypes.GPT41_MINI in NON_REASONING_MODELS
    assert AIModelTypes.GPT51 not in NON_REASONING_MODELS


def test_default_reasoning_policy_remains_conservative():
    assert DEFAULT_REASONING_EFFORT[AIModelTypes.O4_MINI] == "high"
    assert DEFAULT_REASONING_EFFORT[AIModelTypes.O4_MINI_HIGH] == "high"
    assert AIModelTypes.GPT51 not in DEFAULT_REASONING_EFFORT


def test_reasoning_effort_validation():
    assert validate_reasoning_effort("gpt-5.6", " HIGH ") == "high"
    assert validate_reasoning_effort("gpt-5.6", "max") == "max"
    import pytest
    with pytest.raises(ValueError, match="Unsupported reasoning_effort"):
        validate_reasoning_effort("gpt-5.1", "max")
    with pytest.raises(ValueError, match="does not expose reasoning_effort"):
        validate_reasoning_effort("gpt-4.1", "high")


def test_limit_accessors_use_canonical_registry():
    assert get_model_token_limit("gpt-5.6") == 1_050_000
    assert get_model_max_output_tokens("gpt-5.1") == 128_000
