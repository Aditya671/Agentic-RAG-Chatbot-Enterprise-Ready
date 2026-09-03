import json

from agentic_rag_chatbot_enterprise_ready.backend.utils import parse_response_sources, to_millions, to_thousands


def test_response_sources_json_string_is_decoded():
    assert parse_response_sources(json.dumps(["a", "b"])) == ["a", "b"]


def test_response_sources_raw_output_is_unwrapped():
    class Output:
        raw_output = '{"source": "document.pdf"}'

    assert parse_response_sources(Output()) == {"source": "document.pdf"}


def test_response_sources_empty_and_plain_text():
    assert parse_response_sources(None) == []
    assert parse_response_sources("plain text") == "plain text"


def test_numeric_helpers_preserve_sign():
    assert to_millions(2_500_000) == 2.5
    assert to_millions(-2_500_000) == -2.5
    assert to_thousands(12_340) == 12.34
    assert to_thousands(-12_340) == -12.34
