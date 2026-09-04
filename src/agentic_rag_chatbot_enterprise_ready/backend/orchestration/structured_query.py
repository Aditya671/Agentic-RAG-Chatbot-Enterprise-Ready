"""Deterministic, pandas-native structured-data query engine.

The application deliberately does not use LlamaIndex's legacy/experimental
PandasQueryEngine. That engine delegates arbitrary Python execution to an LLM,
which is an unsafe and unnecessary boundary for production tabular analysis.

This module keeps the useful natural-language interface while separating:
1. LLM intent planning, and
2. deterministic, allow-listed pandas execution.

The dataframe is never mutated by a query and dataframe cell values are always
treated as data, never executable instructions.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd


_ALLOWED_OPERATIONS = frozenset(
    {
        "count_rows",
        "count_non_null",
        "sum",
        "mean",
        "median",
        "min",
        "max",
        "value_counts",
        "group_by_aggregate",
        "filter",
        "sort",
        "top_n",
        "describe",
    }
)
_ALLOWED_AGGREGATIONS = frozenset({"count", "sum", "mean", "median", "min", "max"})
_ALLOWED_FILTERS = frozenset({"eq", "neq", "gt", "gte", "lt", "lte", "contains", "startswith", "endswith", "is_null", "not_null"})


@dataclass(frozen=True)
class QueryPlan:
    """Validated, provider-neutral structured-data operation."""

    operation: str
    column: str | None = None
    columns: tuple[str, ...] = ()
    aggregation: str | None = None
    group_by: tuple[str, ...] = ()
    filters: tuple[Mapping[str, Any], ...] = ()
    ascending: bool = False
    limit: int | None = None
    value: Any = None


class StructuredQueryEngine:
    """Natural-language dataframe analysis with deterministic pandas execution."""

    def __init__(
        self,
        dataframe: Any,
        *,
        engine_kwargs: Mapping[str, Any] | None = None,
    ) -> None:
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("dataframe must be a pandas DataFrame")
        self.dataframe = dataframe.copy(deep=True)
        self._kwargs = dict(engine_kwargs or {})
        self.llm = self._kwargs.pop("llm", None)
        self.metadata = self._kwargs.pop("metadata", {})
        self.instruction_str = str(self._kwargs.pop("instruction_str", "")).strip()
        self._legacy_kwargs = self._kwargs

    @property
    def raw_engine(self) -> "StructuredQueryEngine":
        """Compatibility alias for callers that previously accessed the raw engine."""
        return self

    def query(self, question: str) -> dict[str, Any]:
        """Plan and execute a structured query without evaluating generated code."""
        self._validate_question(question)
        plan = self._plan(question)
        return self._execute(plan)

    async def aquery(self, question: str) -> dict[str, Any]:
        """Execute the synchronous deterministic query in a worker thread."""
        return await asyncio.to_thread(self.query, question)

    def _plan(self, question: str) -> QueryPlan:
        if self.llm is None:
            return self._heuristic_plan(question)

        prompt = self._build_planning_prompt(question)
        try:
            response = self.llm.complete(prompt)
            text = self._response_text(response)
            return self._parse_plan(text)
        except Exception as exc:
            raise RuntimeError("Structured-data query planning failed.") from exc

    def _build_planning_prompt(self, question: str) -> str:
        columns = [str(column) for column in self.dataframe.columns]
        dtypes = {str(column): str(dtype) for column, dtype in self.dataframe.dtypes.items()}
        sample = self.dataframe.head(5).to_dict(orient="records")
        metadata = self.metadata if isinstance(self.metadata, Mapping) else {}
        return (
            "You are a structured-data query planner. Return ONLY valid JSON. "
            "Never return Python, pandas code, SQL, markdown, or prose.\n\n"
            "Allowed operations: count_rows, count_non_null, sum, mean, median, min, max, "
            "value_counts, group_by_aggregate, filter, sort, top_n, describe.\n"
            f"Allowed columns: {json.dumps(columns)}\n"
            f"Data types: {json.dumps(dtypes)}\n"
            f"Sample rows: {json.dumps(sample, default=str)}\n"
            f"Metadata: {json.dumps(metadata, default=str)}\n"
            f"Application instructions: {self.instruction_str}\n\n"
            "JSON schema: {\"operation\": string, \"column\": string|null, "
            "\"columns\": [string], \"aggregation\": string|null, "
            "\"group_by\": [string], \"filters\": [{\"column\": string, "
            "\"operator\": string, \"value\": any}], \"ascending\": boolean, "
            "\"limit\": integer|null, \"value\": any}.\n"
            "Use the smallest operation that answers the question. Use only columns that exist.\n"
            f"User question: {question}"
        )

    def _parse_plan(self, text: str) -> QueryPlan:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM returned an invalid structured-query plan") from exc
        if not isinstance(payload, dict):
            raise ValueError("Structured-query plan must be a JSON object")
        return self._validate_plan(payload)

    def _validate_plan(self, payload: Mapping[str, Any]) -> QueryPlan:
        operation = payload.get("operation")
        if operation not in _ALLOWED_OPERATIONS:
            raise ValueError(f"Unsupported structured query operation: {operation!r}")

        column = payload.get("column")
        if column is not None:
            column = self._require_column(column)

        columns = tuple(self._require_column(value) for value in payload.get("columns", []))
        group_by = tuple(self._require_column(value) for value in payload.get("group_by", []))

        aggregation = payload.get("aggregation")
        if aggregation is not None and aggregation not in _ALLOWED_AGGREGATIONS:
            raise ValueError(f"Unsupported aggregation: {aggregation!r}")

        filters_payload = payload.get("filters", [])
        if not isinstance(filters_payload, list):
            raise ValueError("filters must be a list")
        filters: list[Mapping[str, Any]] = []
        for item in filters_payload:
            if not isinstance(item, Mapping):
                raise ValueError("Each filter must be an object")
            filter_column = self._require_column(item.get("column"))
            operator = item.get("operator")
            if operator not in _ALLOWED_FILTERS:
                raise ValueError(f"Unsupported filter operator: {operator!r}")
            filters.append({"column": filter_column, "operator": operator, "value": item.get("value")})

        limit = payload.get("limit")
        if limit is not None:
            if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
                raise ValueError("limit must be an integer between 1 and 1000")

        if operation in {"sum", "mean", "median", "min", "max", "count_non_null", "value_counts", "sort", "top_n"} and column is None:
            raise ValueError(f"{operation} requires a column")
        if operation == "group_by_aggregate" and (not group_by or not column or not aggregation):
            raise ValueError("group_by_aggregate requires group_by, column, and aggregation")
        if operation == "filter" and not filters:
            raise ValueError("filter requires at least one filter")

        return QueryPlan(
            operation=operation,
            column=column,
            columns=columns,
            aggregation=aggregation,
            group_by=group_by,
            filters=tuple(filters),
            ascending=bool(payload.get("ascending", False)),
            limit=limit,
            value=payload.get("value"),
        )

    def _heuristic_plan(self, question: str) -> QueryPlan:
        """Support common deterministic requests when no LLM is configured."""
        normalized = question.casefold()
        if re.search(r"\bhow many rows\b|\brow count\b|\bnumber of rows\b", normalized):
            return QueryPlan(operation="count_rows")
        if normalized.strip() in {"describe", "describe the data", "summary statistics"}:
            return QueryPlan(operation="describe")
        raise RuntimeError("An LLM is required for this structured-data question.")

    def _execute(self, plan: QueryPlan) -> dict[str, Any]:
        frame = self.dataframe.copy(deep=True)
        frame = self._apply_filters(frame, plan.filters)
        operation = plan.operation

        if operation == "count_rows":
            result: Any = int(len(frame))
        elif operation == "count_non_null":
            result = int(frame[plan.column].notna().sum())
        elif operation in {"sum", "mean", "median", "min", "max"}:
            result = self._aggregate(frame[plan.column], operation)
        elif operation == "value_counts":
            counts = frame[plan.column].value_counts(dropna=False).head(plan.limit or 20)
            result = [{"value": self._json_value(index), "count": int(value)} for index, value in counts.items()]
        elif operation == "group_by_aggregate":
            grouped = frame.groupby(list(plan.group_by), dropna=False)[plan.column].agg(plan.aggregation).reset_index()
            result = self._records(grouped)
        elif operation in {"sort", "top_n"}:
            sorted_frame = frame.sort_values(plan.column, ascending=plan.ascending, kind="stable")
            if operation == "top_n":
                sorted_frame = sorted_frame.head(plan.limit or 10)
            elif plan.limit:
                sorted_frame = sorted_frame.head(plan.limit)
            result = self._records(sorted_frame, columns=plan.columns or tuple(frame.columns))
        elif operation == "filter":
            result = self._records(frame, columns=plan.columns or tuple(frame.columns), limit=plan.limit)
        elif operation == "describe":
            result = self._records(frame.describe(include="all", datetime_is_numeric=True).reset_index())
        else:
            raise ValueError(f"Unsupported structured query operation: {operation}")

        return {
            "operation": operation,
            "row_count": int(len(frame)),
            "result": self._json_value(result),
        }

    @staticmethod
    def _aggregate(series: pd.Series, operation: str) -> Any:
        numeric = series if pd.api.types.is_numeric_dtype(series) else pd.to_numeric(series, errors="coerce")
        if operation in {"sum", "mean", "median"} and numeric.notna().sum() == 0:
            raise ValueError(f"Column '{series.name}' contains no numeric values for {operation}")
        value = getattr(numeric if operation in {"sum", "mean", "median"} else series, operation)()
        return StructuredQueryEngine._json_value(value)

    @staticmethod
    def _apply_filters(frame: pd.DataFrame, filters: tuple[Mapping[str, Any], ...]) -> pd.DataFrame:
        for item in filters:
            series = frame[item["column"]]
            operator = item["operator"]
            value = item.get("value")
            if operator == "is_null":
                mask = series.isna()
            elif operator == "not_null":
                mask = series.notna()
            elif operator == "contains":
                mask = series.astype("string").str.contains(str(value), case=False, na=False, regex=False)
            elif operator == "startswith":
                mask = series.astype("string").str.startswith(str(value), na=False)
            elif operator == "endswith":
                mask = series.astype("string").str.endswith(str(value), na=False)
            else:
                comparable = series
                if operator in {"gt", "gte", "lt", "lte"} and not pd.api.types.is_numeric_dtype(series):
                    numeric = pd.to_numeric(series, errors="coerce")
                    if numeric.notna().any():
                        comparable = numeric
                mask = {
                    "eq": comparable.eq(value),
                    "neq": comparable.ne(value),
                    "gt": comparable.gt(value),
                    "gte": comparable.ge(value),
                    "lt": comparable.lt(value),
                    "lte": comparable.le(value),
                }[operator]
            frame = frame.loc[mask]
        return frame

    def _require_column(self, value: Any) -> str:
        if not isinstance(value, str) or value not in self.dataframe.columns:
            raise ValueError(f"Unknown dataframe column: {value!r}")
        return value

    @staticmethod
    def _records(frame: pd.DataFrame, *, columns: tuple[str, ...] | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        if columns:
            frame = frame.loc[:, list(columns)]
        if limit:
            frame = frame.head(limit)
        return [{str(key): StructuredQueryEngine._json_value(value) for key, value in row.items()} for row in frame.to_dict(orient="records")]

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): StructuredQueryEngine._json_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [StructuredQueryEngine._json_value(item) for item in value]
        if pd.isna(value) if not isinstance(value, (dict, list, tuple)) else False:
            return None
        if isinstance(value, (pd.Timestamp, pd.Timedelta)):
            return value.isoformat()
        if hasattr(value, "item"):
            value = value.item()
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return value

    @staticmethod
    def _response_text(response: Any) -> str:
        text = getattr(response, "text", None)
        if text is not None:
            return str(text)
        return str(response)

    @staticmethod
    def _validate_question(question: str) -> None:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")
