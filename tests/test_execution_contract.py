import asyncio

from backend.orchestration.execution_contract import (
    AgentResponse,
    build_response,
    collect_stream,
    extract_text,
)


class TextResponse:
    text = "hello"


class NestedResponse:
    response = TextResponse()


class Block:
    def __init__(self, text):
        self.text = text


class BlockResponse:
    blocks = [Block("hello "), Block("world")]


def test_extract_text_normalizes_common_shapes():
    assert extract_text(None) == ""
    assert extract_text("hello") == "hello"
    assert extract_text(TextResponse()) == "hello"
    assert extract_text(NestedResponse()) == "hello"
    assert extract_text(BlockResponse()) == "hello world"


def test_build_response_returns_stable_application_shape():
    result = build_response(TextResponse(), {"source": "doc.pdf"})

    assert isinstance(result, AgentResponse)
    assert result.response_text == "hello"
    assert result.response_metadata == {"source": "doc.pdf"}


def test_collect_stream_handles_sync_iterable():
    assert asyncio.run(collect_stream(["a", "b", "c"])) == "abc"


def test_collect_stream_handles_async_iterable():
    async def chunks():
        yield "a"
        yield "b"

    assert asyncio.run(collect_stream(chunks())) == "ab"
