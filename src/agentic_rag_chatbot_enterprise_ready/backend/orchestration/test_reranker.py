import importlib.util
import sys
import types
from pathlib import Path

import pytest


MODULE_PATH = Path("/mnt/data/reranker_upgraded.py")


# Dependency-isolated stubs allow the complete regression suite to run without
# Azure, LlamaIndex, or an LLM network call.
llama_index_module = types.ModuleType("llama_index")
llama_index_core_module = types.ModuleType("llama_index.core")
llama_index_llms_module = types.ModuleType("llama_index.core.llms")
llama_index_postprocessor_module = types.ModuleType(
    "llama_index.core.postprocessor"
)


class FakeLLM:
    pass


class FakeLLMRerank:
    created = []
    error = None

    def __init__(self, **kwargs):
        if self.error is not None:
            raise self.error
        self.kwargs = kwargs
        self.created.append(kwargs)


llama_index_llms_module.LLM = FakeLLM
llama_index_postprocessor_module.LLMRerank = FakeLLMRerank

sys.modules["llama_index"] = llama_index_module
sys.modules["llama_index.core"] = llama_index_core_module
sys.modules["llama_index.core.llms"] = llama_index_llms_module
sys.modules["llama_index.core.postprocessor"] = llama_index_postprocessor_module

