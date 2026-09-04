"""Construction boundary for the pandas-native structured CSV runtime."""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from backend.orchestration.prompts import render_pandas_instruction, render_pandas_query_prompt
from backend.orchestration.provider_boundaries import build_structured_query_engine


def build_csv_runtime(
    *,
    csv_bytes: bytes | bytearray,
    metadata: Mapping[str, Any] | None,
    load_csv_file: Callable[[bytes | bytearray, Mapping[str, Any] | None], tuple[Any, Any]],
    llm: Any,
) -> Any:
    """Load CSV bytes and construct the deterministic structured-data engine."""
    if not isinstance(csv_bytes, (bytes, bytearray)) or not csv_bytes:
        raise ValueError("CSV content must be non-empty bytes.")
    if llm is None:
        raise ValueError("Structured CSV runtime requires an LLM for intent planning.")

    dataframe, loaded_metadata = load_csv_file(csv_bytes, metadata or {})
    column_info = (
        f"Columns ({len(dataframe.columns)} total): {', '.join(map(str, dataframe.columns))}\n"
        f"Data types: {json.dumps({str(column): str(dtype) for column, dtype in dataframe.dtypes.items()})}\n"
        f"DataFrame shape: {dataframe.shape[0]} rows, {dataframe.shape[1]} columns"
    )
    metadata_str = json.dumps(loaded_metadata, default=str) if isinstance(loaded_metadata, Mapping) else str(loaded_metadata)
    df_info = f"{dataframe.head(5).to_string()}\n{column_info}"
    instruction_str = render_pandas_instruction(df_info=df_info, metadata_str=metadata_str)
    pandas_prompt = render_pandas_query_prompt(
        df_str=dataframe.head(5).to_string(),
        metadata_str=metadata_str,
        column_info=column_info,
        instruction_str=instruction_str,
    )

    return build_structured_query_engine(
        dataframe,
        engine_kwargs={
            "llm": llm,
            "metadata": dict(loaded_metadata) if isinstance(loaded_metadata, Mapping) else {},
            "instruction_str": instruction_str,
            "pandas_prompt": pandas_prompt,
        },
    )
