from __future__ import annotations

import logging
import os
from typing import Optional

try:
    from e2b_code_interpreter import Sandbox
except ImportError:  # pragma: no cover - exercised by dependency/install checks
    Sandbox = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


class CodeInterpreterError(RuntimeError):
    """Base exception for code-interpreter failures."""


class CodeInterpreterUnavailableError(CodeInterpreterError):
    """Raised when the E2B code-interpreter dependency or API key is unavailable."""


class CodeInterpreterExecutionError(CodeInterpreterError):
    """Raised when E2B cannot execute the submitted code."""


class CodeInterpreterSandbox:
    """Persistent, isolated Python execution adapter backed by E2B.

    The original implementation used the low-level ``e2b`` process API and
    manually shell-escaped Python source. Current E2B guidance provides a
    dedicated Code Interpreter SDK with ``Sandbox.run_code()``, which avoids
    shell construction and exposes execution, stdout/stderr, errors and
    execution timeouts directly.

    The class intentionally keeps a synchronous public API because the
    application currently exposes ``run_python`` as a synchronous agent tool.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        timeout: float = 30.0,
        request_timeout: float = 60.0,
        sandbox_timeout: int = 300,
        max_code_length: int = 100_000,
        raise_on_execution_error: bool = False,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")
        if request_timeout <= 0:
            raise ValueError("request_timeout must be greater than zero.")
        if sandbox_timeout <= 0:
            raise ValueError("sandbox_timeout must be greater than zero.")
        if max_code_length <= 0:
            raise ValueError("max_code_length must be greater than zero.")

        self.api_key = api_key or os.getenv("E2B_API_KEY")
        self.timeout = float(timeout)
        self.request_timeout = float(request_timeout)
        self.sandbox_timeout = int(sandbox_timeout)
        self.max_code_length = int(max_code_length)
        self.raise_on_execution_error = raise_on_execution_error

        self.sandbox = None

        if Sandbox is None:
            logger.error(
                "E2B Code Interpreter SDK is not installed. "
                "Install the 'e2b-code-interpreter' package."
            )
        elif not self.api_key:
            logger.warning(
                "E2B_API_KEY not found. Code interpreter is unavailable."
            )
        else:
            logger.info(
                "CodeInterpreterSandbox initialized; "
                "E2B sandbox will be created lazily."
            )

    @property
    def available(self) -> bool:
        """Whether the configured SDK and API key can create a sandbox."""
        return Sandbox is not None and bool(self.api_key)

    def _ensure_sandbox(self):
        if not self.available:
            raise CodeInterpreterUnavailableError(
                "E2B code interpreter is unavailable. "
                "Install 'e2b-code-interpreter' and configure E2B_API_KEY."
            )

        if self.sandbox is None:
            try:
                # E2B reads E2B_API_KEY from the environment. If the caller
                # supplied a key explicitly, expose it only to this process
                # while creating the client and restore the previous value.
                previous_key = os.environ.get("E2B_API_KEY")
                if self.api_key:
                    os.environ["E2B_API_KEY"] = self.api_key

                try:
                    self.sandbox = Sandbox.create(
                        timeout=self.sandbox_timeout,
                    )
                finally:
                    if previous_key is None:
                        os.environ.pop("E2B_API_KEY", None)
                    else:
                        os.environ["E2B_API_KEY"] = previous_key

                logger.info(
                    "E2B code-interpreter sandbox created successfully."
                )
            except Exception as exc:
                self.sandbox = None
                logger.exception("Failed to create E2B code-interpreter sandbox.")
                raise CodeInterpreterUnavailableError(
                    "Failed to create the E2B code-interpreter sandbox."
                ) from exc

        return self.sandbox

    @staticmethod
    def _normalize_execution_output(execution) -> str:
        """Normalize E2B Execution into a stable string contract."""
        text = getattr(execution, "text", None)
        if text is not None:
            return str(text)

        logs = getattr(execution, "logs", None)
        stdout = getattr(logs, "stdout", None) if logs else None
        stderr = getattr(logs, "stderr", None) if logs else None

        chunks = []
        if stdout:
            chunks.append(str(stdout))
        if stderr:
            chunks.append(str(stderr))

        results = getattr(execution, "results", None)
        if results:
            for result in results:
                result_text = getattr(result, "text", None)
                if result_text:
                    chunks.append(str(result_text))

        return "\n".join(chunks).strip()

    @staticmethod
    def _execution_error(execution) -> Optional[str]:
        error = getattr(execution, "error", None)
        if error is None:
            return None

        if isinstance(error, str):
            return error

        name = getattr(error, "name", None)
        value = getattr(error, "value", None)
        traceback_text = getattr(error, "traceback", None)

        parts = [part for part in (name, value, traceback_text) if part]
        return "\n".join(str(part) for part in parts) or str(error)

    def run_python(self, code: str) -> str:
        """Execute Python in an isolated E2B Code Interpreter sandbox.

        The method keeps the existing string return contract expected by the
        agent tool. Code execution itself is bounded by ``timeout`` and the
        SDK request is bounded by ``request_timeout``.

        ``run_code`` is used instead of constructing ``python -c`` shell
        commands. Therefore arbitrary quotes/newlines in user-generated code
        do not require shell escaping.
        """
        if not isinstance(code, str):
            raise TypeError("code must be a string.")

        if not code.strip():
            raise ValueError("code must not be empty.")

        if len(code) > self.max_code_length:
            raise ValueError(
                f"code exceeds the maximum allowed length of "
                f"{self.max_code_length} characters."
            )

        sandbox = self._ensure_sandbox()

        logger.info(
            "Executing Python code in E2B sandbox (chars=%d).",
            len(code),
        )

        try:
            execution = sandbox.run_code(
                code,
                language="python",
                timeout=self.timeout,
                request_timeout=self.request_timeout,
            )

            error = self._execution_error(execution)
            output = self._normalize_execution_output(execution)

            if error:
                logger.warning("E2B Python execution returned an error.")
                message = (
                    "Execution failed.\n"
                    f"{error}"
                )
                if output:
                    message += f"\nOutput:\n{output}"

                if self.raise_on_execution_error:
                    raise CodeInterpreterExecutionError(message)

                return message

            if not output:
                return "Execution finished successfully with no output."

            return f"Execution finished. Output:\n{output}"

        except CodeInterpreterExecutionError:
            raise
        except Exception as exc:
            logger.exception("E2B Python execution request failed.")
            if self.raise_on_execution_error:
                raise CodeInterpreterExecutionError(
                    "An unexpected error occurred during Python execution."
                ) from exc
            return "Execution failed: unable to execute Python code in the sandbox."

    def close(self) -> None:
        """Kill and release the remote sandbox."""
        if self.sandbox is None:
            return

        sandbox = self.sandbox
        self.sandbox = None

        try:
            kill = getattr(sandbox, "kill", None)
            if callable(kill):
                kill()
            else:
                close = getattr(sandbox, "close", None)
                if callable(close):
                    close()
            logger.info("E2B code-interpreter sandbox released.")
        except Exception:
            logger.exception("Failed to release E2B code-interpreter sandbox.")

    def __enter__(self) -> "CodeInterpreterSandbox":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
