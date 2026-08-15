import importlib.util
import os
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest


# Dependency-isolated regression suite. The real E2B package is intentionally
# not required to test the adapter's contracts.
e2b_module = types.ModuleType("e2b_code_interpreter")


class FakeSandbox:
    create_calls = []
    run_calls = []
    instances = []

    def __init__(self):
        self.killed = False
        self.executions = []
        FakeSandbox.instances.append(self)

    @classmethod
    def create(cls, **kwargs):
        cls.create_calls.append(kwargs)
        return cls()

    def run_code(self, code, **kwargs):
        self.run_calls.append((code, kwargs))
        return self.executions.pop(0)

    def kill(self):
        self.killed = True


e2b_module.Sandbox = FakeSandbox
sys.modules["e2b_code_interpreter"] = e2b_module

MODULE_PATH = Path("/mnt/data/code_interpreter_upgraded.py")
spec = importlib.util.spec_from_file_location(
    "code_interpreter_under_test",
    MODULE_PATH,
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

CodeInterpreterSandbox = module.CodeInterpreterSandbox
CodeInterpreterUnavailableError = module.CodeInterpreterUnavailableError
CodeInterpreterExecutionError = module.CodeInterpreterExecutionError


class Execution:
    def __init__(self, text=None, error=None, logs=None):
        self.text = text
        self.error = error
        self.logs = logs


@pytest.fixture(autouse=True)
def reset_fake_e2b():
    FakeSandbox.create_calls.clear()
    FakeSandbox.run_calls.clear()
    FakeSandbox.instances.clear()
    yield


def test_missing_api_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("E2B_API_KEY", raising=False)

    sandbox = CodeInterpreterSandbox()

    assert sandbox.available is False
    with pytest.raises(CodeInterpreterUnavailableError):
        sandbox.run_python("print('hello')")


def test_explicit_api_key_makes_adapter_available():
    sandbox = CodeInterpreterSandbox(api_key="test-key")
    assert sandbox.available is True


def test_empty_code_is_rejected():
    sandbox = CodeInterpreterSandbox(api_key="test-key")

    with pytest.raises(ValueError, match="empty"):
        sandbox.run_python("   ")


def test_non_string_code_is_rejected():
    sandbox = CodeInterpreterSandbox(api_key="test-key")

    with pytest.raises(TypeError):
        sandbox.run_python(None)


def test_code_length_limit_is_enforced():
    sandbox = CodeInterpreterSandbox(
        api_key="test-key",
        max_code_length=5,
    )

    with pytest.raises(ValueError, match="maximum"):
        sandbox.run_python("123456")


def test_constructor_validates_timeouts():
    with pytest.raises(ValueError):
        CodeInterpreterSandbox(api_key="x", timeout=0)

    with pytest.raises(ValueError):
        CodeInterpreterSandbox(api_key="x", request_timeout=0)

    with pytest.raises(ValueError):
        CodeInterpreterSandbox(api_key="x", sandbox_timeout=0)


def test_sandbox_is_created_lazily():
    sandbox = CodeInterpreterSandbox(api_key="test-key")

    assert sandbox.sandbox is None
    assert FakeSandbox.create_calls == []

    sandbox.run_python("print('hello')")

    assert sandbox.sandbox is not None
    assert len(FakeSandbox.create_calls) == 1


def test_sandbox_is_reused_between_executions():
    sandbox = CodeInterpreterSandbox(api_key="test-key")

    first = FakeSandbox.instances
    sandbox.run_python("print(1)")
    created = sandbox.sandbox

    sandbox.run_python("print(2)")

    assert sandbox.sandbox is created
    assert len(FakeSandbox.create_calls) == 1


def test_run_code_uses_e2b_code_interpreter_api_without_shell_escaping():
    sandbox = CodeInterpreterSandbox(api_key="test-key")
    sandbox.sandbox = FakeSandbox()
    sandbox.sandbox.executions.append(Execution(text="hello"))

    code = "print(\"It's safe\")\nprint('a;b')"

    result = sandbox.run_python(code)

    assert "hello" in result
    assert FakeSandbox.run_calls[0][0] == code
    assert FakeSandbox.run_calls[0][1]["language"] == "python"
    assert FakeSandbox.run_calls[0][1]["timeout"] == 30.0
    assert FakeSandbox.run_calls[0][1]["request_timeout"] == 60.0


def test_execution_text_is_preferred():
    sandbox = CodeInterpreterSandbox(api_key="test-key")
    sandbox.sandbox = FakeSandbox()
    sandbox.sandbox.executions.append(Execution(text="2"))

    assert sandbox.run_python("1 + 1") == "Execution finished. Output:\n2"


def test_logs_are_used_when_execution_has_no_text():
    logs = types.SimpleNamespace(
        stdout=["hello\n"],
        stderr=["warning\n"],
    )
    sandbox = CodeInterpreterSandbox(api_key="test-key")
    sandbox.sandbox = FakeSandbox()
    sandbox.sandbox.executions.append(Execution(logs=logs))

    result = sandbox.run_python("print('hello')")

    assert "hello" in result
    assert "warning" in result


def test_execution_error_is_returned_without_raising_by_default():
    error = types.SimpleNamespace(
        name="NameError",
        value="name 'x' is not defined",
        traceback="Traceback...",
    )
    sandbox = CodeInterpreterSandbox(api_key="test-key")
    sandbox.sandbox = FakeSandbox()
    sandbox.sandbox.executions.append(
        Execution(text="", error=error)
    )

    result = sandbox.run_python("print(x)")

    assert "Execution failed." in result
    assert "NameError" in result
    assert "not defined" in result


def test_execution_error_can_be_raised():
    error = types.SimpleNamespace(
        name="ValueError",
        value="bad value",
        traceback="Traceback...",
    )
    sandbox = CodeInterpreterSandbox(
        api_key="test-key",
        raise_on_execution_error=True,
    )
    sandbox.sandbox = FakeSandbox()
    sandbox.sandbox.executions.append(
        Execution(text="", error=error)
    )

    with pytest.raises(CodeInterpreterExecutionError, match="ValueError"):
        sandbox.run_python("raise ValueError('bad value')")


def test_empty_successful_output_has_stable_message():
    sandbox = CodeInterpreterSandbox(api_key="test-key")
    sandbox.sandbox = FakeSandbox()
    sandbox.sandbox.executions.append(Execution(text=""))

    assert (
        sandbox.run_python("x = 1")
        == "Execution finished successfully with no output."
    )


def test_sandbox_creation_failure_is_translated():
    class BrokenSandbox:
        @classmethod
        def create(cls, **kwargs):
            raise RuntimeError("network failure")

    original = module.Sandbox
    module.Sandbox = BrokenSandbox
    try:
        sandbox = CodeInterpreterSandbox(api_key="test-key")
        with pytest.raises(CodeInterpreterUnavailableError):
            sandbox.run_python("print(1)")
    finally:
        module.Sandbox = original


def test_execution_request_failure_can_be_raised():
    sandbox = CodeInterpreterSandbox(
        api_key="test-key",
        raise_on_execution_error=True,
    )
    sandbox.sandbox = FakeSandbox()

    def broken(*args, **kwargs):
        raise RuntimeError("request failed")

    sandbox.sandbox.run_code = broken

    with pytest.raises(CodeInterpreterExecutionError):
        sandbox.run_python("print(1)")


def test_close_kills_sandbox_and_is_idempotent():
    sandbox = CodeInterpreterSandbox(api_key="test-key")
    sandbox.sandbox = FakeSandbox()

    sandbox.close()

    assert sandbox.sandbox is None
    assert FakeSandbox.instances[0].killed is True

    sandbox.close()
    assert sandbox.sandbox is None


def test_context_manager_releases_sandbox():
    with CodeInterpreterSandbox(api_key="test-key") as sandbox:
        sandbox.sandbox = FakeSandbox()
        assert sandbox.sandbox is not None

    assert sandbox.sandbox is None
    assert FakeSandbox.instances[0].killed is True


def test_explicit_key_is_restored_after_creation(monkeypatch):
    monkeypatch.setenv("E2B_API_KEY", "original")

    sandbox = CodeInterpreterSandbox(api_key="explicit")
    sandbox.run_python("print(1)")

    assert os.environ["E2B_API_KEY"] == "original"


def test_default_key_is_used_from_environment(monkeypatch):
    monkeypatch.setenv("E2B_API_KEY", "env-key")

    sandbox = CodeInterpreterSandbox()
    assert sandbox.available is True


def test_no_secret_or_code_is_logged_as_payload(monkeypatch, caplog):
    sandbox = CodeInterpreterSandbox(api_key="secret-key")
    sandbox.sandbox = FakeSandbox()
    sandbox.sandbox.executions.append(Execution(text="ok"))

    with caplog.at_level("INFO"):
        sandbox.run_python("print('do not log this source')")

    combined = "\n".join(record.getMessage() for record in caplog.records)

    assert "do not log this source" not in combined
    assert "secret-key" not in combined
