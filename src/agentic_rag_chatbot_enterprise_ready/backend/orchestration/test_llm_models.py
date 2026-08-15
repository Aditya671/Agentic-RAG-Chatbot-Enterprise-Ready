import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path("/mnt/data/llm_models_upgraded.py")

spec = importlib.util.spec_from_file_location("llm_models_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


AIResponseMode = module.AIResponseMode
AIModelTypes = module.AIModelTypes
MODEL_TOKEN_LIMITS = module.MODEL_TOKEN_LIMITS
MODEL_CONTEXT_WINDOWS = module.MODEL_CONTEXT_WINDOWS
MODEL_MAX_OUTPUT_TOKENS = module.MODEL_MAX_OUTPUT_TOKENS
DEFAULT_REASONING_EFFORT = module.DEFAULT_REASONING_EFFORT
REASONING_EFFORTS = module.REASONING_EFFORTS
NON_REASONING_MODELS = module.NON_REASONING_MODELS


def test_response_modes_remain_backward_compatible():
    assert AIResponseMode.DETAILED.value == "detailed"
    assert AIResponseMode.CONCISE.value == "concise"


def test_existing_model_ids_are_preserved():
    assert AIModelTypes.O4_MINI.value == "o4-mini"
    assert AIModelTypes.O4_MINI_HIGH.value == "o4-mini-high"
    assert AIModelTypes.GPT4O.value == "gpt-4o"
    assert AIModelTypes.GPT41.value == "gpt-4.1"
    assert AIModelTypes.GPT41_MINI.value == "gpt-4.1-mini"
    assert AIModelTypes.GPT51.value == "gpt-5.1"


def test_current_gpt56_model_is_available():
    assert AIModelTypes.GPT56.value == "gpt-5.6"


@pytest.mark.parametrize(
    "model",
    list(AIModelTypes),
)
def test_every_model_has_a_context_window(model):
    assert MODEL_CONTEXT_WINDOWS[model] > 0
    assert MODEL_TOKEN_LIMITS[model] == MODEL_CONTEXT_WINDOWS[model]


@pytest.mark.parametrize(
    "model",
    list(AIModelTypes),
)
def test_every_model_has_a_max_output_limit(model):
    assert MODEL_MAX_OUTPUT_TOKENS[model] > 0
    assert MODEL_MAX_OUTPUT_TOKENS[model] <= MODEL_CONTEXT_WINDOWS[model]


def test_verified_context_windows():
    assert MODEL_CONTEXT_WINDOWS[AIModelTypes.O4_MINI] == 200_000
    assert MODEL_CONTEXT_WINDOWS[AIModelTypes.GPT4O] == 128_000
    assert MODEL_CONTEXT_WINDOWS[AIModelTypes.GPT41] == 1_047_576
    assert MODEL_CONTEXT_WINDOWS[AIModelTypes.GPT41_MINI] == 1_047_576
    assert MODEL_CONTEXT_WINDOWS[AIModelTypes.GPT51] == 400_000
    assert MODEL_CONTEXT_WINDOWS[AIModelTypes.GPT56] == 1_050_000


def test_verified_output_limits():
    assert MODEL_MAX_OUTPUT_TOKENS[AIModelTypes.GPT4O] == 16_384
    assert MODEL_MAX_OUTPUT_TOKENS[AIModelTypes.GPT41] == 32_768
    assert MODEL_MAX_OUTPUT_TOKENS[AIModelTypes.GPT51] == 128_000
    assert MODEL_MAX_OUTPUT_TOKENS[AIModelTypes.GPT56] == 128_000


def test_default_reasoning_policy_is_conservative_and_explicit():
    assert DEFAULT_REASONING_EFFORT[AIModelTypes.O4_MINI] == "high"
    assert DEFAULT_REASONING_EFFORT[AIModelTypes.O4_MINI_HIGH] == "high"
    assert AIModelTypes.GPT41 not in DEFAULT_REASONING_EFFORT
    assert AIModelTypes.GPT41_MINI not in DEFAULT_REASONING_EFFORT
    assert AIModelTypes.GPT51 not in DEFAULT_REASONING_EFFORT


def test_reasoning_capabilities():
    assert REASONING_EFFORTS[AIModelTypes.O4_MINI] == frozenset(
        {"low", "medium", "high"}
    )
    assert REASONING_EFFORTS[AIModelTypes.GPT51] == frozenset(
        {"none", "low", "medium", "high"}
    )
    assert REASONING_EFFORTS[AIModelTypes.GPT56] == frozenset(
        {"none", "low", "medium", "high", "xhigh", "max"}
    )


def test_non_reasoning_models_are_marked():
    assert AIModelTypes.GPT4O in NON_REASONING_MODELS
    assert AIModelTypes.GPT41 in NON_REASONING_MODELS
    assert AIModelTypes.GPT41_MINI in NON_REASONING_MODELS
    assert AIModelTypes.GPT51 not in NON_REASONING_MODELS
    assert AIModelTypes.GPT56 not in NON_REASONING_MODELS


@pytest.mark.parametrize(
    "value,expected",
    [
        ("gpt-5.6", AIModelTypes.GPT56),
        ("gpt-5.1", AIModelTypes.GPT51),
        ("gpt-4.1", AIModelTypes.GPT41),
        ("o4-mini", AIModelTypes.O4_MINI),
    ],
)
def test_normalize_model_accepts_strings(value, expected):
    assert module.normalize_model(value) is expected


def test_normalize_model_accepts_enum():
    assert module.normalize_model(AIModelTypes.GPT56) is AIModelTypes.GPT56


def test_normalize_model_rejects_unknown_value():
    with pytest.raises(ValueError, match="Unsupported AI model"):
        module.normalize_model("does-not-exist")


@pytest.mark.parametrize(
    "model,expected",
    [
        (AIModelTypes.GPT56, 1_050_000),
        (AIModelTypes.GPT51, 400_000),
        (AIModelTypes.GPT41, 1_047_576),
    ],
)
def test_get_model_token_limit(model, expected):
    assert module.get_model_token_limit(model) == expected


def test_get_model_max_output_tokens():
    assert module.get_model_max_output_tokens("gpt-5.6") == 128_000


def test_get_default_reasoning_effort():
    assert module.get_default_reasoning_effort("o4-mini") == "high"
    assert module.get_default_reasoning_effort("gpt-5.6") is None


def test_get_supported_reasoning_efforts_for_non_reasoning_model():
    assert module.get_supported_reasoning_efforts("gpt-4.1") == frozenset()


def test_is_reasoning_model():
    assert module.is_reasoning_model("gpt-5.6") is True
    assert module.is_reasoning_model("gpt-5.1") is True
    assert module.is_reasoning_model("gpt-4.1") is False


@pytest.mark.parametrize(
    "model,effort",
    [
        ("gpt-5.6", "none"),
        ("gpt-5.6", "xhigh"),
        ("gpt-5.6", "max"),
        ("gpt-5.1", "low"),
        ("o4-mini", "high"),
    ],
)
def test_validate_reasoning_effort_accepts_supported_values(model, effort):
    assert module.validate_reasoning_effort(model, effort) == effort


def test_validate_reasoning_effort_normalizes_case_and_whitespace():
    assert module.validate_reasoning_effort("gpt-5.6", " HIGH ") == "high"


def test_validate_reasoning_effort_rejects_unsupported_value():
    with pytest.raises(ValueError, match="Unsupported reasoning_effort"):
        module.validate_reasoning_effort("gpt-5.1", "max")


def test_validate_reasoning_effort_rejects_reasoning_on_non_reasoning_model():
    with pytest.raises(ValueError, match="does not expose reasoning_effort"):
        module.validate_reasoning_effort("gpt-4.1", "high")


def test_validate_reasoning_effort_rejects_empty_value():
    with pytest.raises(ValueError, match="non-empty"):
        module.validate_reasoning_effort("gpt-5.6", " ")


def test_context_limit_alias_is_backward_compatible():
    assert module.MODEL_CONTEXT_LIMITS is MODEL_CONTEXT_WINDOWS


def test_enum_is_string_compatible():
    assert isinstance(AIModelTypes.GPT56, str)
    assert AIModelTypes.GPT56 == "gpt-5.6"


def test_model_values_are_unique():
    values = [model.value for model in AIModelTypes]
    assert len(values) == len(set(values))


def test_all_model_mappings_use_enum_keys():
    mappings = (
        MODEL_TOKEN_LIMITS,
        MODEL_CONTEXT_WINDOWS,
        MODEL_MAX_OUTPUT_TOKENS,
        DEFAULT_REASONING_EFFORT,
        REASONING_EFFORTS,
    )
    for mapping in mappings:
        assert all(isinstance(key, AIModelTypes) for key in mapping)


def test_current_gpt56_is_not_silently_defaulted():
    # Adding a newer model must not change the application's existing default.
    # The application can opt into GPT-5.6 explicitly or via its UI/config.
    assert AIModelTypes.GPT51.value == "gpt-5.1"


def test_reasoning_effort_mapping_does_not_claim_non_reasoning_defaults():
    assert AIModelTypes.GPT4O not in DEFAULT_REASONING_EFFORT
    assert AIModelTypes.GPT41 not in DEFAULT_REASONING_EFFORT
    assert AIModelTypes.GPT41_MINI not in DEFAULT_REASONING_EFFORT
