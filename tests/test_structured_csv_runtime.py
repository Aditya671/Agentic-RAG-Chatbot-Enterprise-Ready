from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from backend.orchestration.structured_csv_runtime import build_csv_runtime


class _FakeStructuredEngine:
    def __init__(self, dataframe, engine_kwargs):
        self.dataframe = dataframe
        self.engine_kwargs = engine_kwargs


def test_build_csv_runtime_delegates_loaded_dataframe_and_native_prompts(monkeypatch):
    captured = {}
    dataframe = pd.DataFrame({"name": ["A", "B"], "value": [1, 2]})

    def load_csv(content, metadata):
        captured["content"] = content
        captured["metadata"] = metadata
        return dataframe, metadata

    def build_engine(df, *, engine_kwargs=None):
        return _FakeStructuredEngine(df, engine_kwargs or {})

    monkeypatch.setattr("backend.orchestration.structured_csv_runtime.build_structured_query_engine", build_engine)

    result = build_csv_runtime(
        csv_bytes=b"name,value\nA,1\nB,2\n",
        metadata={"source": "test.csv"},
        load_csv_file=load_csv,
        llm=SimpleNamespace(),
    )

    assert result.dataframe is dataframe
    assert captured["content"].startswith(b"name,value")
    assert captured["metadata"] == {"source": "test.csv"}
    assert set(result.engine_kwargs) == {"instruction_str", "pandas_prompt", "llm", "metadata"}
    assert "Return only this shape" in result.engine_kwargs["pandas_prompt"]


def test_build_csv_runtime_rejects_empty_content():
    try:
        build_csv_runtime(
            csv_bytes=b"",
            metadata={},
            load_csv_file=lambda *_: (_ for _ in ()).throw(AssertionError()),
            llm=object(),
        )
    except ValueError as exc:
        assert str(exc) == "CSV content must be non-empty bytes."
    else:
        raise AssertionError("expected ValueError")
