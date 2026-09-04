"""Regression tests for the pandas-native structured-query boundary."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pandas as pd
import pytest

from backend.orchestration.structured_query import StructuredQueryEngine


class _FakeLLM:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.prompts: list[str] = []

    def complete(self, prompt: str):
        self.prompts.append(prompt)
        return SimpleNamespace(text=self.payload)


def test_engine_executes_validated_plan_deterministically() -> None:
    dataframe = pd.DataFrame({"asset": ["A", "B", "C"], "noi": [100.0, 250.0, 50.0]})
    llm = _FakeLLM('{"operation":"sum","column":"noi"}')

    result = StructuredQueryEngine(dataframe, engine_kwargs={"llm": llm}).query("total NOI")

    assert result["operation"] == "sum"
    assert result["result"] == 400.0
    assert llm.prompts


def test_engine_rejects_unknown_columns() -> None:
    dataframe = pd.DataFrame({"asset": ["A"], "noi": [100.0]})
    llm = _FakeLLM('{"operation":"sum","column":"secret"}')

    with pytest.raises(ValueError, match="Unknown dataframe column"):
        StructuredQueryEngine(dataframe, engine_kwargs={"llm": llm}).query("sum secret")


@pytest.mark.parametrize("question", ["", "   ", None])
def test_engine_rejects_empty_questions(question) -> None:
    engine = StructuredQueryEngine(pd.DataFrame({"value": [1, 2]}))
    with pytest.raises(ValueError, match="non-empty"):
        engine.query(question)


def test_engine_filter_and_group_aggregation() -> None:
    dataframe = pd.DataFrame(
        {
            "asset": ["A", "A", "B"],
            "status": ["open", "closed", "open"],
            "noi": [100.0, 200.0, 300.0],
        }
    )
    llm = _FakeLLM(
        '{"operation":"group_by_aggregate","column":"noi",'
        '"group_by":["asset"],"aggregation":"sum",'
        '"filters":[{"column":"status","operator":"eq","value":"open"}]}'
    )

    result = StructuredQueryEngine(dataframe, engine_kwargs={"llm": llm}).query("open NOI by asset")

    assert result["result"] == [{"asset": "A", "noi": 100.0}, {"asset": "B", "noi": 300.0}]


def test_async_query_uses_non_blocking_adapter_boundary() -> None:
    dataframe = pd.DataFrame({"value": [1, 2]})
    llm = _FakeLLM('{"operation":"count_rows"}')
    engine = StructuredQueryEngine(dataframe, engine_kwargs={"llm": llm})

    result = asyncio.run(engine.aquery("count rows"))

    assert result["result"] == 2