spec = importlib.util.spec_from_file_location(
    "reranker_under_test",
    MODULE_PATH,
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

initialize_reranker = module.initialize_reranker
RerankerConfigurationError = module.RerankerConfigurationError


@pytest.fixture(autouse=True)
def reset_fake():
    FakeLLMRerank.created.clear()
    FakeLLMRerank.error = None
    yield


def test_default_reranker_configuration():
    reranker = initialize_reranker(FakeLLM())

    assert isinstance(reranker, FakeLLMRerank)
    assert reranker.kwargs["top_n"] == 5
    assert reranker.kwargs["choice_batch_size"] == 5
    assert reranker.kwargs["llm"].__class__ is FakeLLM


def test_custom_top_n_is_forwarded():
    reranker = initialize_reranker(
        FakeLLM(),
        top_n=3,
    )

    assert reranker.kwargs["top_n"] == 3


def test_custom_batch_size_is_forwarded():
    reranker = initialize_reranker(
        FakeLLM(),
        choice_batch_size=10,
    )

    assert reranker.kwargs["choice_batch_size"] == 10


def test_batch_size_can_exceed_top_n():
    reranker = initialize_reranker(
        FakeLLM(),
        top_n=3,
        choice_batch_size=10,
    )

    assert reranker.kwargs["top_n"] == 3
    assert reranker.kwargs["choice_batch_size"] == 10


def test_top_n_can_exceed_batch_size():
    reranker = initialize_reranker(
        FakeLLM(),
        top_n=10,
        choice_batch_size=3,
    )

    assert reranker.kwargs["top_n"] == 10
    assert reranker.kwargs["choice_batch_size"] == 3


def test_zero_top_n_is_rejected():
    with pytest.raises(RerankerConfigurationError):
        initialize_reranker(FakeLLM(), top_n=0)


def test_negative_top_n_is_rejected():
    with pytest.raises(RerankerConfigurationError):
        initialize_reranker(FakeLLM(), top_n=-1)


def test_zero_batch_size_is_rejected():
    with pytest.raises(RerankerConfigurationError):
        initialize_reranker(FakeLLM(), choice_batch_size=0)


def test_negative_batch_size_is_rejected():
    with pytest.raises(RerankerConfigurationError):
        initialize_reranker(FakeLLM(), choice_batch_size=-1)


@pytest.mark.parametrize(
    "value",
    [True, False, 1.0, 5.0, "5", None, [], {}],
)
def test_top_n_must_be_integer(value):
    with pytest.raises(RerankerConfigurationError):
        initialize_reranker(FakeLLM(), top_n=value)


@pytest.mark.parametrize(
    "value",
    [True, False, 1.0, 5.0, "5", None, [], {}],
)
def test_batch_size_must_be_integer(value):
    with pytest.raises(RerankerConfigurationError):
        initialize_reranker(FakeLLM(), choice_batch_size=value)


def test_none_llm_is_rejected():
    with pytest.raises(RerankerConfigurationError, match="llm is required"):
        initialize_reranker(None)


def test_callback_manager_is_optional():
    callback_manager = object()

    reranker = initialize_reranker(
        FakeLLM(),
        callback_manager=callback_manager,
    )

    assert reranker.kwargs["callback_manager"] is callback_manager


def test_callback_manager_is_not_passed_when_omitted():
    reranker = initialize_reranker(FakeLLM())

    assert "callback_manager" not in reranker.kwargs


def test_custom_choice_select_prompt_is_forwarded():
    prompt = object()

    reranker = initialize_reranker(
        FakeLLM(),
        choice_select_prompt=prompt,
    )

    assert reranker.kwargs["choice_select_prompt"] is prompt


def test_custom_prompt_is_not_passed_when_omitted():
    reranker = initialize_reranker(FakeLLM())

    assert "choice_select_prompt" not in reranker.kwargs


def test_llm_initialization_error_is_normalized():
    FakeLLMRerank.error = RuntimeError("provider failure")

    with pytest.raises(RuntimeError, match="Failed to initialize"):
        initialize_reranker(FakeLLM())


def test_original_exception_is_preserved_as_cause():
    original = RuntimeError("provider failure")
    FakeLLMRerank.error = original

    with pytest.raises(RuntimeError) as exc_info:
        initialize_reranker(FakeLLM())

    assert exc_info.value.__cause__ is original


def test_no_secret_is_written_to_environment():
    import os

    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.pop("AZURE_OPENAI_API_KEY", None)

    initialize_reranker(FakeLLM())

    assert "OPENAI_API_KEY" not in os.environ
    assert "AZURE_OPENAI_API_KEY" not in os.environ


def test_no_secret_is_logged(caplog):
    secret = "super-secret-api-key"

    with caplog.at_level("INFO"):
        initialize_reranker(FakeLLM())

    assert secret not in caplog.text


def test_reranker_returns_actual_llamaindex_postprocessor_type():
    reranker = initialize_reranker(FakeLLM())

    assert isinstance(reranker, FakeLLMRerank)


def test_multiple_rerankers_are_independent():
    first = initialize_reranker(FakeLLM(), top_n=3)
    second = initialize_reranker(FakeLLM(), top_n=7)

    assert first is not second
    assert first.kwargs["top_n"] == 3
    assert second.kwargs["top_n"] == 7


def test_configuration_error_does_not_call_llm_rerank():
    with pytest.raises(RerankerConfigurationError):
        initialize_reranker(FakeLLM(), top_n=0)

    assert FakeLLMRerank.created == []


def test_batch_size_validation_happens_before_constructor():
    with pytest.raises(RerankerConfigurationError):
        initialize_reranker(
            FakeLLM(),
            choice_batch_size=0,
        )

    assert FakeLLMRerank.created == []


def test_source_uses_current_llamaindex_core_import():
    source = MODULE_PATH.read_text()

    assert "from llama_index.core.postprocessor import LLMRerank" in source
    assert "from llama_index.core.llms import LLM" in source


def test_source_does_not_use_removed_service_context_argument():
    source = MODULE_PATH.read_text()

    assert "service_context" not in source


def test_source_does_not_use_legacy_llamaindex_import_path():
    source = MODULE_PATH.read_text()

    assert "llama_index.indices.query.schema" not in source
    assert "llama_index.core.postprocessor.llm_rerank" not in source


def test_source_does_not_mutate_environment_credentials():
    source = MODULE_PATH.read_text()

    assert "os.environ[" not in source
    assert "os.getenv(" not in source


def test_source_does_not_contain_hardcoded_api_keys():
    source = MODULE_PATH.read_text()

    assert "api_key=" not in source
    assert "api_token=" not in source
    assert "AZURE_OPENAI_API_KEY" not in source


def test_logging_uses_parameterized_messages():
    source = MODULE_PATH.read_text()

    assert 'logger.info(f"' not in source
    assert 'logger.error(f"' not in source
    assert 'logger.exception(f"' not in source


def test_exception_is_not_silently_swallowed():
    source = MODULE_PATH.read_text()

    assert "raise RuntimeError" in source
    assert "from exc" in source


def test_public_initializer_has_type_hints():
    annotations = initialize_reranker.__annotations__

    assert "llm" in annotations
    assert "top_n" in annotations
    assert "choice_batch_size" in annotations
    assert "return" in annotations


def test_reranker_configuration_error_is_public():
    assert issubclass(RerankerConfigurationError, ValueError)


def test_default_values_match_existing_application_contract():
    # agentic_ai_system.py currently calls initialize_reranker with top_n only;
    # preserving the existing defaults avoids changing runtime behavior.
    reranker = initialize_reranker(FakeLLM(), top_n=5)

    assert reranker.kwargs["choice_batch_size"] == 5


def test_no_unbounded_dynamic_arguments_are_forwarded():
    reranker = initialize_reranker(
        FakeLLM(),
        top_n=4,
        choice_batch_size=8,
    )

    assert set(reranker.kwargs) == {
        "llm",
        "top_n",
        "choice_batch_size",
    }


def test_optional_arguments_are_only_forwarded_when_explicitly_configured():
    callback_manager = object()
    prompt = object()

    reranker = initialize_reranker(
        FakeLLM(),
        callback_manager=callback_manager,
        choice_select_prompt=prompt,
    )

    assert reranker.kwargs["callback_manager"] is callback_manager
    assert reranker.kwargs["choice_select_prompt"] is prompt
