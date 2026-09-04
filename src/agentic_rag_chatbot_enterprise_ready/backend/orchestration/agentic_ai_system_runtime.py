"""Compatibility import surface for the maintained agent runtime core."""
from __future__ import annotations

import asyncio

from backend.ai_models import AIModelTypes
from backend.llm_loader import load_llm
from .agentic_ai_system_runtime_core import AsyncAgenticAiSystem as _CoreAsyncAgenticAiSystem
from .agentic_ai_system_runtime_core import log_filename, logger


class AsyncAgenticAiSystem(_CoreAsyncAgenticAiSystem):
    """Preserve the historical runtime API over the maintained runtime core."""

    def generate_thread_title(self):
        first_question = first_answer = ""
        for message in self.memory.get_all():
            role = getattr(message, "role", None)
            content = getattr(message, "content", "") or ""
            role_value = getattr(role, "value", str(role).lower())
            if role_value == "user" and not first_question:
                first_question = str(content)
            elif role_value == "assistant" and not first_answer:
                first_answer = str(content)
            if first_question and first_answer:
                break
        prompt = (
            "Give me a short descriptive title based on this conversation. Maximum 8 words; "
            "do not use generic words such as Conversation, Overview, or Request.\n\n"
            f"User: {first_question}\nAssistant: {first_answer}"
        )
        llm = load_llm(
            model=AIModelTypes.GPT41_MINI,
            index_name=self.index_name,
            use_azure=True,
            callback_manager=self.callback_manager,
        )
        return self._extract_response_text(llm.complete(prompt)).strip()

    def get_response_async(self, question):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            response_block = asyncio.run(self.run_agent_async(question))
        else:
            raise RuntimeError(
                "get_response_async() cannot be called from a running event loop; "
                "use 'await get_response()' instead."
            )
        return {
            "response_text": self._extract_response_text(response_block),
            "response_metadata": self.get_retriever_metadata(response_block),
        }


__all__ = ["AsyncAgenticAiSystem", "logger", "log_filename"]
